import { client } from './client'
import { ApiError } from './queries'
import type { components } from './schema'

export type RunnerLanguage = components['schemas']['RunnerLanguage']
export type RunnerCapabilityState = 'supported' | 'missing' | 'incompatible'
export type RunnerState = 'pending-confirmation' | 'queued' | 'preparing' | 'running' | 'cancel-requested' | 'completed' | 'failed' | 'timed-out-or-limited' | 'cancelled' | 'cleanup-pending' | 'cleanup-complete' | 'cleanup-failed'

export type RunnerInput = components['schemas']['RunnerInputRequest']

export type RunnerCapability = components['schemas']['RunnerCapabilityItemResponse']

export type RunnerCapabilities = components['schemas']['RunnerCapabilitiesResponse']

export type RunnerConfirmation = components['schemas']['RunnerConfirmationResponse']

export interface RunnerOutputChunk {
  phase: 'compile' | 'test'
  stream: 'stdout' | 'stderr'
  sequence: number
  ordinal?: number
  content: string
  truncated: boolean
}

export interface RunnerPhase {
  state: string
  exit_code?: number | null
  signal?: string | null
}

export interface RunnerRun extends Omit<components['schemas']['RunnerRunResponse'], 'state' | 'output_chunks' | 'compile_phase' | 'test_phase' | 'static_phase'> {
  state: RunnerState
  output_chunks: RunnerOutputChunk[]
  compile_phase: RunnerPhase
  test_phase: RunnerPhase
  static_phase: RunnerPhase
}

export async function getRunnerCapabilities() {
  const { data, error, response } = await client.GET('/api/v1/runner/capabilities')
  if (error || !data) throw new ApiError(error?.message ?? 'Runner capabilities could not be loaded.', response.status)
  return data
}

export async function confirmRunnerInputs(body: components['schemas']['RunnerConfirmationRequest']) {
  const { data, error, response } = await client.POST('/api/v1/runner/confirmations', { body })
  if (error || !data) throw new ApiError(error?.message ?? 'Runner inputs could not be confirmed.', response.status)
  return data
}

export async function createRunnerRun(body: { confirmation_id: string }, idempotencyKey: string) {
  const { data, error, response } = await client.POST('/api/v1/runner-runs', { body, params: { header: { 'Idempotency-Key': idempotencyKey } } })
  if (error || !data) throw new ApiError(error?.message ?? 'The runner run could not be created.', response.status)
  return data
}

export async function getRunnerRun(id: string) {
  const { data, error, response } = await client.GET('/api/v1/runner-runs/{run_id}', { params: { path: { run_id: id } } })
  if (error || !data) throw new ApiError(error?.message ?? 'The runner run could not be loaded.', response.status)
  return data as unknown as RunnerRun
}

export async function cancelRunnerRun(id: string, idempotencyKey: string) {
  const { data, error, response } = await client.POST('/api/v1/runner-runs/{run_id}/cancel', { params: { path: { run_id: id }, header: { 'Idempotency-Key': idempotencyKey } } })
  if (error || !data) throw new ApiError(error?.message ?? 'The runner run could not be cancelled.', response.status)
  return data as unknown as RunnerRun
}

export async function sha256(value: string) {
  const bytes = new TextEncoder().encode(value)
  const digest = await crypto.subtle.digest('SHA-256', bytes)
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('')
}

export function inlineContentRef(value: string) {
  const bytes = new TextEncoder().encode(value)
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return `inline-base64:${btoa(binary)}`
}
