import { queryOptions } from '@tanstack/react-query'

import { client } from './client'
import { ApiError } from './queries'
import type { components } from './schema'

export type HandsOnWorkspace = components['schemas']['HandsOnLifecycleResponse']
export type HandsOnStaticReview = components['schemas']['HandsOnReviewResponse']
export type HandsOnSubmitRequest = components['schemas']['HandsOnSubmitRequest']
export type HandsOnSubmitResponse = components['schemas']['JobRefResponse']

export function handsOnWorkspaceQueryOptions(goalId: string | null, topicId: string | null) {
  return queryOptions({
    queryKey: ['goals', goalId, 'topics', topicId, 'hands-on'],
    enabled: Boolean(goalId && topicId),
    refetchInterval: (query) => {
      const data = query.state.data
      return data && data.artifacts.length > data.reviews.length ? 1_500 : false
    },
    queryFn: async () => {
      const { data: workspace, error, response } = await client.GET(
        '/api/v1/goals/{goal_id}/topics/{topic_id}/hands-on',
        { params: { path: { goal_id: goalId!, topic_id: topicId! } } },
      )
      if (error || !workspace) {
        throw new ApiError(error?.message ?? 'Hands-on work could not be loaded.', response.status)
      }
      for (const review of workspace.reviews) {
        if (review.review_mode === 'static' && !review.limitation.trim()) {
          throw new ApiError('Static review response is missing its required limitation.', 502)
        }
      }
      return workspace
    },
  })
}

export async function submitHandsOnArtifact(goalId: string, topicId: string, body: HandsOnSubmitRequest, idempotencyKey: string): Promise<HandsOnSubmitResponse> {
  const { data, error, response } = await client.POST(
    '/api/v1/goals/{goal_id}/topics/{topic_id}/hands-on/submit',
    {
      params: {
        path: { goal_id: goalId, topic_id: topicId },
        header: { 'Idempotency-Key': idempotencyKey },
      },
      body,
    },
  )
  if (error || !data) {
    throw new ApiError(error?.message ?? 'The hands-on artifact could not be submitted.', response.status)
  }
  return data
}
