import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LearningStateProvider } from '../../shared/state'
import type { GoalWorkspace } from '../../shared/api/profile-goals'
import { Home, Onboarding, Roadmap } from './CorePages'
import type { DiagnosticSession } from '../../shared/api/diagnostics'

const profile = { experience: null, strengths: null, weaknesses: null, current_goal_id: null, profile_revision: 1, updated_at: '2026-08-12T00:00:00Z' }
const goal = (id: string, name: string): GoalWorkspace => ({ id, name, path: 'learn', subject: 'Distributed systems', role: null, target_level: 'Senior', target_capability: 'implement', graph_version_id: 'graph-1', status: 'active', resume_position: `Checkpoint ${id}`, resume_destination: '/app/topic-studio', dismissed_recommendation_keys: [], last_accessed_at: null, row_version: 1, created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z' })
const diagnosticSession = (patch: Partial<DiagnosticSession> = {}): DiagnosticSession => ({
  id: 'diagnostic-1', captured_graph_version_id: 'graph-1', question_set_version: 'diagnostic-fixture-v1', setup_inputs: { path: 'learn', subject: 'Distributed systems', role: null, target_level: 'Senior', target_capability: 'implement', goal_name: 'Reliable consumers' }, state: 'in-progress', untrusted_seed_kind: null, untrusted_seed_text: null, seed_skipped: false, diagnostic_skipped: false, answers: [], next_question: { ref: 'delivery-contract', prompt: 'What can standard queue delivery guarantee?', sequence: 1, adaptive_context_version: 'diagnostic-fixture-v1' }, started_at: '2026-08-12T00:00:00Z', paused_at: null, expires_at: null, failure_code: null, failure_reference: null, confirmed_goal_id: null, row_version: 1, created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z', ...patch,
})

function json(value: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }))
}

function requestFrom(input: RequestInfo | URL, init?: RequestInit) {
  return input instanceof Request ? input : new Request(new URL(String(input), 'http://localhost'), init)
}

function renderPage(page: React.ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}><LearningStateProvider>{page}</LearningStateProvider></QueryClientProvider>)
}

beforeEach(() => {
  const values = new Map<string, string>()
  Object.defineProperty(window, 'localStorage', { configurable: true, value: { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key), clear: () => values.clear() } })
})
afterEach(() => vi.unstubAllGlobals())

describe('profile-backed goal pages', () => {
  it('keeps the accepted roadmap visible when a background refresh fails', async () => {
    let roadmapFails = false
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestFrom(input, init).url
      if (url.endsWith('/profile')) return json({ ...profile, current_goal_id: 'a' })
      if (url.endsWith('/goals')) return json([goal('a', 'Messaging reliability')])
      if (url.endsWith('/learning-states')) return json([])
      if (url.endsWith('/roadmap')) return roadmapFails
        ? json({ message: 'Refresh failed' }, 503)
        : json({ goal_id: 'a', graph_version_id: 'graph-1', projection_version: 'projection-1', state: 'stale-canonical-version', topics: [{ stable_id: 'delivery-contract', title: 'Delivery contracts', subject: 'Queues', level_tag: 'Senior', target_capability: 'implement', scope_tags: [], classification: 'unverified', recommended_depth: 'Implementation', depth_override: null, is_skipped: false, has_transferred_evidence: false, explanation: 'Saved projection', pending_proposals: [], conflicts: [] }] })
      return json([])
    }))
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={queryClient}><LearningStateProvider><Roadmap navigate={vi.fn()} /></LearningStateProvider></QueryClientProvider>)

    expect(await screen.findByText('Delivery contracts')).toBeInTheDocument()
    expect(screen.getByText(/newer approved curriculum is available/i)).toBeInTheDocument()
    roadmapFails = true
    await queryClient.invalidateQueries({ queryKey: ['goals', 'a', 'roadmap'] })

    expect(await screen.findByText(/last accepted projection is still shown/i)).toBeInTheDocument()
    expect(screen.getByText('Delivery contracts')).toBeInTheDocument()
  })

  it('renders the explicit empty My learning state', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => requestFrom(input, init).url.endsWith('/profile') ? json(profile) : json([])))
    renderPage(<Home navigate={vi.fn()} />)
    expect(await screen.findByRole('heading', { name: 'No learning goals yet' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Set up a goal/i })).toBeInTheDocument()
  })

  it.each([[423, 'locked'], [503, 'unavailable']] as const)('renders the explicit %s failure state', async (status, state) => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => requestFrom(input, init).url.endsWith('/profile') ? json({ message: 'Unavailable' }, status) : json([])))
    renderPage(<Home navigate={vi.fn()} />)
    const view = (await screen.findByRole('heading', { name: new RegExp(`My learning is ${state}`) })).closest('main')
    expect(view).toHaveAttribute('data-workspace-state', state)
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('labels a goal stale only when a newer approved graph exists', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestFrom(input, init).url
      if (url.endsWith('/profile')) return json({ ...profile, current_goal_id: 'a' })
      if (url.endsWith('/canonical/versions')) return json([{ id: 'graph-2', created_at: '', manifest_version: '2', published_at: '', supersedes_version_id: 'graph-1', version_label: 'v2' }])
      return json([goal('a', 'Messaging reliability')])
    }))
    renderPage(<Home navigate={vi.fn()} />)
    const view = (await screen.findByRole('heading', { name: 'Messaging reliability' })).closest('main')
    expect(view).toHaveAttribute('data-workspace-state', 'stale')
    expect(screen.getByText(/stays pinned until you review it/i)).toBeInTheDocument()
  })

  it('renders unavailable when the selected goal is missing', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestFrom(input, init).url
      if (url.endsWith('/profile')) return json({ ...profile, current_goal_id: 'missing' })
      if (url.endsWith('/canonical/versions')) return json([])
      return json([goal('a', 'Messaging reliability')])
    }))
    renderPage(<Home navigate={vi.fn()} />)
    const view = (await screen.findByRole('heading', { name: 'My learning is unavailable' })).closest('main')
    expect(view).toHaveAttribute('data-workspace-state', 'unavailable')
  })

  it('shows multiple goal cards and archives a workspace', async () => {
    let goals = [goal('a', 'Messaging reliability'), goal('b', 'System design interviews')]
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      const url = request.url
      if (url.endsWith('/profile')) return json({ ...profile, current_goal_id: 'a' })
      if (url.endsWith('/goals') && request.method === 'GET') return json(goals)
      if (url.endsWith('/goals/b/archive') && request.method === 'POST') {
        goals = [goals[0]!, { ...goals[1]!, status: 'archived' as const, row_version: 2 }]
        return json(goals[1])
      }
      return json({}, 404)
    })
    vi.stubGlobal('fetch', fetchMock)
    renderPage(<Home navigate={vi.fn()} />)
    expect(await screen.findByRole('heading', { name: 'Messaging reliability' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'System design interviews' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Archive System design interviews' }))
    await userEvent.click(screen.getByRole('button', { name: 'Archive goal' }))
    await waitFor(() => expect(screen.queryByRole('heading', { name: 'System design interviews' })).not.toBeInTheDocument())
  })

  it('offers only approved target levels with the audience statement', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestFrom(input, init).url
      if (url.endsWith('/canonical/versions')) return json([{ id: 'graph-1', created_at: '', manifest_version: '1', published_at: '', supersedes_version_id: null, version_label: 'v1' }])
      if (url.endsWith('/profile')) return json(profile)
      return json([])
    }))
    renderPage(<Onboarding navigate={vi.fn()} />)
    const level = await screen.findByRole('combobox', { name: /Target level/i })
    expect(Array.from((level as HTMLSelectElement).options, (option) => option.text)).toEqual(['Mid-level', 'Senior', 'Staff'])
    expect(screen.getByText(/for experienced backend engineers and does not include a beginner track/i)).toBeInTheDocument()
  })

  it('skips every optional setup step and opens the persisted roadmap preview', async () => {
    const actions: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/canonical/versions')) return json([{ id: 'graph-1', created_at: '', manifest_version: '1', published_at: '', supersedes_version_id: null, version_label: 'v1' }])
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([])
      if (request.url.endsWith('/diagnostics') && request.method === 'POST') return json(diagnosticSession(), 201)
      if (request.url.endsWith('/diagnostics/diagnostic-1') && request.method === 'PATCH') {
        const body = await request.json() as { action?: string }
        if (body.action) actions.push(body.action)
        if (body.action === 'skip_notes') return json(diagnosticSession({ seed_skipped: true, row_version: 2 }))
        if (body.action === 'skip_diagnostic') return json(diagnosticSession({ state: 'skipped', seed_skipped: true, diagnostic_skipped: true, next_question: null, row_version: 3 }))
        return json(diagnosticSession({ state: 'roadmap-preview', seed_skipped: true, diagnostic_skipped: true, next_question: null, row_version: 4 }))
      }
      if (request.url.endsWith('/diagnostics/diagnostic-1/roadmap-preview')) return json({ session_id: 'diagnostic-1', captured_graph_version_id: 'graph-1', state: 'roadmap-preview', answer_count: 0, diagnostic_skipped: true, projection_version: 'diagnostic-preview-v1', topic_recommendations: [] })
      return json({}, 404)
    }))
    renderPage(<Onboarding navigate={vi.fn()} />)
    await userEvent.type(await screen.findByRole('textbox', { name: 'Subject' }), 'Distributed systems')
    await userEvent.type(screen.getByRole('textbox', { name: 'Goal name' }), 'Reliable consumers')
    await userEvent.click(screen.getByRole('button', { name: /Skip to roadmap preview/i }))
    expect(await screen.findByRole('heading', { name: 'Create a goal from this roadmap' })).toBeInTheDocument()
    expect(actions).toEqual(['skip_notes', 'skip_diagnostic', 'open_roadmap_preview'])
  })

  it('resumes a paused server session with every prior answer visible', async () => {
    const savedAnswer = { id: 'answer-1', sequence: 1, question_ref: 'delivery-contract', answer: 'At-least-once delivery permits duplicates.', confidence: 'high' as const, adaptive_context_version: 'diagnostic-fixture-v1', answered_at: '2026-08-12T00:01:00Z' }
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/canonical/versions')) return json([])
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([])
      if (request.url.endsWith('/diagnostics/active') && request.method === 'GET') return json(diagnosticSession({ state: 'paused', seed_skipped: true, answers: [savedAnswer], next_question: null, paused_at: '2026-08-12T00:02:00Z' }))
      if (request.url.endsWith('/diagnostics/diagnostic-1') && request.method === 'PATCH') return json(diagnosticSession({ state: 'resumed', seed_skipped: true, answers: [savedAnswer], next_question: { ref: 'atomic-boundary', prompt: 'Where should the duplicate decision live?', sequence: 2, adaptive_context_version: 'diagnostic-fixture-v1' }, row_version: 2 }))
      return json({}, 404)
    }))
    renderPage(<Onboarding navigate={vi.fn()} />)
    expect(await screen.findByText('1 answer saved on this device’s server')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Resume diagnostic/i }))
    expect(await screen.findByRole('heading', { name: 'Where should the duplicate decision live?' })).toBeInTheDocument()
    expect(screen.getByText('1 answer saved on this device’s server')).toBeInTheDocument()
  })

  it('stores optional Learn notes verbatim and marks them untrusted', async () => {
    const exactSeed = '# Retry notes\n\n- Preserve  two spaces.'
    let receivedSeed = ''
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/canonical/versions')) return json([{ id: 'graph-1', created_at: '', manifest_version: '1', published_at: '', supersedes_version_id: null, version_label: 'v1' }])
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([])
      if (request.url.endsWith('/diagnostics') && request.method === 'POST') return json(diagnosticSession(), 201)
      if (request.url.endsWith('/diagnostics/diagnostic-1') && request.method === 'GET') return json(diagnosticSession({ untrusted_seed_kind: receivedSeed ? 'notes' : null, untrusted_seed_text: receivedSeed || null, row_version: receivedSeed ? 2 : 1 }))
      if (request.url.endsWith('/diagnostics/diagnostic-1') && request.method === 'PATCH') {
        const body = await request.json() as { untrusted_seed_text?: string }
        receivedSeed = body.untrusted_seed_text ?? ''
        return json(diagnosticSession({ untrusted_seed_kind: 'notes', untrusted_seed_text: receivedSeed, row_version: 2 }))
      }
      return json({}, 404)
    }))
    renderPage(<Onboarding navigate={vi.fn()} />)
    await userEvent.type(await screen.findByRole('textbox', { name: 'Subject' }), 'Distributed systems')
    await userEvent.type(screen.getByRole('textbox', { name: 'Goal name' }), 'Reliable consumers')
    await userEvent.click(screen.getByRole('radio', { name: /Take a short diagnostic/i }))
    await userEvent.type(screen.getByRole('textbox', { name: /Optional notes/i }), exactSeed)
    await userEvent.click(screen.getByRole('button', { name: /Start diagnostic/i }))
    expect(await screen.findByText('Untrusted seed · review later in Imports')).toBeInTheDocument()
    expect(receivedSeed).toBe(exactSeed)
    expect(document.querySelector('.sb-untrusted-seed pre')?.textContent).toBe(exactSeed)
  })

})
