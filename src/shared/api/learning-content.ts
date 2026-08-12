import { queryOptions } from '@tanstack/react-query'

import { client } from './client'
import { ApiError } from './queries'
import type { components } from './schema'

export type TopicLayerName = components['schemas']['TopicLayer']
export type TopicLayerContent = components['schemas']['TopicLayerResponse']
export type TopicCheckpoint = components['schemas']['TopicCheckpointResponse']
export type ArtifactProvenanceSummary = components['schemas']['ArtifactProvenanceResponse']

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
    refetchInterval: (query) => {
      const layers = query.state.data?.layers ?? []
      return layers.some(layer => {
        const generation = layer.generation
        return layer.state === 'generating' || generation?.status === 'queued' || generation?.status === 'running'
      }) ? 1_000 : false
    },
  })
}

export function artifactProvenanceQueryOptions(artifactId: string | null) {
  return queryOptions({
    queryKey: ['artifacts', artifactId, 'provenance'],
    enabled: Boolean(artifactId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/artifacts/{artifact_id}/provenance', { params: { path: { artifact_id: artifactId! } } })
      if (error || !data) throw new ApiError(error?.message ?? 'Artifact provenance could not be loaded.', response.status)
      return data
    },
  })
}

export async function generateTopicLayer(goalId: string, topicId: string, layer: TopicLayerName) {
  const { data, error, response } = await client.POST('/api/v1/goals/{goal_id}/topics/{topic_id}/generate', {
    params: { path: { goal_id: goalId, topic_id: topicId }, query: { layer }, header: { 'Idempotency-Key': crypto.randomUUID() } },
  })
  if (error || !data) throw new ApiError(error?.message ?? 'Content generation could not be started.', response.status)
  return data
}

export async function regenerateArtifact(artifactId: string) {
  const { data, error, response } = await client.POST('/api/v1/artifacts/{artifact_id}/regenerate', {
    params: { path: { artifact_id: artifactId }, header: { 'Idempotency-Key': crypto.randomUUID() } },
  })
  if (error || !data) throw new ApiError(error?.message ?? 'Content regeneration could not be started.', response.status)
  return data
}
