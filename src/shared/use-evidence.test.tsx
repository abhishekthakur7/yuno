import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useGoalEvidenceReport } from './use-evidence'

function json(value: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }))
}

function requestFrom(input: RequestInfo | URL, init?: RequestInit) {
  return input instanceof Request ? input : new Request(new URL(String(input), 'http://localhost'), init)
}

function HistoryProbe() {
  const report = useGoalEvidenceReport('goal-1')
  const history = report.entries[0]?.assessmentHistory
  if (!history) return <p>Loading report…</p>
  if (history.isError) return <button onClick={() => void history.refetch()}>Retry full history</button>
  if (history.isPending) return <p>Loading history…</p>
  return <p>{history.data.map((assessment) => assessment.id).join(',')}</p>
}

afterEach(() => vi.unstubAllGlobals())

describe('goal evidence report data', () => {
  it('surfaces and retries a failed predecessor deeper than one revision', async () => {
    let oldestAvailable = false
    let oldestReads = 0
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      const path = new URL(request.url).pathname
      if (path.endsWith('/goals/goal-1/evidence')) return json([{ id: 'evidence-1', goal_id: 'goal-1', topic_stable_id: 'topic-1', evidence_type: 'answer', capability: 'implement', summary: 'Atomic boundary', origin: 'learner', payload_hash: 'hash-1', created_at: '2026-08-12T00:00:00Z', active_assessment_id: 'assessment-3' }])
      if (path.endsWith('/evidence/evidence-1')) return json({ id: 'evidence-1', goal_id: 'goal-1', topic_stable_id: 'topic-1', evidence_type: 'answer', capability: 'implement', summary: 'Atomic boundary', origin: 'learner', payload_hash: 'hash-1', created_at: '2026-08-12T00:00:00Z', active_assessment_id: 'assessment-3', content: 'artifact', content_version: 'v1', tombstoned: false, transfers: [] })
      if (path.endsWith('/assessments/assessment-3')) return json(assessment('assessment-3', 'assessment-2'))
      if (path.endsWith('/assessments/assessment-2')) return json(assessment('assessment-2', 'assessment-1'))
      if (path.endsWith('/assessments/assessment-1')) {
        oldestReads += 1
        return oldestAvailable
          ? json(assessment('assessment-1', null))
          : json({ code: 'unavailable', message: 'Oldest assessment unavailable.' }, 503)
      }
      if (path.endsWith('/goals/goal-1/progress')) return json({})
      return json({ code: 'not_found', message: 'Not found.' }, 404)
    }))
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={queryClient}><HistoryProbe /></QueryClientProvider>)

    const retry = await screen.findByRole('button', { name: 'Retry full history' })
    expect(oldestReads).toBe(1)
    oldestAvailable = true
    await userEvent.click(retry)

    await waitFor(() => expect(screen.getByText('assessment-3,assessment-2,assessment-1')).toBeInTheDocument())
    expect(oldestReads).toBe(2)
  })
})

function assessment(id: string, predecessorAssessmentId: string | null) {
  return {
    id,
    evidence_id: 'evidence-1',
    goal_id: 'goal-1',
    run_id: null,
    rubric_id: 'rubric-1',
    rubric_version: 'v1',
    task_ref: 'task-1',
    assumptions: [],
    requested_capability: 'implement',
    source_refs: [],
    provenance_refs: [],
    role: null,
    level: null,
    evaluation_method: 'static',
    state: 'feedback-ready',
    dimensions: [],
    facts: [],
    trade_offs: [],
    citations: [],
    ambiguities: [],
    feedback: `${id} feedback`,
    cross_question_candidate: null,
    revision_invitation: null,
    warnings: [],
    limitation_labels: [],
    predecessor_assessment_id: predecessorAssessmentId,
    derivation_excluded: predecessorAssessmentId !== 'assessment-2',
    created_at: '2026-08-12T00:00:00Z',
    disputes: [],
  }
}
