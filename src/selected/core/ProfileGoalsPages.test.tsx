import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LearningStateProvider } from '../../shared/state'
import type { GoalWorkspace } from '../../shared/api/profile-goals'
import { Home, Onboarding } from './CorePages'

const profile = { experience: null, strengths: null, weaknesses: null, current_goal_id: null, profile_revision: 1, updated_at: '2026-08-12T00:00:00Z' }
const goal = (id: string, name: string): GoalWorkspace => ({ id, name, path: 'learn', subject: 'Distributed systems', role: null, target_level: 'Senior', target_capability: 'implement', graph_version_id: 'graph-1', status: 'active', resume_position: `Checkpoint ${id}`, resume_destination: '/app/topic-studio', dismissed_recommendation_keys: [], last_accessed_at: null, row_version: 1, created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z' })

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

})
