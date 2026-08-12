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
})
