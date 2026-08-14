import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

// IDK-504: the one way a client-side measurement producer records what it observed.
// Raw samples stay raw here — every value the run produced, in order, with the
// context it was taken under. Distributions, outliers and prose are the report
// builder's job (scripts/perf/build-report.mjs), never the producer's.

export type Sample = {
  /** A measurement id from scripts/perf/measurement-set.mjs. */
  measurement: string
  /** What was measured: a route, a control, a viewport — specific enough to reproduce. */
  subject: string
  unit: 'ms' | 'bytes' | 'percent' | 'px'
  /** Every observed value, in observation order. One value is a sample of one, and is reported as such. */
  values: number[]
  /** How the value was obtained, when that is not obvious from the subject. */
  method?: string
  notes?: string
}

/** A measurement that could not be taken reproducibly. §8.6 reports the gap; it never fabricates a number. */
export type Gap = { measurement: string; subject?: string; reason: string }

export type SampleFile = { producer: string; samples: Sample[]; gaps: Gap[] }

const OUT_DIR = process.env['YUNO_PERF_OUT'] ?? 'perf-results/samples'

export function samplePath(producer: string) {
  return resolve(process.cwd(), OUT_DIR, `${producer}.json`)
}

export function writeSamples(producer: string, samples: Sample[], gaps: Gap[] = []) {
  const path = samplePath(producer)
  mkdirSync(dirname(path), { recursive: true })
  const file: SampleFile = { producer, samples, gaps }
  writeFileSync(path, `${JSON.stringify(file, null, 2)}\n`, 'utf8')
  return path
}

export async function repeat(times: number, body: (iteration: number) => Promise<number>) {
  const values: number[] = []
  for (let iteration = 0; iteration < times; iteration += 1) values.push(await body(iteration))
  return values
}
