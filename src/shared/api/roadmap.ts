import { queryOptions } from '@tanstack/react-query'

import { client } from './client'
import { ApiError } from './queries'
import type { components } from './schema'

export type Roadmap = components['schemas']['RoadmapResponse']
export type RoadmapMutation = components['schemas']['RoadmapMutationResponse']
export type LearnerCorrection = components['schemas']['LearnerCorrectionRequest']
export type OrderConstraint = components['schemas']['OrderConstraintRequest']
export type SkipDecision = components['schemas']['SkipDecisionRequest']
export type DepthOverride = components['schemas']['DepthOverrideRequest']

function failure(error: components['schemas']['ErrorResponse'] | undefined, status: number): never {
  throw new ApiError(error?.message ?? 'The roadmap could not be saved', status)
}

export function roadmapQueryOptions(goalId: string | null) {
  return queryOptions({
    queryKey: ['goals', goalId, 'roadmap'],
    enabled: Boolean(goalId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/goals/{goal_id}/roadmap', {
        params: { path: { goal_id: goalId! } },
      })
      if (error || !data) failure(error, response.status)
      return data
    },
  })
}

export function learningStatesQueryOptions(goalId: string | null) {
  return queryOptions({
    queryKey: ['goals', goalId, 'learning-states'],
    enabled: Boolean(goalId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/goals/{goal_id}/learning-states', {
        params: { path: { goal_id: goalId! } },
      })
      if (error || !data) failure(error, response.status)
      return data
    },
  })
}

type RoadmapCommandPath =
  | '/api/v1/goals/{goal_id}/corrections'
  | '/api/v1/goals/{goal_id}/order-constraints'
  | '/api/v1/goals/{goal_id}/skip-decisions'
  | '/api/v1/goals/{goal_id}/depth-overrides'

async function command(path: RoadmapCommandPath, goalId: string, body: object, key: string): Promise<RoadmapMutation> {
  // The generated client's path-specific body overloads cannot be preserved through a
  // path union, so keep the tiny dispatch explicit and fully generated-type checked.
  const params = { path: { goal_id: goalId }, header: { 'Idempotency-Key': key } }
  let result
  if (path.endsWith('/corrections')) result = await client.POST('/api/v1/goals/{goal_id}/corrections', { params, body: body as LearnerCorrection })
  else if (path.endsWith('/order-constraints')) result = await client.POST('/api/v1/goals/{goal_id}/order-constraints', { params, body: body as OrderConstraint })
  else if (path.endsWith('/skip-decisions')) result = await client.POST('/api/v1/goals/{goal_id}/skip-decisions', { params, body: body as SkipDecision })
  else result = await client.POST('/api/v1/goals/{goal_id}/depth-overrides', { params, body: body as DepthOverride })
  if (result.error || !result.data) failure(result.error, result.response.status)
  return result.data
}

export const saveLearnerCorrection = (goalId: string, body: LearnerCorrection, key: string) => command('/api/v1/goals/{goal_id}/corrections', goalId, body, key)
export const saveOrderConstraint = (goalId: string, body: OrderConstraint, key: string) => command('/api/v1/goals/{goal_id}/order-constraints', goalId, body, key)
export const saveSkipDecision = (goalId: string, body: SkipDecision, key: string) => command('/api/v1/goals/{goal_id}/skip-decisions', goalId, body, key)
export const saveDepthOverride = (goalId: string, body: DepthOverride, key: string) => command('/api/v1/goals/{goal_id}/depth-overrides', goalId, body, key)
