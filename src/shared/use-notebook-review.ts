import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createNotebookEntry,
  createReviewAttempt,
  deleteNotebookEntry,
  dismissReview,
  notebookQueryOptions,
  patchNotebookEntry,
  patchReviewPreferences,
  reviewPreferencesQueryOptions,
  reviewsQueryOptions,
  type NotebookEntry,
  type NotebookEntryCreate,
  type NotebookEntryPatch,
  type ReviewAttemptCreate,
  type ReviewPreferences,
  type ReviewPreferencesPatch,
} from './api/notebook-review'

export function useNotebookReview(goalId: string | null) {
  const queryClient = useQueryClient()
  const notebook = useQuery(notebookQueryOptions(goalId))
  const preferences = useQuery(reviewPreferencesQueryOptions(goalId))
  const reviews = useQuery(reviewsQueryOptions(goalId))
  const refreshNotebook = () => queryClient.invalidateQueries({ queryKey: ['goals', goalId, 'notebook'] })
  const refreshReviews = () => queryClient.invalidateQueries({ queryKey: ['goals', goalId, 'reviews'] })
  const createEntry = useMutation({ mutationFn: (body: NotebookEntryCreate) => createNotebookEntry(goalId!, body), onSuccess: refreshNotebook })
  const updateEntry = useMutation({ mutationFn: ({ entry, body }: { entry: NotebookEntry; body: NotebookEntryPatch }) => patchNotebookEntry(entry, body), onSuccess: refreshNotebook })
  const removeEntry = useMutation({ mutationFn: deleteNotebookEntry, onSuccess: refreshNotebook })
  const savePreferences = useMutation({
    mutationFn: ({ current, patch }: { current: ReviewPreferences; patch: ReviewPreferencesPatch }) => patchReviewPreferences(current, patch),
    onSuccess: (updated) => {
      queryClient.setQueryData(['goals', goalId, 'review-preferences'], updated)
      void refreshReviews()
    },
  })
  const attempt = useMutation({ mutationFn: ({ itemId, body }: { itemId: string; body: ReviewAttemptCreate }) => createReviewAttempt(itemId, body), onSuccess: refreshReviews })
  const dismiss = useMutation({ mutationFn: dismissReview, onSuccess: refreshReviews })
  return { notebook, preferences, reviews, createEntry, updateEntry, removeEntry, savePreferences, attempt, dismiss }
}

export function useReviewPreferences(goalId: string | null) {
  const queryClient = useQueryClient()
  const preferences = useQuery(reviewPreferencesQueryOptions(goalId))
  const save = useMutation({
    mutationFn: ({ current, patch }: { current: ReviewPreferences; patch: ReviewPreferencesPatch }) => patchReviewPreferences(current, patch),
    onSuccess: (updated) => queryClient.setQueryData(['goals', goalId, 'review-preferences'], updated),
  })
  return { preferences, save }
}
