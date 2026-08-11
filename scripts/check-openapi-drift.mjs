#!/usr/bin/env node
/**
 * CI gate for OpenAPI-to-TypeScript client drift (spec Sec 5.1).
 *
 * Regenerates src/shared/api/schema.d.ts from server/openapi.json into a
 * temp file -- using the same openapi-typescript CLI that `pnpm
 * openapi:generate` runs -- and diffs it against the committed file. Exits
 * non-zero with a message naming the regeneration command when they differ.
 */

import { execFileSync } from 'node:child_process'
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)))
const SCHEMA_INPUT = join(ROOT, 'server', 'openapi.json')
const COMMITTED_OUTPUT = join(ROOT, 'src', 'shared', 'api', 'schema.d.ts')
const CLI_BIN = join(ROOT, 'node_modules', '.bin', 'openapi-typescript')
const GENERATE_COMMAND = 'pnpm openapi:generate'
const EXPORT_COMMAND = 'pnpm openapi:export'

function relative(absolutePath) {
  return absolutePath.startsWith(`${ROOT}/`) ? absolutePath.slice(ROOT.length + 1) : absolutePath
}

function main() {
  if (!existsSync(SCHEMA_INPUT)) {
    console.error(
      `\n✖ ${relative(SCHEMA_INPUT)} does not exist. Run \`${EXPORT_COMMAND}\` to generate it from the FastAPI app.\n`,
    )
    return 1
  }

  if (!existsSync(COMMITTED_OUTPUT)) {
    console.error(
      `\n✖ ${relative(COMMITTED_OUTPUT)} does not exist. Run \`${GENERATE_COMMAND}\` and commit the result.\n`,
    )
    return 1
  }

  const tmpDir = mkdtempSync(join(tmpdir(), 'openapi-drift-'))
  const freshOutput = join(tmpDir, 'schema.d.ts')

  try {
    execFileSync(CLI_BIN, [SCHEMA_INPUT, '-o', freshOutput], { stdio: 'inherit' })

    const fresh = readFileSync(freshOutput, 'utf8')
    const committed = readFileSync(COMMITTED_OUTPUT, 'utf8')

    if (fresh !== committed) {
      console.error(
        `\n✖ ${relative(COMMITTED_OUTPUT)} is out of date with ${relative(SCHEMA_INPUT)}.\n` +
          `  Run \`${GENERATE_COMMAND}\` and commit the result.\n`,
      )
      return 1
    }

    console.log(`${relative(COMMITTED_OUTPUT)} matches ${relative(SCHEMA_INPUT)}.`)
    return 0
  } catch (err) {
    console.error(`\n✖ Failed to regenerate OpenAPI types: ${err.message}\n`)
    return 1
  } finally {
    rmSync(tmpDir, { recursive: true, force: true })
  }
}

process.exitCode = main()
