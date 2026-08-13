import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ workspace: {} as any, settings: {} as any }))
vi.mock('../../shared/use-profile-goals', () => ({ useProfileGoals: () => ({ currentGoal: { id: 'goal-1', name: 'Goal' } }) }))
vi.mock('../../shared/use-evidence', () => ({ useEvidence: () => mocks.workspace }))
vi.mock('../../shared/use-settings', () => ({ useOwnerSettings: () => mocks.settings }))

import { OperationalPageView } from './OperationalPages'

const query = (data: unknown) => ({ data, isPending: false, isError: false, refetch: vi.fn() })

beforeEach(() => {
  const values = new Map<string, string>()
  Object.defineProperty(window, 'localStorage', { configurable: true, value: { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key), clear: () => values.clear() } })
  const evidence = { id: 'evidence-1', summary: 'The implementation supports atomic duplicate handling.', evidence_type: 'lab', capability: 'implement', origin: 'learner', payload_hash: 'hash', created_at: '2026-08-12', active_assessment_id: 'assessment-1' }
  const predecessor = { id: 'assessment-0', feedback: 'The first review found a missing retry boundary.', state: 'feedback-ready', created_at: '2026-08-11T09:00:00Z', dimensions: [{ dimension_id: 'correctness', outcome: 'factual-correction', rationale: 'Retry handling was incomplete.', evidence_refs: ['evidence-1'] }], assumptions: [], ambiguities: [], limitation_labels: [], warnings: [], revision_invitation: null, evaluation_method: 'static review', citations: [], provenance_refs: [], source_refs: [], disputes: [], predecessor_assessment_id: null }
  const assessment = { id: 'assessment-1', feedback: 'The implementation supports atomic duplicate handling.', state: 'ambiguity-unresolved', created_at: '2026-08-12T09:00:00Z', limitation_labels: ['Runtime behavior was not observed.'], warnings: [], revision_invitation: 'Exercise the acknowledgement failure window next.', dimensions: [{ dimension_id: 'correctness', outcome: 'ambiguity-unresolved', rationale: 'The boundary is atomic, but runtime ordering is unknown.', evidence_refs: ['evidence-1'] }], assumptions: ['The database enforces uniqueness.'], ambiguities: ['The acknowledgement timing is not observable in this artifact.'], evaluation_method: 'static review', citations: ['source-1 · section 4'], provenance_refs: ['artifact-1'], source_refs: ['source-1'], disputes: [], predecessor_assessment_id: 'assessment-0' }
  mocks.workspace = {
    evidence: query([evidence]), detail: query({ ...evidence, transfers: [], tombstoned: false }), assessment: query(assessment), assessmentHistory: { ...query([assessment, predecessor]), queries: [] },
    sources: { ...query([
      { id: 'source-1', title: 'Retired delivery guide', availability_status: 'withdrawn' },
      { id: 'source-2', title: 'Current delivery guide', availability_status: 'available' },
    ]), queries: [] },
    progress: query({ coverage: { classification: 'partial', definition: 'Coverage', uncertainty: 'One artifact.', supporting_evidence_refs: ['evidence-1'] }, proficiency: { classification: 'partial', definition: 'Proficiency', uncertainty: 'Limited.', supporting_evidence_refs: [] }, retention: { classification: 'unverified', definition: 'Retention', uncertainty: 'Not retested.', supporting_evidence_refs: [] }, readiness: { classification: 'partial', definition: 'Readiness', uncertainty: 'Transfer needed.', supporting_evidence_refs: [] } }),
    dispute: { mutate: vi.fn(), isPending: false, isError: false }, reevaluate: { mutate: vi.fn(), isPending: false, isError: false },
    sourceRetrieval: { mutate: vi.fn(), isPending: false, isError: false },
    sourceJob: query(undefined),
  }
  mocks.settings = { settings: query({ progress_display: 'detailed' }), saveProgressDisplay: { mutate: vi.fn(), isPending: false, isError: false } }
})

describe('learner-readable Evidence presentation', () => {
  it('prioritizes the conclusion, warns about tombstones, and retrieves available sources explicitly', async () => {
    const { container } = render(<OperationalPageView page="evidence" navigate={vi.fn()} />)
    const conclusion = screen.getByRole('heading', { name: 'The implementation supports atomic duplicate handling.' })
    const limitation = screen.getByText(/Runtime behavior was not observed/)
    const nextAction = screen.getByText('Exercise the acknowledgement failure window next.')
    const firstDisclosure = container.querySelector('details')!

    for (const lead of [conclusion, limitation, nextAction]) {
      expect(lead.compareDocumentPosition(firstDisclosure) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    }
    expect(screen.getByText(/Tombstoned source warning/i)).toBeInTheDocument()
    expect(screen.getAllByText(/Retired delivery guide/).length).toBeGreaterThan(0)

    await userEvent.click(screen.getByText('Sources and provenance'))
    await userEvent.click(screen.getByRole('button', { name: 'Retrieve current snapshot' }))
    expect(mocks.workspace.sourceRetrieval.mutate).toHaveBeenCalledWith('source-2')
  })

  it('shows unresolved ambiguity and the full predecessor assessment chain', () => {
    render(<OperationalPageView page="evidence" navigate={vi.fn()} />)
    expect(screen.getByText('ambiguity-unresolved')).toBeInTheDocument()
    expect(screen.getByText('The acknowledgement timing is not observable in this artifact.')).toBeInTheDocument()
    expect(screen.getByText(/carries no readiness penalty/i)).toBeInTheDocument()
    expect(screen.getByText('The first review found a missing retry boundary.')).toBeInTheDocument()
    expect(screen.getByText(/assessment-0 · original assessment/i)).toBeInTheDocument()
    expect(screen.getByText(/2026-08-11T09:00:00Z · feedback-ready/i)).toBeInTheDocument()
    expect(screen.getByText(/Retry handling was incomplete/)).toBeInTheDocument()
  })

  it('shows pending assessment and provenance reads as loading instead of empty', () => {
    mocks.workspace = {
      ...mocks.workspace,
      assessmentId: 'assessment-1',
      assessment: { ...query(undefined), isPending: true },
      detail: { ...query(undefined), isPending: true },
      assessmentHistory: { ...query([]), queries: [], isPending: true },
    }
    render(<OperationalPageView page="evidence" navigate={vi.fn()} />)
    expect(screen.getByText('Loading assessment detail…')).toBeInTheDocument()
    expect(screen.getByText('Loading evidence provenance…')).toBeInTheDocument()
    expect(screen.getByText('Loading transfer lineage…')).toBeInTheDocument()
    expect(screen.getByText('Loading disputes and re-evaluation history…')).toBeInTheDocument()
    expect(screen.getByText('Loading assessment history…')).toBeInTheDocument()
    expect(screen.queryByText('No assessment is attached to this evidence.')).not.toBeInTheDocument()
    expect(screen.queryByText('No assessment history is available.')).not.toBeInTheDocument()
  })

  it('does not present a pending evidence list as an empty evidence state', () => {
    mocks.workspace = { ...mocks.workspace, evidence: { ...query(undefined), isPending: true } }
    render(<OperationalPageView page="evidence" navigate={vi.fn()} />)
    expect(screen.getByRole('heading', { name: 'Loading submitted evidence…' })).toBeInTheDocument()
    expect(screen.getByText(/No evidence conclusion is inferred before the server read completes/i)).toBeInTheDocument()
    expect(screen.queryByText('No submitted lab evidence is available yet.')).not.toBeInTheDocument()
  })
})
