import { queryOptions } from '@tanstack/react-query'

import { client } from './client'
import { ApiError } from './queries'
import type { components } from './schema'

export type EvidenceDetail = components['schemas']['EvidenceDetailResponse']
export type Assessment = components['schemas']['AssessmentResponse']
export type AssessmentDispute = components['schemas']['AssessmentDisputeResponse']
export type AssessmentDisputeCreate = components['schemas']['AssessmentDisputeRequest']
export type AssessmentReevaluationCreate = components['schemas']['AssessmentReevaluateRequest']
export type GoalProgress = components['schemas']['GoalProgressResponse']
export type Source = components['schemas']['SourceResponse']
export type JobRef = components['schemas']['JobRefResponse']

function failure(error: components['schemas']['ErrorResponse'] | undefined, status: number, message: string): never {
  throw new ApiError(error?.message ?? message, status)
}

export function evidenceQueryOptions(goalId: string | null) {
  return queryOptions({
    queryKey: ['goals', goalId, 'evidence'],
    enabled: Boolean(goalId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/goals/{goal_id}/evidence', {
        params: { path: { goal_id: goalId! } },
      })
      if (error || !data) failure(error, response.status, 'Evidence could not be loaded.')
      return data
    },
  })
}

export function evidenceDetailQueryOptions(evidenceId: string | null) {
  return queryOptions({
    queryKey: ['evidence', evidenceId],
    enabled: Boolean(evidenceId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/evidence/{evidence_id}', {
        params: { path: { evidence_id: evidenceId! } },
      })
      if (error || !data) failure(error, response.status, 'The evidence record could not be loaded.')
      return data
    },
  })
}

export function assessmentQueryOptions(assessmentId: string | null) {
  return queryOptions({
    queryKey: ['assessments', assessmentId],
    enabled: Boolean(assessmentId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/assessments/{assessment_id}', {
        params: { path: { assessment_id: assessmentId! } },
      })
      if (error || !data) failure(error, response.status, 'The assessment could not be loaded.')
      return data
    },
  })
}

export function progressQueryOptions(goalId: string | null) {
  return queryOptions({
    queryKey: ['goals', goalId, 'progress'],
    enabled: Boolean(goalId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/goals/{goal_id}/progress', {
        params: { path: { goal_id: goalId! } },
      })
      if (error || !data) failure(error, response.status, 'Progress could not be loaded.')
      return data
    },
  })
}

export function sourceQueryOptions(sourceId: string | null) {
  return queryOptions({
    queryKey: ['sources', sourceId],
    enabled: Boolean(sourceId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/sources/{source_id}', {
        params: { path: { source_id: sourceId! } },
      })
      if (error || !data) failure(error, response.status, 'A cited source could not be loaded.')
      return data
    },
  })
}

export async function createAssessmentDispute(
  assessmentId: string,
  body: AssessmentDisputeCreate,
): Promise<AssessmentDispute> {
  const { data, error, response } = await client.POST('/api/v1/assessments/{assessment_id}/disputes', {
    params: {
      path: { assessment_id: assessmentId },
      header: { 'Idempotency-Key': crypto.randomUUID() },
    },
    body,
  })
  if (error || !data) failure(error, response.status, 'The dispute could not be recorded.')
  return data
}

export async function requestAssessmentReevaluation(
  assessmentId: string,
  body: AssessmentReevaluationCreate,
): Promise<JobRef> {
  const { data, error, response } = await client.POST('/api/v1/assessments/{assessment_id}/reevaluate', {
    params: {
      path: { assessment_id: assessmentId },
      header: { 'Idempotency-Key': crypto.randomUUID() },
    },
    body,
  })
  if (error || !data) failure(error, response.status, 'Re-evaluation could not be requested.')
  return data
}

export async function retrieveSource({ sourceId, idempotencyKey }: { sourceId: string; idempotencyKey: string }): Promise<JobRef> {
  const { data, error, response } = await client.POST('/api/v1/sources/{source_id}/retrieve', {
    params: {
      path: { source_id: sourceId },
      header: { 'Idempotency-Key': idempotencyKey },
    },
  })
  if (error || !data) failure(error, response.status, 'Source retrieval could not be started.')
  return data
}
