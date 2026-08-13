import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ practice: {} as any }))
vi.mock('../../shared/use-profile-goals', () => ({
  useProfileGoals: () => ({
    currentGoal: { id: 'goal-1', target_capability: 'implement', resume_position: null },
    goals: { isPending: false },
    recordNavigation: { isPending: false, mutate: vi.fn() },
  }),
}))
vi.mock('../../shared/use-roadmap', () => ({
  useRoadmap: () => ({ roadmap: { data: { topics: [] } } }),
}))
vi.mock('../../shared/use-interview', () => ({
  useInterview: () => ({
    questions: { isPending: false, data: [{ id: 'item-1', bundle_id: 'bundle-1', included: true, question: 'Where is the durable boundary?' }] },
  }),
  usePracticeRun: () => mocks.practice,
}))

import { ApiError } from '../../shared/api/queries'
import { Practice } from './CorePages'

const run = {
  id: 'practice-run-1', state: 'evaluating', question: 'Where is the durable boundary?', active_job_id: 'job-1',
  failure_reference: null, retryable: true, turns: [], results: [],
}

function mutation(overrides: Record<string, unknown> = {}) {
  return { data: undefined, error: null, isPending: false, isError: false, mutate: vi.fn(), mutateAsync: vi.fn(), ...overrides }
}

function setup(job: Record<string, unknown> | undefined, submitError: unknown = null) {
  mocks.practice = {
    run: { data: run, isPending: false, isError: false },
    activeJob: { data: job },
    create: mutation(), hint: mutation(), submit: mutation({ error: submitError, isError: Boolean(submitError) }),
    retry: mutation(), cancel: mutation(),
  }
  return render(<Practice navigate={vi.fn()} selection={{ bundleId: 'bundle-1', bundleItemId: 'item-1' }} />)
}

beforeEach(() => {
  Object.defineProperty(window, '__YUNO_E2E_PRACTICE__', { configurable: true, value: { rubric_id: 'rubric-1', rubric_version: 'v1' } })
})

describe('Practice provider job presentation', () => {
  it.each(['queued', 'running', 'succeeded', 'cancel-requested', 'cancelled'] as const)('renders the safe %s state', status => {
    setup({ job_id: 'job-1', kind: 'practice_evaluation', status, enqueued_at: '2026-08-12T00:00:00Z', retryable: false })

    expect(screen.getByText(`Practice evaluation ${status}`)).toBeInTheDocument()
    expect(document.querySelector('[data-provider-job-state]')).toHaveAttribute('data-provider-job-state', status)
    if (status === 'cancel-requested') expect(screen.getByRole('button', { name: 'Cancellation requested…' })).toBeDisabled()
  })

  it('renders a retryable failure and invokes the durable retry action', async () => {
    setup({ job_id: 'job-1', kind: 'practice_evaluation', status: 'failed', enqueued_at: '2026-08-12T00:00:00Z', retryable: true })

    await userEvent.click(screen.getByRole('button', { name: 'Retry practice evaluation' }))
    expect(mocks.practice.retry.mutate).toHaveBeenCalledOnce()
  })

  it.each([
    [412, /Waiting for disclosure/i],
    [503, /unavailable or misconfigured/i],
  ] as const)('renders safe recovery guidance for status %s', (status, guidance) => {
    setup(undefined, new ApiError('secret-like provider detail', status))

    expect(screen.getByText(guidance)).toBeInTheDocument()
    expect(screen.queryByText(/secret-like provider detail/i)).not.toBeInTheDocument()
  })
})
