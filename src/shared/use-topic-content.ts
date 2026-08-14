import { useEffect, useRef } from 'react'
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'

import { artifactProvenanceQueryOptions, generateTopicLayer, regenerateArtifact, sendTutorTurn, sourceSnapshotsQueryOptions, topicConversationQueryOptions, topicLayersQueryOptions, type SourceSnapshot, type TopicLayerName } from './api/learning-content'
import { jobQueryOptions } from './api/jobs'
import { useJobEvents } from './job-events'

export function useTopicContent(goalId: string | null, topicId: string | null) {
  const queryClient = useQueryClient()
  const query = useQuery(topicLayersQueryOptions(goalId, topicId))
  const intentKeys = useRef(new Map<string, string>())
  const intentKey = (scope: string) => {
    const current = intentKeys.current.get(scope) ?? crypto.randomUUID()
    intentKeys.current.set(scope, current)
    return current
  }
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['goals', goalId, 'topics', topicId, 'layers'] })
  const generate = useMutation({ mutationFn: (layer: TopicLayerName) => generateTopicLayer(goalId!, topicId!, layer, intentKey(`generate:${layer}`)), onSuccess: refresh })
  const regenerate = useMutation({ mutationFn: (artifactId: string) => regenerateArtifact(artifactId, intentKey(`regenerate:${artifactId}`)), onSuccess: refresh })
  const activeJobId = regenerate.data?.job_id ?? generate.data?.job_id ?? null
  useJobEvents([activeJobId])
  const activeJob = useQuery(jobQueryOptions(activeJobId))
  useEffect(() => {
    if (!activeJob.data || !['succeeded', 'failed', 'cancelled'].includes(activeJob.data.status)) return
    if (regenerate.data?.job_id === activeJob.data.job_id && regenerate.variables) intentKeys.current.delete(`regenerate:${regenerate.variables}`)
    if (generate.data?.job_id === activeJob.data.job_id && generate.variables) intentKeys.current.delete(`generate:${generate.variables}`)
  }, [activeJob.data, generate.data, generate.variables, regenerate.data, regenerate.variables])
  return { ...query, generate, regenerate, activeJob }
}

export function useArtifactProvenance(artifactId: string | null) {
  const provenance = useQuery(artifactProvenanceQueryOptions(artifactId))
  // Citations only carry a `source_snapshot_id`; the referenced snapshot's retrieval
  // timestamp and version label live behind GET /sources/{source_id}/snapshots (IDK-003 §7).
  const sourceIds = [...new Set(
    (provenance.data?.claims ?? [])
      .flatMap(claim => claim.citations)
      .filter(citation => citation.source_snapshot_id !== null)
      .map(citation => citation.source.id),
  )]
  const snapshotQueries = useQueries({ queries: sourceIds.map(sourceSnapshotsQueryOptions) })
  const snapshotsById = new Map<string, SourceSnapshot>(
    snapshotQueries.flatMap(query => query.data ?? []).map(snapshot => [snapshot.id, snapshot] as const),
  )
  return { ...provenance, snapshotsById }
}

export function useTopicConversation(goalId: string | null, topicId: string | null) {
  const queryClient = useQueryClient()
  const conversation = useQuery(topicConversationQueryOptions(goalId, topicId))
  const intentKeys = useRef(new Map<string, string>())
  const send = useMutation({
    mutationFn: (message: string) => {
      const key = intentKeys.current.get(message) ?? crypto.randomUUID()
      intentKeys.current.set(message, key)
      return sendTutorTurn(goalId!, topicId!, message, key)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['goals', goalId, 'topics', topicId, 'conversation'] }),
  })
  const activeJobId = send.data?.job_id ?? null
  useJobEvents([activeJobId])
  const activeJob = useQuery(jobQueryOptions(activeJobId))
  useEffect(() => {
    if (activeJob.data && ['succeeded', 'failed', 'cancelled'].includes(activeJob.data.status) && send.variables) intentKeys.current.delete(send.variables)
  }, [activeJob.data, send.variables])
  return { conversation, send, activeJob }
}
