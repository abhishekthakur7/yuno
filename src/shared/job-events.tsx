import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { getJob, type JobEvent } from './api/jobs'
import './job-events.css'

export type JobConnectionState = 'connected' | 'reconnecting' | 'unavailable'

interface JobEventsContextValue {
  status: JobConnectionState
  register: (token: symbol, ids: readonly string[]) => void
  unregister: (token: symbol) => void
  refresh: () => Promise<void>
}

const JobEventsContext = createContext<JobEventsContextValue>({
  status: 'unavailable',
  register: () => undefined,
  unregister: () => undefined,
  refresh: async () => undefined,
})
const MAX_SEEN_EVENTS = 2_048

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string'
}

export function parseJobEvent(raw: string): JobEvent | null {
  try {
    const value: unknown = JSON.parse(raw)
    if (!value || typeof value !== 'object' || Array.isArray(value)) return null
    const event = value as Record<string, unknown>
    if (
      typeof event.event_id !== 'string' || typeof event.job_id !== 'string' ||
      typeof event.owner_id !== 'string' || typeof event.event_type !== 'string' ||
      typeof event.timestamp !== 'string' || typeof event.retryable !== 'boolean' ||
      !['queued', 'running', 'succeeded', 'failed', 'cancel-requested', 'cancelled'].includes(String(event.state)) ||
      !isNullableString(event.goal_id) || !isNullableString(event.progress) ||
      !isNullableString(event.result_ref) || typeof event.request_id !== 'string' ||
      typeof event.correlation_id !== 'string' || !isNullableString(event.run_id)
    ) return null
    return {
      event_id: event.event_id,
      job_id: event.job_id,
      owner_id: event.owner_id,
      goal_id: event.goal_id,
      state: event.state as JobEvent['state'],
      event_type: event.event_type,
      timestamp: event.timestamp,
      progress: event.progress,
      result_ref: event.result_ref,
      retryable: event.retryable,
      request_id: event.request_id,
      correlation_id: event.correlation_id,
      run_id: event.run_id,
    }
  } catch {
    return null
  }
}

export function JobEventsProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState<JobConnectionState>('reconnecting')
  const registrations = useRef(new Map<symbol, readonly string[]>())
  const seen = useRef(new Set<string>())
  const seenOrder = useRef<string[]>([])
  const lostConnection = useRef(false)
  const sourceOpen = useRef(false)
  const connectionVersion = useRef(0)
  const reconciliationQueue = useRef(new Map<string, Promise<void>>())

  const watchedIds = useCallback(() => new Set([...registrations.current.values()].flat()), [])
  const reconcile = useCallback(async (ids: Iterable<string>) => {
    const reads = await Promise.allSettled([...new Set(ids)].map(id => {
      const prior = reconciliationQueue.current.get(id) ?? Promise.resolve()
      const next = prior.catch(() => undefined).then(async () => {
        const job = await getJob(id)
        queryClient.setQueryData(['jobs', id], job)
      }).finally(() => {
        if (reconciliationQueue.current.get(id) === next) reconciliationQueue.current.delete(id)
      })
      reconciliationQueue.current.set(id, next)
      return next
    }))
    await Promise.allSettled([
      queryClient.invalidateQueries({ queryKey: ['jobs'] }),
      queryClient.invalidateQueries({ queryKey: ['interview-runs'] }),
      queryClient.invalidateQueries({ queryKey: ['imports'] }),
      queryClient.invalidateQueries({ queryKey: ['goals'] }),
    ])
    return reads.every(result => result.status === 'fulfilled')
  }, [queryClient])

  useEffect(() => {
    if (typeof EventSource === 'undefined') {
      setStatus('unavailable')
      return
    }
    const source = new EventSource('/api/v1/events')
    source.onopen = () => {
      const openedVersion = ++connectionVersion.current
      sourceOpen.current = true
      if (!lostConnection.current) {
        setStatus('connected')
        return
      }
      void reconcile(watchedIds()).then(reconciled => {
        if (
          connectionVersion.current !== openedVersion ||
          !sourceOpen.current
        ) return
        setStatus(reconciled ? 'connected' : 'unavailable')
      })
    }
    source.onerror = () => {
      connectionVersion.current += 1
      sourceOpen.current = false
      lostConnection.current = true
      setStatus(source.readyState === EventSource.CLOSED ? 'unavailable' : 'reconnecting')
      void reconcile(watchedIds())
    }
    const onJob = (message: MessageEvent<string>) => {
      const event = parseJobEvent(message.data)
      if (!event || seen.current.has(event.event_id)) return
      seen.current.add(event.event_id)
      seenOrder.current.push(event.event_id)
      if (seenOrder.current.length > MAX_SEEN_EVENTS) {
        const oldest = seenOrder.current.shift()
        if (oldest) seen.current.delete(oldest)
      }
      void reconcile([event.job_id])
    }
    source.addEventListener('job', onJob as EventListener)
    return () => {
      connectionVersion.current += 1
      sourceOpen.current = false
      source.removeEventListener('job', onJob as EventListener)
      source.close()
    }
  }, [reconcile, watchedIds])

  const value = useMemo<JobEventsContextValue>(() => ({
    status,
    register: (token, ids) => registrations.current.set(token, ids),
    unregister: token => { registrations.current.delete(token) },
    refresh: async () => {
      const reconciled = await reconcile(watchedIds())
      if (!reconciled) setStatus('unavailable')
      else if (sourceOpen.current) setStatus('connected')
    },
  }), [reconcile, status, watchedIds])
  return <JobEventsContext.Provider value={value}>{children}</JobEventsContext.Provider>
}

export function useJobEvents(ids: readonly (string | null | undefined)[]) {
  const context = useContext(JobEventsContext)
  const token = useRef(Symbol('job-events-watcher'))
  const stableIds = [...new Set(ids.filter((id): id is string => Boolean(id)))].sort()
  const key = stableIds.join('\u0000')
  useEffect(() => {
    context.register(token.current, stableIds)
    return () => context.unregister(token.current)
  }, [context, key]) // eslint-disable-line react-hooks/exhaustive-deps
  return { status: context.status, refresh: context.refresh }
}

export function JobConnectionStatus({ ids, always = false }: { ids: readonly (string | null | undefined)[]; always?: boolean }) {
  const events = useJobEvents(ids)
  if (!always && ids.every(id => !id)) return null
  return <div className="job-connection" data-job-connection={events.status} role="status">
    <div><strong>Job updates {events.status}</strong><p>Job reads remain authoritative after every connection loss.</p></div>
    <button type="button" onClick={() => void events.refresh()}>Refresh</button>
  </div>
}
