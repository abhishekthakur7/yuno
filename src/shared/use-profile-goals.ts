import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  archiveGoal,
  createGoal,
  dismissGoalRecommendation,
  goalsQueryOptions,
  profileQueryOptions,
  recordGoalNavigation,
  setCurrentGoal,
  updateProfile,
  type GoalWorkspace,
  type GoalCreate,
  type ProfileUpdate,
  type ResumeDestination,
} from './api/profile-goals'

export function useProfileGoals() {
  const queryClient = useQueryClient()
  const profile = useQuery(profileQueryOptions())
  const goals = useQuery(goalsQueryOptions())
  const refresh = async () => {
    await Promise.all([profile.refetch(), goals.refetch()])
  }
  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['profile'] }),
      queryClient.invalidateQueries({ queryKey: ['goals'] }),
    ])
  }
  const switchGoal = useMutation({ mutationFn: setCurrentGoal, onSuccess: invalidate })
  const archive = useMutation({ mutationFn: archiveGoal, onSuccess: invalidate })
  const recordNavigation = useMutation({
    mutationFn: ({ goal, position, destination }: { goal: GoalWorkspace; position: string; destination: ResumeDestination }) => recordGoalNavigation(goal, position, destination),
    onSuccess: invalidate,
  })
  const dismissRecommendation = useMutation({
    mutationFn: ({ goal, key }: { goal: GoalWorkspace; key: string }) => dismissGoalRecommendation(goal, key),
    onSuccess: invalidate,
  })
  const create = useMutation({
    mutationFn: ({ input, idempotencyKey }: { input: GoalCreate; idempotencyKey: string }) => createGoal(input, idempotencyKey),
  })
  const saveProfile = useMutation({
    mutationFn: ({ update, revision }: { update: ProfileUpdate; revision: number }) => updateProfile(update, revision),
    onSuccess: (updated) => {
      queryClient.setQueryData(['profile'], updated)
    },
  })

  const activeGoals = (goals.data ?? []).filter((goal) => goal.status === 'active')
  const currentGoal = activeGoals.find((goal) => goal.id === profile.data?.current_goal_id) ?? null

  return {
    profile,
    goals,
    activeGoals,
    currentGoal,
    refresh,
    switchGoal,
    archive,
    recordNavigation,
    dismissRecommendation,
    create,
    saveProfile,
  }
}

export function goalDestination(goal: GoalWorkspace): 'learn-roadmap' | 'interview-hub' {
  return goal.path === 'learn' ? 'learn-roadmap' : 'interview-hub'
}

export function resumePage(goal: GoalWorkspace): 'learn-roadmap' | 'topic-studio' | 'interview-hub' | 'practice' | 'mock' {
  switch (goal.resume_destination) {
    case '/app/learn-roadmap': return 'learn-roadmap'
    case '/app/topic-studio': return 'topic-studio'
    case '/app/interview-hub': return 'interview-hub'
    case '/app/practice': return 'practice'
    case '/app/mock': return 'mock'
    default: return goalDestination(goal)
  }
}
