import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ workspace: {} as any, settings: {} as any, run: {} as any, report: {} as any, reportEnabled: undefined as boolean | undefined }))
vi.mock('../../shared/use-profile-goals', () => ({ useProfileGoals: () => ({ currentGoal: { id: 'goal-1', name: 'Goal' } }) }))
vi.mock('../../shared/use-evidence', () => ({ useGoalEvidenceReport: () => mocks.workspace }))
vi.mock('../../shared/use-settings', () => ({ useOwnerSettings: () => mocks.settings }))
vi.mock('../../shared/use-interview', () => ({
  useMockRun: () => ({ run: mocks.run }),
  useMockReport: (_runId: string | null, enabled: boolean) => { mocks.reportEnabled = enabled; return mocks.report },
}))

import { Reports } from './CorePages'

const query = (data: unknown) => ({ data, isPending: false, isError: false, refetch: vi.fn() })

beforeEach(() => {
  mocks.workspace = {
    evidence: query([]), entries: [], progress: query(undefined), dispute: { mutate: vi.fn(), isPending: false, isError: false }, reevaluate: { mutate: vi.fn(), isPending: false, isError: false },
  }
  mocks.settings = { settings: query({ progress_display: 'detailed' }), saveProgressDisplay: { mutate: vi.fn(), isPending: false, isError: false } }
  mocks.run = query(undefined)
  mocks.report = query(undefined)
  mocks.reportEnabled = undefined
})

describe('learning Reports presentation', () => {
  it('places its conclusion and next action before report disclosures', () => {
    const { container } = render(<Reports navigate={vi.fn()} />)
    const conclusion = screen.getByRole('heading', { name: 'No terminal mock report is available.' })
    const nextAction = screen.getByRole('heading', { name: /Complete the Mock interview/i })
    const firstDisclosure = container.querySelector('details')!
    expect(conclusion.compareDocumentPosition(firstDisclosure) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(nextAction.compareDocumentPosition(firstDisclosure) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('does not enable the report request before authoritative terminal completion', () => {
    mocks.run = query({ state: 'completing' })
    render(<Reports navigate={vi.fn()} selection={{ runId: 'run-1' }} />)
    expect(mocks.reportEnabled).toBe(false)
    expect(screen.queryByText(/Facts and corrections|Rubric dimensions|Provenance refs/i)).not.toBeInTheDocument()
    expect(screen.getByText('Evaluating')).toBeInTheDocument()
  })

  it('renders a terminal assessment in strict disclosure order without fixture branches', () => {
    const assessment = {
      id: 'assessment-1', feedback: 'Use the durable write as the acknowledgement boundary.', revision_invitation: 'Test the same decision under delayed delivery.',
      assumptions: ['The broker retries delivery.'], facts: ['The write is atomic.'], trade_offs: ['Failing closed reduces availability.'],
      dimensions: [{ dimension_id: 'reasoning', outcome: 'pass', rationale: 'The boundary is explicit.' }], ambiguities: ['Retry timing is unknown.'],
      evaluation_method: 'interactive', citations: ['source-1'], provenance_refs: ['provider-run-1'], limitation_labels: ['Interview transcript only'], disputes: [],
    }
    mocks.run = query({ state: 'completed' })
    mocks.report = query({ run_id: 'run-1', goal_id: 'goal-1', state: 'completed', assessment, transcript: [{ id: 'turn-1', turn_number: 1, kind: 'question', body: 'Where is the boundary?', answer_turn_id: null, created_at: 'now' }] })
    const { container } = render(<Reports navigate={vi.fn()} selection={{ runId: 'run-1' }} />)
    const labels = ['Assumptions', 'Facts and corrections', 'Trade-offs', 'Rubric dimensions', 'Ambiguity', 'Interview transcript', 'Provenance'].map(name => screen.getByRole('heading', { name }))
    labels.slice(1).forEach((item, index) => expect(labels[index]!.compareDocumentPosition(item) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy())
    expect(container.textContent).not.toMatch(/fixture|exact string match/i)
  })

  it('aggregates source warnings and keeps per-entry failures retryable', () => {
    const evidence = { id: 'evidence-1', summary: 'Atomic duplicate handling', evidence_type: 'lab', capability: 'implement', origin: 'learner' }
    const retryDetail = vi.fn()
    const retryAssessment = vi.fn()
    const retrySources = vi.fn()
    mocks.workspace = {
      ...mocks.workspace,
      evidence: query([evidence]),
      entries: [{ evidence, detail: { ...query(undefined), isError: true, refetch: retryDetail }, assessment: { ...query(undefined), isError: true, refetch: retryAssessment }, assessmentHistory: query([]), sources: { ...query([{ id: 'source-1', title: 'Withdrawn guide', availability_status: 'withdrawn' }]), unavailable: [{ id: 'source-1', title: 'Withdrawn guide', availability_status: 'withdrawn' }], refetch: retrySources } }],
    }
    render(<Reports navigate={vi.fn()} />)
    expect(screen.getByText(/Tombstoned source warning/i)).toBeInTheDocument()
    expect(screen.getAllByText(/Withdrawn guide/).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: /Retry evidence evidence-1 detail/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Retry evidence evidence-1 assessment/i })).toBeInTheDocument()
  })

  it('discloses assessment revisions with rubric and dispute history for each evidence entry', () => {
    const evidence = { id: 'evidence-1', summary: 'Atomic duplicate handling', evidence_type: 'lab', capability: 'implement', origin: 'learner' }
    const prior = { id: 'assessment-0', created_at: '2026-08-11T09:00:00Z', state: 'feedback-ready', feedback: 'Prior assessment found a retry gap.', predecessor_assessment_id: null, dimensions: [{ dimension_id: 'correctness', outcome: 'factual-correction', rationale: 'The retry boundary was incomplete.' }], disputes: [{ id: 'dispute-1', status: 'resolved', reason: 'The artifact included a transaction guard.', reevaluation: { status: 'succeeded' } }] }
    const current = { id: 'assessment-1', created_at: '2026-08-12T09:00:00Z', state: 'ambiguity-unresolved', feedback: 'Current assessment preserves one ambiguity.', predecessor_assessment_id: 'assessment-0', ambiguities: ['Acknowledgement timing is not observable.'], dimensions: [{ dimension_id: 'correctness', outcome: 'ambiguity-unresolved', rationale: 'Atomicity is supported; timing is unknown.' }], disputes: [] }
    mocks.workspace = {
      ...mocks.workspace,
      evidence: query([evidence]),
      entries: [{ evidence, detail: query(undefined), assessment: query(current), assessmentHistory: query([current, prior]), sources: { ...query([]), unavailable: [] } }],
    }
    render(<Reports navigate={vi.fn()} />)
    expect(screen.getByText('Assessment history (2)')).toBeInTheDocument()
    expect(screen.getByText('Prior assessment found a retry gap.')).toBeInTheDocument()
    expect(screen.getByText(/2026-08-11T09:00:00Z · feedback-ready/)).toBeInTheDocument()
    expect(screen.getByText('Original assessment')).toBeInTheDocument()
    expect(screen.getByText(/correctness · factual-correction/)).toBeInTheDocument()
    expect(screen.getByText('The retry boundary was incomplete.')).toBeInTheDocument()
    expect(screen.getByText(/The artifact included a transaction guard/)).toHaveTextContent(/Re-evaluation succeeded/)
  })

  it('shows pending per-entry reads as loading instead of empty', () => {
    const evidence = { id: 'evidence-1', summary: 'Atomic duplicate handling', evidence_type: 'lab', capability: 'implement', origin: 'learner' }
    mocks.workspace = {
      ...mocks.workspace,
      evidence: query([evidence]),
      entries: [{
        evidence,
        detail: { ...query(undefined), isPending: true },
        assessment: { ...query(undefined), isPending: true },
        assessmentHistory: { ...query([]), isPending: true },
        sources: { ...query([]), unavailable: [], isPending: true },
      }],
    }
    render(<Reports navigate={vi.fn()} />)
    expect(screen.getByText('Loading evidence detail…')).toBeInTheDocument()
    expect(screen.getByText('Loading assessment…')).toBeInTheDocument()
    expect(screen.getByText('Loading assessment history…')).toBeInTheDocument()
    expect(screen.getByText('Loading cited sources…')).toBeInTheDocument()
    expect(screen.queryByText('No assessment attached.')).not.toBeInTheDocument()
  })

  it('does not present a pending evidence list as an empty report region', () => {
    mocks.workspace = { ...mocks.workspace, evidence: { ...query(undefined), isPending: true } }
    render(<Reports navigate={vi.fn()} />)
    expect(screen.getByText('Loading submitted lab evidence…')).toBeInTheDocument()
    expect(screen.queryByText('No submitted lab evidence.')).not.toBeInTheDocument()
  })
})
