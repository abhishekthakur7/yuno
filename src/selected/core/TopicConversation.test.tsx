import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { TopicTools } from './CorePages'

function json(value: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }))
}

afterEach(() => vi.unstubAllGlobals())

describe('topic-attached tutor conversation', () => {
  it('persists a learner turn and refreshes the conversation', async () => {
    let sentMessage: string | null = null
    let conversationReads = 0
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = input instanceof Request ? input : new Request(new URL(String(input), 'http://localhost'), init)
      const path = new URL(request.url).pathname
      if (path.endsWith('/notebook')) return json([])
      if (path.endsWith('/review-preferences')) return json({ goal_id: 'goal-1', enabled: false, cadence: 'weekly', row_version: 1 })
      if (path.endsWith('/reviews')) return json({ goal_id: 'goal-1', items: [] })
      if (path.endsWith('/conversation') && request.method === 'POST') {
        sentMessage = (await request.json() as { message: string }).message
        return json({ job_id: 'tutor-job-1', kind: 'tutor_turn', status: 'queued', enqueued_at: '2026-08-13T00:00:00Z', deduplicated: false }, 202)
      }
      if (path.endsWith('/conversation')) {
        conversationReads += 1
        return json(sentMessage ? [
          { id: 'learner-1', goal_id: 'goal-1', topic_id: 'topic-1', role: 'learner', body: sentMessage, response_to_id: null, job_id: 'tutor-job-1', created_at: '2026-08-13T00:00:00Z' },
          { id: 'tutor-1', goal_id: 'goal-1', topic_id: 'topic-1', role: 'tutor', body: 'The commit is the durable boundary.', response_to_id: 'learner-1', job_id: null, created_at: '2026-08-13T00:00:01Z' },
        ] : [])
      }
      return json({ message: 'Not found' }, 404)
    }))
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    render(<QueryClientProvider client={queryClient}><TopicTools goalId="goal-1" topicId="topic-1" conversationScope="goal-1:topic-1" sourcesMarkdown={null} /></QueryClientProvider>)

    await userEvent.click(screen.getByRole('tab', { name: /Help/i }))
    expect(await screen.findByText('No messages yet')).toBeInTheDocument()
    await userEvent.type(screen.getByRole('textbox', { name: /Ask the topic tutor/i }), 'Where is the durable boundary?')
    await userEvent.click(screen.getByRole('button', { name: 'Send question' }))

    await waitFor(() => expect(sentMessage).toBe('Where is the durable boundary?'))
    expect(await screen.findByText('The commit is the durable boundary.')).toBeInTheDocument()
    expect(conversationReads).toBeGreaterThan(1)
  })
})
