// Companion declaration file for measurement-set.mjs (untouched). TS cannot infer
// types across a plain .mjs boundary without allowJs, and this repo does not enable
// allowJs; a same-directory, same-basename .d.mts is the standard way to type a
// hand-written .mjs module without editing it or enabling allowJs project-wide.
// Every tests/perf/*.perf.spec.ts producer that imports measurement-set.mjs needs
// this shim, so it is additive-only and never re-exports invented values.

export type Unit = 'ms' | 'bytes' | 'percent' | 'px'

export type Measurement = {
  id: string
  title: string
  specBullet: string
  unit: Unit
  producer: string
}

export const MEASUREMENT_SET: readonly Measurement[]
export const REQUIRED_CONTEXT_FIELDS: readonly string[]
export const VIEWPORTS: readonly { width: number; height: number }[]
export const CANONICAL_ROUTES: readonly string[]
export const DISCLAIMER: string
export const THRESHOLD_LANGUAGE: readonly RegExp[]
export function measurementById(id: string): Measurement | undefined
