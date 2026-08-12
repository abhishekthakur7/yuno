import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'

import { JobConnectionStatus, JobEventsProvider, parseJobEvent, useJobEvents } from './job-events'
import { getJob, type Job } from './api/jobs'

vi.mock('./api/jobs', async importOriginal => {
  const original = await importOriginal<typeof import('./api/jobs')>()
  return { ...original, getJob: vi.fn() }
})

class FakeEventSource {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSED = 2
  static instances: FakeEventSource[] = []
  readonly url: string
  readyState = FakeEventSource.CONNECTING
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  private listeners = new Map<string, EventListener>()

  constructor(url: string | URL) {
    this.url = String(url)
    FakeEventSource.instances.push(this)
  }
  addEventListener(type: string, listener: EventListener) { this.listeners.set(type, listener) }
  removeEventListener(type: string) { this.listeners.delete(type) }
  close() { this.readyState = FakeEventSource.CLOSED }
  open() { this.readyState = FakeEventSource.OPEN; this.onopen?.() }
  fail(permanent = false) {
    this.readyState = permanent ? FakeEventSource.CLOSED : FakeEventSource.CONNECTING
    this.onerror?.()
  }
  job(data: string) { this.listeners.get('job')?.(new MessageEvent('job', { data })) }
  keepalive() {}
}

function Probe() {
  const events = useJobEvents(['job-1', 'job-2'])
  return <><span>{events.status}</span><button onClick={() => void events.refresh()}>Refresh</button></>
}

const event = (id: string, jobId = 'job-1') => JSON.stringify({
  event_id: id,
  job_id: jobId,
  owner_id: 'owner-1',
  goal_id: null,
  state: 'running',
  event_type: 'claimed',
  timestamp: '2026-08-12T00:00:00Z',
  progress: null,
  result_ref: null,
  retryable: false,
  request_id: 'request-1',
  correlation_id: 'correlation-1',
  run_id: null,
})

const job = (jobId: string, status: Job['status'] = 'running'): Job => ({
  job_id: jobId, kind: 'fixture', status, enqueued_at: '2026-08-12T00:00:00Z',
  deduplicated: false, lane: 'background' as const, retryable: false, goal_id: null,
  schema_version: '1', attempt: 1, diagnostic: null, started_at: null,
  terminal_at: status === 'succeeded' ? '2026-08-12T00:01:00Z' : null, substitution_ref: null,
})

function renderStream(children = <Probe />) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><JobEventsProvider>{children}</JobEventsProvider></QueryClientProvider>)
  return { client, source: FakeEventSource.instances[0]! }
}

describe('shared job event stream', () => {
  beforeEach(() => {
    FakeEventSource.instances = []
    vi.stubGlobal('EventSource', FakeEventSource)
    vi.mocked(getJob).mockReset().mockImplementation(async jobId => job(jobId))
  })
  afterEach(() => vi.unstubAllGlobals())

  it('reconciles every watched job after loss and again before reconnect is connected', async () => {
    const { source } = renderStream()
    act(() => source.open())
    expect(screen.getByText('connected')).toBeInTheDocument()
    act(() => source.fail())
    expect(screen.getByText('reconnecting')).toBeInTheDocument()
    await waitFor(() => expect(vi.mocked(getJob)).toHaveBeenCalledTimes(2))
    act(() => source.open())
    await waitFor(() => expect(vi.mocked(getJob)).toHaveBeenCalledTimes(4))
    expect(screen.getByText('connected')).toBeInTheDocument()
  })

  it('does not report connected until every authoritative reconnect read succeeds', async () => {
    vi.mocked(getJob).mockRejectedValue(new Error('jobs endpoint unavailable'))
    const { source } = renderStream()
    act(() => source.open())
    act(() => source.fail())
    await waitFor(() => expect(vi.mocked(getJob)).toHaveBeenCalledTimes(2))
    act(() => source.open())
    await waitFor(() => expect(vi.mocked(getJob)).toHaveBeenCalledTimes(4))
    expect(screen.getByText('unavailable')).toBeInTheDocument()

    vi.mocked(getJob).mockImplementation(async jobId => job(jobId))
    act(() => screen.getByRole('button', { name: 'Refresh' }).click())
    await waitFor(() => expect(screen.getByText('connected')).toBeInTheDocument())
  })

  it('does not let a stale reconnect read overwrite a newer transport loss', async () => {
    let callCount = 0
    let releaseReconnectReads: () => void = () => undefined
    const reconnectReads = new Promise<void>(resolve => { releaseReconnectReads = resolve })
    vi.mocked(getJob).mockImplementation(async jobId => {
      callCount += 1
      if (callCount === 3 || callCount === 4) await reconnectReads
      return job(jobId)
    })
    const { source } = renderStream()
    act(() => source.open())
    act(() => source.fail())
    await waitFor(() => expect(vi.mocked(getJob)).toHaveBeenCalledTimes(2))
    act(() => source.open())
    await waitFor(() => expect(vi.mocked(getJob)).toHaveBeenCalledTimes(4))
    act(() => source.fail())
    expect(screen.getByText('reconnecting')).toBeInTheDocument()
    act(() => releaseReconnectReads())
    await waitFor(() => expect(vi.mocked(getJob)).toHaveBeenCalledTimes(6))
    expect(screen.getByText('reconnecting')).toBeInTheDocument()
  })

  it('deduplicates events, ignores malformed data, and exposes manual GET reconciliation', async () => {
    const { source } = renderStream()
    act(() => { source.job('not-json'); source.job(event('event-1')); source.job(event('event-1')) })
    await waitFor(() => expect(vi.mocked(getJob)).toHaveBeenCalledTimes(1))
    act(() => screen.getByRole('button', { name: 'Refresh' }).click())
    await waitFor(() => expect(vi.mocked(getJob)).toHaveBeenCalledTimes(3))
  })

  it('shows unavailable when the browser closes the stream', () => {
    const { source } = renderStream()
    act(() => source.fail(true))
    expect(screen.getByText('unavailable')).toBeInTheDocument()
  })

  it('recovers a missed replay through GET even when no event arrives', async () => {
    vi.mocked(getJob).mockImplementation(async jobId => job(jobId, 'succeeded'))
    const { client, source } = renderStream()
    act(() => source.fail())
    await waitFor(() => expect(client.getQueryData<{ status: string }>(['jobs', 'job-1'])?.status).toBe('succeeded'))
  })

  it('treats keepalive comments as transport-only', () => {
    const { source } = renderStream()
    act(() => { source.open(); source.keepalive() })
    expect(screen.getByText('connected')).toBeInTheDocument()
    expect(getJob).not.toHaveBeenCalled()
  })

  it('renders a textual connection state and Refresh on an idle Jobs view', () => {
    renderStream(<JobConnectionStatus ids={[]} always />)
    expect(screen.getByRole('status')).toHaveTextContent('Job updates reconnecting')
    expect(screen.getByRole('button', { name: 'Refresh' })).toBeEnabled()
  })
})

describe('job event validation', () => {
  it('accepts the exact event contract and rejects missing fields', () => {
    expect(parseJobEvent(event('event-1'))?.event_id).toBe('event-1')
    expect(parseJobEvent(JSON.stringify({ event_id: 'event-1' }))).toBeNull()
  })
})
