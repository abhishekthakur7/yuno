import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef } from 'react'

import {
  activeDiagnosticQueryOptions,
  answerDiagnostic,
  createDiagnostic,
  confirmDiagnosticGoal,
  getDiagnosticRoadmapPreview,
  patchDiagnostic,
  saveDiagnosticRoadmapPreview,
  type DiagnosticPreviewEdit,
  type DiagnosticConfidence,
  type DiagnosticPatch,
  type DiagnosticSession,
  type DiagnosticSetup,
} from './api/diagnostics'

export function useDiagnostic() {
  const queryClient = useQueryClient()
  const createIdempotencyKey = useRef(crypto.randomUUID())
  const session = useQuery(activeDiagnosticQueryOptions())
  const sessionId = session.data?.id ?? null
  const store = (updated: DiagnosticSession) => {
    queryClient.setQueryData(['diagnostics', updated.id], updated)
    queryClient.setQueryData(['diagnostics', 'active'], updated)
    return updated
  }
  const create = useMutation({
    mutationFn: (input: DiagnosticSetup) =>
      createDiagnostic(input, createIdempotencyKey.current),
    onSuccess: store,
  })
  const patch = useMutation({
    mutationFn: ({ session, patch }: {
      session: DiagnosticSession
      patch: DiagnosticPatch
    }) => patchDiagnostic(session, patch),
    onSuccess: store,
  })
  const answer = useMutation({
    mutationFn: ({ session, answer, confidence, idempotencyKey }: {
      session: DiagnosticSession
      answer: string
      confidence: DiagnosticConfidence
      idempotencyKey: string
    }) => answerDiagnostic(session, answer, confidence, idempotencyKey),
    onSuccess: store,
  })
  const preview = useMutation({
    mutationFn: getDiagnosticRoadmapPreview,
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: ['diagnostics', 'active'] }),
  })
  const savePreview = useMutation({
    mutationFn: ({ sessionId, edits }: { sessionId: string; edits: DiagnosticPreviewEdit[] }) =>
      saveDiagnosticRoadmapPreview(sessionId, edits),
  })
  const confirm = useMutation({
    mutationFn: async ({ session, edits }: { session: DiagnosticSession; edits: DiagnosticPreviewEdit[] }) => {
      await saveDiagnosticRoadmapPreview(session.id, edits)
      return confirmDiagnosticGoal(session.id)
    },
    onSuccess: () => {
      queryClient.setQueryData(['diagnostics', 'active'], null)
      void queryClient.invalidateQueries({ queryKey: ['profile'] })
      void queryClient.invalidateQueries({ queryKey: ['goals'] })
    },
  })
  const clear = () => {
    queryClient.setQueryData(['diagnostics', 'active'], null)
  }

  return { session, sessionId, create, patch, answer, preview, savePreview, confirm, clear }
}

export type { DiagnosticConfidence, DiagnosticPreviewEdit, DiagnosticSetup }
