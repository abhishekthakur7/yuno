import { queryOptions } from '@tanstack/react-query'

import { client } from './client'
import { ApiError } from './queries'
import type { components } from './schema'

export type NotebookEntry = components['schemas']['NotebookEntryResponse']
export type NotebookEntryCreate = components['schemas']['NotebookEntryCreateRequest']
export type NotebookEntryPatch = components['schemas']['NotebookEntryPatchRequest']
export type ReviewPreferences = components['schemas']['ReviewPreferencesResponse']
export type ReviewPreferencesPatch = components['schemas']['ReviewPreferencesPatchRequest']
export type ReviewItem = components['schemas']['ReviewItemResponse']
export type ReviewQueue = components['schemas']['ReviewQueueResponse']
export type ReviewAttemptCreate = components['schemas']['ReviewAttemptCreateRequest']
export type ReviewAttempt = components['schemas']['ReviewAttemptResponse']

function failure(error: components['schemas']['ErrorResponse'] | undefined, status: number, message: string): never {
  throw new ApiError(error?.message ?? message, status)
}

export function notebookQueryOptions(goalId: string | null) {
  return queryOptions({
    queryKey: ['goals', goalId, 'notebook'],
    enabled: Boolean(goalId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/goals/{goal_id}/notebook', { params: { path: { goal_id: goalId! } } })
      if (error || !data) failure(error, response.status, 'The goal notebook could not be loaded.')
      return data
    },
  })
}

export async function createNotebookEntry(goalId: string, body: NotebookEntryCreate) {
  const { data, error, response } = await client.POST('/api/v1/goals/{goal_id}/notebook', {
    params: { path: { goal_id: goalId }, header: { 'Idempotency-Key': crypto.randomUUID() } }, body,
  })
  if (error || !data) failure(error, response.status, 'The notebook entry could not be saved.')
  return data
}

export async function patchNotebookEntry(entry: NotebookEntry, body: NotebookEntryPatch) {
  const { data, error, response } = await client.PATCH('/api/v1/notebook/{entry_id}', {
    params: { path: { entry_id: entry.id }, header: { 'If-Match': String(entry.row_version) } }, body,
  })
  if (error || !data) failure(error, response.status, 'The notebook entry could not be updated.')
  return data
}

export async function deleteNotebookEntry(entry: NotebookEntry) {
  const { error, response } = await client.DELETE('/api/v1/notebook/{entry_id}', {
    params: { path: { entry_id: entry.id }, header: { 'If-Match': String(entry.row_version), 'Idempotency-Key': crypto.randomUUID() } },
  })
  if (error) failure(error, response.status, 'The notebook entry could not be deleted.')
}

export function reviewPreferencesQueryOptions(goalId: string | null) {
  return queryOptions({
    queryKey: ['goals', goalId, 'review-preferences'],
    enabled: Boolean(goalId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/goals/{goal_id}/review-preferences', { params: { path: { goal_id: goalId! } } })
      if (error || !data) failure(error, response.status, 'Review preferences could not be loaded.')
      return data
    },
  })
}

export async function patchReviewPreferences(preferences: ReviewPreferences, body: ReviewPreferencesPatch) {
  const { data, error, response } = await client.PATCH('/api/v1/goals/{goal_id}/review-preferences', {
    params: { path: { goal_id: preferences.goal_id }, header: { 'If-Match': String(preferences.row_version) } }, body,
  })
  if (error || !data) failure(error, response.status, 'Review preferences could not be saved.')
  return data
}

export function reviewsQueryOptions(goalId: string | null) {
  return queryOptions({
    queryKey: ['goals', goalId, 'reviews'],
    enabled: Boolean(goalId),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/goals/{goal_id}/reviews', { params: { path: { goal_id: goalId! } } })
      if (error || !data) failure(error, response.status, 'The review queue could not be loaded.')
      return data
    },
  })
}

export async function createReviewAttempt(itemId: string, body: ReviewAttemptCreate) {
  const { data, error, response } = await client.POST('/api/v1/reviews/{review_id}/attempts', {
    params: { path: { review_id: itemId }, header: { 'Idempotency-Key': crypto.randomUUID() } }, body,
  })
  if (error || !data) failure(error, response.status, 'The review response could not be submitted.')
  return data
}

export async function dismissReview(itemId: string) {
  const { data, error, response } = await client.POST('/api/v1/reviews/{review_id}/dismiss', {
    params: { path: { review_id: itemId }, header: { 'Idempotency-Key': crypto.randomUUID() } },
  })
  if (error || !data) failure(error, response.status, 'The review item could not be dismissed.')
  return data
}
