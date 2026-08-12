import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { JobsPage } from './OperationalPages'
import * as jobsApi from '../../shared/api/jobs'

vi.mock('../../shared/job-events', () => ({
  JobConnectionStatus: () => <div>Live job events</div>,
}))
vi.mock('../../shared/api/jobs', async () => {
  const actual = await vi.importActual<typeof import('../../shared/api/jobs')>('../../shared/api/jobs')
  return { ...actual, cancelJob: vi.fn(), retryJob: vi.fn() }
})

const failed = {
  job_id: 'job-failed', kind: 'generate_mock_next_turn', status: 'failed' as const,
  enqueued_at: '2026-08-12T00:00:00Z', deduplicated: false, lane: 'interactive' as const,
  retryable: true, schema_version: '1', attempt: 2,
  started_at: '2026-08-12T00:00:01Z', terminal_at: '2026-08-12T00:00:02Z',
  diagnostic: 'provider unavailable', result_ref: null, result_hash: null,
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  client.setQueryData(['jobs'], {
    jobs: [failed, { ...failed, job_id: 'job-ok', status: 'succeeded', retryable: false, result_ref: 'Assessment:abc', result_hash: 'hash-abc' }],
    pending_job_cap: 100, background_age_promotion_seconds: 60, janitor_retention_seconds: 60,
  })
  return render(<QueryClientProvider client={client}><JobsPage /></QueryClientProvider>)
}

describe('JobsPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows persisted diagnostics/results and supplies retry recovery inputs', async () => {
    vi.mocked(jobsApi.retryJob).mockResolvedValue(failed)
    renderPage()
    expect(screen.getAllByText('provider unavailable')).toHaveLength(2)
    expect(screen.getByText('Assessment:abc')).toBeInTheDocument()
    expect(screen.getByText('hash-abc')).toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText('Required for interview-turn retries'), { target: { value: 'turn:replacement' } })
    fireEvent.change(screen.getByPlaceholderText('Required for runner retries'), { target: { value: 'confirm:fresh' } })
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(jobsApi.retryJob).toHaveBeenCalled())
    expect(vi.mocked(jobsApi.retryJob).mock.calls[0]?.[0]).toEqual({ jobId: 'job-failed', substitutionRef: 'turn:replacement', confirmationRef: 'confirm:fresh' })
  })

  it('renders mutation errors without hiding persisted job state', async () => {
    vi.mocked(jobsApi.retryJob).mockRejectedValue(new Error('retry rejected'))
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('job action failed')
    expect(screen.getAllByText('provider unavailable')).toHaveLength(2)
  })
})
