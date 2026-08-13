import { queryOptions } from '@tanstack/react-query'

import { client } from './client'
import { ApiError } from './queries'
import type { components } from './schema'

export type TargetLevel = components['schemas']['TargetLevel']
export type GoalPath = components['schemas']['GoalPath']
export type GoalStatus = components['schemas']['GoalStatus']
export type LearnerProfile = components['schemas']['LearnerProfileResponse']
export type GoalWorkspace = components['schemas']['GoalResponse']
export type ProfileUpdate = components['schemas']['LearnerProfilePatchRequest']
export type GoalCreate = components['schemas']['GoalCreateRequest']
export type GoalPatch = components['schemas']['GoalPatchRequest']
export type ResumeDestination = NonNullable<GoalPatch['resume_destination']>

function failure(error: components['schemas']['ErrorResponse'] | undefined, status: number, fallback: string): never {
  throw new ApiError(error?.message ?? fallback, status)
}

export function profileQueryOptions() {
  return queryOptions({
    queryKey: ['profile'],
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/profile')
      if (error || !data) failure(error, response.status, 'Failed to load the learner profile')
      return data
    },
  })
}

export function goalsQueryOptions() {
  return queryOptions({
    queryKey: ['goals'],
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/goals')
      if (error || !data) failure(error, response.status, 'Failed to load goal workspaces')
      return data
    },
  })
}

export async function updateProfile(update: ProfileUpdate, profileRevision: number): Promise<LearnerProfile> {
  const { data, error, response } = await client.PATCH('/api/v1/profile', { params: { header: { 'If-Match': String(profileRevision) } }, body: update })
  if (error || !data) failure(error, response.status, 'Failed to update the learner profile')
  return data
}

export async function createGoal(input: GoalCreate, idempotencyKey: string): Promise<GoalWorkspace> {
  const { data, error, response } = await client.POST('/api/v1/goals', { params: { header: { 'Idempotency-Key': idempotencyKey } }, body: input })
  if (error || !data) failure(error, response.status, 'Failed to create the goal')
  return data
}

async function patchGoal(goal: GoalWorkspace, body: GoalPatch): Promise<GoalWorkspace> {
  const { data, error, response } = await client.PATCH('/api/v1/goals/{goal_id}', { params: { path: { goal_id: goal.id }, header: { 'If-Match': String(goal.row_version) } }, body })
  if (error || !data) failure(error, response.status, 'Failed to update the goal')
  return data
}

export function updateGoal(goal: GoalWorkspace, body: GoalPatch): Promise<GoalWorkspace> {
  return patchGoal(goal, body)
}

export function setCurrentGoal(goal: GoalWorkspace): Promise<GoalWorkspace> {
  return patchGoal(goal, { set_current: true })
}

export function recordGoalNavigation(goal: GoalWorkspace, resumePosition: string, resumeDestination: ResumeDestination): Promise<GoalWorkspace> {
  return patchGoal(goal, { resume_position: resumePosition, resume_destination: resumeDestination })
}

export function dismissGoalRecommendation(goal: GoalWorkspace, recommendationKey: string): Promise<GoalWorkspace> {
  return patchGoal(goal, { dismiss_recommendation_key: recommendationKey })
}

export async function archiveGoal(goal: GoalWorkspace): Promise<GoalWorkspace> {
  const { data, error, response } = await client.POST('/api/v1/goals/{goal_id}/archive', { params: { path: { goal_id: goal.id }, header: { 'Idempotency-Key': crypto.randomUUID(), 'If-Match': String(goal.row_version) } } })
  if (error || !data) failure(error, response.status, 'Failed to archive the goal')
  return data
}
