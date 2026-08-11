import { queryOptions } from '@tanstack/react-query'

import { client } from './client'
import { ApiError } from './queries'
import type { components } from './schema'

export type DiagnosticConfidence = components['schemas']['DiagnosticConfidence']
export type DiagnosticSetup = components['schemas']['DiagnosticCreateRequest']
export type DiagnosticSession = components['schemas']['DiagnosticResponse']
export type DiagnosticRoadmapPreview = components['schemas']['DiagnosticRoadmapPreviewResponse']
export type DiagnosticPatch = components['schemas']['DiagnosticPatchRequest']
export type DiagnosticPreviewEdit = components['schemas']['DiagnosticPreviewEditRequest']
export type GoalWorkspace = components['schemas']['GoalResponse']

function failure(
  error: components['schemas']['ErrorResponse'] | undefined,
  status: number,
): never {
  throw new ApiError(error?.message ?? 'The diagnostic could not be saved', status)
}

export function diagnosticQueryOptions(id: string | null) {
  return queryOptions({
    queryKey: ['diagnostics', id],
    enabled: Boolean(id),
    queryFn: () => getDiagnostic(id!),
  })
}

export function activeDiagnosticQueryOptions() {
  return queryOptions({
    queryKey: ['diagnostics', 'active'],
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/diagnostics/active')
      if (error) failure(error, response.status)
      return data ?? null
    },
  })
}

export async function createDiagnostic(
  input: DiagnosticSetup,
  idempotencyKey: string,
): Promise<DiagnosticSession> {
  const { data, error, response } = await client.POST('/api/v1/diagnostics', {
    params: { header: { 'Idempotency-Key': idempotencyKey } },
    body: input,
  })
  if (error || !data) failure(error, response.status)
  return data
}

export async function getDiagnostic(id: string): Promise<DiagnosticSession> {
  const { data, error, response } = await client.GET(
    '/api/v1/diagnostics/{session_id}',
    { params: { path: { session_id: id } } },
  )
  if (error || !data) failure(error, response.status)
  return data
}

export async function patchDiagnostic(
  session: DiagnosticSession,
  patch: DiagnosticPatch,
): Promise<DiagnosticSession> {
  const { data, error, response } = await client.PATCH(
    '/api/v1/diagnostics/{session_id}',
    {
      params: {
        path: { session_id: session.id },
        header: { 'If-Match': String(session.row_version) },
      },
      body: patch,
    },
  )
  if (error || !data) failure(error, response.status)
  return data
}

export async function answerDiagnostic(
  session: DiagnosticSession,
  answer: string,
  confidence: DiagnosticConfidence,
  idempotencyKey: string,
): Promise<DiagnosticSession> {
  if (!session.next_question) throw new Error('The diagnostic has no current question')
  const result = await client.POST('/api/v1/diagnostics/{session_id}/answers', {
    params: {
      path: { session_id: session.id },
      header: { 'Idempotency-Key': idempotencyKey },
    },
    body: { question_ref: session.next_question.ref, answer, confidence },
  })
  if (result.error || !result.data) failure(result.error, result.response.status)
  return getDiagnostic(session.id)
}

export async function getDiagnosticRoadmapPreview(
  sessionId: string,
): Promise<DiagnosticRoadmapPreview> {
  const { data, error, response } = await client.GET(
    '/api/v1/diagnostics/{session_id}/roadmap-preview',
    { params: { path: { session_id: sessionId } } },
  )
  if (error || !data) failure(error, response.status)
  return data
}

export async function saveDiagnosticRoadmapPreview(
  sessionId: string,
  edits: DiagnosticPreviewEdit[],
): Promise<DiagnosticRoadmapPreview> {
  const { data, error, response } = await client.PUT(
    '/api/v1/diagnostics/{session_id}/roadmap-preview',
    { params: { path: { session_id: sessionId } }, body: { edits } },
  )
  if (error || !data) failure(error, response.status)
  return data
}

export async function confirmDiagnosticGoal(sessionId: string): Promise<GoalWorkspace> {
  const { data, error, response } = await client.POST(
    '/api/v1/diagnostics/{session_id}/confirm-goal',
    { params: { path: { session_id: sessionId } } },
  )
  if (error || !data) failure(error, response.status)
  return data
}
