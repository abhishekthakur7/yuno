import { queryOptions } from '@tanstack/react-query'

import { client } from './client'
import { ApiError } from './queries'
import type { components } from './schema'

export type Job = components['schemas']['JobRefResponse']
export interface JobEvent {
  event_id: string
  job_id: string
  owner_id: string
  goal_id: string | null
  state: Job['status']
  event_type: string
  timestamp: string
  progress: string | null
  result_ref: string | null
  retryable: boolean
  request_id: string
  correlation_id: string
  run_id: string | null
}

export function jobsQueryOptions() {
  return queryOptions({
    queryKey: ['jobs'],
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/jobs')
      if (error || !data) throw new ApiError(error?.message ?? 'Failed to load jobs', response.status)
      return data
    },
  })
}

export async function getJob(jobId: string): Promise<Job> {
  const { data, error, response } = await client.GET('/api/v1/jobs/{job_id}', { params: { path: { job_id: jobId } } })
  if (error || !data) throw new ApiError(error?.message ?? 'Failed to load job', response.status)
  return data
}

export function jobQueryOptions(jobId: string | null) {
  return queryOptions({
    queryKey: ['jobs', jobId],
    enabled: Boolean(jobId),
    queryFn: () => getJob(jobId!),
  })
}

export async function cancelJob(jobId: string) {
  const { data, error, response } = await client.POST('/api/v1/jobs/{job_id}/cancel', { params: { path: { job_id: jobId } } })
  if (error || !data) throw new ApiError(error?.message ?? 'Failed to cancel job', response.status)
  return data
}

export async function retryJob(input: { jobId: string; substitutionRef: string | null; confirmationRef: string | null }) {
  const { data, error, response } = await client.POST('/api/v1/jobs/{job_id}/retry', { params: { path: { job_id: input.jobId } }, body: { substitution_ref: input.substitutionRef, confirmation_ref: input.confirmationRef } })
  if (error || !data) throw new ApiError(error?.message ?? 'Failed to retry job', response.status)
  return data
}
