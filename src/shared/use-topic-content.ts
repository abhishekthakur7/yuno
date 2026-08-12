import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { artifactProvenanceQueryOptions, generateTopicLayer, regenerateArtifact, topicLayersQueryOptions, type TopicLayerName } from './api/learning-content'

export function useTopicContent(goalId: string | null, topicId: string | null) {
  const queryClient = useQueryClient()
  const query = useQuery(topicLayersQueryOptions(goalId, topicId))
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['goals', goalId, 'topics', topicId, 'layers'] })
  const generate = useMutation({ mutationFn: (layer: TopicLayerName) => generateTopicLayer(goalId!, topicId!, layer), onSuccess: refresh })
  const regenerate = useMutation({ mutationFn: regenerateArtifact, onSuccess: refresh })
  return { ...query, generate, regenerate }
}

export function useArtifactProvenance(artifactId: string | null) {
  return useQuery(artifactProvenanceQueryOptions(artifactId))
}
