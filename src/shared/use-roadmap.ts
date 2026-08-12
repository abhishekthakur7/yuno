import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import {
  learningStatesQueryOptions,
  overlayProposalsQueryOptions,
  decideOverlayProposal,
  roadmapQueryOptions,
  saveDepthOverride,
  saveLearnerCorrection,
  saveOrderConstraint,
  saveSkipDecision,
  type DepthOverride,
  type LearnerCorrection,
  type OrderConstraint,
  type OverlayProposal,
  type OverlayProposalDecisionInput,
  type RoadmapMutation,
  type SkipDecision,
} from './api/roadmap'

export function useRoadmap(goalId: string | null, includeProposals = false) {
  const queryClient = useQueryClient()
  const [checkpointSaved, setCheckpointSaved] = useState(false)
  const roadmap = useQuery(roadmapQueryOptions(goalId))
  const learningStates = useQuery(learningStatesQueryOptions(goalId))
  const proposals = useQuery(overlayProposalsQueryOptions(includeProposals ? goalId : null))
  const acceptProjection = (result: RoadmapMutation) => {
    queryClient.setQueryData(['goals', goalId, 'roadmap'], result.projection)
    void queryClient.invalidateQueries({ queryKey: ['goals', goalId, 'learning-states'] })
    setCheckpointSaved(result.checkpoint_saved)
  }
  useEffect(() => {
    if (!checkpointSaved) return
    const timeout = window.setTimeout(() => setCheckpointSaved(false), 2500)
    return () => window.clearTimeout(timeout)
  }, [checkpointSaved])
  const correction = useMutation({
    mutationFn: (body: LearnerCorrection) => saveLearnerCorrection(goalId!, body, crypto.randomUUID()),
    onSuccess: acceptProjection,
  })
  const order = useMutation({
    mutationFn: (body: OrderConstraint) => saveOrderConstraint(goalId!, body, crypto.randomUUID()),
    onSuccess: acceptProjection,
  })
  const skip = useMutation({
    mutationFn: (body: SkipDecision) => saveSkipDecision(goalId!, body, crypto.randomUUID()),
    onSuccess: acceptProjection,
  })
  const depth = useMutation({
    mutationFn: (body: DepthOverride) => saveDepthOverride(goalId!, body, crypto.randomUUID()),
    onSuccess: acceptProjection,
  })
  const decideProposal = useMutation({
    mutationFn: ({ proposal, input }: { proposal: OverlayProposal; input: OverlayProposalDecisionInput }) => decideOverlayProposal(proposal, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['goals', goalId, 'overlay-proposals'] })
      void queryClient.invalidateQueries({ queryKey: ['goals', goalId, 'roadmap'] })
    },
    onError: () => {
      void queryClient.invalidateQueries({ queryKey: ['goals', goalId, 'overlay-proposals'] })
    },
  })

  return { roadmap, learningStates, proposals, correction, order, skip, depth, decideProposal, checkpointSaved }
}
