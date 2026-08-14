import { test, expect, type Page } from '@playwright/test'
import { performance } from 'node:perf_hooks'
import { CANONICAL_ROUTES, VIEWPORTS } from '../../scripts/perf/measurement-set.mjs'
import { writeSamples, type Sample, type Gap } from './samples'

// IDK-504: viewport-overflow and viewport-input-latency, producer id
// "client-viewport". Measured against the REAL seeded backend started by
// playwright.perf.config.ts's webServer -- never against installApiMocks, so
// this file deliberately does not import tests/e2e/harness.ts (importing it
// would attach its auto `apiMocks` fixture to every test in this module).
//
// Scaffolding reused from tests/e2e/harness.ts's `expectNoHorizontalOverflow`
// (document/body scrollWidth vs documentElement clientWidth), extended here to
// record the overflow amount -- and, separately, real-event-to-visible-DOM
// timing -- rather than asserting either away. Spec §8.6 invents no pass/fail
// number: every assertion below only confirms a measurement was taken.

const APP_ROOT = '[data-app="yuno-learning"]'
const REPETITIONS = 6

const samples: Sample[] = []
const gaps: Gap[] = []

test.describe.configure({ mode: 'serial' })

async function settle(page: Page) {
  // Not a fixed sleep: waits for the next real animation frame, i.e. "one
  // more paint has happened", which is the smallest legitimate way to let
  // layout/fonts settle before reading geometry.
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => resolve(undefined))))
}

async function openRoute(page: Page, route: string) {
  await page.goto(route)
  await expect(page.locator(APP_ROOT)).toBeVisible()
  await settle(page)
}

async function horizontalOverflowPx(page: Page) {
  const { documentOverflow, bodyOverflow } = await page.evaluate(() => {
    const viewport = document.documentElement.clientWidth
    return {
      documentOverflow: document.documentElement.scrollWidth - viewport,
      bodyOverflow: document.body.scrollWidth - viewport,
    }
  })
  // "record the larger" of the two; overflow amounts below zero are not
  // overflow (the document is simply narrower than the viewport), so each is
  // floored at zero before comparing.
  return Math.max(0, documentOverflow, bodyOverflow)
}

test('viewport-overflow: 14 canonical routes at each required viewport', async ({ page }) => {
  test.setTimeout(10 * 60_000)
  for (const viewport of VIEWPORTS) {
    await page.setViewportSize(viewport)
    for (const route of CANONICAL_ROUTES) {
      const subject = `${route} @ ${viewport.width}x${viewport.height}`
      try {
        await openRoute(page, route)
        const overflow = await horizontalOverflowPx(page)
        samples.push({
          measurement: 'viewport-overflow',
          subject,
          unit: 'px',
          values: [overflow],
          method: 'max(0, document.documentElement.scrollWidth, document.body.scrollWidth) - document.documentElement.clientWidth, one frame after navigation settles',
        })
      } catch (error) {
        gaps.push({
          measurement: 'viewport-overflow',
          subject,
          reason: `route did not load against the seeded backend: ${error instanceof Error ? error.message : String(error)}`,
        })
      }
    }
  }
})

// ---------------------------------------------------------------------------
// viewport-input-latency: real input event -> resulting visible DOM change,
// on one representative text input, one representative select, and one
// representative button that changes rendered state, at each viewport.
// Every act below is a genuine trusted browser event (Playwright keyboard
// press / select / click), timed with a high-resolution Node clock around the
// dispatch and a rAF-polled `waitForFunction` (never a fixed sleep) around the
// observed DOM change.
// ---------------------------------------------------------------------------

async function measureLatency(act: () => Promise<unknown>, untilChanged: () => Promise<unknown>) {
  const start = performance.now()
  await act()
  await untilChanged()
  return performance.now() - start
}

async function measureTextInputControl(page: Page, viewport: { width: number; height: number }) {
  const route = '/app/search'
  const subject = `${route} text input @ ${viewport.width}x${viewport.height}`
  await page.setViewportSize(viewport)
  await openRoute(page, route)
  const input = page.locator('#so-search-input')
  await expect(input).toBeVisible()

  const values: number[] = []
  for (let iteration = 0; iteration < REPETITIONS; iteration += 1) {
    const typed = `perf-${iteration}`
    await input.fill('')
    const elapsed = await measureLatency(
      () => input.pressSequentially(typed, { delay: 0 }),
      () => page.waitForFunction(text => (document.querySelector('#so-search-input') as HTMLInputElement | null)?.value === text, typed, { polling: 'raf' }),
    )
    values.push(elapsed)
  }
  samples.push({
    measurement: 'viewport-input-latency',
    subject,
    unit: 'ms',
    values,
    method: 'keyboard keypress events (Locator.pressSequentially) to the input reflecting the typed value, rAF-polled',
  })
}

async function measureSelectControl(page: Page, viewport: { width: number; height: number }) {
  const route = '/app/imports'
  const subject = `${route} select @ ${viewport.width}x${viewport.height}`
  await page.setViewportSize(viewport)
  await openRoute(page, route)
  const select = page.getByRole('combobox', { name: 'Format' })
  await expect(select).toBeVisible()

  const values: number[] = []
  let current = (await select.inputValue()) || 'markdown'
  for (let iteration = 0; iteration < REPETITIONS; iteration += 1) {
    const target = current === 'markdown' ? 'plain_text' : 'markdown'
    const handle = await select.elementHandle()
    const elapsed = await measureLatency(
      () => select.selectOption(target),
      () => page.waitForFunction(([element, value]) => (element as HTMLSelectElement).value === value, [handle, target] as const, { polling: 'raf' }),
    )
    values.push(elapsed)
    current = target
  }
  samples.push({
    measurement: 'viewport-input-latency',
    subject,
    unit: 'ms',
    values,
    method: 'Locator.selectOption (real change event) to the select reflecting the chosen value, rAF-polled',
  })
}

async function measureButtonControl(page: Page, viewport: { width: number; height: number }) {
  const route = '/app/learn-roadmap'
  const subject = `${route} button @ ${viewport.width}x${viewport.height}`
  await page.setViewportSize(viewport)
  await openRoute(page, route)
  const toggle = page.locator('.sb-customize').first()
  await expect(toggle).toBeVisible()
  await toggle.scrollIntoViewIfNeeded()

  const values: number[] = []
  for (let iteration = 0; iteration < REPETITIONS; iteration += 1) {
    const before = await toggle.getAttribute('aria-expanded')
    const elapsed = await measureLatency(
      () => toggle.click(),
      () => page.waitForFunction(([selector, previous]) => document.querySelector(selector as string)?.getAttribute('aria-expanded') !== previous, [
        '.sb-customize',
        before,
      ] as const, { polling: 'raf' }),
    )
    values.push(elapsed)
  }
  samples.push({
    measurement: 'viewport-input-latency',
    subject,
    unit: 'ms',
    values,
    method: 'Locator.click (real click event) on the roadmap row\'s "Customize" toggle to its aria-expanded state flipping, rAF-polled',
  })
}

test('viewport-input-latency: text input, select and button controls at each required viewport', async ({ page }) => {
  test.setTimeout(10 * 60_000)
  for (const viewport of VIEWPORTS) {
    const controls: Array<{ label: string; run: (page: Page, viewport: { width: number; height: number }) => Promise<void> }> = [
      { label: 'text input', run: measureTextInputControl },
      { label: 'select', run: measureSelectControl },
      { label: 'button', run: measureButtonControl },
    ]
    for (const control of controls) {
      try {
        await control.run(page, viewport)
      } catch (error) {
        gaps.push({
          measurement: 'viewport-input-latency',
          subject: `${control.label} @ ${viewport.width}x${viewport.height}`,
          reason: `control was not reachable against the seeded dataset: ${error instanceof Error ? error.message : String(error)}`,
        })
      }
    }
  }
})

test.afterAll(() => {
  writeSamples('client-viewport', samples, gaps)
})
