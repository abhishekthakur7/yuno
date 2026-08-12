import { queryOptions } from '@tanstack/react-query'

import { client } from './client'
import { ApiError } from './queries'
import type { components } from './schema'

export type CanonicalUpdate = components['schemas']['CanonicalUpdateResponse']
export type CanonicalUpdateItem = components['schemas']['CanonicalMergeItemResponse']
export type CanonicalUpdateResolution = NonNullable<components['schemas']['CanonicalMergeSelectionRequest']['resolution']>
export type CanonicalUpdateAcceptInput = components['schemas']['CanonicalUpdateAcceptRequest']

export function canonicalUpdateQueryOptions(goalId: string | null) {
  return queryOptions({
    queryKey: ['goals', goalId, 'canonical-update'],
    enabled: Boolean(goalId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/goals/{goal_id}/canonical-update', {
        params: { path: { goal_id: goalId! } },
      })
      if (error || !data) throw new ApiError(error?.message ?? 'The canonical update could not be loaded.', response.status)
      return data
    },
  })
}

export async function decideCanonicalUpdate(proposalId: string, decision: 'postpone' | 'dismiss', idempotencyKey: string) {
  const { data, error, response } = await client.POST('/api/v1/canonical-update-proposals/{proposal_id}/decision', {
    params: { path: { proposal_id: proposalId }, header: { 'Idempotency-Key': idempotencyKey } },
    body: { decision, reason: null },
  })
  if (error || !data) throw new ApiError(error?.message ?? 'The canonical update decision could not be saved.', response.status)
  return data
}

export async function acceptCanonicalUpdate(proposalId: string, body: CanonicalUpdateAcceptInput, idempotencyKey: string) {
  const { data, error, response } = await client.POST('/api/v1/canonical-update-proposals/{proposal_id}/accept', {
    params: { path: { proposal_id: proposalId }, header: { 'Idempotency-Key': idempotencyKey } },
    body,
  })
  if (error || !data) throw new ApiError(error?.message ?? 'The canonical update could not be accepted.', response.status)
  return data
}
