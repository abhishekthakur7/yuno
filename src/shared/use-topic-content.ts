import { useQuery } from '@tanstack/react-query'

import { topicLayersQueryOptions } from './api/learning-content'

export function useTopicContent(goalId: string | null, topicId: string | null) {
  return useQuery(topicLayersQueryOptions(goalId, topicId))
}
