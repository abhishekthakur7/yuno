// IDK-504, producer "client-jobs-sse". Records:
//   - sse-to-visible-state: server-emitted job event -> corresponding UI state change on
//     screen, correlated by job id + state.
//   - interactive-job-start-under-background-lane: latency of starting a real interactive
//     job while real background-lane work is confirmed running. Appendix H D8's
//     non-blocking claim is OBSERVED here, never certified.
//
// Both measurements run against the REAL seeded backend started by
// playwright.perf.config.ts's webServer -- an SSE stream and a job dispatcher are
// meaningless against a mock. Spec §8.6 invents no pass/fail number: every assertion
// below checks that a measurement was actually taken, never that a duration is
// acceptable, and unreachable states are recorded as gaps (reason, no fabricated value)
// rather than guessed at.
import { test, expect, type APIRequestContext, type APIResponse, type Page } from '@playwright/test'
import { writeSamples, type Gap, type Sample } from './samples'

test.describe.configure({ mode: 'serial' })

const samples: Sample[] = []
const gaps: Gap[] = []

const SSE_REPETITIONS = 5
const API = '/api/v1'

function idempotencyKey(label: string) {
  return `idk-504-${label}-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

async function json<T>(response: APIResponse): Promise<T> {
  return (await response.json()) as T
}

// --- sse-to-visible-state ------------------------------------------------------------
//
// Correlation method: an init script wraps `window.EventSource` before the app loads so
// every 'job' SSE message the app's own EventSource receives is independently logged
// (job_id, state, the event's server-emitted `timestamp` field) into
// `window.__perfJobEvents`, and a MutationObserver independently logs the first moment
// each job id's rendered status text (the /app/jobs list's `<article><small>{job_id}</small>
// ...<p>{status}</p></article>` row) reaches each observed status, into
// `window.__perfVisibleLog` -- both keyed by the same job id, both using the SAME
// in-page `Date.now()` clock, so there is no cross-process clock to skew. The server's
// `timestamp` field (from `now_text`, microsecond resolution) is compared directly
// against that in-page `Date.now()`: server and browser share one OS wall clock on
// localhost, so this is sound here specifically because client and server run on the
// same machine -- it would not be sound across machines, and no cross-machine clock
// arithmetic is attempted.
const INSTRUMENT_SCRIPT = `(() => {
  if (window.__perfInstrumented) return;
  window.__perfInstrumented = true;
  window.__perfJobEvents = [];
  window.__perfVisibleLog = [];
  const NativeEventSource = window.EventSource;
  window.EventSource = new Proxy(NativeEventSource, {
    construct(target, args) {
      const source = new target(...args);
      if (args[0] === '/api/v1/events') {
        source.addEventListener('job', (event) => {
          try {
            const data = JSON.parse(event.data);
            window.__perfJobEvents.push({
              jobId: data.job_id,
              state: data.state,
              timestamp: data.timestamp,
              receivedAt: Date.now(),
            });
          } catch (_error) { /* malformed frame: not this harness's concern */ }
        });
      }
      return source;
    },
  });
  const record = () => {
    document.querySelectorAll('article').forEach((article) => {
      const small = article.querySelector('small');
      const status = article.querySelector('p');
      if (!small || !status) return;
      const jobId = (small.textContent || '').trim();
      const state = (status.textContent || '').replace('\\u25cf', '').trim();
      if (!jobId || !state) return;
      const key = jobId + '|' + state;
      if (!window.__perfVisibleLog.some((entry) => entry.key === key)) {
        window.__perfVisibleLog.push({ key, jobId, state, at: Date.now() });
      }
    });
  };
  // addInitScript runs at document-start, where document.documentElement can still be
  // null -- observing it directly there throws, which would silently leave __perfVisibleLog
  // empty for the whole run while the EventSource proxy above kept working, making every
  // correlation fail as an unexplained timeout. Install once the root element exists, and
  // take one reading at that point so a row already present before the first mutation is
  // still seen.
  const install = () => {
    record();
    new MutationObserver(record).observe(document.documentElement, {
      childList: true,
      subtree: true,
      characterData: true,
    });
  };
  if (document.documentElement) install();
  else document.addEventListener('readystatechange', function once() {
    if (!document.documentElement) return;
    document.removeEventListener('readystatechange', once);
    install();
  });
})()`

async function openInstrumentedJobsPage(page: Page) {
  await page.addInitScript(INSTRUMENT_SCRIPT)
  await page.goto('/app/jobs')
  await expect(page.locator('[data-app="yuno-learning"][data-page="jobs"]')).toBeVisible()
}

async function enqueueRebuildJob(request: APIRequestContext): Promise<string> {
  const response = await request.post(`${API}/search-index/rebuild`, {
    headers: { 'Idempotency-Key': idempotencyKey('rebuild') },
  })
  expect(response.status(), 'search-index/rebuild must be accepted to drive sse-to-visible-state').toBe(202)
  const body = await json<{ job_id: string }>(response)
  return body.job_id
}

type VisibleEntry = { jobId: string; state: string; at: number }
type JobEventEntry = { jobId: string; state: string; timestamp: string; receivedAt: number }

async function waitForVisibleTerminal(page: Page, jobId: string, timeoutMs: number) {
  await page.waitForFunction(
    ([id, states]) => (window as unknown as { __perfVisibleLog: VisibleEntry[] }).__perfVisibleLog
      .some((entry) => entry.jobId === id && (states as string[]).includes(entry.state)),
    [jobId, ['succeeded', 'failed']],
    { timeout: timeoutMs },
  )
}

async function measureSseToVisibleState(page: Page, request: APIRequestContext) {
  for (let iteration = 0; iteration < SSE_REPETITIONS; iteration += 1) {
    const subject = `search-index rebuild #${iteration}`
    try {
      const jobId = await enqueueRebuildJob(request)
      await waitForVisibleTerminal(page, jobId, 20_000)
      const { visible, event } = await page.evaluate(
        (id) => {
          const visibleLog = (window as unknown as { __perfVisibleLog: VisibleEntry[] }).__perfVisibleLog
          const eventLog = (window as unknown as { __perfJobEvents: JobEventEntry[] }).__perfJobEvents
          const visibleEntry = visibleLog.find((entry) => entry.jobId === id && entry.state === 'succeeded')
            ?? visibleLog.find((entry) => entry.jobId === id && entry.state === 'failed')
          const eventEntry = eventLog.find((entry) => entry.jobId === id && entry.state === (visibleEntry?.state ?? ''))
          return { visible: visibleEntry ?? null, event: eventEntry ?? null }
        },
        jobId,
      )
      if (!visible) {
        gaps.push({ measurement: 'sse-to-visible-state', subject, reason: 'the job reached a terminal DOM state but the MutationObserver log has no matching entry; the state change could not be correlated.' })
        continue
      }
      if (!event) {
        gaps.push({ measurement: 'sse-to-visible-state', subject, reason: `the /app/jobs list showed job ${jobId} as ${visible.state}, but no matching SSE 'job' event (id+state) was ever received by the instrumented EventSource -- the visible change cannot be attributed to a specific server-emitted event.` })
        continue
      }
      const serverEmittedAt = Date.parse(event.timestamp)
      if (!Number.isFinite(serverEmittedAt)) {
        gaps.push({ measurement: 'sse-to-visible-state', subject, reason: `the event's server timestamp ('${event.timestamp}') did not parse as a date.` })
        continue
      }
      const delta = visible.at - serverEmittedAt
      if (delta < 0) {
        gaps.push({ measurement: 'sse-to-visible-state', subject, reason: `computed a negative latency (${delta}ms): server-emitted timestamp and in-page Date.now() disagree on ordering, which this harness only trusts on a single machine with a shared clock -- recorded as a gap rather than a fabricated value.` })
        continue
      }
      samples.push({
        measurement: 'sse-to-visible-state',
        subject,
        unit: 'ms',
        values: [delta],
        method: `Correlated by job id ${jobId} and terminal state '${visible.state}': server-emitted event.timestamp (row.created_at, same-machine wall clock) to the in-page Date.now() at which the /app/jobs list row's rendered status text first reached '${visible.state}' (MutationObserver-detected).`,
      })
    } catch (error) {
      gaps.push({ measurement: 'sse-to-visible-state', subject, reason: `measurement threw: ${error instanceof Error ? error.message : String(error)}` })
    }
  }
}

// --- interactive-job-start-under-background-lane --------------------------------------
//
// "Genuinely running" is confirmed by polling GET /jobs/{id} (not the 1s-cadence SSE
// stream) until the dispatcher's own row reports status 'running', before the
// interactive POST is ever sent. If the background job reaches a terminal state before
// 'running' is ever observed, that attempt is not usable as a background-lane-running
// precondition and is recorded as a gap rather than timed anyway.
const BACKGROUND_LINE_COUNTS = [800, 1600, 3200, 4800, 6400]
const INTERACTIVE_REPETITIONS = BACKGROUND_LINE_COUNTS.length

function syntheticImportText(lines: number, salt: string): string {
  const rows: string[] = []
  for (let index = 0; index < lines; index += 1) {
    rows.push(`Representative perf import statement ${salt} ${index}: a distinct non-blank line so the parser records it as its own statement.`)
  }
  return rows.join('\n')
}

async function firstGoalAndTopic(request: APIRequestContext): Promise<{ goalId: string; topicId: string } | null> {
  const goalsResponse = await request.get(`${API}/goals`)
  if (!goalsResponse.ok()) return null
  const goals = await json<Array<{ id: string }>>(goalsResponse)
  const goal = goals[0]
  if (!goal) return null
  const roadmapResponse = await request.get(`${API}/goals/${goal.id}/roadmap`)
  if (!roadmapResponse.ok()) return null
  const roadmap = await json<{ topics: Array<{ stable_id: string }> }>(roadmapResponse)
  const topic = roadmap.topics[0]
  if (!topic) return null
  return { goalId: goal.id, topicId: topic.stable_id }
}

/** Configures a real, working interactive provider path (disclosure + selection), or returns null with the reason it could not be reached. */
async function prepareInteractiveProvider(request: APIRequestContext): Promise<{ provider: string } | { reason: string }> {
  const capabilitiesResponse = await request.get(`${API}/provider-capabilities`, { params: { refresh: 'true' } })
  if (!capabilitiesResponse.ok()) return { reason: `GET /provider-capabilities returned ${capabilitiesResponse.status()}` }
  const capabilities = await json<Array<{ provider: string; state: string; reason: string | null }>>(capabilitiesResponse)
  const configured = capabilities.find((entry) => entry.state === 'configured')
  if (!configured) {
    return {
      reason: `no provider adapter reports state 'configured' in this environment (${capabilities.map((entry) => `${entry.provider}: ${entry.state}${entry.reason ? ` (${entry.reason})` : ''}`).join('; ') || 'no providers listed'}). Interactive-lane provider-backed jobs cannot be started without a configured provider.`,
    }
  }

  const disclosuresResponse = await request.get(`${API}/disclosures`)
  if (!disclosuresResponse.ok()) return { reason: `GET /disclosures returned ${disclosuresResponse.status()}` }
  const disclosures = await json<Array<{ category: string; disclosure_version: string; accepted_at: string | null }>>(disclosuresResponse)
  const generation = disclosures.find((entry) => entry.category === 'provider-generation')
  if (!generation) return { reason: "no 'provider-generation' disclosure is defined by this server." }
  if (!generation.accepted_at) {
    const acceptResponse = await request.post(`${API}/disclosures/provider-generation/accept`, {
      data: { disclosure_version: generation.disclosure_version },
    })
    if (!acceptResponse.ok()) return { reason: `POST /disclosures/provider-generation/accept returned ${acceptResponse.status()}` }
  }

  const settingsResponse = await request.get(`${API}/settings`)
  if (!settingsResponse.ok()) return { reason: `GET /settings returned ${settingsResponse.status()}` }
  const settings = await json<{ row_version: number; provider_selection: string | null }>(settingsResponse)
  if (settings.provider_selection !== configured.provider) {
    const patchResponse = await request.patch(`${API}/settings`, {
      headers: { 'If-Match': String(settings.row_version) },
      data: { provider_selection: configured.provider },
    })
    if (!patchResponse.ok()) return { reason: `PATCH /settings (provider_selection=${configured.provider}) returned ${patchResponse.status()}: ${await patchResponse.text()}` }
  }
  return { provider: configured.provider }
}

async function pollUntilRunning(request: APIRequestContext, jobId: string, timeoutMs: number): Promise<'running' | 'terminal' | 'timeout'> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const response = await request.get(`${API}/jobs/${jobId}`)
    if (response.ok()) {
      const body = await json<{ status: string }>(response)
      if (body.status === 'running') return 'running'
      if (['succeeded', 'failed', 'cancelled'].includes(body.status)) return 'terminal'
    }
    // A readiness poll, not a fixed-duration measurement: yields briefly between checks
    // rather than asserting anything about elapsed time.
    await new Promise((resolve) => setTimeout(resolve, 5))
  }
  return 'timeout'
}

async function enqueueBackgroundImportParse(request: APIRequestContext, goalId: string, lines: number, salt: string): Promise<string | null> {
  const createResponse = await request.post(`${API}/imports`, {
    headers: { 'Idempotency-Key': idempotencyKey(`import-create-${salt}`) },
    data: { goal_id: goalId, import_type: 'plain_text', original_content: syntheticImportText(lines, salt) },
  })
  if (createResponse.status() !== 201) return null
  const record = await json<{ id: string }>(createResponse)
  const parseResponse = await request.post(`${API}/imports/${record.id}/parse`, {
    headers: { 'Idempotency-Key': idempotencyKey(`import-parse-${salt}`) },
  })
  if (parseResponse.status() !== 202) return null
  const ref = await json<{ job_id: string }>(parseResponse)
  return ref.job_id
}

async function measureInteractiveJobStartUnderBackgroundLane(request: APIRequestContext) {
  const measurement = 'interactive-job-start-under-background-lane'
  const provider = await prepareInteractiveProvider(request)
  if ('reason' in provider) {
    gaps.push({ measurement, reason: provider.reason })
    return
  }

  const target = await firstGoalAndTopic(request)
  if (!target) {
    gaps.push({ measurement, reason: 'no seeded goal with a roadmap topic was reachable via GET /goals + GET /goals/{id}/roadmap.' })
    return
  }

  const values: number[] = []
  for (let iteration = 0; iteration < INTERACTIVE_REPETITIONS; iteration += 1) {
    const salt = `d8-${iteration}`
    const backgroundJobId = await enqueueBackgroundImportParse(request, target.goalId, BACKGROUND_LINE_COUNTS[iteration]!, salt)
    if (!backgroundJobId) {
      gaps.push({ measurement, subject: `attempt ${iteration}`, reason: 'the background-lane import/parse job could not be enqueued for this attempt.' })
      continue
    }
    const readiness = await pollUntilRunning(request, backgroundJobId, 5_000)
    if (readiness !== 'running') {
      gaps.push({
        measurement,
        subject: `attempt ${iteration} (${BACKGROUND_LINE_COUNTS[iteration]} lines)`,
        reason: readiness === 'terminal'
          ? 'the background-lane job reached a terminal state before its running status could be observed by polling; it cannot be treated as "genuinely running" for this attempt.'
          : 'polling GET /jobs/{id} never observed the background-lane job as running or terminal within the timeout.',
      })
      continue
    }

    const before = Date.now()
    const response = await request.post(`${API}/goals/${target.goalId}/topics/${target.topicId}/conversation`, {
      headers: { 'Idempotency-Key': idempotencyKey(`tutor-${salt}`) },
      data: { message: `IDK-504 interactive-start probe ${salt}.` },
    })
    const after = Date.now()
    if (response.status() !== 202) {
      gaps.push({ measurement, subject: `attempt ${iteration}`, reason: `the interactive job start returned ${response.status()} instead of 202: ${await response.text()}` })
      continue
    }
    values.push(after - before)
  }

  if (values.length > 0) {
    samples.push({
      measurement,
      subject: `${target.goalId}/${target.topicId}`,
      unit: 'ms',
      values,
      method: `Real background-lane import-parse jobs (${BACKGROUND_LINE_COUNTS.join(', ')} lines) enqueued and confirmed 'running' via polling GET /jobs/{id} before each timed POST to start a real interactive-lane tutor-turn job; timed from request send to the 202 response. This measurement OBSERVES that the interactive start completed while background-lane work was running; it certifies nothing about D8 non-blocking behaviour (Appendix H D8 is observed here, never asserted).`,
      notes: 'Each attempt used a differently sized synthetic background import so a longer-running attempt was available if a shorter one finished before "running" could be confirmed; attempts that never confirmed "running" are recorded as gaps, not timed.',
    })
  }
}

test('IDK-504: client-jobs-sse records sse-to-visible-state against the real seeded backend', async ({ page, request }) => {
  test.setTimeout(5 * 60_000)
  await openInstrumentedJobsPage(page)
  await measureSseToVisibleState(page, request)
})

test('IDK-504: client-jobs-sse records interactive-job-start-under-background-lane against the real seeded backend', async ({ request }) => {
  test.setTimeout(5 * 60_000)
  await measureInteractiveJobStartUnderBackgroundLane(request)
})

test.afterAll(() => {
  const path = writeSamples('client-jobs-sse', samples, gaps)
  console.log(`client-jobs-sse: wrote ${samples.length} sample series and ${gaps.length} gaps to ${path}`)
})
