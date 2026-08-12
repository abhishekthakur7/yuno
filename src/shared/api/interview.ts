import { queryOptions } from '@tanstack/react-query'

import { client } from './client'
import { ApiError } from './queries'
import type { components } from './schema'

export type InterviewLevel = components['schemas']['InterviewBundleCreateRequest']['target_level']
export type InterviewBundleSubject = components['schemas']['BundleSubject']
export type InterviewBundleItem = components['schemas']['InterviewBundleItemResponse']
export type InterviewBundle = Omit<components['schemas']['InterviewBundleResponse'], 'target_level'> & { target_level: InterviewLevel }
export type InterviewBundleItemCreate = components['schemas']['InterviewBundleItemCreateRequest']
export type InterviewBundleCreate = components['schemas']['InterviewBundleCreateRequest']
export type InterviewBundlePatch = components['schemas']['InterviewBundlePatchRequest']
export type InterviewBundleCopy = components['schemas']['InterviewBundleCopyRequest']
export type InterviewRefresher = components['schemas']['RefresherResponse']
export type InterviewQuestion = components['schemas']['InterviewQuestionResponse']

export type PracticeState = components['schemas']['PracticeRunState']
export type PracticeTurn = components['schemas']['PracticeTurnResponse']
export type PracticeDimension = components['schemas']['PracticeDimensionResultResponse']
export type PracticeResult = components['schemas']['PracticeTurnResultResponse']
export type PracticeRun = components['schemas']['PracticeRunResponse']
export type PracticeRunCreate = components['schemas']['PracticeRunCreateRequest'] & { mode: 'Practice' }
export type PracticeJob = components['schemas']['JobRefResponse']

export type MockRun = components['schemas']['MockRunResponse']
export type MockRunCreate = Omit<components['schemas']['PracticeRunCreateRequest'], 'mode' | 'rubric_id' | 'rubric_version' | 'hint'> & { mode: 'Mock' }
export type MockReport = components['schemas']['MockReportResponse']

export const mockRunQueryOptions = (runId: string | null) => queryOptions({
  queryKey: ['interview-runs', runId],
  enabled: Boolean(runId),
  queryFn: async () => {
    const { data, error, response } = await client.GET('/api/v1/interview-runs/{run_id}', { params: { path: { run_id: runId! } } })
    if (error || !data || data.mode !== 'Mock') failure(error, response.status, 'The Mock run could not be loaded.')
    return data
  },
})

export async function createMockRun(body: MockRunCreate) {
  const { data, error, response } = await client.POST('/api/v1/interview-runs', { body })
  if (error || !data || data.mode !== 'Mock') failure(error, response.status, 'The Mock run could not be created.')
  return data
}

export async function pauseMockRun(runId: string, draft: string) {
  const { data, error, response } = await client.POST('/api/v1/interview-runs/{run_id}/pause', { params: { path: { run_id: runId } }, body: { draft } })
  if (error || !data) failure(error, response.status, 'The Mock draft could not be saved.')
  return data
}

export async function resumeMockRun(runId: string) {
  const { data, error, response } = await client.POST('/api/v1/interview-runs/{run_id}/resume', { params: { path: { run_id: runId } } })
  if (error || !data) failure(error, response.status, 'The Mock run could not be resumed.')
  return data
}

export async function submitMockAnswer(runId: string, answer: string) {
  const { data, error, response } = await client.POST('/api/v1/interview-runs/{run_id}/answers', { params: { path: { run_id: runId }, header: { 'Idempotency-Key': crypto.randomUUID() } }, body: { answer } })
  if (error || !data) failure(error, response.status, 'The Mock answer could not be submitted.')
  return data
}

export async function completeMockRun(runId: string, draft: string, idempotencyKey: string) {
  const { data, error, response } = await client.POST('/api/v1/interview-runs/{run_id}/complete', { params: { path: { run_id: runId }, header: { 'Idempotency-Key': idempotencyKey } }, body: { draft } })
  if (error || !data) failure(error, response.status, 'The Mock interview could not be completed.')
  return data
}

export async function retryMockRun(runId: string) {
  const { data, error, response } = await client.POST('/api/v1/interview-runs/{run_id}/retry-evaluation', { params: { path: { run_id: runId }, header: { 'Idempotency-Key': crypto.randomUUID() } } })
  if (error || !data) failure(error, response.status, 'The Mock operation could not be retried.')
  return data
}

export const mockReportQueryOptions = (runId: string | null, enabled = true) => queryOptions({
  queryKey: ['interview-runs', runId, 'report'],
  enabled: Boolean(runId) && enabled,
  retry: false,
  queryFn: async () => {
    const { data, error, response } = await client.GET('/api/v1/interview-runs/{run_id}/report', { params: { path: { run_id: runId! } } })
    if (error || !data) failure(error, response.status, 'The Mock report is not available.')
    return data
  },
})

export const practiceRunQueryOptions = (runId: string | null) => queryOptions({
  queryKey: ['interview-runs', runId], enabled: Boolean(runId),
  queryFn: async () => {
    const { data, error, response } = await client.GET('/api/v1/interview-runs/{run_id}', { params: { path: { run_id: runId! } } })
    if (error || !data || data.mode !== 'Practice') failure(error, response.status, 'The Practice run could not be loaded.')
    return data
  },
})

export async function createPracticeRun(body: PracticeRunCreate) {
  const { data, error, response } = await client.POST('/api/v1/interview-runs', { body })
  if (error || !data || data.mode !== 'Practice') failure(error, response.status, 'The Practice run could not be created.')
  return data
}

export async function requestPracticeHint(runId: string) {
  const { data, error, response } = await client.POST('/api/v1/interview-runs/{run_id}/hints', { params: { path: { run_id: runId } } })
  if (error || !data) failure(error, response.status, 'The Practice hint could not be requested.')
  return data
}

export async function submitPracticeAnswer(runId: string, answer: string) {
  const { data, error, response } = await client.POST('/api/v1/interview-runs/{run_id}/answers', {
    params: { path: { run_id: runId }, header: { 'Idempotency-Key': crypto.randomUUID() } },
    body: { answer },
  })
  if (error || !data) failure(error, response.status, 'The Practice answer could not be submitted.')
  return data
}

export async function retryPracticeEvaluation(runId: string) {
  const { data, error, response } = await client.POST('/api/v1/interview-runs/{run_id}/retry-evaluation', {
    params: { path: { run_id: runId }, header: { 'Idempotency-Key': crypto.randomUUID() } },
  })
  if (error || !data) failure(error, response.status, 'The Practice evaluation could not be retried.')
  return data
}

export async function cancelPracticeEvaluation(runId: string) {
  const { data, error, response } = await client.POST('/api/v1/interview-runs/{run_id}/cancel-evaluation', { params: { path: { run_id: runId } } })
  if (error || !data || data.mode !== 'Practice') failure(error, response.status, 'The Practice evaluation could not be cancelled.')
  return data
}

function failure(error: components['schemas']['ErrorResponse'] | undefined, status: number, message: string): never {
  throw new ApiError(error?.message ?? message, status)
}

export function interviewBundlesQueryOptions() {
  return queryOptions({
    queryKey: ['interview-bundles'],
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/interview-bundles')
      if (error || !data) failure(error, response.status, 'Interview bundles could not be loaded.')
      return data as InterviewBundle[]
    },
  })
}

export function interviewBundleQueryOptions(bundleId: string | null) {
  return queryOptions({
    queryKey: ['interview-bundles', bundleId],
    enabled: Boolean(bundleId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/interview-bundles/{bundle_id}', { params: { path: { bundle_id: bundleId! } } })
      if (error || !data) failure(error, response.status, 'The interview bundle could not be loaded.')
      return data as InterviewBundle
    },
  })
}

export function refreshersQueryOptions(goalId: string | null) {
  return queryOptions({
    queryKey: ['goals', goalId, 'refreshers'],
    enabled: Boolean(goalId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/goals/{goal_id}/refreshers', { params: { path: { goal_id: goalId! } } })
      if (error || !data) failure(error, response.status, 'Refresher artifacts could not be loaded.')
      return data
    },
  })
}

export function interviewQuestionsQueryOptions(goalId: string | null) {
  return queryOptions({
    queryKey: ['goals', goalId, 'questions'],
    enabled: Boolean(goalId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/goals/{goal_id}/questions', { params: { path: { goal_id: goalId! } } })
      if (error || !data) failure(error, response.status, 'Interview questions could not be loaded.')
      return data
    },
  })
}

export async function createInterviewBundle(body: InterviewBundleCreate) {
  const { data, error, response } = await client.POST('/api/v1/interview-bundles', { params: { header: { 'Idempotency-Key': crypto.randomUUID() } }, body })
  if (error || !data) failure(error, response.status, 'The interview bundle could not be created.')
  return data as InterviewBundle
}

export async function patchInterviewBundle(bundle: InterviewBundle, body: InterviewBundlePatch) {
  const { data, error, response } = await client.PATCH('/api/v1/interview-bundles/{bundle_id}', {
    params: { path: { bundle_id: bundle.id }, header: { 'If-Match': String(bundle.row_version) } }, body,
  })
  if (error || !data) failure(error, response.status, 'The interview bundle could not be updated.')
  return data as InterviewBundle
}

export async function deleteInterviewBundle(bundle: InterviewBundle) {
  const { error, response } = await client.DELETE('/api/v1/interview-bundles/{bundle_id}', { params: { path: { bundle_id: bundle.id } } })
  if (error) failure(error, response.status, 'The interview bundle could not be deleted.')
}

export async function copyInterviewBundle(bundleId: string, body: InterviewBundleCopy) {
  const { data, error, response } = await client.POST('/api/v1/interview-bundles/{bundle_id}/copy', {
    params: { path: { bundle_id: bundleId }, header: { 'Idempotency-Key': crypto.randomUUID() } }, body,
  })
  if (error || !data) failure(error, response.status, 'The interview bundle could not be copied.')
  return data as InterviewBundle
}
