#!/usr/bin/env node
// IDK-503's optional mechanical scan. It confirms the review records carry the
// fields a review record must carry -- gate, reviewer role, date, referenced
// artifact, disposition, attestation -- and that no gate or Appendix C row was
// silently dropped. It does NOT substitute for the review: it cannot tell a real
// inspection from a plausible sentence, and deliberately makes no attempt to.

import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

const GATE_DIR = 'docs/approvals/IDK-503'
const RECORD = 'docs/approvals/IDK-503-content-and-safety-review.md'

// The seven gates IDK-503's scope names. A missing file here means a gate was skipped.
const GATES = [
  'gate-1-curriculum-boundary.md',
  'gate-2-editorial-approvals.md',
  'gate-3-sources-licensing.md',
  'gate-4-role-copy.md',
  'gate-5-rubrics-scenarios.md',
  'gate-6-privacy-lifecycle.md',
  'gate-7-runner-posture.md',
]

// PRD Appendix C's six rows, used verbatim as the runner-review checklist so no
// row is skipped.
const APPENDIX_C_ROWS = [
  'Shell injection',
  'Excess CPU/time/output',
  'File pollution',
  'Environment/secrets leakage',
  'Misleading validation',
  'Orphaned process',
]

const REQUIRED_FIELDS = [
  { label: 'gate', pattern: /^- Gate: \S/m },
  { label: 'reviewer role', pattern: /^- Reviewer role required: \S/m },
  { label: 'inspection date', pattern: /^- Inspection date: \d{4}-\d{2}-\d{2}$/m },
  { label: 'disposition', pattern: /^- Disposition: (inspection-passed-pending-attestation|blocking-finding)$/m },
  { label: 'attestation', pattern: /^- Attestation: \S/m },
]

// A referenced artifact is a real path, a database query, or a named test -- not a
// description of a feature. This is the one acceptance criterion the scan can check
// mechanically: "no gate is approved from a description of intended behavior".
const ARTIFACT_REFERENCE = /(?:[\w./-]+\.(?:py|ts|tsx|mjs|json|md|db)(?::\d+)?|sqlite3 |SELECT )/

const failures = []
const check = (file, condition, message) => { if (!condition) failures.push(`${file}: ${message}`) }

const present = new Set(readdirSync(GATE_DIR).filter(name => name.endsWith('.md')))
for (const gate of GATES) {
  if (!present.has(gate)) {
    failures.push(`${GATE_DIR}/${gate}: missing -- this gate has no recorded review`)
    continue
  }
  const path = join(GATE_DIR, gate)
  const text = readFileSync(path, 'utf8')
  for (const field of REQUIRED_FIELDS) check(path, field.pattern.test(text), `no ${field.label} field`)
  check(path, ARTIFACT_REFERENCE.test(text), 'cites no specific artifact (path, query or named test)')
  check(path, /^## Blocking findings$/m.test(text), 'no blocking-findings section')
  check(path, !/^- Disposition: approved$/m.test(text), 'records an approval; only the named approver may approve a gate')
}
for (const extra of present) {
  if (!GATES.includes(extra)) failures.push(`${GATE_DIR}/${extra}: unexpected file -- not one of the seven named gates`)
}

const record = readFileSync(RECORD, 'utf8')
for (const gate of GATES) {
  const id = gate.replace(/^gate-(\d)-.*$/, '$1')
  check(RECORD, new RegExp(`^\\| ${id} \\|`, 'm').test(record), `no disposition row for gate ${id}`)
  check(RECORD, record.includes(gate), `does not reference ${gate}`)
}
for (const row of APPENDIX_C_ROWS) {
  check(RECORD, record.includes(row), `Appendix C row "${row}" has no recorded disposition`)
}

if (failures.length) {
  console.error('Review-record scan failed:')
  for (const failure of failures) console.error(`  ${failure}`)
  process.exit(1)
}
console.log(`Review-record scan passed: ${GATES.length} gates, ${APPENDIX_C_ROWS.length} Appendix C rows, all required fields present.`)
