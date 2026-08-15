import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LearningStateProvider } from '../../shared/state'
import { InterviewHub, ROLE_LEVEL_COPY, ROLE_LEVEL_TITLE_VARIATION_HELPER } from './CorePages'

const profile = { experience: null, strengths: null, weaknesses: null, current_goal_id: 'goal-1', profile_revision: 1, updated_at: '2026-08-12T00:00:00Z' }
const goal = { id: 'goal-1', name: 'Existing Learn goal', path: 'learn', subject: 'Messaging', role: null, target_level: 'Senior', target_capability: 'implement', graph_version_id: 'graph-1', status: 'active', resume_position: null, resume_destination: null, dismissed_recommendation_keys: [], last_accessed_at: null, row_version: 1, created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z' }
const bundle = {
  id: 'bundle-1', goal_id: 'goal-1', name: 'Senior backend interview', generic_role: 'Backend Engineer', target_level: 'Senior', origin: 'recommended', copy_source_id: null, status: 'active', row_version: 1, created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z',
  items: [
    { id: 'item-technical', bundle_id: 'bundle-1', subject: 'technical', topic_stable_id: 'delivery', question: 'Explain delivery.', position: 0, is_optional: false, included: true },
    { id: 'item-behavioral', bundle_id: 'bundle-1', subject: 'behavioral', topic_stable_id: null, question: 'Describe a trade-off.', position: 1, is_optional: true, included: true },
    { id: 'item-leadership', bundle_id: 'bundle-1', subject: 'leadership', topic_stable_id: null, question: 'Describe alignment.', position: 2, is_optional: true, included: true },
  ],
}

function json(value: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }))
}

function requestFrom(input: RequestInfo | URL, init?: RequestInit) {
  return input instanceof Request ? input : new Request(new URL(String(input), 'http://localhost'), init)
}

function renderHub(mode?: 'refresher' | 'questions', navigate = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}><LearningStateProvider><InterviewHub navigate={navigate} {...(mode ? { mode } : {})} /></LearningStateProvider></QueryClientProvider>)
}

beforeEach(() => {
  const values = new Map<string, string>()
  Object.defineProperty(window, 'localStorage', { configurable: true, value: { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key), clear: () => values.clear() } })
})
afterEach(() => vi.unstubAllGlobals())

describe('API-backed Interview Prep hub', () => {
  it('preserves all four approved cards and loads bundles without a Learn prerequisite', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([goal])
      if (request.url.endsWith('/interview-bundles')) return json([bundle])
      if (request.url.endsWith('/refreshers')) return json([])
      if (request.url.endsWith('/questions')) return json([])
      return json({ message: 'Not found' }, 404)
    }))
    renderHub()

    expect(await screen.findByRole('heading', { name: 'Interview bundles' })).toBeInTheDocument()
    expect(screen.getByText('Review the message delivery contract and evidence gaps.')).toBeInTheDocument()
    expect(screen.getByText('Choose a scenario without completing the Learn path.')).toBeInTheDocument()
    expect(screen.getByText('Request a hint, submit, inspect feedback, and repair.')).toBeInTheDocument()
    expect(screen.getByText('Answer without hints, rubrics, or evaluation until completion.')).toBeInTheDocument()
    expect(await screen.findByDisplayValue('Senior backend interview')).toBeInTheDocument()
  })

  it('associates the Role and level control with the exact title-variation helper and the selected level\'s approved description', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([goal])
      if (request.url.endsWith('/interview-bundles')) return json([bundle])
      if (request.url.endsWith('/refreshers')) return json([])
      if (request.url.endsWith('/questions')) return json([])
      return json({ message: 'Not found' }, 404)
    }))
    renderHub()

    const levelSelect = await screen.findByRole('combobox', { name: 'Role and level' })
    const description = `${ROLE_LEVEL_TITLE_VARIATION_HELPER} ${ROLE_LEVEL_COPY.Senior.description}`
    expect(screen.getByRole('combobox', { name: 'Role and level', description })).toBe(levelSelect)
  })

  it("derives the Interview prep eyebrow from the goal's actual target level using the approved IDK-004 label, for a Mid-level goal", async () => {
    const midGoal = { ...goal, target_level: 'Mid-level' as const }
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([midGoal])
      if (request.url.endsWith('/interview-bundles')) return json([{ ...bundle, target_level: 'Mid-level' }])
      if (request.url.endsWith('/refreshers')) return json([])
      if (request.url.endsWith('/questions')) return json([])
      return json({ message: 'Not found' }, 404)
    }))
    renderHub()

    const eyebrow = await screen.findByText(`Interview prep · ${ROLE_LEVEL_COPY['Mid-level'].label}`)
    expect(eyebrow).toBeInTheDocument()
    expect(eyebrow).toHaveClass('sb-eyebrow')
  })

  it("derives the Interview prep eyebrow from the goal's actual target level using the approved IDK-004 label, for a Staff goal", async () => {
    const staffGoal = { ...goal, target_level: 'Staff' as const }
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([staffGoal])
      if (request.url.endsWith('/interview-bundles')) return json([{ ...bundle, target_level: 'Staff' }])
      if (request.url.endsWith('/refreshers')) return json([])
      if (request.url.endsWith('/questions')) return json([])
      return json({ message: 'Not found' }, 404)
    }))
    renderHub()

    expect(await screen.findByText(`Interview prep · ${ROLE_LEVEL_COPY.Staff.label}`)).toBeInTheDocument()
  })

  it('shows every real refresher linkage and an explicit stale state', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([goal])
      if (request.url.endsWith('/interview-bundles')) return json([bundle])
      if (request.url.endsWith('/refreshers')) return json([{ artifact_id: 'artifact-1', state: 'stale', subject: 'Message delivery', layer: 'Production', source_ref: 'source-1', source_title: 'Approved delivery guide', evidence_gap_ref: 'evidence-1', evidence_gap: 'Commit-before-ack recovery was not explained.', content: 'Review the durable decision boundary.' }])
      if (request.url.endsWith('/questions')) return json([])
      return json({ message: 'Not found' }, 404)
    }))
    renderHub('refresher')

    const content = await screen.findByRole('heading', { name: 'Refresher artifacts' })
    const region = content.closest('section')!
    await waitFor(() => expect(region).toHaveAttribute('data-interview-state', 'stale'))
    expect(within(region).getByText('Message delivery')).toBeInTheDocument()
    expect(within(region).getByText('Production')).toBeInTheDocument()
    expect(within(region).getByText('Approved delivery guide')).toBeInTheDocument()
    expect(within(region).getByText('Commit-before-ack recovery was not explained.')).toBeInTheDocument()
  })

  it('patches only the optional row being toggled and copies without a company field', async () => {
    const commands: Array<{ path: string; body: Record<string, unknown> }> = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([goal])
      if (request.url.endsWith('/refreshers') || request.url.endsWith('/questions')) return json([])
      if (request.url.endsWith('/interview-bundles') && request.method === 'GET') return json([bundle])
      if (request.url.endsWith('/interview-bundles/bundle-1') && request.method === 'PATCH') {
        const body = await request.json() as Record<string, unknown>
        commands.push({ path: request.url, body })
        const itemPatch = (body.items as Array<{ id: string; included: boolean }> | undefined)?.[0]
        return json({ ...bundle, row_version: 2, items: bundle.items.map(item => item.id === itemPatch?.id ? { ...item, included: itemPatch.included } : item) })
      }
      if (request.url.endsWith('/interview-bundles/bundle-1/copy')) {
        const body = await request.json() as Record<string, unknown>
        commands.push({ path: request.url, body })
        return json({ ...bundle, id: 'bundle-copy', name: body.name, copy_source_id: bundle.id }, 201)
      }
      return json({ message: 'Not found' }, 404)
    }))
    renderHub()

    await userEvent.click(await screen.findByRole('checkbox', { name: /behavioral/i }))
    await waitFor(() => expect(commands).toHaveLength(1))
    expect(commands[0]!.body).toEqual({ items: [{ id: 'item-behavioral', included: false }] })
    expect(JSON.stringify(commands[0]!.body)).not.toContain('item-technical')

    await userEvent.click(screen.getByRole('button', { name: 'Copy bundle' }))
    await waitFor(() => expect(commands).toHaveLength(2))
    expect(commands[1]!.body).toEqual({ name: 'Senior backend interview copy' })
    expect(JSON.stringify(commands[1]!.body).toLowerCase()).not.toContain('company')
  })

  it('selects bundle questions and only exposes Practice and Mock handoffs', async () => {
    const navigate = vi.fn()
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([goal])
      if (request.url.endsWith('/interview-bundles')) return json([bundle])
      if (request.url.endsWith('/refreshers')) return json([])
      if (request.url.endsWith('/questions')) return json([{ id: 'question-1', bundle_id: bundle.id, subject: 'technical', topic_stable_id: 'delivery', question: 'Where is the durable boundary?', position: 0, included: true }])
      return json({ message: 'Not found' }, 404)
    }))
    renderHub('questions', navigate)

    const question = await screen.findByRole('checkbox', { name: /Where is the durable boundary/i })
    const region = screen.getByRole('heading', { name: 'Questions' }).closest('section')!
    expect(within(region).getByRole('button', { name: /Open Guided practice/i })).toBeDisabled()
    expect(within(region).getByRole('button', { name: /Open Mock interview/i })).toBeDisabled()
    await userEvent.click(question)
    expect(within(region).getByRole('button', { name: /Open Guided practice/i })).toBeEnabled()
    expect(within(region).getByRole('button', { name: /Open Mock interview/i })).toBeEnabled()
    await userEvent.click(within(region).getByRole('button', { name: /Open Guided practice/i }))
    expect(navigate).toHaveBeenCalledWith('practice', undefined, { bundleId: 'bundle-1', bundleItemId: 'question-1' })
    expect(within(region).queryByText(/score|rubric|post-submission review/i)).not.toBeInTheDocument()
  })

  it('keeps the hub available when bundle reads fail and never synthesizes replacement material', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([goal])
      if (request.url.endsWith('/interview-bundles')) return json({ message: 'Provider unavailable' }, 503)
      if (request.url.endsWith('/refreshers') || request.url.endsWith('/questions')) return json([])
      return json({ message: 'Not found' }, 404)
    }))
    renderHub()

    expect(await screen.findByText('Interview bundles are unavailable')).toBeInTheDocument()
    expect(screen.getByText('No replacement bundle was synthesized.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Refresher' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Question bank' })).toBeInTheDocument()
    expect(document.querySelector('main')).toHaveAttribute('data-interview-state', 'unavailable')
  })

  it('requires an explicit level choice before creating the recommended bundle from the empty state (IDK-004 §4)', async () => {
    let createBody: Record<string, unknown> | null = null
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/profile')) return json({ ...profile, current_goal_id: null })
      if (request.url.endsWith('/goals')) return json([])
      if (request.url.endsWith('/interview-bundles') && request.method === 'GET') return json([])
      if (request.url.endsWith('/interview-bundles') && request.method === 'POST') {
        createBody = await request.json() as Record<string, unknown>
        return json({ ...bundle, ...createBody, goal_id: null }, 201)
      }
      return json({ message: 'Not found' }, 404)
    }))
    renderHub()

    const createButton = await screen.findByRole('button', { name: 'Create recommended bundle' })
    // No level is preselected: creation stays disabled until the learner makes an explicit choice.
    expect(createButton).toBeDisabled()

    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Role and level' }), ROLE_LEVEL_COPY.Senior.label)
    expect(createButton).toBeEnabled()
    await userEvent.click(createButton)
    await waitFor(() => expect(createBody).not.toBeNull())
    expect(createBody).not.toHaveProperty('goal_id')
    expect(JSON.stringify(createBody).toLowerCase()).not.toContain('company')
    expect(createBody).toMatchObject({ generic_role: 'Backend Engineer', target_level: 'Senior', origin: 'recommended' })
    expect(await screen.findByDisplayValue('Senior backend interview')).toBeInTheDocument()
  })
})
