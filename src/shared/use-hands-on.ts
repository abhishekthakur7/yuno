import { useEffect, useRef } from 'react'
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'

import { handsOnWorkspaceQueryOptions, submitHandsOnArtifact, type HandsOnSubmitRequest } from './api/hands-on'
import { assessmentQueryOptions } from './api/evidence'
import { getJob } from './api/jobs'

export function useHandsOn(goalId: string | null, topicId: string | null) {
  const queryClient = useQueryClient()
  const submitKeys = useRef(new Map<string, string>())
  const workspace = useQuery(handsOnWorkspaceQueryOptions(goalId, topicId))
  const assessmentQueries = useQueries({ queries: (workspace.data?.reviews ?? []).map(review => assessmentQueryOptions(review.assessment_id)) })
  const assessments = new Map(assessmentQueries.flatMap(query => query.data ? [[query.data.id, query.data] as const] : []))
  const submit = useMutation({
    mutationFn: (body: HandsOnSubmitRequest) => {
      const intent = JSON.stringify(body)
      const key = submitKeys.current.get(intent) ?? crypto.randomUUID()
      submitKeys.current.set(intent, key)
      return submitHandsOnArtifact(goalId!, topicId!, body, key)
    },
    onSuccess: (_data, body) => {
      submitKeys.current.delete(JSON.stringify(body))
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: ['goals', goalId, 'topics', topicId, 'hands-on'] }),
        queryClient.invalidateQueries({ queryKey: ['goals', goalId, 'evidence'] }),
      ])
    },
  })
  const reviewJobId = submit.data?.job_id ?? null
  const reviewJob = useQuery({
    queryKey: ['jobs', reviewJobId],
    enabled: Boolean(reviewJobId),
    queryFn: () => getJob(reviewJobId!),
    refetchInterval: (query) => ['queued', 'running'].includes(query.state.data?.status ?? '') ? 1_500 : false,
  })
  useEffect(() => {
    if (reviewJob.data?.status === 'succeeded') {
      void queryClient.invalidateQueries({ queryKey: ['goals', goalId, 'topics', topicId, 'hands-on'] })
    }
  }, [goalId, queryClient, reviewJob.data?.status, topicId])
  return { workspace, submit, assessments, reviewJob }
}
