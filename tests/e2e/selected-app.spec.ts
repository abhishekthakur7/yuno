import AxeBuilder from '@axe-core/playwright'
import { createHash } from 'node:crypto'
import {
  apiEvidence,
  artifactProvenanceFixture,
  defaultProfile,
  expect,
  expectNoHorizontalOverflow,
  fillGoalBasics,
  generatedLayerResponse,
  type GoalPatch,
  goalFixture,
  learningApiSnapshot,
  longestMotionMs,
  open,
  roadmapTopics,
  routes,
  seedAssessedEvidence,
  skipOptionalSetup,
  test,
  viewports,
} from './harness'

const exactDraft = '  Preserve this leading space.\nSecond line with a trailing space.  '
const practiceDraft = 'The commit-before-ack window needs an atomic idempotency key with an explicit retention policy.'

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`
  if (value !== null && typeof value === 'object') {
    return `{${Object.entries(value).sort(([left], [right]) => left.localeCompare(right)).map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`).join(',')}}`
  }
  return JSON.stringify(value) ?? 'null'
}

test('all 14 canonical routes render at every required viewport without overflow or runtime/network errors', async ({ page, diagnostics }) => {
  test.setTimeout(60_000)
  void diagnostics
  for (const viewport of viewports) {
    await page.setViewportSize(viewport)
    for (const [route, heading] of routes) {
      await open(page, route)
      await expect(page.getByRole('heading', { level: 1 }).first()).toHaveText(heading)
      await expectNoHorizontalOverflow(page, `${route} at ${viewport.width}x${viewport.height}`)
    }
  }
})

test('all canonical routes have no automated WCAG A or AA violations', async ({ page, diagnostics }) => {
  void diagnostics
  test.setTimeout(240_000)
  for (const viewport of viewports) {
    await page.setViewportSize(viewport)
    for (const [route] of routes) {
      await open(page, route)
      const { violations } = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
      expect(violations, `${route} at ${viewport.width}x${viewport.height}: automated accessibility violations`).toEqual([])
    }
  }
})

test('API-backed Home keeps persisted Resume separate from recommendation dismissal', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/')
  const resume = page.getByRole('region', { name: /Implement an idempotency boundary/i })
  await expect(resume.getByRole('button', { name: /^Resume$/i })).toBeVisible()
  await page.getByRole('button', { name: /Dismiss recommended next item/i }).click()
  await expect(page.getByText('Recommended next')).toHaveCount(0)
  await expect(resume.getByRole('button', { name: /^Resume$/i })).toBeVisible()
  await page.reload()
  await expect(page.getByText('Recommended next')).toHaveCount(0)
  await expect(page.getByRole('region', { name: /Implement an idempotency boundary/i })).toBeVisible()
})

test('switching A to B to A uses each goal’s API-backed Resume position', async ({ page, diagnostics }) => {
  void diagnostics
  let goals = [
    goalFixture({ id: 'goal-a', name: 'Goal A', subject: 'Backend systems', resume_position: 'delivery-contract' }),
    goalFixture({ id: 'goal-b', name: 'Goal B', subject: 'Backend systems', resume_position: 'observability' }),
  ]
  let currentGoalId = 'goal-a'
  await page.route('**/api/v1/profile', route => route.fulfill({ json: { ...defaultProfile, current_goal_id: currentGoalId } }))
  await page.route('**/api/v1/goals', route => route.fulfill({ json: goals }))
  await page.route('**/api/v1/goals/**', async route => {
    if (route.request().method() === 'GET') {
      await route.fallback()
      return
    }
    const id = new URL(route.request().url()).pathname.split('/').at(-1)
    const body = route.request().postDataJSON() as GoalPatch
    if (body.set_current && id) {
      currentGoalId = id
      goals = goals.map(goal => goal.id === id ? { ...goal, row_version: goal.row_version + 1 } : goal)
    }
    const position = body.resume_position
    if (position) goals = goals.map(goal => goal.id === id ? { ...goal, resume_position: position, row_version: goal.row_version + 1 } : goal)
    await route.fulfill({ json: goals.find(goal => goal.id === id) })
  })
  await open(page, '/')
  await page.getByRole('button', { name: 'Open Goal B' }).click()
  await expect(page).toHaveURL(/learn-roadmap/)
  await open(page, '/')
  await page.getByRole('button', { name: 'Open Goal A' }).click()
  await expect(page).toHaveURL(/learn-roadmap/)
  await open(page, '/')
  await page.getByRole('button', { name: 'Resume' }).click()
  await expect(page.getByRole('heading', { level: 1, name: /Model the delivery contract before choosing a pattern/i })).toBeVisible()
})

test('API-backed onboarding confirms once and survives browser storage clearing', async ({ page, diagnostics }) => {
  void diagnostics
  let confirmationRequests = 0
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/diagnostics/diagnostic-e2e/confirm-goal')) confirmationRequests += 1
  })
  await open(page, '/app/onboarding')
  await fillGoalBasics(page)
  await skipOptionalSetup(page)
  await expect(page.getByText(/Model the delivery contract before choosing a pattern/i)).toBeVisible()
  await page.getByRole('button', { name: /Create goal from roadmap/i }).click()
  await expect(page).toHaveURL(/\/app\/learn-roadmap$/)
  await expect.poll(() => confirmationRequests).toBe(1)

  const retryStatus = await page.evaluate(() => fetch('/api/v1/diagnostics/diagnostic-e2e/confirm-goal', { method: 'POST' }).then(response => response.status))
  expect(retryStatus).toBe(409)
  await page.evaluate(() => localStorage.clear())
  await page.reload()
  await expect(page.getByRole('heading', { level: 1, name: /Your editable roadmap/i })).toBeVisible()
  await open(page, '/')
  await expect(page.getByRole('heading', { level: 1, name: /Continue Resilient order fulfillment/i })).toBeVisible()
})

test('onboarding preview keeps full depth labels usable and tablet controls inside their card', async ({ page, diagnostics }) => {
  void diagnostics
  await page.setViewportSize({ width: 1366, height: 768 })
  await open(page, '/app/onboarding')
  await fillGoalBasics(page)
  await skipOptionalSetup(page)
  const secondPreviewTopic = page.locator('#preview-topic-commit-window')
  await page.getByRole('button', { name: /^Jump$/i }).nth(1).click()
  await expect(secondPreviewTopic).toBeFocused()
  await expect(secondPreviewTopic).toHaveAttribute('aria-current', 'step')
  const depthWidth = await page.getByRole('combobox', { name: /^Depth\b/i }).first().evaluate(element => element.getBoundingClientRect().width)
  expect(depthWidth, 'depth control is wide enough for Implementation').toBeGreaterThanOrEqual(140)
  await page.setViewportSize({ width: 768, height: 1024 })
  await expectNoHorizontalOverflow(page, 'onboarding preview at 768x1024')
  const bounds = await page.evaluate(() => {
    const card = document.querySelector('.sb-card')?.getBoundingClientRect()
    const controls = Array.from(document.querySelectorAll('.sb-preview select, .sb-preview button')).map(element => {
      const box = element.getBoundingClientRect()
      return { left: box.left, right: box.right, width: box.width }
    })
    return { card: card ? { left: card.left, right: card.right } : null, controls }
  })
  expect(bounds.card).not.toBeNull()
  for (const control of bounds.controls) {
    expect(control.width, 'roadmap control has usable rendered width').toBeGreaterThanOrEqual(44)
    expect(control.left, 'roadmap control stays inside the card left edge').toBeGreaterThanOrEqual((bounds.card?.left ?? 0) - 0.5)
    expect(control.right, 'roadmap control stays inside the card right edge').toBeLessThanOrEqual((bounds.card?.right ?? 0) + 0.5)
  }
})

test('onboarding persists verbatim source material as visibly untrusted seed', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/onboarding')
  await fillGoalBasics(page)
  const source = '# Notes\n- How long can a duplicate key remain trustworthy?'
  await page.getByRole('radio', { name: /Take a short diagnostic/i }).check()
  await page.getByRole('textbox', { name: /Optional notes · untrusted seed/i }).fill(source)
  await page.getByRole('button', { name: /Start diagnostic/i }).click()
  await expect(page.getByText(/Untrusted seed · review later in Imports/i)).toBeVisible()
  await expect(page.locator('.sb-untrusted-seed pre')).toHaveText(source)
  await page.reload()
  await expect(page.locator('.sb-untrusted-seed pre')).toHaveText(source)
  await expect.poll(async () => (await apiEvidence(page)).length).toBe(0)
})

test('API-backed roadmap depth, knowledge, skip, and order edits survive reload', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/learn-roadmap')
  page.on('dialog', dialog => dialog.accept())
  await page.getByRole('combobox', { name: /^Depth\b/i }).first().selectOption('Production')
  await expect(page.getByText('Checkpoint saved.')).toBeVisible()
  await page.getByRole('combobox', { name: /^Knowledge$/i }).first().selectOption('new')
  await page.getByRole('button', { name: /^Skip$/i }).first().click()
  await page.getByRole('button', { name: /Move Model the delivery contract before choosing a pattern later/i }).click()
  await expect(page.getByRole('button', { name: /^Restore$/i }).first()).toBeVisible()
  await page.reload()
  const delivery = page.getByRole('article').filter({ hasText: /Model the delivery contract before choosing a pattern/i })
  await expect(delivery.getByRole('combobox', { name: /^Depth\b/i })).toHaveValue('Production')
  await expect(delivery.getByRole('combobox', { name: /^Knowledge$/i })).toHaveValue('new')
  await expect(delivery.getByRole('button', { name: /^Restore$/i })).toBeVisible()
  await expect(page.getByRole('button', { name: /Move Model the delivery contract before choosing a pattern earlier/i })).toBeEnabled()
})

test('roadmap and curriculum selections change and preserve the current lesson', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/learn-roadmap')
  await page.getByRole('button', { name: /^01 Model the delivery contract before choosing a pattern/i }).click()
  await expect(page).toHaveURL(/\/app\/topic-studio$/)
  await expect(page.getByRole('heading', { level: 1, name: /Model the delivery contract before choosing a pattern/i })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { level: 1, name: /Model the delivery contract before choosing a pattern/i })).toBeVisible()
  await page.getByRole('button', { name: /^Implement an idempotency boundary under concurrent retries/i }).click()
  await expect(page.getByRole('heading', { level: 1, name: /Implement an idempotency boundary under concurrent retries/i })).toBeVisible()
})

test('Topic Studio generates absent content through an explicit generating state', async ({ page, diagnostics }) => {
  void diagnostics
  let state: 'absent' | 'generating' | 'ready' = 'absent'
  let generatingReads = 0
  await page.route('**/api/v1/artifacts/artifact-e2e-1/provenance', route => route.fulfill({ json: artifactProvenanceFixture() }))
  await page.route('**/api/v1/goals/goal-default/topics/idempotency-retry/generate**', async route => {
    state = 'generating'
    await route.fulfill({ status: 202, json: { job_id: 'generation-job-e2e-1', kind: 'generate_topic_content', status: 'queued', enqueued_at: '2026-08-12T00:01:00Z', deduplicated: false } })
  })
  await page.route('**/api/v1/goals/goal-default/topics/idempotency-retry/layers', async route => {
    if (state === 'generating') {
      generatingReads += 1
      if (generatingReads > 1) state = 'ready'
    }
    const essential = state === 'absent'
      ? generatedLayerResponse({ state: 'absent', artifact_id: null, markdown: null, markdown_hash: null, content_origin: null, generation: null })
      : state === 'generating'
        ? generatedLayerResponse({ state: 'generating', markdown: null, markdown_hash: null, generation: { job_id: 'generation-job-e2e-1', status: 'running', retryable: true, failure_reference: null } })
        : generatedLayerResponse()
    await route.fulfill({ json: { goal_id: 'goal-default', graph_version_id: 'graph-1', topic_id: 'idempotency-retry', conversation_scope: 'goal-default:idempotency-retry', layers: [essential] } })
  })

  await open(page, '/app/topic-studio')
  await expect(page.getByRole('heading', { name: 'No Essential content yet' })).toBeVisible()
  await page.getByRole('button', { name: 'Generate Essential' }).click()
  await expect(page.getByRole('heading', { name: 'Generating Essential' })).toBeVisible()
  await page.reload()
  await expect(page.getByText('Generated ready body.')).toBeVisible({ timeout: 5_000 })
})

test('Topic Studio keeps a stale body through explicit regeneration and exposes source warnings', async ({ page, diagnostics }) => {
  void diagnostics
  let regenerating = false
  let regenerationReads = 0
  await page.route('**/api/v1/artifacts/artifact-e2e-1/provenance', route => route.fulfill({ json: artifactProvenanceFixture() }))
  await page.route('**/api/v1/artifacts/artifact-e2e-1/regenerate', async route => {
    regenerating = true
    await route.fulfill({ status: 202, json: { job_id: 'regeneration-job-e2e-1', kind: 'regenerate_artifact', status: 'queued', enqueued_at: '2026-08-12T00:02:00Z', deduplicated: false } })
  })
  await page.route('**/api/v1/goals/goal-default/topics/idempotency-retry/layers', async route => {
    if (regenerating) regenerationReads += 1
    const essential = regenerating && regenerationReads > 1
      ? generatedLayerResponse({ markdown: 'Regenerated body after explicit action.', markdown_hash: 'regenerated-hash' })
      : generatedLayerResponse({ state: 'stale', markdown: 'Original stale generated body.', markdown_hash: 'stale-hash', stale_reason: 'personalization-snapshot-mismatch', generation: regenerating ? { job_id: 'regeneration-job-e2e-1', status: 'running', retryable: true, failure_reference: null } : { job_id: 'generation-job-e2e-1', status: 'succeeded', retryable: false, failure_reference: null } })
    await route.fulfill({ json: { goal_id: 'goal-default', graph_version_id: 'graph-1', topic_id: 'idempotency-retry', conversation_scope: 'goal-default:idempotency-retry', layers: [essential] } })
  })

  await open(page, '/app/topic-studio')
  await expect(page.getByText('Original stale generated body.')).toBeVisible()
  await expect(page.getByText(/existing content remains visible and unchanged/i)).toBeVisible()
  await page.getByText('About this content').click()
  await expect(page.getByText('This version-dependent claim needs direct support.')).toBeVisible()
  await expect(page.getByText('Routine claim · no citation required')).toBeVisible()
  await expect(page.getByRole('alert')).toContainText('Withdrawn fixture advisory is withdrawn')
  await page.getByRole('button', { name: 'Regenerate', exact: true }).click()
  await expect(page.getByText('Original stale generated body.')).toBeVisible()
  await expect(page.getByText('Generating updated content')).toBeVisible()
  await page.reload()
  await expect(page.getByText('Regenerated body after explicit action.')).toBeVisible({ timeout: 5_000 })
})

test('Topic Studio keeps Submit usable while controlled runner posture is disabled', async ({ page, diagnostics }) => {
  void diagnostics
  await page.setViewportSize({ width: 1366, height: 768 })
  await open(page, '/app/topic-studio')
  const openLab = page.getByRole('button', { name: /Open implementation lab/i })
  const openLabBox = await openLab.boundingBox()
  expect(openLabBox).not.toBeNull()
  expect((openLabBox?.y ?? 0) + (openLabBox?.height ?? 0), 'primary lesson action is in the first viewport').toBeLessThanOrEqual(768)
  await openLab.click()
  await expect(page.getByRole('textbox', { name: /Java artifact/i })).toBeInViewport()
  await expect(page.getByRole('button', { name: 'Run', exact: true })).toBeDisabled()
  await expect(page.getByText(/Submit remains available for static review/i)).toBeVisible()
  await expect.poll(async () => (await apiEvidence(page)).length).toBe(0)
  await page.getByRole('button', { name: 'Submit artifact', exact: true }).click()
  await expect(page.getByText('Revision 1', { exact: true })).toBeVisible()
  await expect(page.getByText(/Static-review limitation/i)).toBeVisible()
  await expect.poll(async () => (await apiEvidence(page)).length).toBe(1)
})

test('Topic Studio confirms a hashed input, separates runtime phases, and cancels a run', async ({ page, diagnostics }) => {
  void diagnostics
  let cancelled = false
  await page.route('**/api/v1/runner/**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path.endsWith('/capabilities')) {
      await route.fulfill({ json: { enabled: true, disabled_reason: null, environment_policy_version: 'runner-env-e2e', limits_config_version: 'runner-limits-e2e', limitation: 'Controlled subprocess execution only.', capabilities: [{ language: 'java', capability: 'compile-test', state: 'supported', detail: 'Configured.' }] } })
      return
    }
    if (path.endsWith('/confirmations')) {
      const body = request.postDataJSON() as { inputs: unknown[] }
      await route.fulfill({ status: 201, json: { id: 'runner-confirmation-e2e', language: 'java', capability: 'compile-test', inputs: body.inputs, confirmed_at: '2026-08-13T02:00:00Z' } })
      return
    }
    await route.fallback()
  })
  await page.route('**/api/v1/runner-runs**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path.endsWith('/cancel')) {
      cancelled = true
      await route.fulfill({ json: { id: 'runner-e2e', state: 'cancel-requested', inputs: [], output_chunks: [], compile_phase: { state: 'running' }, test_phase: { state: 'queued' }, cleanup_state: 'cleanup-pending', limitation: 'Controlled subprocess execution only.' } })
      return
    }
    if (request.method() === 'POST') {
      await route.fulfill({ status: 202, json: { job_id: 'runner-e2e' } })
      return
    }
    await route.fulfill({ json: { id: 'runner-e2e', state: cancelled ? 'cancelled' : 'running', inputs: [], output_chunks: [{ phase: 'compile', stream: 'stdout', sequence: 1, content: 'Compilation started', truncated: false }, { phase: 'test', stream: 'stdout', sequence: 2, content: 'Tests queued', truncated: false }], compile_phase: { state: 'running' }, test_phase: { state: 'queued' }, cleanup_state: cancelled ? 'cleanup-complete' : 'cleanup-pending', limitation: 'Controlled subprocess execution only.' } })
  })
  await open(page, '/app/topic-studio')
  await page.getByRole('button', { name: /Open implementation lab/i }).click()
  await page.getByRole('button', { name: 'Run', exact: true }).click()
  const confirmation = page.getByRole('alertdialog')
  await expect(confirmation.getByRole('heading', { name: 'Confirm controlled Java run' })).toBeVisible()
  await expect(confirmation.getByText(/^[a-f0-9]{64}$/)).toBeVisible()
  await expect(confirmation).toContainText('not a sandbox or hostile-code isolation')
  await confirmation.getByRole('button', { name: 'Confirm and run' }).click()
  const runtime = page.locator('[data-result-region="runtime"]')
  await expect(runtime.getByText('Compilation started')).toBeVisible()
  await expect(runtime.getByText('Tests queued')).toBeVisible()
  await runtime.getByRole('button', { name: 'Cancel run' }).click()
  await expect(runtime.getByText(/Cancel requested/)).toBeVisible()
})

test('Practice reveals a requested hint, then feedback, repair, and append-only history', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/practice?bundleId=bundle-e2e-1&bundleItemId=question-e2e-1')
  await expect(page.getByText(/Name the failure window first/i)).toHaveCount(0)
  await expect(page.getByRole('button', { name: /Repair answer/i })).toHaveCount(0)
  await page.getByRole('button', { name: /Request hint/i }).click()
  await expect(page.getByText(/Name the failure window first/i)).toBeVisible()
  await page.getByRole('textbox', { name: /Your response/i }).fill(practiceDraft)
  await page.getByRole('button', { name: /Submit response/i }).click()
  await expect(page.getByRole('heading', { name: /Facts and corrections/i })).toBeVisible()
  await expect(page.getByRole('heading', { name: /Trade-offs to defend/i })).toBeVisible()
  await page.getByRole('button', { name: /Repair answer/i }).click()
  await expect(page.getByRole('textbox', { name: /Your response/i })).toHaveValue(practiceDraft)
  const repairedDraft = `  ${practiceDraft} Repaired.  \n`
  await page.getByRole('textbox', { name: /Your response/i }).fill(repairedDraft)
  await page.getByRole('button', { name: /Submit response/i }).click()
  await expect(page.getByText(/Earlier attempts \(1\)/i)).toBeVisible()
  await expect.poll(async () => page.evaluate(async () => {
    const response = await fetch('/api/v1/interview-runs/practice-run-e2e-1')
    const run = await response.json()
    return run.turns.filter((turn: { kind: string }) => turn.kind === 'answer').length
  })).toBe(2)
  await expect.poll(async () => page.evaluate(async () => {
    const response = await fetch('/api/v1/interview-runs/practice-run-e2e-1')
    const run = await response.json()
    return run.turns.filter((turn: { kind: string }) => turn.kind === 'answer').at(-1)?.body
  })).toBe(repairedDraft)
})

test('Mock pause/resume preserves the exact API draft and Complete remains an explicit terminal action', async ({ page, diagnostics }) => {
  void diagnostics
  let completeRequests = 0
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/mock-run-e2e-1/complete')) completeRequests += 1
  })
  await open(page, '/app/mock?bundleId=bundle-e2e-1&bundleItemId=bundle-item-technical')
  const answer = page.getByRole('textbox', { name: /Your response/i })
  await expect(answer).toHaveValue('')
  await expect(page.getByRole('button', { name: /Complete interview/i })).toBeDisabled()
  await answer.fill(exactDraft)
  await expect(page.getByText(/Facts in transcript/i)).toHaveCount(0)
  const exit = page.getByRole('button', { name: /Save & exit/i })
  await exit.click()
  const pauseDialog = page.getByRole('alertdialog', { name: /Pause this mock/i })
  await pauseDialog.getByRole('button', { name: /Keep answering/i }).click()
  await expect(exit).toBeFocused()
  await exit.click()
  await pauseDialog.getByRole('button', { name: /^Save & exit$/i }).click()
  await expect(page).toHaveURL(/\/app\/interview-hub\?runId=mock-run-e2e-1$/)
  await expect.poll(async () => page.evaluate(() => fetch('/api/v1/interview-runs/mock-run-e2e-1').then(response => response.json()).then(run => ({ state: run.state, draft: run.draft })))).toEqual({ state: 'paused', draft: exactDraft })
  await page.getByRole('button', { name: /Mock interview/i }).click()
  await expect(page).toHaveURL(/\/app\/mock\?runId=mock-run-e2e-1$/)
  await expect(page.getByRole('textbox', { name: /Your response/i })).toHaveValue(exactDraft)
  const withheld = await page.evaluate(() => fetch('/api/v1/interview-runs/mock-run-e2e-1/report').then(async response => ({ status: response.status, body: await response.json() })))
  expect(withheld).toMatchObject({ status: 409, body: { code: 'mock_feedback_withheld' } })
  const complete = page.getByRole('button', { name: /Complete interview/i })
  await complete.click()
  const completeDialog = page.getByRole('alertdialog', { name: /Complete the interview/i })
  await completeDialog.getByRole('button', { name: /Return to answer/i }).click()
  await expect(complete).toBeFocused()
  await complete.click()
  await completeDialog.getByRole('button', { name: /^Complete interview$/i }).click()
  await expect.poll(async () => page.evaluate(() => fetch('/api/v1/interview-runs/mock-run-e2e-1').then(response => response.json()).then(run => ({ state: run.state, draft: run.draft, activeJobId: run.active_job_id })))).toEqual({ state: 'completing', draft: exactDraft, activeJobId: 'mock-final-evaluation-e2e-1' })
  await expect(page.getByRole('button', { name: /Open report/i })).toHaveCount(0)
  await expect(page).toHaveURL(/\/app\/mock\?runId=mock-run-e2e-1$/)
  expect(completeRequests).toBe(1)
  await page.evaluate(() => fetch('/api/v1/interview-runs/mock-run-e2e-1?finish=1'))
  await page.reload()
  await expect(page.getByRole('button', { name: /Open report/i })).toBeVisible()
  await page.getByRole('button', { name: /Open report/i }).click()
  await expect(page).toHaveURL(/\/app\/reports\?runId=mock-run-e2e-1$/)
  const report = page.locator('main.sb-reports')
  await expect(report.getByText('Where is the durable idempotency boundary?')).toBeVisible()
  const reportText = await report.innerText()
  const orderedSections = [
    'The transcript identifies the durable idempotency boundary.',
    'Test the boundary during acknowledgement loss.',
    'Assumptions',
    'Facts and corrections',
    'Trade-offs',
    'Rubric dimensions',
    'Ambiguity',
    'Interview transcript',
    'Provenance',
  ]
  const positions = orderedSections.map(section => reportText.indexOf(section))
  expect(positions).not.toContain(-1)
  expect(positions.every((position, index) => index === 0 || positions[index - 1]! < position)).toBe(true)
})

test('Evidence reads API-backed assessment history and records a dispute without overwriting evidence', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/evidence')
  await expect(page.getByRole('heading', { name: /No submitted lab evidence is available yet/i })).toBeVisible()
  const seeded = await seedAssessedEvidence(page)
  const original = await page.evaluate(id => fetch(`/api/v1/evidence/${id}`).then(response => response.json()), seeded.id)
  await open(page, '/app/evidence')
  await expect(page.getByRole('heading', { name: /submitted decision supports a bounded idempotency conclusion/i })).toBeVisible()
  await expect(page.getByRole('alert')).toContainText(/Tombstoned source warning/i)
  await page.getByRole('button', { name: /Record dispute/i }).click()
  await expect(page.getByRole('button', { name: /Request re-evaluation/i })).toBeVisible()
  await expect.poll(async () => page.evaluate(id => fetch(`/api/v1/assessments/${id}`).then(response => response.json()).then(value => value.disputes.length), seeded.active_assessment_id)).toBe(1)
  const preserved = await page.evaluate(id => fetch(`/api/v1/evidence/${id}`).then(response => response.json()), seeded.id)
  expect(preserved).toEqual(original)
  await page.getByText(/Disputes and re-evaluation/i).click()
  await expect(page.getByText(/learner requested correction and re-evaluation/i)).toBeVisible()
  await page.getByRole('button', { name: /Open transfer check/i }).click()
  await expect(page).toHaveURL(/\/app\/practice$/)
})

test('progress display persists as presentation-only and leaves learning APIs unchanged', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/evidence')
  const seeded = await seedAssessedEvidence(page)
  const before = await learningApiSnapshot(page, seeded.id, seeded.active_assessment_id)

  await open(page, '/app/settings')
  const simple = page.getByRole('radio', { name: /Simple/i })
  await simple.click()
  await expect(simple).toBeChecked()
  await expect.poll(async () => page.evaluate(() => fetch('/api/v1/settings').then(response => response.json()).then(settings => settings.progress_display))).toBe('simple')

  await open(page, '/app/evidence')
  await expect(page.locator('[data-progress-display="simple"]')).toBeVisible()
  const after = await learningApiSnapshot(page, seeded.id, seeded.active_assessment_id)
  expect(after).toEqual(before)
})

test('Settings exposes truthful provider recovery, selection, and disclosure separation', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/settings')
  const selector = page.getByRole('combobox', { name: 'Preferred provider' })
  await expect(selector.getByRole('option', { name: /claude · authentication-unavailable/i })).toHaveAttribute('disabled', '')
  await selector.selectOption('codex')
  await expect(page.getByText('Provider selection saved.')).toBeVisible()
  await expect(page.getByText(/Disclosure acceptance is not provider authentication/i)).toBeVisible()
  await expect(page.getByText(/Complete the CLI's local sign-in, then refresh/i)).toBeVisible()
  await page.getByRole('button', { name: 'Accept disclosure' }).first().click()
  await expect(page.getByText(/Not accepted; future network enqueues in this category are blocked/i)).toHaveCount(1)
  await expect(selector).toHaveValue('codex')
})

test('server-parsed imports stay exact and untrusted while learner decisions remain personal', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/imports')
  const source = '# Notes\n- SQS may redeliver the same message after a durable commit.\n- A lookup before a write does not arbitrate concurrent requests.'
  await page.getByRole('textbox', { name: /Paste Markdown or plain text/i }).fill(source)
  await page.getByRole('button', { name: /Save and queue parse/i }).click()
  await expect(page.getByText(/receipt does not claim parsing completed/i)).toBeVisible()
  await expect(page.getByText(/Parsed as untrusted/i)).toBeVisible()
  await page.reload()
  await expect(page.getByRole('textbox', { name: /Preserved original text/i })).toHaveValue(source)
  await expect(page.getByText('exact-original-hash')).toBeVisible()
  const first = page.getByText(/“SQS may redeliver the same message/i).locator('xpath=ancestor::article')
  const topic = first.getByRole('combobox', { name: /Map to an approved topic/i })
  await expect(topic.getByRole('option')).toHaveText(['Not mapped', ...roadmapTopics.map(([, title]) => title)])
  await topic.selectOption('delivery-contract')
  await first.getByRole('button', { name: 'Map' }).click()
  await first.getByRole('button', { name: /Verify as mine/i }).click()
  await page.getByText(/“A lookup before a write/i).locator('xpath=ancestor::article').getByRole('button', { name: /Dismiss/i }).click()
  await expect(page.getByText(/Mapping and verification are personal decisions/i)).toBeVisible()
  await expect.poll(async () => (await apiEvidence(page)).length).toBe(0)
})

test('canonical curriculum updates mutate the server pin only after explicit acceptance', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/canonical-updates')
  await expect(page.getByLabel(/Goal pinned to 2026\.07/i)).toBeVisible()
  await expect(page.getByText(/nothing changes until you explicitly accept a selection/i)).toBeVisible()
  await expect(page.getByText('Archived local topic', { exact: true })).toBeVisible()
  await page.getByRole('checkbox', { name: /Select Dead-letter recovery/i }).uncheck()
  await page.getByRole('radio', { name: /Adopt the new canonical wording/i }).first().check()
  await page.getByRole('checkbox', { name: /Approve this exact local selection/i }).check()
  await page.getByRole('button', { name: /Accept selected/i }).click()
  await expect(page.getByText(/3 selected changes accepted/i)).toBeVisible()
  await expect.poll(async () => page.evaluate(() => Promise.all([
    fetch('/api/v1/goals/goal-default/canonical-update').then(response => response.json()),
    fetch('/api/v1/goals').then(response => response.json()),
  ]).then(([update, goals]) => ({ state: update.state, pin: goals[0].graph_version_id })))).toEqual({ state: 'empty', pin: 'graph-2' })
  await page.reload()
  await expect(page.getByLabel(/Goal pinned to 2026\.08/i)).toBeVisible()
  await expect(page.getByText(/already uses the latest approved curriculum graph/i)).toBeVisible()
})

test('postponing a canonical update persists the decision without moving the pin', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/canonical-updates')
  await page.getByRole('button', { name: 'Postpone' }).click()
  await expect.poll(async () => page.evaluate(() => fetch('/api/v1/goals').then(response => response.json()).then(goals => goals[0].graph_version_id))).toBe('graph-1')
  await page.reload()
  await expect(page.getByText('Update postponed')).toBeVisible()
  await expect(page.getByText(/decision is persisted and the proposal is closed/i)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Accept selected' })).toBeDisabled()
  await expect(page.getByLabel(/Goal pinned to 2026\.07/i)).toBeVisible()
})

test('essential selected-app flows are operable from the keyboard', async ({ page, diagnostics }) => {
  void diagnostics
  await page.setViewportSize({ width: 768, height: 1024 })
  await open(page, '/app/onboarding')
  const interviewPath = page.getByRole('button', { name: /Interview Prep/i })
  await interviewPath.focus()
  await page.keyboard.press('Space')
  await expect(interviewPath).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('textbox', { name: 'Goal name' }).fill('Backend interview preparation')
  await page.getByRole('textbox', { name: 'Role' }).fill('Backend engineer')
  const target = page.getByRole('combobox', { name: /Target level/i })
  await target.focus()
  await target.press('s')
  await expect(target).toHaveValue('Staff')
  const preview = page.getByRole('button', { name: /Skip to roadmap preview/i })
  await preview.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { name: /Create a goal from this roadmap/i })).toBeVisible()

  await open(page, '/app/learn-roadmap')
  const customize = page.getByRole('button', { name: /^Customize$/i }).first()
  await customize.focus()
  await page.keyboard.press('Enter')
  await expect(customize).toHaveAttribute('aria-expanded', 'true')

  await open(page, '/app/interview-hub?mode=questions')
  const questionsContent = page.locator('#sb-interview-mode-content')
  const questionCheckbox = questionsContent.getByRole('checkbox', { name: /Where is the durable idempotency boundary/i })
  await questionCheckbox.focus()
  await page.keyboard.press('Space')
  await expect(questionCheckbox).toBeChecked()
  const openGuidedPractice = questionsContent.getByRole('button', { name: /Open Guided practice/i })
  await openGuidedPractice.focus()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/app\/practice\?bundleId=bundle-e2e-1&bundleItemId=question-e2e-1$/)

  await open(page, '/app/practice?bundleId=bundle-e2e-1&bundleItemId=question-e2e-1')
  const hint = page.getByRole('button', { name: /Request hint/i })
  await hint.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByText(/Name the failure window first/i)).toBeVisible()
  const response = page.getByRole('textbox', { name: /Your response/i })
  await response.focus()
  await response.fill(practiceDraft)
  const submitResponse = page.getByRole('button', { name: /Submit response/i })
  await submitResponse.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { name: /Facts and corrections/i })).toBeVisible()
  await expect(page.getByRole('heading', { name: /Trade-offs to defend/i })).toBeVisible()
  await expect(page.getByRole('heading', { name: /Rubric dimensions/i })).toBeVisible()
  const submittedResponseDisclosure = page.locator('summary').filter({ hasText: 'Your submitted response' })
  await submittedResponseDisclosure.focus()
  await expect(page.getByText(practiceDraft, { exact: true })).not.toBeVisible()
  await page.keyboard.press('Enter')
  await expect(page.getByText(practiceDraft, { exact: true })).toBeVisible()

  await open(page, '/app/topic-studio')
  await expect(page.getByRole('button', { name: /Lesson tools/i })).toBeVisible()
  const notesTab = page.getByRole('tab', { name: /Notes/i })
  await notesTab.focus()
  const notebookEntryText = 'Keyboard-authored notebook entry for the idempotency boundary.'
  const notebookEntry = page.getByRole('textbox', { name: 'Add a user entry' })
  await notebookEntry.focus()
  await notebookEntry.fill(notebookEntryText)
  const saveEntry = page.getByRole('button', { name: /Save entry/i })
  await saveEntry.focus()
  await page.keyboard.press('Enter')
  const savedEntry = page.locator('.sb-notebook-list li', { hasText: notebookEntryText })
  await expect(savedEntry).toBeVisible()
  await expect(savedEntry).toContainText('user')
  await expect(savedEntry).toContainText('Topic · idempotency-retry')
  await notesTab.focus()
  await page.keyboard.press('ArrowRight')
  await expect(page.getByRole('tab', { name: /Review/i })).toHaveAttribute('aria-selected', 'true')
  await page.keyboard.press('ArrowRight')
  await expect(page.getByRole('tab', { name: /Resources/i })).toHaveAttribute('aria-selected', 'true')
  await page.keyboard.press('ArrowRight')
  await expect(page.getByRole('tab', { name: /Help/i })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByText(/Conversation attached to this topic/i)).toBeVisible()

  const courseContent = page.getByRole('button', { name: /Course content/i })
  await courseContent.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('dialog', { name: /Course content/i })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog', { name: /Course content/i })).toHaveCount(0)
  await expect(courseContent).toBeFocused()

  await open(page, '/app/settings')
  const experience = page.getByRole('textbox', { name: 'Experience' })
  await experience.focus()
  await experience.fill('Five years building resilient distributed systems.')
  const saveProfile = page.getByRole('button', { name: /^(Save profile|Saving…|Saved)$/ })
  await saveProfile.focus()
  await page.keyboard.press('Enter')
  await expect(saveProfile).toHaveText('Saved')

  const simple = page.getByRole('radio', { name: /Simple/i })
  await simple.focus()
  await page.keyboard.press('Space')
  await expect(simple).toBeChecked()

  const reducedMotion = page.getByRole('checkbox', { name: /Reduce motion/i })
  await reducedMotion.focus()
  await page.keyboard.press('Space')
  await expect(reducedMotion).toBeChecked()

  const provider = page.getByRole('combobox', { name: 'Preferred provider' })
  await provider.focus()
  await provider.press('c')
  await expect(provider).toHaveValue('codex')
  await expect(page.getByText('Provider selection saved.')).toBeVisible()

  const createExport = page.getByRole('button', { name: 'Create export' })
  await createExport.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('link', { name: /Download yuno-export-v1-20260813T000200Z.json/ })).toBeVisible()

  const reviewImports = page.getByRole('button', { name: /Review imports/i })
  await reviewImports.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { level: 1, name: /Bring notes in as untrusted material/i })).toBeVisible()
})

test('unsupported and retired routes render the not-found view', async ({ page, diagnostics }) => {
  void diagnostics
  for (const route of [
    '/app/home',
    '/app/report',
    '/app/not-a-real-view',
    '/concept-a/home',
    '/concept-b/home',
    '/concept-c/home',
    '/concept-anything/home',
  ]) {
    await page.goto(route)
    await expect(page.getByRole('heading', { name: /That learning view does not exist/i })).toBeVisible()
    await expect(page.locator('[data-app="yuno-learning"]')).toHaveCount(0)
  }
})

test('navigation drawer and destructive dialog restore focus to their triggers', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/')
  const tools = page.getByRole('button', { name: /^Tools$/i })
  await tools.click()
  const drawer = page.getByRole('dialog', { name: /Workspace navigation/i })
  await expect(drawer).toBeVisible()
  await drawer.getByRole('button', { name: /Close navigation/i }).click()
  await expect(tools).toBeFocused()

  await open(page, '/app/settings')
  const previewDeletion = page.getByRole('button', { name: /Preview deletion/i }).first()
  await previewDeletion.click()
  const dialog = page.getByRole('alertdialog', { name: /Delete Resilient order fulfillment/i })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: /Cancel/i }).click()
  await expect(previewDeletion).toBeFocused()

  await page.evaluate(() => fetch('/api/v1/imports', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ goal_id: 'goal-default', import_type: 'markdown', original_content: 'sensitive import body for focus restoration' }),
  }))
  await page.reload()
  const deleteImport = page.getByRole('button', { name: 'Delete import import-1' })
  await deleteImport.click()
  const importDialog = page.getByRole('alertdialog', { name: 'Delete this import body?' })
  await expect(importDialog).toBeVisible()
  await importDialog.getByRole('button', { name: 'Cancel' }).click()
  await expect(deleteImport).toBeFocused()

  await page.getByRole('textbox', { name: 'Interview session ID' }).fill('practice-run-e2e-1')
  const deleteSession = page.getByRole('button', { name: 'Delete session body' })
  await deleteSession.click()
  const sessionDialog = page.getByRole('alertdialog', { name: 'Delete this interview session body?' })
  await expect(sessionDialog).toBeVisible()
  await sessionDialog.getByRole('button', { name: 'Cancel' }).click()
  await expect(deleteSession).toBeFocused()
})

test('Settings discloses policy 1.0 guarantees and downloads canonical local JSON', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/settings')
  await page.evaluate(() => fetch('/api/v1/imports', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ goal_id: 'goal-default', import_type: 'markdown', original_content: 'sensitive import body' }),
  }))
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible()
  await expect(page.getByText(/Deletion is irreversible/)).toBeVisible()
  await expect(page.getByText(/no undelete or recovery window/i).first()).toBeVisible()
  await expect(page.getByText(/External OS, filesystem, VM, or user-created backups may retain deleted data/i)).toBeVisible()
  await expect(page.getByText(/no remote support access/i)).toBeVisible()

  await page.getByText(/Data limits and retention/).click()
  await expect(page.getByText(/10 MiB each, 100 retained per owner/)).toBeVisible()
  await expect(page.getByText(/5 local files of at most 10 MiB each \(50 MiB total\)/)).toBeVisible()

  await page.getByRole('button', { name: 'Delete import import-1' }).click()
  const importDialog = page.getByRole('alertdialog', { name: 'Delete this import body?' })
  await expect(importDialog.getByText(/no undelete, recovery window, or Yuno-managed backup/i)).toBeVisible()
  await importDialog.getByRole('button', { name: 'Confirm import body deletion' }).click()
  await expect(page.getByText('The selected import body was deleted.')).toBeVisible()

  await page.getByRole('textbox', { name: 'Interview session ID' }).fill('practice-run-e2e-1')
  await page.getByRole('button', { name: 'Delete session body' }).click()
  const sessionDialog = page.getByRole('alertdialog', { name: 'Delete this interview session body?' })
  await sessionDialog.getByRole('button', { name: 'Confirm session body deletion' }).click()
  await expect(page.getByText('The interview session body was deleted.')).toBeVisible()

  await page.getByRole('button', { name: 'Create export' }).click()
  const downloadLink = page.getByRole('link', { name: /Download yuno-export-v1-20260813T000200Z.json/ })
  await expect(downloadLink).toBeVisible()
  await expect(downloadLink).toHaveAttribute('download', 'yuno-export-v1-20260813T000200Z.json')
  const href = await downloadLink.getAttribute('href')
  expect(href).toBe('/api/v1/exports/export-e2e/download')
  const downloaded = await page.evaluate(async url => {
    const response = await fetch(url)
    return {
      status: response.status,
      disposition: response.headers.get('content-disposition'),
      body: await response.text(),
    }
  }, href!)
  expect(downloaded.status).toBe(200)
  expect(downloaded.disposition).toBe('attachment; filename="yuno-export-v1-20260813T000200Z.json"')
  const raw = downloaded.body
  expect(raw).toBe(canonicalJson(JSON.parse(raw)))
  const envelope = JSON.parse(raw) as { data: unknown; integrity: { algorithm: string; digest: string }; format: string; version: string }
  expect(envelope.format).toBe('yuno-portable-export')
  expect(envelope.version).toBe('1.0')
  expect(envelope.integrity.algorithm).toBe('sha256')
  const canonicalData = canonicalJson(envelope.data)
  expect(envelope.integrity.digest).toBe(createHash('sha256').update(canonicalData).digest('hex'))
})

test('reduced-motion preference suppresses non-essential motion', async ({ page, diagnostics }) => {
  void diagnostics
  test.setTimeout(90_000)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  for (const [route] of routes) {
    await open(page, route)
    expect(await longestMotionMs(page), `${route}: OS prefers-reduced-motion did not suppress motion`).toBeLessThanOrEqual(0.01)
  }

  // The app's own accessibility.reduced_motion setting must also suppress motion, independent of the OS preference.
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await page.evaluate(async () => {
    const current = await fetch('/api/v1/settings').then(response => response.json())
    await fetch('/api/v1/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', 'If-Match': String(current.row_version) },
      body: JSON.stringify({ accessibility: { reduced_motion: true } }),
    })
  })
  await open(page, '/app/jobs')
  await expect(page.locator('main.so-reduced-motion')).toBeVisible()
  expect(await longestMotionMs(page), '/app/jobs: app-level reduced-motion setting did not suppress motion').toBeLessThanOrEqual(0.01)
})

test('interview-hub Refresher and Question bank are query-string modes of the one route, not new routes', async ({ page, diagnostics }) => {
  void diagnostics
  const modeDetail = page.getByTestId('interview-mode-detail')
  const notFound = page.getByRole('heading', { name: /That learning view does not exist/i })

  await open(page, '/app/interview-hub?mode=refresher')
  expect(new URL(page.url()).pathname).toBe('/app/interview-hub')
  await expect(page.locator('[data-app="yuno-learning"]')).toHaveAttribute('data-page', 'interview-hub')
  await expect(page.locator('[data-app="yuno-learning"]')).toHaveAttribute('data-mode', 'refresher')
  await expect(modeDetail).toBeVisible()
  await expect(modeDetail).toHaveAttribute('data-mode', 'refresher')
  const refresherContent = page.locator('#sb-interview-mode-content')
  await expect(refresherContent).toHaveAttribute('data-interview-state', 'stale')
  await expect(refresherContent.getByText('Approved messaging guide')).toBeVisible()
  await expect(refresherContent.getByText('Recovery after commit was not yet supported.')).toBeVisible()

  await open(page, '/app/interview-hub?mode=questions')
  expect(new URL(page.url()).pathname).toBe('/app/interview-hub')
  await expect(page.locator('[data-app="yuno-learning"]')).toHaveAttribute('data-mode', 'questions')
  await expect(modeDetail).toBeVisible()
  await expect(modeDetail).toHaveAttribute('data-mode', 'questions')
  const questionsContent = page.locator('#sb-interview-mode-content')
  const selectedQuestion = questionsContent.getByRole('checkbox', { name: /Where is the durable idempotency boundary/i })
  await expect(selectedQuestion).toBeVisible()
  await expect(questionsContent.getByRole('button', { name: /Open Guided practice/i })).toBeDisabled()
  await selectedQuestion.check()
  await expect(questionsContent.getByRole('button', { name: /Open Guided practice/i })).toBeEnabled()
  await expect(questionsContent.getByText(/score|rubric outcome|post-submission review/i)).toHaveCount(0)

  await open(page, '/app/interview-hub?mode=bogus')
  await expect(page.getByRole('heading', { level: 1, name: /Choose the mode you need/i })).toBeVisible()
  await expect(page.locator('[data-app="yuno-learning"]')).not.toHaveAttribute('data-mode')
  await expect(modeDetail).toHaveCount(0)
  await expect(notFound).toHaveCount(0)

  await open(page, '/app/interview-hub')
  await expect(page.locator('.sb-bundle-workspace')).toHaveAttribute('data-interview-state', 'ready')
  await page.getByRole('button', { name: /Open Refresher/i }).click()
  await expect(page).toHaveURL(/\/app\/interview-hub\?mode=refresher$/)
  await expect(modeDetail).toBeVisible()
  await expect(modeDetail).toHaveAttribute('data-mode', 'refresher')

  await open(page, '/app/interview-hub')
  await page.getByRole('button', { name: /Open Question bank/i }).click()
  await expect(page).toHaveURL(/\/app\/interview-hub\?mode=questions$/)
  await expect(modeDetail).toBeVisible()
  await expect(modeDetail).toHaveAttribute('data-mode', 'questions')
})

test('focused Mock renders without GlobalHeader or CourseBand at every required viewport', async ({ page, diagnostics }) => {
  void diagnostics
  for (const viewport of viewports) {
    await page.setViewportSize(viewport)
    await open(page, '/app/mock?bundleId=bundle-e2e-1&bundleItemId=bundle-item-technical')
    await expect(page.locator('header.app-header')).toHaveCount(0)
    await expect(page.locator('.app-course-band')).toHaveCount(0)
    await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
  }
})

test('a failed backend read shows the route failure state with retry, and leaves not-found unaffected', async ({ page }) => {
  await page.route('**/api/v1/**', route => route.abort())

  await open(page, '/app/reports')
  const failure = page.locator('[data-route-state="failure"]')
  await expect(failure).toBeVisible()
  await expect(failure.getByRole('button', { name: 'Retry' })).toBeVisible()
  await expect(page.locator('header.app-header')).toBeVisible()

  await page.unroute('**/api/v1/**')
  await failure.getByRole('button', { name: 'Retry' }).click()
  await expect(page.getByText(/No terminal mock report is available/i)).toBeVisible()
  await expect(page.locator('[data-route-state]')).toHaveCount(0)

  await page.route('**/api/v1/**', route => route.abort())
  await page.goto('/app/home')
  await expect(page.getByRole('heading', { name: /That learning view does not exist/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /Open My learning/i })).toBeVisible()
})
