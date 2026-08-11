import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import {
  activeDiagnosticId,
  answerDiagnostic,
  createDiagnostic,
  diagnosticQueryOptions,
  forgetActiveDiagnostic,
  getDiagnosticRoadmapPreview,
  patchDiagnostic,
  rememberActiveDiagnostic,
  type DiagnosticConfidence,
  type DiagnosticPatch,
  type DiagnosticSession,
  type DiagnosticSetup,
} from './api/diagnostics'

export function useDiagnostic() {
  const queryClient = useQueryClient()
  const [sessionId, setSessionId] = useState(activeDiagnosticId)
  const createIdempotencyKey = useRef(crypto.randomUUID())
  const session = useQuery(diagnosticQueryOptions(sessionId))
  const store = (updated: DiagnosticSession) => {
    rememberActiveDiagnostic(updated.id)
    setSessionId(updated.id)
    queryClient.setQueryData(['diagnostics', updated.id], updated)
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
      void queryClient.invalidateQueries({ queryKey: ['diagnostics', sessionId] }),
  })
  const clear = () => {
    forgetActiveDiagnostic()
    setSessionId(null)
  }

  return { session, sessionId, create, patch, answer, preview, clear }
}

export type { DiagnosticConfidence, DiagnosticSetup }
