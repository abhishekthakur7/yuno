import { queryOptions } from '@tanstack/react-query'

import { client } from './client'
import { ApiError } from './queries'
import type { components } from './schema'

export type TopicLayerName = components['schemas']['TopicLayer']
export type TopicLayerContent = components['schemas']['TopicLayerResponse']
export type TopicCheckpoint = components['schemas']['TopicCheckpointResponse']

export const TOPIC_LAYERS: readonly TopicLayerName[] = [
  'Essential',
  'Implementation',
  'Internals',
  'Production',
  'Alternatives',
  'Failures',
  'Interview',
  'Sources',
]

export function topicLayersQueryOptions(goalId: string | null, topicId: string | null) {
  return queryOptions({
    queryKey: ['goals', goalId, 'topics', topicId, 'layers'],
    enabled: Boolean(goalId && topicId),
    queryFn: async () => {
      const { data, error, response } = await client.GET(
        '/api/v1/goals/{goal_id}/topics/{topic_id}/layers',
        { params: { path: { goal_id: goalId!, topic_id: topicId! } } },
      )
      if (error || !data) {
        throw new ApiError(error?.message ?? 'Failed to load topic layers', response.status)
      }
      return data
    },
  })
}
