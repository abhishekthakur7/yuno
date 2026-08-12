import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { HandsOnWorkspace } from '../../shared/api/hands-on'
import { LearningStateProvider } from '../../shared/state'
import { HandsOnLab } from './HandsOnLab'

const workspace: HandsOnWorkspace = {
  work_id: 'work-1',
  goal_id: 'goal-1',
  topic_id: 'topic-1',
  scenario: { title: 'Make duplicate delivery atomic', prompt: 'Repair the reservation write boundary.', role: 'Platform engineer', level: 'Senior', constraints: ['Multiple consumers can receive the same request.', 'The durable decision must survive restart.'], status: 'fixture', source: 'fixture-pending-idk-009' },
  artifacts: [{ id: 'artifact-1', revision_number: 1, content: 'first', content_hash: 'hash-1', response_to_question_id: null, cross_question_response: null, created_at: '2026-08-13T00:00:00Z', evidence_id: 'evidence-1' }],
  reviews: [{ id: 'review-1', artifact_id: 'artifact-1', assessment_id: 'assessment-1', rubric_id: 'rubric-1', rubric_version: 'fixture-v1', rubric_status: 'fixture', review_mode: 'static', limitation: 'This review can inspect the atomic API boundary but cannot observe concurrent database scheduling.', feedback: 'The durable winner is returned.', created_at: '2026-08-13T00:00:01Z' }],
  cross_questions: [{ id: 'question-1', review_id: 'review-1', artifact_id: 'artifact-1', question: 'What happens if acknowledgement fails after commit?', target_gap: 'post-commit retry', created_at: '2026-08-13T00:00:02Z' }],
}

function json(value: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }))
}

function renderLab() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}><LearningStateProvider><HandsOnLab goalId="goal-1" topicId="topic-1" /></LearningStateProvider></QueryClientProvider>)
}

afterEach(() => vi.unstubAllGlobals())

describe('hands-on lifecycle', () => {
  it('keeps Submit usable when runner posture is disabled and separates static from runtime results', async () => {
    const requests: Request[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(new URL(String(input), 'http://localhost'), init)
      requests.push(request)
      if (new URL(request.url).pathname === '/api/v1/runner/capabilities') return json({ enabled: false, disabled_reason: 'Runner posture is awaiting approval.', environment_policy_version: 'blocked', limits_config_version: null, limitation: 'Controlled subprocess execution is not enabled.', capabilities: [] })
      if (new URL(request.url).pathname === '/api/v1/assessments/assessment-1') return json({ id: 'assessment-1', feedback: 'The durable winner is returned.', state: 'feedback-ready', created_at: '2026-08-13T00:00:01Z', dimensions: [{ dimension_id: 'atomicity', outcome: 'pass', rationale: 'The write decides duplicates atomically.', evidence_refs: ['evidence-1'] }], assumptions: [], ambiguities: [], limitation_labels: [workspace.reviews[0]!.limitation], warnings: [], revision_invitation: null, evaluation_method: 'static', citations: [], provenance_refs: [], source_refs: [], disputes: [], predecessor_assessment_id: null })
      if (new URL(request.url).pathname === '/api/v1/jobs/job-2') return json({ job_id: 'job-2', kind: 'hands_on_static_review', status: 'queued', enqueued_at: '2026-08-13T00:01:00Z', deduplicated: false })
      return request.method === 'POST'
        ? json({ job_id: 'job-2', kind: 'hands_on_static_review', status: 'queued', enqueued_at: '2026-08-13T00:01:00Z', deduplicated: false }, 202)
        : json(workspace)
    }))
    const { container } = renderLab()

    expect(await screen.findByRole('heading', { name: workspace.scenario.title })).toBeInTheDocument()
    expect(screen.getByText('Platform engineer')).toBeInTheDocument()
    expect(screen.getByText('Senior')).toBeInTheDocument()
    expect(screen.getByText(workspace.scenario.constraints[0]!)).toBeInTheDocument()
    const staticRegion = container.querySelector('[data-result-region="static-analysis"]')
    const runtimeRegion = container.querySelector('[data-result-region="runtime"]')
    expect(staticRegion).toBeTruthy()
    expect(runtimeRegion).toBeTruthy()
    expect(staticRegion).not.toBe(runtimeRegion)
    expect(staticRegion).toHaveTextContent('Static-review limitation')

    expect(await screen.findByRole('button', { name: /^Run$/ })).toBeDisabled()
    expect(screen.getByText(/Submit remains available for static review/i)).toBeInTheDocument()
    expect(requests.filter(request => request.method === 'POST')).toHaveLength(0)

    await userEvent.type(screen.getByRole('textbox', { name: 'Response required with your revision' }), 'The redelivery reads the committed winner.')
    await userEvent.click(screen.getByRole('button', { name: 'Submit revision' }))
    await waitFor(() => expect(requests.filter(request => request.method === 'POST')).toHaveLength(1))
    const submit = requests.find(request => request.method === 'POST')!
    expect(new URL(submit.url).pathname).toBe('/api/v1/goals/goal-1/topics/topic-1/hands-on/submit')
    expect(await submit.json()).toEqual({ artifact: expect.any(String), cross_question_response: { question_id: 'question-1', response: 'The redelivery reads the committed winner.' } })
    expect(screen.getByText('Revision 1')).toBeInTheDocument()
    expect(screen.getByText('Evidence evidence-1')).toBeInTheDocument()
  })

  it('confirms the exact input hash, keeps compilation and tests separate, and cancels a running process', async () => {
    const requests: Request[] = []
    const createKeys: Array<string | null> = []
    let cancelled = false
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(new URL(String(input), 'http://localhost'), init)
      requests.push(request)
      const path = new URL(request.url).pathname
      if (path === '/api/v1/runner/capabilities') return json({ enabled: true, disabled_reason: null, environment_policy_version: 'runner-env-v1', limits_config_version: 'runner-limits-v1', limitation: 'Controlled subprocess only.', capabilities: [{ language: 'java', capability: 'compile-test', state: 'supported', detail: 'Configured Java toolchain.' }, { language: 'python', capability: 'execute', state: 'supported', detail: 'Configured Python.' }] })
      if (path === '/api/v1/runner/confirmations') return json({ id: 'confirmation-1', language: 'java', capability: 'compile-test', inputs: [(await request.clone().json() as { inputs: unknown[] }).inputs[0]], confirmed_at: '2026-08-13T01:00:00Z' }, 201)
      if (path === '/api/v1/runner-runs' && request.method === 'POST') {
        createKeys.push(request.headers.get('Idempotency-Key'))
        if (createKeys.length === 1) return json({ message: 'Temporary failure' }, 503)
        return json({ job_id: 'runner-1' }, 202)
      }
      if (path === '/api/v1/runner-runs/runner-1/cancel') {
        cancelled = true
        return json({ id: 'runner-1', state: 'cancel-requested', inputs: [], output_chunks: [], compile_phase: { state: 'running' }, test_phase: { state: 'queued' }, cleanup_state: 'cleanup-pending', limitation: 'Controlled subprocess only.' })
      }
      if (path === '/api/v1/runner-runs/runner-1') return json({ id: 'runner-1', state: cancelled ? 'cancelled' : 'running', inputs: [], output_chunks: [{ phase: 'compile', stream: 'stdout', sequence: 2, content: 'second', truncated: false }, { phase: 'compile', stream: 'stdout', sequence: 1, content: 'first', truncated: false }], compile_phase: { state: 'running' }, test_phase: { state: 'queued' }, cleanup_state: cancelled ? 'cleanup-complete' : 'cleanup-pending', limitation: 'Controlled subprocess only.' })
      if (path === '/api/v1/assessments/assessment-1') return json({ id: 'assessment-1', feedback: '', state: 'feedback-ready', created_at: '', dimensions: [], assumptions: [], ambiguities: [], limitation_labels: ['static only'], warnings: [], revision_invitation: null, evaluation_method: 'static', citations: [], provenance_refs: [], source_refs: [], disputes: [], predecessor_assessment_id: null })
      return json(workspace)
    }))
    const { container } = renderLab()
    const runButton = await screen.findByRole('button', { name: /^Run$/ })
    await waitFor(() => expect(runButton).toBeEnabled())
    await userEvent.click(runButton)
    expect(await screen.findByRole('heading', { name: 'Confirm controlled Java run' })).toBeInTheDocument()
    expect(screen.getByText('Main.java')).toBeInTheDocument()
    expect(screen.getByText('java-source')).toBeInTheDocument()
    expect(screen.getByText(/^[a-f0-9]{64}$/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Confirm and run' }))
    await waitFor(() => expect(createKeys).toHaveLength(1))
    await userEvent.click(screen.getByRole('button', { name: 'Confirm and run' }))
    expect(await screen.findByText(/Run runner-1/)).toBeInTheDocument()
    const confirmationRequest = requests.find(request => new URL(request.url).pathname.endsWith('/runner/confirmations'))!
    const confirmationBody = await confirmationRequest.json() as { acknowledgement_version: string; operation: string; inputs: Array<Record<string, string>> }
    expect(confirmationBody.acknowledgement_version).toBe('runner-not-a-sandbox-v1')
    expect(confirmationBody.operation).toBe('test')
    expect(confirmationBody.inputs[0]).toMatchObject({ logical_path: 'Main.java', declared_type: 'java-source', content_hash: expect.stringMatching(/^[a-f0-9]{64}$/), content_ref: expect.stringMatching(/^inline-base64:/) })
    expect(await requests.find(request => new URL(request.url).pathname === '/api/v1/runner-runs' && request.method === 'POST')!.json()).toEqual({ confirmation_id: 'confirmation-1' })
    expect(createKeys[0]).toBeTruthy()
    expect(createKeys[1]).toBe(createKeys[0])
    expect(requests.filter(request => new URL(request.url).pathname.endsWith('/runner/confirmations'))).toHaveLength(1)
    const runtime = container.querySelector('[data-result-region="runtime"]')!
    expect(runtime.textContent!.indexOf('first')).toBeLessThan(runtime.textContent!.indexOf('second'))
    expect(screen.getByText('Also configured: Python')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Cancel run' }))
    expect(await screen.findByText(/Cancel requested/i)).toBeInTheDocument()
    const cancelRequest = requests.find(request => new URL(request.url).pathname.endsWith('/runner-1/cancel'))!
    expect(cancelRequest.headers.get('Idempotency-Key')).toBeTruthy()
    await userEvent.click(await screen.findByRole('button', { name: 'Confirm fresh retry' }, { timeout: 2_000 }))
    expect(await screen.findByRole('heading', { name: 'Confirm controlled Java run' })).toBeInTheDocument()
    expect(requests.filter(request => new URL(request.url).pathname.endsWith('/runner/confirmations'))).toHaveLength(1)
  })

  it('rejects a static review response without a review-specific limitation', async () => {
    vi.stubGlobal('fetch', vi.fn(() => json({ ...workspace, reviews: [{ ...workspace.reviews[0], limitation: '  ' }] })))
    renderLab()
    expect(await screen.findByRole('alert')).toHaveTextContent('Hands-on scenario unavailable')
  })

  it('reuses one idempotency key when an unchanged Submit intent is retried', async () => {
    const keys: Array<string | null> = []
    const bodies: unknown[] = []
    const emptyWorkspace = { ...workspace, work_id: null, artifacts: [], reviews: [], cross_questions: [] }
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(new URL(String(input), 'http://localhost'), init)
      const path = new URL(request.url).pathname
      if (path === '/api/v1/runner/capabilities') return json({ enabled: false, disabled_reason: 'Runner disabled.', environment_policy_version: null, limits_config_version: null, limitation: 'Static only.', capabilities: [] })
      if (path.endsWith('/hands-on/submit')) {
        keys.push(request.headers.get('Idempotency-Key'))
        bodies.push(await request.json())
        if (keys.length === 1) return json({ message: 'Temporary failure' }, 503)
        return json({ job_id: 'review-job', kind: 'review_hands_on_artifact', status: 'queued', enqueued_at: '2026-08-13T00:00:00Z' }, 202)
      }
      if (path === '/api/v1/jobs/review-job') return json({ job_id: 'review-job', kind: 'review_hands_on_artifact', status: 'queued', enqueued_at: '2026-08-13T00:00:00Z' })
      return json(emptyWorkspace)
    }))
    renderLab()
    const submit = await screen.findByRole('button', { name: 'Submit artifact' })
    await userEvent.click(submit)
    expect(await screen.findByRole('alert')).toHaveTextContent('Submit failed')
    await userEvent.click(submit)
    await waitFor(() => expect(keys).toHaveLength(2))
    expect(keys[0]).toBeTruthy()
    expect(keys[1]).toBe(keys[0])
    expect(bodies[1]).toEqual(bodies[0])
  })
})
