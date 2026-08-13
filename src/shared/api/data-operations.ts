import { queryOptions } from '@tanstack/react-query'

import { client } from './client'
import { ApiError } from './queries'
import type { components } from './schema'

export type DeleteImpact = components['schemas']['GoalDeleteImpactResponse']
type JobRef = components['schemas']['JobRefResponse']

function failure(error: components['schemas']['ErrorResponse'] | undefined, status: number, fallback: string): never {
  throw new ApiError(error?.message ?? fallback, status)
}

export async function createExport(goalId: string | null, idempotencyKey: string): Promise<JobRef> {
  const { data, error, response } = await client.POST('/api/v1/exports', {
    params: { header: { 'Idempotency-Key': idempotencyKey } }, body: { goal_id: goalId, version: '1.0' },
  })
  if (error || !data) failure(error, response.status, 'The export could not be started.')
  return data
}

export function exportOperationQueryOptions(operationId: string | null) {
  return queryOptions({
    queryKey: ['exports', operationId], enabled: Boolean(operationId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/exports/{operation_id}', { params: { path: { operation_id: operationId! } } })
      if (error || !data) failure(error, response.status, 'Export status could not be loaded.')
      return data
    },
    refetchInterval: (query) => query.state.data && ['queued', 'running'].includes(query.state.data.status) ? 2_000 : false,
  })
}

export async function createDeletePreflight(goalId: string, idempotencyKey: string): Promise<DeleteImpact> {
  const { data, error, response } = await client.POST('/api/v1/goals/{goal_id}/delete-preflight', {
    params: { path: { goal_id: goalId }, header: { 'Idempotency-Key': idempotencyKey } },
  })
  if (error || !data) failure(error, response.status, 'The delete impact could not be calculated.')
  return data
}

export async function confirmGoalDelete(goalId: string, impact: DeleteImpact, idempotencyKey: string): Promise<JobRef> {
  const { data, error, response } = await client.POST('/api/v1/goals/{goal_id}/delete', {
    params: { path: { goal_id: goalId }, header: { 'Idempotency-Key': idempotencyKey } },
    body: { operation_id: impact.operation_id, snapshot_id: impact.snapshot_id },
  })
  if (error || !data) failure(error, response.status, 'The goal delete could not be started.')
  return data
}

export function deleteOperationQueryOptions(operationId: string | null) {
  return queryOptions({
    queryKey: ['delete-operations', operationId], enabled: Boolean(operationId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/delete-operations/{operation_id}', { params: { path: { operation_id: operationId! } } })
      if (error || !data) failure(error, response.status, 'Delete status could not be loaded.')
      return data
    },
    refetchInterval: (query) => query.state.data && ['queued', 'running', 'cleanup-pending', 'cleanup-failed'].includes(query.state.data.status) ? 2_000 : false,
  })
}
