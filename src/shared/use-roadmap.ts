import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import {
  learningStatesQueryOptions,
  roadmapQueryOptions,
  saveDepthOverride,
  saveLearnerCorrection,
  saveOrderConstraint,
  saveSkipDecision,
  type DepthOverride,
  type LearnerCorrection,
  type OrderConstraint,
  type RoadmapMutation,
  type SkipDecision,
} from './api/roadmap'

export function useRoadmap(goalId: string | null) {
  const queryClient = useQueryClient()
  const [checkpointSaved, setCheckpointSaved] = useState(false)
  const roadmap = useQuery(roadmapQueryOptions(goalId))
  const learningStates = useQuery(learningStatesQueryOptions(goalId))
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

  return { roadmap, learningStates, correction, order, skip, depth, checkpointSaved }
}
