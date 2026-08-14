// IDK-504, producer "client-navigation". Records cold/warm navigation across the 14
// canonical routes, full-roadmap render, and roadmap interaction latency (Customize,
// Jump, Skip, Restore, depth, order) against the real seeded backend started by
// playwright.perf.config.ts. §8.6 invents no pass threshold: every assertion below
// checks that a measurement was actually taken (finite, non-negative, expected sample
// count), never that a duration is acceptable.
import { test, expect, type APIRequestContext, type Browser, type Page } from '@playwright/test'
import { CANONICAL_ROUTES, VIEWPORTS } from '../../scripts/perf/measurement-set.mjs'
import { writeSamples, type Gap, type Sample } from './samples'

const COLD_WARM_REPETITIONS = 5
const ROADMAP_RENDER_REPETITIONS = 5
const INTERACTION_REPETITIONS = 5
/** How long to wait for a rendered state before treating it as absent rather than slow. */
const READINESS_TIMEOUT = 30_000
/** How long one measurement stage may run before it is recorded as a gap instead. */
const STAGE_DEADLINE = 5 * 60 * 1000
const DEPTHS = ['Essential', 'Implementation', 'Production', 'Interview'] as const
// The roadmap row's Customize toggle (aria-expanded, .sb-customize) is a collapsible
// pattern that only exists below core.css's 1000px breakpoint -- at Desktop Chrome's
// default viewport (~1280px) .sb-customize is `display:none` and .sb-roadmap-controls
// is always shown inline instead, so a click on the (invisible, non-actionable) toggle
// never resolves. Measure the interaction stage at the same 768x1024 viewport
// scripts/perf/measurement-set.mjs's viewport-input-latency already exercises this
// control at, where it is genuinely visible and clickable.
const INTERACTION_VIEWPORT = VIEWPORTS.find(viewport => viewport.width === 768)!
// Recorded in every roadmap-interaction method string below, not just in code comments:
// a reader of the report sees these six numbers under a heading with no viewport in
// it and would otherwise assume the default desktop viewport. They don't cover it --
// see INTERACTION_VIEWPORT above for why -- so the report has to say so.
const INTERACTION_VIEWPORT_NOTE =
  'Measured in a 768x1024 browser context (all six roadmap-interaction subjects share this context): below core.css\'s 1000px breakpoint, .sb-customize (the Customize toggle) is visible and .sb-roadmap-controls is reachable only after toggling it open; above that breakpoint .sb-customize is absent and .sb-roadmap-controls is shown inline instead. This measurement does not exercise that wide-viewport inline-controls path.'

function pageIdForRoute(route: string): string {
  return route === '/' ? 'home' : route.replace(/^\/app\//, '')
}

async function waitForRouteReady(page: Page, route: string) {
  await expect(page.locator(`[data-app="yuno-learning"][data-page="${pageIdForRoute(route)}"]`)).toBeVisible()
}

/** Wall-clock time from navigation start to the route's own rendered-root marker becoming visible. */
async function timeNavigation(page: Page, route: string): Promise<number> {
  const start = Date.now()
  await page.goto(route)
  await waitForRouteReady(page, route)
  return Date.now() - start
}

async function measureColdNavigation(browser: Browser): Promise<Sample[]> {
  const samples: Sample[] = []
  for (const route of CANONICAL_ROUTES) {
    const values: number[] = []
    for (let iteration = 0; iteration < COLD_WARM_REPETITIONS; iteration += 1) {
      const context = await browser.newContext()
      // Every fresh context opens the app's own SSE stream, and the server-side stream
      // outlives the context that opened it -- ~15 of those exhaust the connection pool
      // partway through this loop, after which routes stop rendering and there is no
      // measurement left to take. Cold navigation is not an SSE measurement (that is
      // client-jobs-sse's, against the real stream), so these contexts do not open one.
      await context.route('**/api/v1/events', route => route.abort())
      const page = await context.newPage()
      values.push(await timeNavigation(page, route))
      await context.close()
    }
    samples.push({
      measurement: 'cold-navigation',
      subject: route,
      unit: 'ms',
      values,
      method: 'A fresh, uncached browser context per repetition; timed from page.goto to the route-specific [data-app][data-page] marker becoming visible.',
      notes: 'The SSE stream is not opened in these contexts: a server-side stream outlives the browser context that opened it, and the accumulated streams exhaust the connection pool before the sweep finishes. Every other request on the route is real and unmocked.',
    })
  }
  return samples
}

async function measureWarmNavigation(browser: Browser): Promise<Sample[]> {
  const samples: Sample[] = []
  const context = await browser.newContext()
  const page = await context.newPage()
  await timeNavigation(page, '/') // Warms the context's cache; not itself recorded.
  for (const route of CANONICAL_ROUTES) {
    const values: number[] = []
    for (let iteration = 0; iteration < COLD_WARM_REPETITIONS; iteration += 1) values.push(await timeNavigation(page, route))
    samples.push({
      measurement: 'warm-navigation',
      subject: route,
      unit: 'ms',
      values,
      method: 'The same browser context and page, already warmed by an initial "/" load; timed from page.goto to the route-specific [data-app][data-page] marker becoming visible.',
    })
  }
  await context.close()
  return samples
}

/** Navigation start to the roadmap actually rendered (rows visible) and interactive (Customize enabled). */
async function measureRoadmapRender(browser: Browser): Promise<Sample> {
  const values: number[] = []
  for (let iteration = 0; iteration < ROADMAP_RENDER_REPETITIONS; iteration += 1) {
    // Unlike cold navigation (see measureColdNavigation for why that one aborts the
    // stream), this context keeps its real SSE stream: aborting it would make EventSource
    // retry and drive the client's reconcile -> invalidate pass into a refetch storm, a
    // harness artefact rather than product behaviour. Five contexts' worth of streams is
    // well inside what the pool tolerates.
    const context = await browser.newContext()
    const page = await context.newPage()
    const start = Date.now()
    await page.goto('/app/learn-roadmap')
    await waitForRouteReady(page, '/app/learn-roadmap')
    // READINESS_TIMEOUT, not the 5s default: this bound exists to notice a render that
    // never happens, not to cap how long one may take. A slow render is a larger recorded
    // number -- the measurement §8.6 asks for -- so a tight bound would discard exactly
    // the observation worth having.
    await expect(page.locator('.sb-roadmap-row').first()).toBeVisible({ timeout: READINESS_TIMEOUT })
    await expect(page.locator('.sb-customize').first()).toBeEnabled({ timeout: READINESS_TIMEOUT })
    values.push(Date.now() - start)
    await context.close()
  }
  return {
    measurement: 'roadmap-render',
    subject: '/app/learn-roadmap',
    unit: 'ms',
    values,
    method: 'A fresh browser context per repetition; timed from page.goto to the first roadmap row visible and its Customize control enabled, at the seeded dataset size.',
  }
}

async function openRoadmap(page: Page) {
  await page.goto('/app/learn-roadmap')
  await waitForRouteReady(page, '/app/learn-roadmap')
  await expect(page.locator('.sb-roadmap-row').first()).toBeVisible({ timeout: READINESS_TIMEOUT })
}

async function ensureCustomizeOpen(row: ReturnType<Page['locator']>) {
  const button = row.locator('.sb-customize')
  if ((await button.getAttribute('aria-expanded')) !== 'true') await button.click()
  await expect(button).toHaveAttribute('aria-expanded', 'true')
}

/** Click the first row's Customize control repeatedly; times each open/close transition from input to aria-expanded flip. */
async function measureCustomize(page: Page): Promise<Sample> {
  await openRoadmap(page)
  const button = page.locator('.sb-customize').first()
  const values: number[] = []
  for (let iteration = 0; iteration < INTERACTION_REPETITIONS; iteration += 1) {
    const wasExpanded = (await button.getAttribute('aria-expanded')) === 'true'
    const start = Date.now()
    await button.click()
    await expect(button).toHaveAttribute('aria-expanded', wasExpanded ? 'false' : 'true')
    values.push(Date.now() - start)
  }
  return {
    measurement: 'roadmap-interaction',
    subject: 'Customize',
    unit: 'ms',
    values,
    method: `Alternating open/close clicks on the first roadmap row's Customize control, timed from click to its aria-expanded attribute flipping. ${INTERACTION_VIEWPORT_NOTE}`,
  }
}

/** Click "Jump to current"; times from click to the topic-studio route becoming the rendered root. */
async function measureJump(page: Page): Promise<Sample> {
  const values: number[] = []
  for (let iteration = 0; iteration < INTERACTION_REPETITIONS; iteration += 1) {
    await openRoadmap(page)
    const jumpButton = page.getByRole('button', { name: /Jump to current/i })
    await expect(jumpButton).toBeEnabled()
    const start = Date.now()
    await jumpButton.click()
    await waitForRouteReady(page, '/app/topic-studio')
    values.push(Date.now() - start)
  }
  return {
    measurement: 'roadmap-interaction',
    subject: 'Jump',
    unit: 'ms',
    values,
    method: `Click on "Jump to current" from the roadmap, timed to the topic-studio route becoming the rendered root ([data-app][data-page="topic-studio"]). ${INTERACTION_VIEWPORT_NOTE}`,
  }
}

/** Toggle the first row's Skip/Restore control; native confirm() is auto-accepted; times click to label + mutation settling. */
async function measureSkipRestore(page: Page): Promise<Sample[]> {
  await openRoadmap(page)
  const row = page.locator('.sb-roadmap-row').first()
  await ensureCustomizeOpen(row)
  const toggleButton = row.getByRole('button', { name: /^(Skip|Restore)$/ })
  const skipValues: number[] = []
  const restoreValues: number[] = []
  for (let iteration = 0; iteration < INTERACTION_REPETITIONS; iteration += 1) {
    const label = (await toggleButton.textContent())?.trim()
    const nextLabel = label === 'Skip' ? 'Restore' : 'Skip'
    const start = Date.now()
    await toggleButton.click()
    await expect(toggleButton).toHaveText(nextLabel)
    const duration = Date.now() - start
    if (label === 'Skip') skipValues.push(duration)
    else restoreValues.push(duration)
  }
  const method = `Click on the first roadmap row's Skip/Restore control (native confirm() auto-accepted), timed from click to the button label reflecting the new state. ${INTERACTION_VIEWPORT_NOTE}`
  return [
    { measurement: 'roadmap-interaction', subject: 'Skip', unit: 'ms', values: skipValues, method },
    { measurement: 'roadmap-interaction', subject: 'Restore', unit: 'ms', values: restoreValues, method },
  ]
}

/** Cycle the second row's Depth select through every depth; times selectOption to the override note updating. */
async function measureDepth(page: Page): Promise<Sample> {
  await openRoadmap(page)
  const row = page.locator('.sb-roadmap-row').nth(1)
  await ensureCustomizeOpen(row)
  const depthLabel = row.locator('label', { hasText: 'Depth' })
  const select = depthLabel.locator('select')
  const note = depthLabel.locator('small')
  const values: number[] = []
  for (let iteration = 0; iteration < INTERACTION_REPETITIONS; iteration += 1) {
    const depth = DEPTHS[iteration % DEPTHS.length]!
    const start = Date.now()
    await select.selectOption(depth)
    await expect(note).toContainText(`Your override: ${depth}`)
    values.push(Date.now() - start)
  }
  return {
    measurement: 'roadmap-interaction',
    subject: 'depth',
    unit: 'ms',
    values,
    method: `Cycling the second roadmap row's Depth select through every depth value (native confirm() auto-accepted), timed from selectOption to the "Your override" note reflecting the new depth. ${INTERACTION_VIEWPORT_NOTE}`,
  }
}

// Row 9 (0-indexed)/row 10 is the one adjacent pair in the seeded 60-topic roadmap
// without a canonical PREREQUISITE edge between them: dsa (rows 0-9) is its own
// 10-topic prerequisite chain, separate from the java -> spring_boot -> aws ->
// system_design -> rdb chain that fills rows 10-59 (server/scripts/
// seed_performance_dataset.py's _SUBJECT_CHAIN). Every other adjacent pair sits
// inside one of those chains, so the roadmap correctly rejects reordering it
// (validate_order_constraint: "... is an unmodified prerequisite of ... that
// prerequisite cannot be reversed") and a click there never produces a visible
// change to wait on.
const ORDER_BOUNDARY_ROW_INDEX = 9

/** Move row 10 "later" against row 11 repeatedly; times click to that row-slot's title text changing (reorder settled). */
async function measureOrder(page: Page): Promise<Sample> {
  await openRoadmap(page)
  const values: number[] = []
  for (let iteration = 0; iteration < INTERACTION_REPETITIONS; iteration += 1) {
    const row = page.locator('.sb-roadmap-row').nth(ORDER_BOUNDARY_ROW_INDEX)
    await ensureCustomizeOpen(row)
    const title = row.locator('.sb-lesson-link strong')
    const beforeTitle = await title.textContent()
    // Always "later": each move is the previous move's own reverse, which the server
    // treats as replacing that override rather than a conflict, so this oscillates row
    // 10 and row 11 against each other -- a real, always-valid move every iteration.
    const orderButton = row.locator('.sb-order button').last()
    const start = Date.now()
    await orderButton.click()
    // READINESS_TIMEOUT, not the 5s default: same reasoning as measureRoadmapRender --
    // a reorder that settles slowly is a larger recorded number, not a failure to discard.
    await expect(row.locator('.sb-lesson-link strong')).not.toHaveText(beforeTitle ?? '', { timeout: READINESS_TIMEOUT })
    values.push(Date.now() - start)
  }
  return {
    measurement: 'roadmap-interaction',
    subject: 'order',
    unit: 'ms',
    values,
    method: `Repeatedly clicking "move later" on the roadmap's row 10 (native confirm() auto-accepted), oscillating it against row 11 -- the one adjacent pair in the seeded roadmap without a canonical prerequisite edge between them -- timed from click to that row-slot's topic title changing. ${INTERACTION_VIEWPORT_NOTE}`,
  }
}

async function measureRoadmapInteraction(browser: Browser): Promise<{ samples: Sample[]; gaps: Gap[] }> {
  const context = await browser.newContext({ viewport: INTERACTION_VIEWPORT })
  const page = await context.newPage()
  page.on('dialog', dialog => void dialog.accept())
  const samples: Sample[] = []
  const gaps: Gap[] = []
  try {
    samples.push(await measureCustomize(page))
    samples.push(await measureJump(page))
    samples.push(...(await measureSkipRestore(page)))
    samples.push(await measureDepth(page))
    samples.push(await measureOrder(page))
  } finally {
    await context.close()
  }
  return { samples, gaps }
}

function assertSample(sample: Sample, expectedCount: number) {
  expect(sample.values).toHaveLength(expectedCount)
  for (const value of sample.values) {
    expect(Number.isFinite(value), `${sample.measurement}/${sample.subject} produced a non-finite value`).toBe(true)
    expect(value, `${sample.measurement}/${sample.subject} produced a negative value`).toBeGreaterThanOrEqual(0)
  }
}

/**
 * Waits until no job is queued or running before navigation is timed.
 *
 * The jobs/SSE producer deliberately puts real background-lane work in flight, and that work
 * keeps draining after its own file finishes. Navigation measured on top of it is measuring
 * two things at once -- and with the server's connection pool saturated, routes that need a
 * read simply fail to render. Neither outcome is the number §8.6 asks for, so wait for the
 * backend to go quiet and say so in the report if it never does.
 */
async function waitForQuietBackend(request: APIRequestContext, timeoutMs = 180_000) {
  const active = new Set(['queued', 'running', 'cancel-requested'])
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const response = await request.get('/api/v1/jobs')
    if (response.ok()) {
      const body = (await response.json()) as { jobs: Array<{ status: string }> }
      if (!body.jobs.some(job => active.has(job.status))) return true
    }
    await new Promise(resolve => setTimeout(resolve, 1_000))
  }
  return false
}

/**
 * Runs one measurement stage in isolation. A stage that throws records a gap and leaves
 * every other stage's samples intact: §8.6 wants the measurements that were taken plus an
 * explicit reason for the one that was not, and losing four good distributions because a
 * fifth failed would report neither.
 */
async function stage(measurement: string, gaps: Gap[], body: () => Promise<void>) {
  // A stage that hangs must become a recorded gap quickly, not sit on the whole run's
  // clock until Playwright kills the test -- a stalled stage that takes the file's other
  // measurements down with it is the failure mode this deadline exists to prevent.
  let timer: ReturnType<typeof setTimeout> | undefined
  const deadline = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new Error(`stage exceeded ${STAGE_DEADLINE / 1000}s`)), STAGE_DEADLINE)
  })
  try {
    await Promise.race([body(), deadline])
  } catch (error) {
    // Playwright colours its assertion messages, and those escape codes would end up in a
    // committed report; strip them so the recorded reason is readable prose.
    const raw = error instanceof Error ? error.message : String(error)
    const firstLine = raw.split('\n')[0] ?? raw
    const reason = firstLine.replace(/\u001b\[[0-9;]*m/g, '').trim()
    gaps.push({ measurement, reason: `measurement stage did not complete: ${reason}` })
  } finally {
    clearTimeout(timer)
  }
}

test('IDK-504: client-navigation records cold/warm navigation and roadmap render/interaction against the real seeded backend', async ({ browser, request }) => {
  test.setTimeout(25 * 60 * 1000)
  const samples: Sample[] = []
  const gaps: Gap[] = []

  const quiet = await waitForQuietBackend(request)
  if (!quiet) {
    gaps.push({
      measurement: 'cold-navigation',
      reason: 'the backend still had queued or running jobs when navigation measurement began, so these values include unrelated background-lane work.',
    })
  }

  await stage('cold-navigation', gaps, async () => {
    const coldSamples = await measureColdNavigation(browser)
    for (const sample of coldSamples) assertSample(sample, COLD_WARM_REPETITIONS)
    samples.push(...coldSamples)
  })

  await stage('warm-navigation', gaps, async () => {
    const warmSamples = await measureWarmNavigation(browser)
    for (const sample of warmSamples) assertSample(sample, COLD_WARM_REPETITIONS)
    samples.push(...warmSamples)
  })

  await stage('roadmap-render', gaps, async () => {
    const roadmapRenderSample = await measureRoadmapRender(browser)
    assertSample(roadmapRenderSample, ROADMAP_RENDER_REPETITIONS)
    samples.push(roadmapRenderSample)
  })

  await stage('roadmap-interaction', gaps, async () => {
    const { samples: interactionSamples, gaps: interactionGaps } = await measureRoadmapInteraction(browser)
    for (const sample of interactionSamples) {
      // Skip/Restore split one repetition budget across two subjects, so each subject's
      // count depends on which state the toggle started in rather than a fixed total.
      expect(sample.values.length, `${sample.measurement}/${sample.subject} produced no values`).toBeGreaterThan(0)
      for (const value of sample.values) {
        expect(Number.isFinite(value), `${sample.measurement}/${sample.subject} produced a non-finite value`).toBe(true)
        expect(value, `${sample.measurement}/${sample.subject} produced a negative value`).toBeGreaterThanOrEqual(0)
      }
    }
    samples.push(...interactionSamples)
    gaps.push(...interactionGaps)
  })

  const path = writeSamples('client-navigation', samples, gaps)
  console.log(`client-navigation: wrote ${samples.length} sample series and ${gaps.length} gaps to ${path}`)
  expect(samples.length + gaps.length, 'the producer recorded neither a sample nor a gap').toBeGreaterThan(0)
})
