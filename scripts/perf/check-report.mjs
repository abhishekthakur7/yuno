#!/usr/bin/env node
// IDK-504's automated assertion. It confirms the built report covers every §8.6
// measurement and carries no invented threshold -- it does NOT judge whether any
// measured value is fast enough, because §8.6 invents no pass threshold for it to
// check against.

import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { MEASUREMENT_SET, REQUIRED_CONTEXT_FIELDS, DISCLAIMER, THRESHOLD_LANGUAGE } from './measurement-set.mjs'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '..', '..')
const REPORT_PATH = resolve(ROOT, 'docs/performance/IDK-504-representative-measurements.md')

const failures = []
const fail = message => failures.push(message)

let report
try {
  report = readFileSync(REPORT_PATH, 'utf8')
} catch (error) {
  if (error.code === 'ENOENT') {
    console.error(`${REPORT_PATH}: missing -- run \`node scripts/perf/build-report.mjs\` first`)
    process.exit(1)
  }
  throw error
}

// Every MEASUREMENT_SET id appears with either a distribution or a recorded gap.
// The report renders each measurement under its title as an H2 heading; a
// "_No sample or recorded gap found..._" marker means the producer silently
// dropped it, which fails.
for (const measurement of MEASUREMENT_SET) {
  const headingIndex = report.indexOf(`## ${measurement.title}`)
  if (headingIndex === -1) {
    fail(`measurement "${measurement.id}" (${measurement.title}): no section found in the report`)
    continue
  }
  const nextHeadingIndex = report.indexOf('\n## ', headingIndex + 1)
  const section = report.slice(headingIndex, nextHeadingIndex === -1 ? report.length : nextHeadingIndex)
  if (section.includes('_No sample or recorded gap found for this measurement._')) {
    fail(`measurement "${measurement.id}" (${measurement.title}): no sample and no recorded gap -- a silently missing measurement is not allowed`)
  }
}

// Every REQUIRED_CONTEXT_FIELDS key is present and non-empty in the context section.
const contextHeadingIndex = report.indexOf('## Context')
if (contextHeadingIndex === -1) {
  fail('report has no "## Context" section')
} else {
  const nextHeadingIndex = report.indexOf('\n## ', contextHeadingIndex + 1)
  const contextSection = report.slice(contextHeadingIndex, nextHeadingIndex === -1 ? report.length : nextHeadingIndex)
  for (const field of REQUIRED_CONTEXT_FIELDS) {
    const pattern = new RegExp(`^- \\*\\*${field}\\*\\*: (.+)$`, 'm')
    const match = contextSection.match(pattern)
    if (!match || match[1].trim().length === 0) {
      fail(`context field "${field}": missing or empty in the "## Context" section`)
    }
  }
}

// DISCLAIMER appears exactly once, verbatim.
const disclaimerMatches = report.split(DISCLAIMER).length - 1
if (disclaimerMatches !== 1) {
  fail(`DISCLAIMER must appear exactly once, verbatim; found ${disclaimerMatches} occurrence(s)`)
}

// Strip DISCLAIMER, then scan the remaining text against every THRESHOLD_LANGUAGE
// pattern, line by line so a hit can name the exact line.
const stripped = report.split(DISCLAIMER).join('')
const lines = stripped.split('\n')
for (const [index, line] of lines.entries()) {
  for (const pattern of THRESHOLD_LANGUAGE) {
    if (pattern.test(line)) {
      fail(`line ${index + 1} matches threshold-language pattern ${pattern}: "${line.trim()}"`)
    }
  }
}

if (failures.length > 0) {
  console.error(`${REPORT_PATH}: ${failures.length} check(s) failed`)
  for (const failure of failures) console.error(`  - ${failure}`)
  process.exit(1)
}

console.log(`${REPORT_PATH}: all IDK-504 report checks passed`)
