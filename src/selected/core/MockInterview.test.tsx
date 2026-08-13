import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('../../shared/use-profile-goals', () => ({ useProfileGoals: () => ({ currentGoal: { id: 'goal-1', target_capability: 'implement' } }) }))

import { Mock } from './CorePages'

const exactDraft = '  Preserve this draft exactly.\nSecond line.\t'
const baseRun = {
  id: 'mock-run-1', goal_id: 'goal-1', bundle_id: 'bundle-1', bundle_item_id: 'item-1', mode: 'Mock',
  state: 'answering', question: 'Where is the durable boundary?', draft: '', active_job_id: null,
  failure_reference: null, retryable: false, final_assessment_id: null,
  created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z',
  turns: [{ id: 'turn-1', turn_number: 1, kind: 'question', body: 'Where is the durable boundary?', answer_turn_id: null, created_at: '2026-08-12T00:00:00Z' }],
}

function json(value: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }))
}

function renderMock(navigate = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(<QueryClientProvider client={queryClient}><Mock navigate={navigate} selection={{ bundleId: 'bundle-1', bundleItemId: 'item-1' }} /></QueryClientProvider>)
  return navigate
}

afterEach(() => vi.unstubAllGlobals())

describe('API-backed focused Mock', () => {
  it('stores the Save & exit draft byte-for-byte and restores dialog focus', async () => {
    let savedDraft: string | null = null
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(new URL(String(input), 'http://localhost'), init)
      const path = request.url
      if (path.endsWith('/api/v1/interview-runs') && request.method === 'POST') return json(baseRun, 201)
      if (path.endsWith('/mock-run-1')) return json(baseRun)
      if (path.endsWith('/mock-run-1/pause')) {
        savedDraft = (await request.json() as { draft: string }).draft
        return json({ ...baseRun, state: 'paused', draft: savedDraft })
      }
      return json({ message: 'Not found' }, 404)
    }))
    const navigate = renderMock()

    const answer = await screen.findByRole('textbox', { name: /Your response/i })
    await userEvent.type(answer, exactDraft)
    const exit = screen.getByRole('button', { name: /Save & exit/i })
    await userEvent.click(exit)
    await userEvent.click(screen.getByRole('button', { name: /Keep answering/i }))
    expect(exit).toHaveFocus()
    await userEvent.click(exit)
    await userEvent.click(screen.getByRole('button', { name: /^Save & exit$/i }))

    await waitFor(() => expect(savedDraft).toBe(exactDraft))
    expect(navigate).toHaveBeenLastCalledWith('interview-hub', undefined, { runId: 'mock-run-1' })
    expect(screen.queryByRole('button', { name: /hint/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /rubric|score|recommendation|praise/i })).not.toBeInTheDocument()
  })

  it.each(['queued', 'running', 'succeeded', 'cancel-requested', 'cancelled'] as const)('shows the safe %s durable-job state', async status => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(new URL(String(input), 'http://localhost'), init)
      if (request.url.endsWith('/api/v1/interview-runs') && request.method === 'POST') return json({ ...baseRun, state: 'follow-up', active_job_id: 'job-1' }, 201)
      if (request.url.endsWith('/mock-run-1')) return json({ ...baseRun, state: 'follow-up', active_job_id: 'job-1' })
      if (request.url.endsWith('/api/v1/jobs/job-1')) return json({ job_id: 'job-1', kind: 'mock_next_turn', status, enqueued_at: '2026-08-12T00:01:00Z', retryable: false })
      return json({ message: 'Not found' }, 404)
    }))
    renderMock()

    expect(await screen.findByText(`Mock next turn ${status}`)).toBeInTheDocument()
    expect(document.querySelector('[data-provider-job-state]')).toHaveAttribute('data-provider-job-state', status)
    expect(screen.queryByText(/stderr|token|credential|exception/i)).not.toBeInTheDocument()
  })

  it('offers a safe retry for a retryable failed job and tracks the replacement job', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(new URL(String(input), 'http://localhost'), init)
      if (request.url.endsWith('/api/v1/interview-runs') && request.method === 'POST') return json({ ...baseRun, state: 'failed-recoverable', active_job_id: 'job-1', retryable: true }, 201)
      if (request.url.endsWith('/mock-run-1/retry-evaluation') && request.method === 'POST') return json({ job_id: 'job-2', kind: 'mock_next_turn', status: 'queued', enqueued_at: '2026-08-12T00:02:00Z', retryable: false }, 202)
      if (request.url.endsWith('/mock-run-1')) return json({ ...baseRun, state: 'failed-recoverable', active_job_id: 'job-1', retryable: true })
      if (request.url.endsWith('/api/v1/jobs/job-1')) return json({ job_id: 'job-1', kind: 'mock_next_turn', status: 'failed', enqueued_at: '2026-08-12T00:01:00Z', retryable: true })
      if (request.url.endsWith('/api/v1/jobs/job-2')) return json({ job_id: 'job-2', kind: 'mock_next_turn', status: 'queued', enqueued_at: '2026-08-12T00:02:00Z', retryable: false })
      return json({ message: 'Not found' }, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
    renderMock()

    await userEvent.click(await screen.findByRole('button', { name: 'Retry mock next turn' }))
    expect(await screen.findByText('Mock next turn queued')).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([input]) => (input instanceof Request ? input.url : String(input)).endsWith('/mock-run-1/retry-evaluation'))).toBe(true)
  })

  it.each([
    [412, /Waiting for disclosure/i],
    [503, /unavailable or misconfigured/i],
  ] as const)('shows safe recovery guidance when a provider action returns %s', async (status, guidance) => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(new URL(String(input), 'http://localhost'), init)
      if (request.url.endsWith('/api/v1/interview-runs') && request.method === 'POST') return json(baseRun, 201)
      if (request.url.endsWith('/mock-run-1/answers') && request.method === 'POST') return json({ message: 'secret-like provider detail must stay hidden' }, status)
      if (request.url.endsWith('/mock-run-1')) return json(baseRun)
      return json({ message: 'Not found' }, 404)
    }))
    renderMock()

    await userEvent.type(await screen.findByRole('textbox', { name: /Your response/i }), 'A preserved answer')
    await userEvent.click(screen.getByRole('button', { name: 'Submit answer' }))
    expect(await screen.findByText(guidance)).toBeInTheDocument()
    expect(screen.queryByText(/secret-like provider detail/i)).not.toBeInTheDocument()
  })
})
