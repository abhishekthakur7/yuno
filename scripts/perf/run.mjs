#!/usr/bin/env node
// IDK-504: the one committed entry point that reproduces the §8.6 report end to
// end. It recreates perf-results/ from scratch (so every run measures the same
// fixed, freshly seeded dataset, not whatever a prior run left behind), records
// the spec §8.6 context, runs every producer, then builds and checks the report.
//
// A step that fails is reported by name and the run continues into whichever
// later steps are still meaningful (spec §8.6/IDK-504: a partial run reports
// gaps, never fabricates a number, and never silently produces nothing).

import { execFileSync, spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import os from 'node:os'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { REQUIRED_CONTEXT_FIELDS } from './measurement-set.mjs'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '..', '..')
const PERF_RESULTS = resolve(ROOT, 'perf-results')
const PERF_DB = resolve(PERF_RESULTS, 'perf.db')
const PERF_DB_URL = `sqlite+pysqlite:///${PERF_DB}`
const DATASET_SHAPE_PATH = resolve(PERF_RESULTS, 'dataset-shape.json')
const CONTEXT_PATH = resolve(PERF_RESULTS, 'context.json')

const failedSteps = []

function step(name, body) {
  console.log(`\n=== ${name} ===`)
  try {
    body()
    console.log(`--- ${name}: ok`)
    return true
  } catch (error) {
    console.error(`--- ${name}: FAILED`)
    console.error(error?.message ?? error)
    failedSteps.push(name)
    return false
  }
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: ROOT,
    stdio: 'inherit',
    ...options,
  })
  if (result.error) throw result.error
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(' ')} exited with status ${result.status}`)
  }
}

function capture(command, args, options = {}) {
  return execFileSync(command, args, { cwd: ROOT, encoding: 'utf8', ...options }).trim()
}

function installedVersion(packageDir) {
  const packageJsonPath = resolve(ROOT, 'node_modules', packageDir, 'package.json')
  return JSON.parse(readFileSync(packageJsonPath, 'utf8')).version
}

step('Recreate perf-results/ and seed a fresh dataset', () => {
  rmSync(PERF_RESULTS, { recursive: true, force: true })
  mkdirSync(PERF_RESULTS, { recursive: true })
  // Belt and suspenders: rmSync above already removed any stale perf.db, but
  // this makes "no stale database survives into this run" an explicit,
  // independently-true statement rather than an implication of the line above.
  rmSync(PERF_DB, { force: true })

  run('uv', ['run', '--directory', 'server', 'alembic', 'upgrade', 'head'], {
    env: { ...process.env, YUNO_DATABASE_URL: PERF_DB_URL },
  })
  run(
    'uv',
    [
      'run',
      '--directory',
      'server',
      'python',
      'scripts/seed_performance_dataset.py',
      '--database-url',
      PERF_DB_URL,
      '--json-out',
      DATASET_SHAPE_PATH,
    ],
    { env: { ...process.env, YUNO_DATABASE_URL: PERF_DB_URL } },
  )
})

step('Write perf-results/context.json', () => {
  const cpus = os.cpus()
  const pythonVersion = capture('uv', [
    'run',
    '--directory',
    'server',
    'python',
    '--version',
  ])
  const uvVersion = capture('uv', ['--version'])
  const pnpmVersion = capture('pnpm', ['--version'])
  const playwrightVersion = installedVersion('@playwright/test')
  const viteVersion = installedVersion('vite')

  const dataset = existsSync(DATASET_SHAPE_PATH)
    ? JSON.parse(readFileSync(DATASET_SHAPE_PATH, 'utf8'))
    : { gap: 'dataset-shape.json was not produced; seeding step failed.' }

  const context = {
    device: {
      arch: os.arch(),
      cpuModel: cpus[0]?.model ?? null,
      coreCount: cpus.length,
      totalMemoryBytes: os.totalmem(),
    },
    os: {
      platform: os.platform(),
      release: os.release(),
    },
    runtime: {
      node: process.version,
      python: pythonVersion,
      uv: uvVersion,
    },
    toolchain: {
      pnpm: pnpmVersion,
      playwright: playwrightVersion,
      vite: viteVersion,
    },
    dataset,
  }

  for (const field of REQUIRED_CONTEXT_FIELDS) {
    if (!(field in context)) {
      throw new Error(`context.json is missing required field ${JSON.stringify(field)}`)
    }
  }

  mkdirSync(PERF_RESULTS, { recursive: true })
  writeFileSync(CONTEXT_PATH, `${JSON.stringify(context, null, 2)}\n`, 'utf8')
})

step('Run Playwright performance measurements', () => {
  run('pnpm', ['exec', 'playwright', 'test', '--config=playwright.perf.config.ts'])
})

step('Run server-side performance measurements', () => {
  const outPath = resolve(PERF_RESULTS, 'samples', 'server-measurements.json')
  run('uv', [
    'run',
    '--directory',
    'server',
    'python',
    'scripts/measure_performance.py',
    '--database-url',
    PERF_DB_URL,
    '--out',
    outPath,
  ])
})

step('Build the report', () => {
  run('node', ['scripts/perf/build-report.mjs'])
})

step('Check the report', () => {
  run('node', ['scripts/perf/check-report.mjs'])
})

if (failedSteps.length > 0) {
  console.error(`\n${failedSteps.length} step(s) failed: ${failedSteps.join(', ')}`)
  process.exitCode = 1
} else {
  console.log('\nAll steps completed.')
}
