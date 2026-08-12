import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  assessmentQueryOptions,
  createAssessmentDispute,
  evidenceDetailQueryOptions,
  evidenceQueryOptions,
  progressQueryOptions,
  requestAssessmentReevaluation,
  sourceQueryOptions,
  type Assessment,
} from './api/evidence'

export function useEvidence(goalId: string | null, requestedEvidenceId: string | null = null) {
  const queryClient = useQueryClient()
  const evidence = useQuery(evidenceQueryOptions(goalId))
  const selectedEvidenceId = requestedEvidenceId ?? evidence.data?.at(-1)?.id ?? null
  const detail = useQuery(evidenceDetailQueryOptions(selectedEvidenceId))
  const assessmentId = detail.data?.active_assessment_id
    ?? evidence.data?.find((item) => item.id === selectedEvidenceId)?.active_assessment_id
    ?? null
  const assessment = useQuery(assessmentQueryOptions(assessmentId))
  const progress = useQuery(progressQueryOptions(goalId))
  const predecessorIds: string[] = []
  let predecessorId = assessment.data?.predecessor_assessment_id ?? null
  while (predecessorId && !predecessorIds.includes(predecessorId)) {
    predecessorIds.push(predecessorId)
    predecessorId = queryClient.getQueryData<Assessment>(['assessments', predecessorId])
      ?.predecessor_assessment_id ?? null
  }
  const predecessorQueries = useQueries({ queries: predecessorIds.map(assessmentQueryOptions) })
  const assessmentHistoryData = [
    ...(assessment.data ? [assessment.data] : []),
    ...predecessorQueries.flatMap((query) => query.data ? [query.data] : []),
  ]
  const sourceIds = [...new Set(assessmentHistoryData.flatMap((item) => item.source_refs))]
  const sourceQueries = useQueries({ queries: sourceIds.map(sourceQueryOptions) })

  const refreshDerivedReads = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['goals', goalId, 'evidence'] }),
      queryClient.invalidateQueries({ queryKey: ['evidence', selectedEvidenceId] }),
      queryClient.invalidateQueries({ queryKey: ['assessments', assessmentId] }),
      queryClient.invalidateQueries({ queryKey: ['goals', goalId, 'progress'] }),
    ])
  }
  const dispute = useMutation({
    mutationFn: ({ assessmentId: id, reason }: { assessmentId: string; reason: string }) =>
      createAssessmentDispute(id, { reason }),
    onSuccess: refreshDerivedReads,
  })
  const reevaluate = useMutation({
    mutationFn: ({ assessmentId: id, disputeId }: { assessmentId: string; disputeId: string }) =>
      requestAssessmentReevaluation(id, { dispute_id: disputeId }),
    onSuccess: refreshDerivedReads,
  })

  const sources = {
    queries: sourceQueries,
    data: sourceQueries.flatMap((query) => query.data ? [query.data] : []),
    isPending: sourceQueries.some((query) => query.isPending),
    isError: sourceQueries.some((query) => query.isError),
    refetch: () => Promise.all(sourceQueries.map((query) => query.refetch())),
  }
  const assessmentHistory = {
    queries: predecessorQueries,
    data: assessmentHistoryData,
    isPending: Boolean(assessmentId) && (assessment.isPending || predecessorQueries.some((query) => query.isPending)),
    isError: assessment.isError || predecessorQueries.some((query) => query.isError),
    refetch: () => Promise.all([assessment.refetch(), ...predecessorQueries.map((query) => query.refetch())]),
  }

  return {
    evidence,
    selectedEvidenceId,
    detail,
    assessmentId,
    assessment,
    assessmentHistory,
    sources,
    progress,
    dispute,
    reevaluate,
  }
}

export function useGoalEvidenceReport(goalId: string | null) {
  const queryClient = useQueryClient()
  const evidence = useQuery(evidenceQueryOptions(goalId))
  const summaries = evidence.data ?? []
  const detailQueries = useQueries({ queries: summaries.map((item) => evidenceDetailQueryOptions(item.id)) })
  const activeAssessmentIds = [...new Set(summaries.flatMap((item) => item.active_assessment_id ? [item.active_assessment_id] : []))]
  const activeAssessmentQueries = useQueries({ queries: activeAssessmentIds.map(assessmentQueryOptions) })

  const assessmentIds = [...activeAssessmentIds]
  let nextIds = activeAssessmentQueries.flatMap((query) => query.data?.predecessor_assessment_id ? [query.data.predecessor_assessment_id] : [])
  while (nextIds.length) {
    const unseenIds = nextIds.filter((id) => !assessmentIds.includes(id))
    if (!unseenIds.length) break
    assessmentIds.push(...unseenIds)
    nextIds = unseenIds.flatMap((id) => {
      const predecessorId = queryClient.getQueryData<Assessment>(['assessments', id])?.predecessor_assessment_id
      return predecessorId ? [predecessorId] : []
    })
  }
  const predecessorIds = assessmentIds.filter((id) => !activeAssessmentIds.includes(id))
  const predecessorQueries = useQueries({ queries: predecessorIds.map(assessmentQueryOptions) })
  const allAssessmentQueries = [...activeAssessmentQueries, ...predecessorQueries]
  const assessmentsById = new Map(allAssessmentQueries.flatMap((query) => query.data ? [[query.data.id, query.data] as const] : []))
  const assessmentQueriesById = new Map([
    ...activeAssessmentIds.map((id, index) => [id, activeAssessmentQueries[index]!] as const),
    ...predecessorIds.map((id, index) => [id, predecessorQueries[index]!] as const),
  ])
  const sourceIds = [...new Set([...assessmentsById.values()].flatMap((item) => item.source_refs))]
  const sourceQueries = useQueries({ queries: sourceIds.map(sourceQueryOptions) })
  const sourceQueriesById = new Map(sourceIds.map((id, index) => [id, sourceQueries[index]!] as const))

  const entries = summaries.map((summary, index) => {
    const detail = detailQueries[index]!
    const activeAssessment = summary.active_assessment_id ? assessmentsById.get(summary.active_assessment_id) : undefined
    const activeAssessmentQuery = summary.active_assessment_id
      ? assessmentQueriesById.get(summary.active_assessment_id)
      : undefined
    const history: Assessment[] = []
    let item = activeAssessment
    while (item && !history.some((candidate) => candidate.id === item!.id)) {
      history.push(item)
      item = item.predecessor_assessment_id ? assessmentsById.get(item.predecessor_assessment_id) : undefined
    }
    const historyIds = history.map((assessment) => assessment.id)
    const unresolvedPredecessorId = history.at(-1)?.predecessor_assessment_id ?? null
    if (unresolvedPredecessorId && !historyIds.includes(unresolvedPredecessorId)) historyIds.push(unresolvedPredecessorId)
    if (summary.active_assessment_id && !historyIds.includes(summary.active_assessment_id)) historyIds.unshift(summary.active_assessment_id)
    const entrySourceIds = [...new Set(history.flatMap((assessment) => assessment.source_refs))]
    const entrySourceQueries = entrySourceIds.flatMap((id) => {
      const query = sourceQueriesById.get(id)
      return query ? [query] : []
    })
    return {
      evidence: summary,
      detail,
      assessment: {
        data: activeAssessment,
        isPending: activeAssessmentQuery?.isPending ?? false,
        isError: activeAssessmentQuery?.isError ?? false,
        refetch: () => activeAssessmentQuery?.refetch() ?? Promise.resolve(),
      },
      assessmentHistory: {
        data: history,
        isPending: historyIds.some((id) => assessmentQueriesById.get(id)?.isPending),
        isError: historyIds.some((id) => assessmentQueriesById.get(id)?.isError),
        refetch: () => Promise.all(historyIds.map((id) => queryClient.refetchQueries({ queryKey: ['assessments', id] }))),
      },
      sources: {
        data: entrySourceQueries.flatMap((query) => query.data ? [query.data] : []),
        unavailable: entrySourceQueries.flatMap((query) => query.data && query.data.availability_status !== 'available' ? [query.data] : []),
        isPending: entrySourceQueries.some((query) => query.isPending),
        isError: entrySourceQueries.some((query) => query.isError),
        refetch: () => Promise.all(entrySourceQueries.map((query) => query.refetch())),
      },
    }
  })
  const progress = useQuery(progressQueryOptions(goalId))
  return { evidence, entries, progress }
}
