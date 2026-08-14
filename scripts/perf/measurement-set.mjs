// IDK-504: the spec §8.6 measurement set, written down once so the harness, the
// report and the coverage check cannot drift apart. §8.6 invents no pass threshold,
// so nothing in this file carries a target, a baseline or a budget — only what to
// measure, in what unit, and which producer records it.

/** @typedef {{id: string, title: string, specBullet: string, unit: 'ms' | 'bytes' | 'percent' | 'px', producer: string}} Measurement */

/** @type {Measurement[]} */
export const MEASUREMENT_SET = [
  { id: 'cold-navigation', title: 'Cold navigation across the 14 canonical routes', specBullet: 'cold/warm navigation', unit: 'ms', producer: 'client-navigation' },
  { id: 'warm-navigation', title: 'Warm navigation across the 14 canonical routes', specBullet: 'cold/warm navigation', unit: 'ms', producer: 'client-navigation' },
  { id: 'roadmap-render', title: 'Full-roadmap render at the representative dataset size', specBullet: 'full-roadmap render and interaction', unit: 'ms', producer: 'client-navigation' },
  { id: 'roadmap-interaction', title: 'Roadmap interaction (Customize, Jump, Skip, Restore, depth, order)', specBullet: 'full-roadmap render and interaction', unit: 'ms', producer: 'client-navigation' },
  { id: 'fts-query', title: 'FTS query latency', specBullet: 'FTS query and stale fallback', unit: 'ms', producer: 'server-measurements' },
  { id: 'fts-stale-fallback', title: 'Deterministic stale-fallback search latency', specBullet: 'FTS query and stale fallback', unit: 'ms', producer: 'server-measurements' },
  { id: 'sse-to-visible-state', title: 'Server-emitted job event to corresponding visible UI state change', specBullet: 'SSE-to-visible-state latency', unit: 'ms', producer: 'client-jobs-sse' },
  { id: 'interactive-job-start-under-background-lane', title: 'Interactive job start latency while background-lane work runs', specBullet: 'interactive job start while background work runs', unit: 'ms', producer: 'client-jobs-sse' },
  { id: 'import-parse-effect', title: 'Import parsing effect on concurrent navigation and search responsiveness', specBullet: 'import/index rebuild effects', unit: 'ms', producer: 'server-measurements' },
  { id: 'index-rebuild-effect', title: 'Search-index rebuild effect on concurrent navigation and search responsiveness', specBullet: 'import/index rebuild effects', unit: 'ms', producer: 'server-measurements' },
  { id: 'cpu-usage', title: 'Server CPU under the representative dataset', specBullet: 'CPU, memory and SQLite size', unit: 'percent', producer: 'server-measurements' },
  { id: 'memory-usage', title: 'Server resident memory under the representative dataset', specBullet: 'CPU, memory and SQLite size', unit: 'bytes', producer: 'server-measurements' },
  { id: 'sqlite-size', title: 'SQLite database file size under the representative dataset', specBullet: 'CPU, memory and SQLite size', unit: 'bytes', producer: 'server-measurements' },
  { id: 'viewport-overflow', title: 'Horizontal overflow at 390, 768, 1366 and 1440', specBullet: '390/768/1366/1440 viewport overflow and input latency', unit: 'px', producer: 'client-viewport' },
  { id: 'viewport-input-latency', title: 'Input latency at 390, 768, 1366 and 1440', specBullet: '390/768/1366/1440 viewport overflow and input latency', unit: 'ms', producer: 'client-viewport' },
]

// §8.6's first bullet is context, not a distribution: every measurement is tied to
// it, and an untethered number is not a valid report entry.
export const REQUIRED_CONTEXT_FIELDS = ['device', 'os', 'runtime', 'toolchain', 'dataset']

// The four required viewports, shared by the client producers.
export const VIEWPORTS = [
  { width: 1440, height: 1000 },
  { width: 1366, height: 768 },
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
]

// The 14 canonical routes: `/` (My learning) plus one per id in APP_PAGE_IDS
// (src/selected/app-model.ts), which stays the source of truth for the set.
export const CANONICAL_ROUTES = [
  '/',
  '/app/onboarding',
  '/app/learn-roadmap',
  '/app/topic-studio',
  '/app/interview-hub',
  '/app/practice',
  '/app/mock',
  '/app/reports',
  '/app/evidence',
  '/app/imports',
  '/app/canonical-updates',
  '/app/search',
  '/app/jobs',
  '/app/settings',
]

// The report states this verbatim, and the coverage check strips exactly this
// sentence before scanning for threshold language — so the one legitimate use of
// the word cannot hide an illegitimate one.
export const DISCLAIMER =
  'This report sets no threshold, baseline, target, guarantee or pass/fail number. An approver sets acceptance thresholds later.'

// Wording that would turn a measurement into a promise. Scanned case-insensitively
// over the report with DISCLAIMER removed.
export const THRESHOLD_LANGUAGE = [
  /\bthresholds?\b/i,
  /\bbaselines?\b/i,
  /\bSLAs?\b/i,
  /\bbudgets?\b/i,
  // "target" is only threshold language in a performance sense. A recorded gap may quote a
  // tool's own error ("Target page, context or browser has been closed"), and that is data
  // about a measurement that was not taken, not a claim about how fast anything should be.
  /\b(?:performance|latency|timing|render|navigation|response|budget)\s+targets?\b/i,
  /\btargets?\s+(?:of|under|below|above|within)\s+\d/i,
  /\bguarantee[ds]?\b/i,
  /\bpass\/fail\b/i,
  /\b(?:passes|fails|failed|passed)\s+(?:the\s+)?(?:perf|performance)\b/i,
  /\bacceptance criteri/i,
  /\bmust (?:be|stay|remain) (?:under|below|within|above)\b/i,
  /\bshould (?:be|stay|remain) (?:under|below|within|above)\b/i,
  /\bwithin \d+\s*(?:ms|s|MB|GB)\b/i,
  /\bno (?:slower|worse) than\b/i,
  /\bacceptable (?:latency|performance|range)\b/i,
  /\bregression threshold\b/i,
]

/** @param {string} id */
export function measurementById(id) {
  return MEASUREMENT_SET.find(measurement => measurement.id === id)
}
