import AxeBuilder from '@axe-core/playwright'
import type { Page } from '@playwright/test'
import { expect, longestMotionMs, open, test, viewports } from './harness'

// IDK-502 extends the baseline coverage in selected-app.spec.ts (14 routes x 4 viewports,
// one WCAG sweep, one keyboard walkthrough, one focus-restoration test, one reduced-motion
// test) to the async states that exist only in the production build, never in the prototype:
// job/SSE connection status, Practice's evaluating/feedback-ready transition, the Settings
// delete-confirmation alertdialog, and the canonical-updates merge-conflict controls. Every
// state below is forced deterministically (never by hoping a race lands right) so the axe
// scan, keyboard check, and (where relevant) reduced-motion check run against a state that is
// actually, verifiably, on screen — not a guess about timing.

const practiceDraft = 'The commit-before-ack window needs an atomic idempotency key with an explicit retention policy.'

// Scans the current DOM at all four required viewports with the same WCAG 2 A/AA tags the
// baseline suite uses. No .exclude()/.disableRules() — a violation here is a real defect to
// fix, not a rule to silence.
async function scanAtEveryViewport(page: Page, label: string) {
  for (const viewport of viewports) {
    await page.setViewportSize(viewport)
    const { violations } = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
    expect(violations, `${label} at ${viewport.width}x${viewport.height}`).toEqual([])
  }
}

// --- (a) Job/SSE connection states -----------------------------------------------------
//
// job-events.tsx opens `new EventSource('/api/v1/events')` once per mount. Per the HTML
// living standard, EventSource failure handling is bimodal:
//   - a non-200 response (or wrong content-type) "fails the connection": readyState -> CLOSED,
//     one `error` event, no reconnect attempts. job-events.tsx reports 'unavailable'.
//   - a network-level error (aborted request, connection refused, etc.) "reestablishes the
//     connection": readyState -> CONNECTING, one `error` event, then the browser retries on
//     its own schedule. job-events.tsx reports 'reconnecting' for that.
// Left unmocked, `/api/v1/events` reaches the real backend Playwright's webServer boots and
// settles to 'connected' — the state the first test below leaves unmocked. The other two are
// forced with a route override: fulfil a 404 for 'unavailable', abort the request for
// 'reconnecting'.
//
// The reconnecting/unavailable tests intentionally break the SSE connection, which produces
// browser-level connection-error noise, so they skip the strict `diagnostics` fixture — same
// precedent as the "failed backend read" test at the end of selected-app.spec.ts.

// Shared by all three states below: assert the connection status, scan it at every required
// viewport, then prove the status region's Refresh button is keyboard-operable.
async function assertJobConnectionState(page: Page, state: 'connected' | 'reconnecting' | 'unavailable') {
  const status = page.locator('[data-job-connection]')
  await expect(status).toHaveAttribute('data-job-connection', state, { timeout: 10_000 })
  await expect(status).toHaveAttribute('role', 'status')
  await scanAtEveryViewport(page, `/app/jobs ${state}`)
  const refresh = status.getByRole('button', { name: 'Refresh' })
  await refresh.focus()
  const [request] = await Promise.all([
    page.waitForRequest(req => req.method() === 'GET' && req.url().endsWith('/api/v1/goals')),
    page.keyboard.press('Enter'),
  ])
  expect(request.url()).toContain('/api/v1/goals')
}

test('job/SSE status is connected by default, exposed to assistive tech, keyboard-operable, and axe-clean at every viewport', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/jobs')
  await assertJobConnectionState(page, 'connected')
})

test('job/SSE status reaches reconnecting under a network error, stays accessible, keyboard-operable, and motion-free', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  // Aborting every attempt (not just the first) keeps the UI pinned in 'reconnecting' for the
  // whole test instead of racing a single error event.
  await page.route('**/api/v1/events', route => route.abort('failed'))
  await open(page, '/app/jobs')
  await assertJobConnectionState(page, 'reconnecting')
  expect(await longestMotionMs(page)).toBeLessThanOrEqual(0.01)
})

test('job/SSE status reaches unavailable on a failed HTTP handshake, stays accessible, keyboard-operable, and motion-free', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  // 'unavailable' is also reachable via `typeof EventSource === 'undefined'`, but that branch
  // isn't reachable from a real browser test, so a 404 handshake is the practical substitute.
  await page.route('**/api/v1/events', route => route.fulfill({ status: 404, contentType: 'text/plain', body: 'not found' }))
  await open(page, '/app/jobs')
  await assertJobConnectionState(page, 'unavailable')
  expect(await longestMotionMs(page)).toBeLessThanOrEqual(0.01)
})

// --- (b) Practice evaluating / feedback-ready -------------------------------------------
//
// CorePages.tsx computes `evaluating` from `practice.submit.isPending` among other things,
// so the state is reachable purely client-side, the instant "Submit response" is pressed —
// before the mocked server round-trip even resolves. The harness's default interview-runs
// handler mutates `practiceRun` to 'feedback-ready' synchronously inside the same handler
// that answers the POST, so without intervention the request resolves too fast to ever
// observe 'evaluating' on screen. This test installs its own route in front of the harness's
// (registered after `open()`, so it runs first and can `route.fallback()` back to the
// harness handler) that holds the response open on a manually-released gate, giving a stable
// window to scan and probe 'evaluating' before letting the same request resolve into
// 'feedback-ready'.

test('Practice evaluating and feedback-ready are both reachable, axe-clean at every viewport, and keyboard-operable', async ({ page, diagnostics }) => {
  test.setTimeout(60_000)
  void diagnostics
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await open(page, '/app/practice?bundleId=bundle-e2e-1&bundleItemId=question-e2e-1')

  let releaseAnswer: () => void = () => undefined
  const answerGate = new Promise<void>(resolve => { releaseAnswer = resolve })
  await page.route('**/api/v1/interview-runs/practice-run-e2e-1/answers', async route => {
    await answerGate
    await route.fallback()
  })

  await page.getByRole('textbox', { name: /Your response/i }).fill(practiceDraft)
  const submitResponse = page.getByRole('button', { name: /Submit response/i })
  await submitResponse.focus()
  await page.keyboard.press('Enter')

  // `evaluating`: the answer POST is in flight (held by `answerGate`) and no result exists
  // yet, so CorePages.tsx renders the "Evaluating submitted attempt" aside with its Cancel
  // control.
  const evaluatingAside = page.getByText('Evaluating submitted attempt')
  await expect(evaluatingAside).toBeVisible()
  await scanAtEveryViewport(page, 'Practice evaluating')
  expect(await longestMotionMs(page)).toBeLessThanOrEqual(0.01)

  const cancelEvaluation = page.getByRole('button', { name: /Cancel evaluation/i })
  await cancelEvaluation.focus()
  const [cancelRequest] = await Promise.all([
    page.waitForRequest(req => req.method() === 'POST' && req.url().includes('/cancel-evaluation')),
    page.keyboard.press('Enter'),
  ])
  expect(cancelRequest.url()).toContain('practice-run-e2e-1/cancel-evaluation')

  // `feedback-ready`: releasing the gate lets the held request resolve via the harness's
  // default handler (practiceRun -> 'feedback-ready', result appended) — the same transition
  // selected-app.spec.ts's Practice test already exercises functionally. This test instead
  // proves the resulting screen is keyboard-operable and axe-clean at every viewport.
  releaseAnswer()
  await expect(page.getByRole('heading', { name: /Facts and corrections/i })).toBeVisible()
  await scanAtEveryViewport(page, 'Practice feedback-ready')

  // Both feedback-section controls must be keyboard-reachable. "Choose another question"
  // navigates away, so only its focusability is asserted here; "Repair answer" is exercised
  // for real, proving Enter on a focused button both returns to the answer editor and
  // preserves the exact submitted draft for editing.
  const chooseAnother = page.getByRole('button', { name: /Choose another question/i })
  await expect(chooseAnother).toBeVisible()
  await chooseAnother.focus()
  await expect(chooseAnother).toBeFocused()

  const repairAnswer = page.getByRole('button', { name: /Repair answer/i })
  await repairAnswer.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('textbox', { name: /Your response/i })).toHaveValue(practiceDraft)
})

// --- (c) Settings delete-confirmation ----------------------------------------------------
//
// selected-app.spec.ts already proves the delete-confirmation alertdialog restores focus to
// its trigger when cancelled by mouse click. That leaves two gaps this ticket calls out
// explicitly: opening it from the keyboard alone, and closing it with Escape (Radix's
// AlertDialog treats Escape as a cancel, running the exact same `onCloseAutoFocus` focus
// restoration as the Cancel button) — plus scanning the OPEN dialog itself, which is a
// distinct reachable state axe never sees while the dialog is closed.

test('Settings delete-confirmation alertdialog opens from the keyboard, is axe-clean while open at every viewport, and Escape restores focus', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/settings')
  const trigger = page.getByRole('button', { name: /Preview deletion/i }).first()
  await trigger.focus()
  await page.keyboard.press('Enter')

  const dialog = page.getByRole('alertdialog', { name: /Delete Resilient order fulfillment\?/i })
  await expect(dialog).toBeVisible()
  // Wait for the mocked preflight impact snapshot to settle so the scan covers the dialog's
  // actual informational content, not only its transient "Calculating…" placeholder. Exact
  // match: the dialog's own description text also contains the substring "snapshot".
  await expect(dialog.getByText('Snapshot', { exact: true })).toBeVisible()
  await scanAtEveryViewport(page, 'open Settings delete-confirmation alertdialog')

  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  await expect(trigger).toBeFocused()
})

// --- (d) /app/canonical-updates merge-conflict controls -----------------------------------
//
// The harness's fixture data ships the "idempotency" canonical-update item with
// `conflict_type: 'overlay-conflict'` and `selected: true`, so its `<fieldset class="so-conflict">`
// resolution radios are visible immediately on load — no interaction is required to reach
// this state, only to navigate to the route, matching how the real app would surface a
// conflict as soon as a canonical update touches locally-overlaid content.

test('canonical-updates merge-conflict fieldset is grouped for assistive tech, axe-clean at every viewport, keyboard-operable, and motion-free', async ({ page, diagnostics }) => {
  void diagnostics
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await open(page, '/app/canonical-updates')

  const conflictGroup = page.getByRole('group', { name: /Resolve wording conflict/i })
  await expect(conflictGroup).toBeVisible()
  // The <fieldset><legend> pairing is what gives the radio group its accessible name; assert
  // it explicitly in addition to the axe scan below.
  await expect(conflictGroup).toHaveAccessibleName(/Resolve wording conflict/i)
  await scanAtEveryViewport(page, 'canonical-updates merge-conflict')
  expect(await longestMotionMs(page)).toBeLessThanOrEqual(0.01)

  const overlayWins = conflictGroup.getByRole('radio', { name: /Keep my overlay wording/i })
  const acceptCanonical = conflictGroup.getByRole('radio', { name: /Adopt the new canonical wording/i })
  await expect(overlayWins).toBeChecked()

  // Same-`name` native radios support roving arrow-key navigation without any extra script;
  // this proves the fieldset markup preserves that instead of accidentally breaking it (for
  // example, by giving every radio in the group a distinct `name`).
  await overlayWins.focus()
  await page.keyboard.press('ArrowDown')
  await expect(acceptCanonical).toBeChecked()
  await page.keyboard.press('ArrowUp')
  await expect(overlayWins).toBeChecked()

  const approve = page.getByRole('checkbox', { name: /Approve this exact local selection/i })
  const acceptSelected = page.getByRole('button', { name: /Accept selected/i })
  await expect(acceptSelected).toBeDisabled()
  await approve.focus()
  await page.keyboard.press('Space')
  await expect(approve).toBeChecked()
  await expect(acceptSelected).toBeEnabled()
})

// --- (e) Mock's evaluating / feedback-ready equivalents ---------------------------------
//
// IDK-502's scope names "`evaluating`/`feedback-ready` in Practice and Mock". Mock does not
// literally carry those two state values -- its lifecycle is
// ready/answering/follow-up/paused/completing/completed -- so the equivalent pair is:
//   - evaluating      -> `completing`: the terminal evaluation job is in flight,
//                        `data-mock-state="completing"`, the "Mock final evaluation"
//                        ProviderJobStatus is shown, and /app/reports deliberately renders a
//                        withholding "Report gate" reading "Evaluating" rather than any
//                        partial evaluative payload (CorePages.tsx:1013).
//   - feedback-ready  -> `completed` plus a readable terminal report.
// Both are async states absent from the prototype, and the report gate in particular is a
// state a learner can sit in, so each is scanned and driven by keyboard here.
test('Mock completing and its terminal report are axe-clean at every viewport and keyboard-operable', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/mock?bundleId=bundle-e2e-1&bundleItemId=bundle-item-technical')

  const answer = page.getByRole('textbox', { name: /Your response/i })
  await answer.focus()
  await page.keyboard.type('The idempotency boundary must be durable before acknowledgement.')

  // Complete is an explicit, confirmed terminal action; drive both steps by keyboard only.
  const complete = page.getByRole('button', { name: /Complete interview/i })
  await complete.focus()
  await page.keyboard.press('Enter')
  const completeDialog = page.getByRole('alertdialog', { name: /Complete the interview/i })
  await completeDialog.getByRole('button', { name: /^Complete interview$/i }).focus()
  await page.keyboard.press('Enter')

  await expect(page.locator('main[data-mock-state="completing"]')).toBeVisible()
  await expect(page.getByText(/Mock final evaluation/i).first()).toBeVisible()
  await scanAtEveryViewport(page, 'Mock completing (evaluating equivalent)')

  await page.emulateMedia({ reducedMotion: 'reduce' })
  expect(await longestMotionMs(page), 'Mock completing motion').toBeLessThanOrEqual(0.01)
  await page.emulateMedia({ reducedMotion: 'no-preference' })

  // The withholding report gate is its own reachable state: no evaluative payload is shown
  // while the run is non-terminal, and that refusal still has to be accessible.
  await open(page, '/app/reports?runId=mock-run-e2e-1')
  const gate = page.getByRole('status').filter({ hasText: /Report gate/i })
  await expect(gate).toContainText(/Evaluating/i)
  await scanAtEveryViewport(page, 'Mock report gate while evaluating')

  await page.evaluate(() => fetch('/api/v1/interview-runs/mock-run-e2e-1?finish=1'))
  await open(page, '/app/mock?runId=mock-run-e2e-1')
  const openReport = page.getByRole('button', { name: /Open report/i })
  await expect(openReport).toBeVisible()
  await scanAtEveryViewport(page, 'Mock completed (feedback-ready equivalent)')

  await openReport.focus()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/app\/reports\?runId=mock-run-e2e-1$/)
  await expect(page.locator('main.sb-reports').getByRole('heading', { name: /Rubric dimensions/i })).toBeVisible()
  await scanAtEveryViewport(page, 'Mock terminal report')
})
