#!/usr/bin/env node
// IDK-504: builds the representative-measurement report from every producer's raw
// samples. §8.6 invents no pass threshold, so this script computes distributions
// and outliers only -- it never judges a value as fast enough, and it never writes
// a target, baseline, budget, SLA or guarantee. scripts/perf/check-report.mjs is
// the automated check that this file held to that rule.

import { readFileSync, readdirSync, mkdirSync, writeFileSync } from 'node:fs'
import { join, dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { MEASUREMENT_SET, REQUIRED_CONTEXT_FIELDS, DISCLAIMER } from './measurement-set.mjs'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '..', '..')

const CONTEXT_PATH = resolve(ROOT, 'perf-results/context.json')
const SAMPLES_DIR = resolve(ROOT, 'perf-results/samples')
const REPORT_PATH = resolve(ROOT, 'docs/performance/IDK-504-representative-measurements.md')

// Percentiles use nearest-rank: for a sorted array of n values, the p-th
// percentile is the value at 0-based index ceil(p/100 * n) - 1 (clamped to
// [0, n-1]). Stated here so two runs of the same sample set always agree.
function nearestRank(sorted, percentile) {
  const rank = Math.ceil((percentile / 100) * sorted.length)
  const index = Math.min(Math.max(rank - 1, 0), sorted.length - 1)
  return sorted[index]
}

// Outlier = beyond 1.5x IQR from the quartiles (Tukey's rule), using the same
// nearest-rank method for Q1/Q3 as every other percentile in this report.
function outliers(sorted) {
  const q1 = nearestRank(sorted, 25)
  const q3 = nearestRank(sorted, 75)
  const iqr = q3 - q1
  const low = q1 - 1.5 * iqr
  const high = q3 + 1.5 * iqr
  return sorted.filter(value => value < low || value > high)
}

function distribution(values) {
  const sorted = [...values].sort((a, b) => a - b)
  return {
    count: sorted.length,
    min: sorted[0],
    p50: nearestRank(sorted, 50),
    p90: nearestRank(sorted, 90),
    p95: nearestRank(sorted, 95),
    p99: nearestRank(sorted, 99),
    max: sorted[sorted.length - 1],
    outliers: outliers(sorted),
  }
}

function loadContext() {
  const raw = JSON.parse(readFileSync(CONTEXT_PATH, 'utf8'))
  for (const field of REQUIRED_CONTEXT_FIELDS) {
    if (raw[field] === undefined || raw[field] === null || raw[field] === '') {
      throw new Error(`perf-results/context.json is missing required context field "${field}"`)
    }
  }
  return raw
}

function loadSampleFiles() {
  let names
  try {
    names = readdirSync(SAMPLES_DIR).filter(name => name.endsWith('.json'))
  } catch (error) {
    if (error.code === 'ENOENT') return []
    throw error
  }
  return names.map(name => JSON.parse(readFileSync(join(SAMPLES_DIR, name), 'utf8')))
}

function formatContextValue(value) {
  if (value !== null && typeof value === 'object') {
    return Object.entries(value)
      .map(([key, val]) => `${key}: ${val}`)
      .join(', ')
  }
  return String(value)
}

function renderContext(context) {
  const lines = ['## Context', '']
  for (const field of REQUIRED_CONTEXT_FIELDS) {
    lines.push(`- **${field}**: ${formatContextValue(context[field])}`)
  }
  for (const [key, value] of Object.entries(context)) {
    if (REQUIRED_CONTEXT_FIELDS.includes(key)) continue
    lines.push(`- **${key}**: ${formatContextValue(value)}`)
  }
  lines.push('')
  return lines.join('\n')
}

function renderMeasurementSection(measurement, samplesByProducer, gapsByProducer) {
  const lines = [`## ${measurement.title}`, '', `- id: \`${measurement.id}\``, `- unit: ${measurement.unit}`, `- spec §8.6 bullet: ${measurement.specBullet}`, '']

  const matchingSamples = samplesByProducer
    .filter(entry => entry.sample.measurement === measurement.id)
    .map(entry => ({ producer: entry.producer, sample: entry.sample }))
  const matchingGaps = gapsByProducer.filter(entry => entry.gap.measurement === measurement.id)

  if (matchingSamples.length === 0 && matchingGaps.length === 0) {
    lines.push('_No sample or recorded gap found for this measurement._', '')
    return lines.join('\n')
  }

  for (const { producer, sample } of matchingSamples) {
    lines.push(`### ${sample.subject}`, '')
    lines.push(`- producer: \`${producer}\``)
    if (sample.method) lines.push(`- method: ${sample.method}`)
    if (sample.notes) lines.push(`- notes: ${sample.notes}`)
    lines.push('')

    if (sample.values.length === 1) {
      lines.push(`Sample of one (${sample.unit}): ${sample.values[0]}`, '')
    } else {
      const dist = distribution(sample.values)
      lines.push('| count | min | p50 | p90 | p95 | p99 | max |')
      lines.push('|---|---|---|---|---|---|---|')
      lines.push(`| ${dist.count} | ${dist.min} | ${dist.p50} | ${dist.p90} | ${dist.p95} | ${dist.p99} | ${dist.max} |`)
      lines.push('')
      lines.push(
        dist.outliers.length > 0
          ? `Outliers (beyond 1.5x IQR from Q1/Q3, nearest-rank): ${dist.outliers.join(', ')} ${sample.unit}`
          : 'Outliers (beyond 1.5x IQR from Q1/Q3, nearest-rank): none',
      )
      lines.push('')
    }
  }

  for (const { producer, gap } of matchingGaps) {
    lines.push(`### Gap${gap.subject ? `: ${gap.subject}` : ''}`, '')
    lines.push(`- producer: \`${producer}\``)
    lines.push(`- reason: ${gap.reason}`)
    lines.push('')
  }

  return lines.join('\n')
}

function buildReport() {
  const context = loadContext()
  const sampleFiles = loadSampleFiles()

  const samplesByProducer = sampleFiles.flatMap(file => file.samples.map(sample => ({ producer: file.producer, sample })))
  const gapsByProducer = sampleFiles.flatMap(file => (file.gaps ?? []).map(gap => ({ producer: file.producer, gap })))

  const sections = MEASUREMENT_SET.map(measurement => renderMeasurementSection(measurement, samplesByProducer, gapsByProducer))

  const lines = [
    '# IDK-504 — Representative performance measurements',
    '',
    'Generated by `scripts/perf/build-report.mjs` from `perf-results/context.json` and',
    '`perf-results/samples/*.json`. Every number in this report is tied to the context',
    'above it; an untethered number is not a valid report entry.',
    '',
    renderContext(context),
    '## What this report does not set',
    '',
    DISCLAIMER,
    '',
    'No approval artifact recording an accepted number exists yet. For one to exist, an',
    'approver would need to review this report (or a later run of the same harness) and',
    'record their decision, in writing, as a separate document; this script does not',
    'produce that document.',
    '',
    ...sections,
  ]

  return lines.join('\n')
}

function main() {
  const report = buildReport()
  mkdirSync(dirname(REPORT_PATH), { recursive: true })
  writeFileSync(REPORT_PATH, `${report.trimEnd()}\n`, 'utf8')
  console.log(`Wrote ${REPORT_PATH}`)
}

main()
