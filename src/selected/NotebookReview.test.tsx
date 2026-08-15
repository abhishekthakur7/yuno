import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { TopicTools } from './core/CorePages'
import { ReviewPreferencesPanel } from './operations/OperationalPages'

const preferences = { goal_id: 'goal-1', enabled: true, duration_minutes: 15, cadence: 'twice-weekly', retrieval_enabled: true, varied_context_enabled: true, scheduling_version: 'fixture-review-v1', row_version: 1, updated_at: '2026-08-12T00:00:00Z' }
const reviewItem = { id: 'review-1', goal_id: 'goal-1', topic_stable_id: 'topic-1', prompt_ref: 'fixture-1', prompt_type: 'recall', prompt: 'Where must the duplicate decision be made?', answer: null, status: 'due', due_at: '2026-08-12T00:00:00Z', interval_label: '1 day', context: 'A message is redelivered after commit.', scheduling_version: 'fixture-review-v1', failure_reference: null, row_version: 1, created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z' }

function json(value: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }))
}

function requestFrom(input: RequestInfo | URL, init?: RequestInit) {
  return input instanceof Request ? input : new Request(new URL(String(input), 'http://localhost'), init)
}

function renderWithQuery(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>)
}

afterEach(() => vi.unstubAllGlobals())

describe('goal notebook and review UI', () => {
  it('saves a labelled topic-linked notebook entry through the API', async () => {
    let createdBody: unknown
    let entries: unknown[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/goals/goal-1/notebook') && request.method === 'GET') return json(entries)
      if (request.url.endsWith('/goals/goal-1/notebook') && request.method === 'POST') {
        createdBody = await request.json()
        const entry = { id: 'entry-1', goal_id: 'goal-1', ...(createdBody as object), evidence_id: null, source_id: null, row_version: 1, created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z' }
        entries = [entry]
        return json(entry, 201)
      }
      if (request.url.endsWith('/goals/goal-1/review-preferences')) return json(preferences)
      if (request.url.endsWith('/goals/goal-1/reviews')) return json({ goal_id: 'goal-1', enabled: true, scheduling_version: 'fixture-review-v1', items: [] })
      return json({}, 404)
    }))
    renderWithQuery(<TopicTools goalId="goal-1" topicId="topic-1" conversationScope={null} sourcesMarkdown={null} sourcesProvenance={null} />)

    expect(await screen.findByText('No notebook entries yet')).toBeInTheDocument()
    await userEvent.type(screen.getByRole('textbox', { name: 'Add a user entry' }), 'The write must be atomic.')
    await userEvent.click(screen.getByRole('button', { name: 'Save entry' }))

    await waitFor(() => expect(createdBody).toEqual({ entry_kind: 'user', markdown: 'The write must be atomic.', topic_stable_id: 'topic-1' }))
    expect(await screen.findByText('The write must be atomic.')).toBeInTheDocument()
    expect(screen.getByText('user')).toBeInTheDocument()
    expect(screen.getByText('Topic · topic-1')).toBeInTheDocument()
  })

  it('keeps the answer hidden until a nonblank response is submitted', async () => {
    let attemptBody: unknown
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/goals/goal-1/notebook')) return json([])
      if (request.url.endsWith('/goals/goal-1/review-preferences')) return json(preferences)
      if (request.url.endsWith('/goals/goal-1/reviews')) return json({ goal_id: 'goal-1', enabled: true, scheduling_version: 'fixture-review-v1', items: [reviewItem] })
      if (request.url.endsWith('/reviews/review-1/attempts') && request.method === 'POST') {
        attemptBody = await request.json()
        return json({ id: 'attempt-1', goal_id: 'goal-1', review_item_id: 'review-1', ...(attemptBody as object), feedback: 'Good boundary.', correction: null, next_interval_label: '3 days', context_variation: null, context_result: null, scheduling_version: 'fixture-review-v1', review_status: 'completed', revealed_answer: 'Use one atomic business-and-deduplication write.', created_at: '2026-08-12T00:01:00Z' }, 201)
      }
      return json({}, 404)
    }))
    renderWithQuery(<TopicTools goalId="goal-1" topicId="topic-1" conversationScope={null} sourcesMarkdown={null} sourcesProvenance={null} />)
    await userEvent.click(screen.getByRole('tab', { name: 'Review' }))

    expect(await screen.findByText(reviewItem.prompt)).toBeInTheDocument()
    expect(screen.queryByText('Use one atomic business-and-deduplication write.')).not.toBeInTheDocument()
    const submit = screen.getByRole('button', { name: 'Submit response' })
    expect(submit).toBeDisabled()
    await userEvent.type(screen.getByRole('textbox', { name: 'Your response' }), 'At the durable commit boundary.')
    await userEvent.selectOptions(screen.getByRole('combobox', { name: /Confidence/i }), 'high')
    await userEvent.click(submit)

    await waitFor(() => expect(attemptBody).toEqual({ response: 'At the durable commit boundary.', confidence: 'high' }))
    expect(await screen.findByText('Use one atomic business-and-deduplication write.')).toBeInTheDocument()
  })

  it('does not render a queue answer before an attempt and reports generation failure as retryable', async () => {
    const leakedQueueItem = { ...reviewItem, answer: 'Server must not expose this before an attempt.' }
    const failedItem = { ...reviewItem, id: 'review-failed', status: 'generation-failed', answer: null, failure_reference: 'review-generation-ref-1', retryable: true }
    let reviewReads = 0
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/goals/goal-1/notebook')) return json([])
      if (request.url.endsWith('/goals/goal-1/review-preferences')) return json(preferences)
      if (request.url.endsWith('/goals/goal-1/reviews')) {
        reviewReads += 1
        return json({ goal_id: 'goal-1', enabled: true, scheduling_version: 'fixture-review-v1', items: [leakedQueueItem, failedItem] })
      }
      return json({}, 404)
    }))
    renderWithQuery(<TopicTools goalId="goal-1" topicId="topic-1" conversationScope={null} sourcesMarkdown={null} sourcesProvenance={null} />)
    await userEvent.click(screen.getByRole('tab', { name: 'Review' }))

    expect(await screen.findAllByText(reviewItem.prompt)).toHaveLength(2)
    expect(screen.queryByText('Server must not expose this before an attempt.')).not.toBeInTheDocument()
    expect(screen.getByText(/failure is retryable and the roadmap remains available/i)).toBeInTheDocument()
    expect(screen.getByText(/review-generation-ref-1/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Refresh queue' }))
    await waitFor(() => expect(reviewReads).toBeGreaterThan(1))
  })

  it('persists the selected review controls for the current goal', async () => {
    let current = preferences
    let patch: unknown
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/goals/goal-1/review-preferences') && request.method === 'GET') return json(current)
      if (request.url.endsWith('/goals/goal-1/review-preferences') && request.method === 'PATCH') {
        patch = await request.json()
        current = { ...current, ...(patch as object), row_version: 2 }
        return json(current)
      }
      return json({}, 404)
    }))
    renderWithQuery(<ReviewPreferencesPanel goalId="goal-1" />)

    const sessionLength = await screen.findByRole('combobox', { name: 'Session length' })
    const panel = sessionLength.closest('section')!
    await userEvent.selectOptions(sessionLength, '25')
    await waitFor(() => expect(patch).toEqual({ duration_minutes: 25 }))
    expect(await within(panel).findByText('Review preferences saved.')).toBeInTheDocument()
    expect(within(panel).getByRole('combobox', { name: 'Session length' })).toHaveValue('25')
  })

  it('loads and saves preferences for the newly selected goal', async () => {
    const secondPreferences = { ...preferences, goal_id: 'goal-2', enabled: false, duration_minutes: 25, cadence: 'once-weekly', row_version: 4 }
    const patches: Array<{ goal: string; body: unknown; ifMatch: string | null }> = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/goals/goal-1/review-preferences') && request.method === 'GET') return json(preferences)
      if (request.url.endsWith('/goals/goal-2/review-preferences') && request.method === 'GET') return json(secondPreferences)
      if (request.url.endsWith('/goals/goal-2/review-preferences') && request.method === 'PATCH') {
        const body = await request.json()
        patches.push({ goal: 'goal-2', body, ifMatch: request.headers.get('If-Match') })
        return json({ ...secondPreferences, ...(body as object), row_version: 5 })
      }
      return json({}, 404)
    }))
    const view = renderWithQuery(<ReviewPreferencesPanel goalId="goal-1" />)
    expect(await screen.findByRole('combobox', { name: 'Session length' })).toHaveValue('15')

    view.rerender(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><ReviewPreferencesPanel goalId="goal-2" /></QueryClientProvider>)
    const secondDuration = await screen.findByRole('combobox', { name: 'Session length' })
    expect(secondDuration).toHaveValue('25')
    expect(screen.getByRole('checkbox', { name: /Disabled/i })).not.toBeChecked()
    await userEvent.click(screen.getByRole('checkbox', { name: /Disabled/i }))
    await waitFor(() => expect(patches).toEqual([{ goal: 'goal-2', body: { enabled: true }, ifMatch: '4' }]))
  })
})
