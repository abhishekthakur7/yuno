import { expect, test as base, type Page, type Request } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import type { DiagnosticSession, DiagnosticSetup } from '../../src/shared/api/diagnostics'
import type { GoalCreate, GoalWorkspace, LearnerProfile, ProfileUpdate, ResumeDestination } from '../../src/shared/api/profile-goals'

const routes = [
  ['/', /Continue Resilient order fulfillment/i],
  ['/app/onboarding', /Shape your classroom/i],
  ['/app/learn-roadmap', /Your editable roadmap/i],
  ['/app/topic-studio', /Implement an idempotency boundary/i],
  ['/app/interview-hub', /Choose the mode you need/i],
  ['/app/practice', /Reason through the failure boundary/i],
  ['/app/mock', /idempotency store is unavailable/i],
  ['/app/reports', /No terminal mock report is available/i],
  ['/app/evidence', /What your work supports/i],
  ['/app/imports', /Bring notes in as untrusted material/i],
  ['/app/canonical-updates', /Review changes before they reach this goal/i],
  ['/app/search', /Find a lesson, reading, review, or evidence record/i],
  ['/app/jobs', /Jobs and local activity/i],
  ['/app/settings', /^Settings$/i],
] as const

const viewports = [
  { width: 1440, height: 1000 },
  { width: 1366, height: 768 },
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
] as const

const fixtureDraft = 'Fail closed for reservation creation, return a retryable failure, and keep the message unacknowledged. Failing open can create an irreversible duplicate. Bound retries, expose the dependency failure, and recover from the queue rather than claiming availability.'
const exactDraft = '  Preserve this leading space.\nSecond line with a trailing space.  '
const practiceDraft = 'The commit-before-ack window needs an atomic idempotency key with an explicit retention policy.'

type Diagnostics = { consoleErrors: string[]; pageErrors: string[]; externalRequests: string[] }
type GoalPatch = { set_current?: boolean; resume_position?: string; resume_destination?: ResumeDestination; dismiss_recommendation_key?: string }

const defaultProfile: LearnerProfile = {
  experience: null,
  strengths: null,
  weaknesses: null,
  current_goal_id: 'goal-default',
  profile_revision: 1,
  updated_at: '2026-08-12T00:00:00Z',
}

function goalFixture(overrides: Partial<GoalWorkspace> = {}): GoalWorkspace {
  return {
    id: 'goal-default',
    name: 'Resilient order fulfillment',
    path: 'learn',
    subject: 'Java / Spring Boot · AWS',
    role: null,
    target_level: 'Senior',
    target_capability: 'implement',
    graph_version_id: 'graph-1',
    status: 'active',
    resume_position: 'idempotency-retry',
    resume_destination: '/app/topic-studio',
    last_accessed_at: null,
    dismissed_recommendation_keys: [],
    row_version: 1,
    created_at: '2026-08-12T00:00:00Z',
    updated_at: '2026-08-12T00:00:00Z',
    ...overrides,
  }
}

const test = base.extend<{ diagnostics: Diagnostics }>({
  diagnostics: async ({ page }, use) => {
    const diagnostics: Diagnostics = { consoleErrors: [], pageErrors: [], externalRequests: [] }
    page.on('console', message => {
      if (message.type() === 'error') diagnostics.consoleErrors.push(message.text())
    })
    page.on('pageerror', error => diagnostics.pageErrors.push(error.message))
    page.on('request', request => {
      if (!isLocalRequest(request)) diagnostics.externalRequests.push(`${request.method()} ${request.url()}`)
    })
    await use(diagnostics)
    expect.soft(diagnostics.consoleErrors, 'browser console errors').toEqual([])
    expect.soft(diagnostics.pageErrors, 'uncaught page errors').toEqual([])
    expect.soft(diagnostics.externalRequests, 'unexpected non-local requests').toEqual([])
  },
})

function isLocalRequest(request: Request) {
  const url = new URL(request.url())
  return ['data:', 'blob:'].includes(url.protocol) || ['localhost', '127.0.0.1', '::1', '[::1]'].includes(url.hostname.toLowerCase())
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    if (sessionStorage.getItem('learning-app-test-initialized')) return
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith('yuno.')) localStorage.removeItem(key)
    }
    sessionStorage.setItem('learning-app-test-initialized', 'true')
  })
  let profile = defaultProfile
  let goals = [goalFixture()]
  let diagnostic: DiagnosticSession | null = null
  await page.route('**/api/v1/profile', async route => {
    if (route.request().method() === 'PATCH') {
      profile = { ...profile, ...(route.request().postDataJSON() as ProfileUpdate), profile_revision: profile.profile_revision + 1 }
    }
    await route.fulfill({ json: profile })
  })
  await page.route('**/api/v1/canonical/versions', route => route.fulfill({ json: [{ id: 'graph-1', created_at: '', manifest_version: '1', published_at: '', supersedes_version_id: null, version_label: 'v1' }] }))
  await page.route('**/api/v1/goals', async route => {
    if (route.request().method() === 'POST') {
      const body = route.request().postDataJSON() as GoalCreate
      const created = goalFixture({
        ...body,
        id: `goal-${goals.length + 1}`,
        subject: body.subject ?? null,
        role: body.role ?? null,
        resume_position: null,
        resume_destination: null,
      })
      goals.push(created)
      await route.fulfill({ status: 201, json: created })
      return
    }
    await route.fulfill({ json: goals })
  })
  await page.route('**/api/v1/goals/**', async route => {
    const path = new URL(route.request().url()).pathname.split('/')
    const archived = path.at(-1) === 'archive'
    const id = path.at(archived ? -2 : -1)
    const index = goals.findIndex(goal => goal.id === id)
    if (index < 0) {
      await route.fulfill({ status: 404, json: { message: 'Not found' } })
      return
    }
    const body = route.request().method() === 'PATCH' ? route.request().postDataJSON() as GoalPatch : {}
    if (body.set_current) {
      profile = { ...profile, current_goal_id: id ?? null }
    }
    const current = goals.find(goal => goal.id === id)!
    goals[index] = { ...current, ...(body.resume_position !== undefined ? { resume_position: body.resume_position, resume_destination: body.resume_destination } : {}), dismissed_recommendation_keys: body.dismiss_recommendation_key ? [...current.dismissed_recommendation_keys, body.dismiss_recommendation_key] : current.dismissed_recommendation_keys, status: archived ? 'archived' : current.status, row_version: current.row_version + 1 }
    if (archived && profile.current_goal_id === id) profile = { ...profile, current_goal_id: null }
    await route.fulfill({ json: goals[index] })
  })
  await page.route('**/api/v1/diagnostics', async route => {
    if (route.request().method() !== 'POST') {
      await route.fulfill({ status: 405, json: { message: 'Method not allowed' } })
      return
    }
    const body = route.request().postDataJSON() as DiagnosticSetup
    diagnostic = {
      id: 'diagnostic-e2e',
      captured_graph_version_id: body.graph_version_id,
      question_set_version: 'diagnostic-fixture-v1',
      setup_inputs: {
        ...body.setup_inputs,
        path: body.path,
        subject: body.subject ?? null,
        role: body.role ?? null,
        target_level: body.target_level,
        target_capability: body.target_capability,
      },
      state: 'in-progress',
      untrusted_seed_kind: null,
      untrusted_seed_text: null,
      seed_skipped: false,
      diagnostic_skipped: false,
      answers: [],
      next_question: { ref: 'learn-baseline', prompt: 'What would you verify first?', sequence: 1, adaptive_context_version: 'diagnostic-fixture-v1' },
      started_at: '2026-08-12T00:00:00Z',
      paused_at: null,
      expires_at: null,
      failure_code: null,
      failure_reference: null,
      confirmed_goal_id: null,
      row_version: 1,
      created_at: '2026-08-12T00:00:00Z',
      updated_at: '2026-08-12T00:00:00Z',
    }
    await route.fulfill({ status: 201, json: diagnostic })
  })
  await page.route('**/api/v1/diagnostics/**', async route => {
    if (!diagnostic) {
      await route.fulfill({ status: 404, json: { message: 'Not found' } })
      return
    }
    const request = route.request()
    if (request.url().endsWith('/roadmap-preview')) {
      await route.fulfill({ json: {
        session_id: diagnostic.id,
        captured_graph_version_id: diagnostic.captured_graph_version_id,
        state: 'roadmap-preview',
        answer_count: diagnostic.answers.length,
        diagnostic_skipped: diagnostic.diagnostic_skipped,
        projection_version: 'diagnostic-preview-placeholder-v1',
        topic_recommendations: [],
      } })
      return
    }
    if (request.method() === 'PATCH') {
      const body = request.postDataJSON() as { action?: string; untrusted_seed_text?: string }
      const path = diagnostic.setup_inputs.path
      diagnostic = {
        ...diagnostic,
        ...(body.untrusted_seed_text ? {
          untrusted_seed_kind: path === 'interview_prep' ? 'questions' : 'notes',
          untrusted_seed_text: body.untrusted_seed_text,
        } : {}),
        ...(body.action === 'skip_notes' ? { seed_skipped: true } : {}),
        ...(body.action === 'skip_diagnostic' ? { state: 'skipped' as const, diagnostic_skipped: true, next_question: null } : {}),
        ...(body.action === 'open_roadmap_preview' ? { state: 'roadmap-preview' as const, next_question: null } : {}),
        ...(body.action === 'pause' ? { state: 'paused' as const, paused_at: '2026-08-12T00:01:00Z' } : {}),
        ...(body.action === 'resume' ? { state: 'resumed' as const, paused_at: null } : {}),
        row_version: diagnostic.row_version + 1,
        updated_at: '2026-08-12T00:01:00Z',
      }
    }
    await route.fulfill({ json: diagnostic })
  })
})

async function open(page: Page, route: string) {
  await page.goto(route)
  await expect(page.locator('[data-app="yuno-learning"]')).toBeVisible()
}

async function learningState(page: Page) {
  return page.evaluate(() => {
    const key = Object.keys(localStorage).filter(item => item.startsWith('yuno.learning.state.v1.') && item !== 'yuno.learning.state.v1.setup').at(-1)
    return JSON.parse(key ? localStorage.getItem(key) || 'null' : 'null')
  })
}

async function operationsState(page: Page) {
  return page.evaluate(() => JSON.parse(localStorage.getItem('yuno.operations.state.v1') || 'null'))
}

async function fillGoalBasics(page: Page, name = 'Resilient order fulfillment') {
  await page.getByRole('textbox', { name: 'Goal name' }).fill(name)
  await page.getByRole('textbox', { name: 'Subject' }).fill('Java / Spring Boot · AWS')
}

async function skipOptionalSetup(page: Page) {
  await page.getByRole('button', { name: /Skip to roadmap preview/i }).click()
  await expect(page.getByRole('heading', { level: 1, name: /Create a goal from this roadmap/i })).toBeVisible()
}

test('malformed nested storage falls back field by field without runtime errors or default loss', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/settings')
  await page.evaluate(() => {
    localStorage.setItem('yuno.learning.state.v1.goal-default', JSON.stringify({
      version: 1,
      onboarding: null,
      roadmap: { observability: { depth: 42, learnerState: [], skipped: 'yes' } },
      roadmapOrder: [null, 'observability'],
      practice: { questionIndex: -4, attempts: {}, hintRequested: 'yes' },
      mock: { priorTurns: [null], completedTurns: [null], reportKind: 'invented' },
      evidence: [null],
    }))
    localStorage.setItem('yuno.operations.state.v1', JSON.stringify({
      version: 1,
      owner: null,
      review: { duration: 'forever', retrieval: 'yes' },
      importStatements: [null, { id: 4, decision: 'trusted' }],
      acceptedUpdates: {},
    }))
  })
  await page.reload()

  await expect(page.getByRole('heading', { level: 1, name: /^Settings$/i })).toBeVisible()
  await expect.poll(async () => {
    const learning = await learningState(page)
    return {
      onboarding: learning?.onboarding,
      practice: learning?.practice,
      mockPriorTurns: learning?.mock.priorTurns.length,
      mockReport: learning?.mock.reportKind,
      observability: learning?.roadmap.observability,
      evidence: learning?.evidence,
    }
  }).toEqual({
    onboarding: { path: 'Learn', target: 'Senior', goalName: '', approved: false },
    practice: { questionIndex: 0, draft: '', hintRequested: false, mode: 'answering', attempts: [] },
    mockPriorTurns: 2,
    mockReport: null,
    observability: { id: 'observability', depth: 'Production', learnerState: 'unverified', skipped: false },
    evidence: [],
  })
  await expect.poll(async () => {
    const operations = await operationsState(page)
    return { owner: operations?.owner, review: operations?.review, imports: operations?.importStatements, updates: operations?.acceptedUpdates }
  }).toEqual({
    owner: { name: 'Aditi Rao', role: 'Senior backend engineer' },
    review: { enabled: true, duration: 15, cadence: 'Twice a week', retrieval: true, variedContext: true },
    imports: [],
    updates: [],
  })
})

test('persisted current lesson moves to an adjacent active lesson when that lesson is skipped', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/topic-studio')
  await page.evaluate(() => {
    const learning = JSON.parse(localStorage.getItem('yuno.learning.state.v1.goal-default') || '{}')
    localStorage.setItem('yuno.learning.state.v1.goal-default', JSON.stringify({
      ...learning,
      currentLessonId: 'observability',
      roadmap: {
        ...learning.roadmap,
        observability: { ...learning.roadmap.observability, skipped: true },
      },
    }))
  })
  await page.reload()

  await expect.poll(async () => (await learningState(page))?.currentLessonId).toBe('failure-injection')
  await expect(page.getByRole('heading', { level: 1, name: /Use bounded failure injection to inspect recovery/i })).toBeVisible()
})

async function expectNoHorizontalOverflow(page: Page, label: string) {
  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
    visualOffset: window.visualViewport?.offsetLeft ?? 0,
  }))
  expect(dimensions.document, `${label}: document overflow`).toBeLessThanOrEqual(dimensions.viewport)
  expect(dimensions.body, `${label}: body overflow`).toBeLessThanOrEqual(dimensions.viewport)
  expect(dimensions.visualOffset, `${label}: visual viewport panned`).toBeLessThanOrEqual(0.5)
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
  await page.setViewportSize({ width: 1440, height: 1000 })
  for (const [route] of routes) {
    await open(page, route)
    const { violations } = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
    expect(violations, `${route}: automated accessibility violations`).toEqual([])
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

test('switching A to B to A resumes A without leaking B learning state', async ({ page, diagnostics }) => {
  void diagnostics
  let goals = [
    goalFixture({ id: 'goal-a', name: 'Goal A', subject: 'Backend systems', resume_position: 'delivery-contract' }),
    goalFixture({ id: 'goal-b', name: 'Goal B', subject: 'Backend systems', resume_position: 'observability' }),
  ]
  let currentGoalId = 'goal-a'
  await page.addInitScript(() => {
    const base = { version: 1, onboarding: { path: 'Learn', target: 'Senior', goalName: '', approved: false } }
    localStorage.setItem('yuno.learning.state.v1.goal-a', JSON.stringify({ ...base, currentLessonId: 'delivery-contract' }))
    localStorage.setItem('yuno.learning.state.v1.goal-b', JSON.stringify({ ...base, currentLessonId: 'observability' }))
  })
  await page.route('**/api/v1/profile', route => route.fulfill({ json: { ...defaultProfile, current_goal_id: currentGoalId } }))
  await page.route('**/api/v1/goals', route => route.fulfill({ json: goals }))
  await page.route('**/api/v1/goals/**', async route => {
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

test('onboarding can skip optional setup and explicitly create a goal workspace', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/onboarding')
  await fillGoalBasics(page)
  await expect.poll(async () => (await learningState(page))?.onboarding.approved).toBe(false)
  await skipOptionalSetup(page)
  await expect.poll(async () => (await learningState(page))?.onboarding.approved).toBe(false)
  await page.getByRole('button', { name: /Create goal from roadmap/i }).click()
  await expect(page).toHaveURL(/\/app\/learn-roadmap$/)
  await expect(page.getByText(/Unapproved roadmap preview/i)).toBeVisible()
})

test('onboarding preview keeps full depth labels usable and tablet controls inside their card', async ({ page, diagnostics }) => {
  void diagnostics
  await page.setViewportSize({ width: 1366, height: 768 })
  await open(page, '/app/onboarding')
  await fillGoalBasics(page)
  await skipOptionalSetup(page)
  const depthWidth = await page.getByRole('combobox', { name: /^Depth$/i }).first().evaluate(element => element.getBoundingClientRect().width)
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
  await expect.poll(async () => (await learningState(page))?.evidence.length).toBe(0)
})

test('roadmap depth, knowledge, skip, and order edits survive reload', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/onboarding')
  await fillGoalBasics(page)
  await skipOptionalSetup(page)
  await page.getByRole('button', { name: /Create goal from roadmap/i }).click()
  await open(page, '/app/learn-roadmap')
  await page.getByRole('combobox', { name: /^Depth$/i }).first().selectOption('Production')
  await page.getByRole('combobox', { name: /^Knowledge$/i }).first().selectOption('new')
  await page.getByRole('button', { name: /^Skip$/i }).first().click()
  await page.getByRole('button', { name: /Move Model the delivery contract before choosing a pattern later/i }).click()
  await expect.poll(async () => (await learningState(page))?.roadmapOrder.indexOf('delivery-contract')).toBe(1)
  await expect.poll(async () => (await learningState(page))?.onboarding.approved).toBe(false)
  await page.reload()
  await expect(page.getByRole('button', { name: /Move Model the delivery contract before choosing a pattern earlier/i })).toBeEnabled()
  await expect.poll(async () => {
    const state = await learningState(page)
    const choice = state?.roadmap['delivery-contract']
    return { depth: choice?.depth, knowledge: choice?.learnerState, skipped: choice?.skipped, position: state?.roadmapOrder.indexOf('delivery-contract') }
  }).toEqual({ depth: 'Production', knowledge: 'new', skipped: true, position: 1 })
})

test('skip and reorder change active course position and previous-next progression', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/learn-roadmap')
  const atomicRow = page.getByRole('article').filter({ hasText: /Keep the business write and duplicate marker atomic/i })
  await atomicRow.getByRole('button', { name: /^Skip$/i }).click()
  await page.getByRole('button', { name: /^03 Implement an idempotency boundary under concurrent retries/i }).click()
  await expect(page.getByText(/Position 3 of 10 active/i)).toBeVisible()
  await expect(page.getByRole('button', { name: /Next: Design for delayed, duplicated, and out-of-order deliveries/i })).toBeVisible()
  await expect(page.getByRole('button', { name: /Next: Keep the business write and duplicate marker atomic/i })).toHaveCount(0)
})

test('roadmap and curriculum selections change and preserve the current lesson', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/learn-roadmap')
  await page.getByRole('button', { name: /^08 Instrument retry, duplicate, and latency signals/i }).click()
  await expect(page).toHaveURL(/\/app\/topic-studio$/)
  await expect(page.getByRole('heading', { level: 1, name: /Instrument retry, duplicate, and latency signals/i })).toBeVisible()
  await expect.poll(async () => (await learningState(page))?.currentLessonId).toBe('observability')
  await page.reload()
  await expect(page.getByRole('heading', { level: 1, name: /Instrument retry, duplicate, and latency signals/i })).toBeVisible()
  await page.getByRole('button', { name: /^Use bounded failure injection to inspect recovery/i }).click()
  await expect(page.getByRole('heading', { level: 1, name: /Use bounded failure injection to inspect recovery/i })).toBeVisible()
  await expect.poll(async () => (await learningState(page))?.currentLessonId).toBe('failure-injection')
})

test('Topic Studio Run is exploratory and Submit alone appends evidence', async ({ page, diagnostics }) => {
  void diagnostics
  await page.setViewportSize({ width: 1366, height: 768 })
  await open(page, '/app/topic-studio')
  const openLab = page.getByRole('button', { name: /Open implementation lab/i })
  const openLabBox = await openLab.boundingBox()
  expect(openLabBox).not.toBeNull()
  expect((openLabBox?.y ?? 0) + (openLabBox?.height ?? 0), 'primary lesson action is in the first viewport').toBeLessThanOrEqual(768)
  await openLab.click()
  await expect(page.getByRole('textbox', { name: /Java code/i })).toBeInViewport()
  await expect.poll(async () => (await learningState(page))?.evidence.length).toBe(0)
  await page.getByRole('button', { name: /Run static checks/i }).click()
  await expect(page.getByText(/Carries a stable request key/i)).toBeVisible()
  await expect.poll(async () => (await learningState(page))?.runResult?.status).toBeTruthy()
  await expect.poll(async () => (await learningState(page))?.evidence.length).toBe(0)
  await page.getByRole('button', { name: /Submit evidence/i }).click()
  await expect.poll(async () => (await learningState(page))?.evidence.length).toBe(1)
})

test('Practice reveals a requested hint, then feedback, repair, and append-only history', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/practice')
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
  await page.getByRole('textbox', { name: /Your response/i }).fill(`${practiceDraft} Repaired.`)
  await page.getByRole('button', { name: /Submit response/i }).click()
  await expect(page.getByText(/Earlier attempts \(1\)/i)).toBeVisible()
  await expect.poll(async () => (await learningState(page))?.practice.attempts.length).toBe(2)
})

test('Mock pause/resume preserves the exact draft and evaluation appears only after terminal completion', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/mock')
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
  await page.getByRole('button', { name: /Open Mock interview/i }).click()
  await expect(page.getByRole('textbox', { name: /Your response/i })).toHaveValue(exactDraft)
  await expect.poll(async () => (await learningState(page))?.mock.draft).toBe(exactDraft)
  await page.getByRole('textbox', { name: /Your response/i }).fill(fixtureDraft)
  const complete = page.getByRole('button', { name: /Complete interview/i })
  await complete.click()
  const completeDialog = page.getByRole('alertdialog', { name: /Complete the interview/i })
  await completeDialog.getByRole('button', { name: /Return to answer/i }).click()
  await expect(complete).toBeFocused()
  await expect(page.getByText(/Facts in transcript/i)).toHaveCount(0)
  await complete.click()
  await completeDialog.getByRole('button', { name: /Complete & view report/i }).click()
  await expect(page).toHaveURL(/\/app\/reports$/)
  await expect(page.getByRole('heading', { name: /Facts in transcript/i })).toBeVisible()
  await expect.poll(async () => (await learningState(page))?.mock.reportKind).toBe('fixture-evaluation')
})

test('Evidence is unavailable before submission and derives its conclusion from submitted learner state', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/evidence')
  await expect(page.getByRole('heading', { name: /No submitted lab evidence is available yet/i })).toBeVisible()
  await page.getByRole('button', { name: /Open Topic Studio/i }).click()
  await expect.poll(async () => (await learningState(page))?.currentLessonId).toBe('idempotency-retry')
  await page.getByRole('button', { name: /Submit evidence/i }).click()
  const conclusion = (await learningState(page))?.evidence.at(-1)?.conclusion
  await open(page, '/app/evidence')
  await expect(page.getByRole('heading', { name: conclusion })).toBeVisible()
  await page.getByRole('button', { name: /Open transfer check/i }).click()
  await expect(page).toHaveURL(/\/app\/practice$/)
})

test('parsed imports remain personal untrusted material and cannot create evidence or completion', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/imports')
  const source = '# Notes\n- SQS may redeliver the same message after a durable commit.\n- A lookup before a write does not arbitrate concurrent requests.'
  await page.getByRole('textbox', { name: /Paste Markdown or plain text/i }).fill(source)
  await page.getByRole('button', { name: /Parse locally/i }).click()
  await expect(page.getByText(/Parsed as untrusted/i)).toBeVisible()
  await expect(page.getByText(/^untrusted$/i)).toHaveCount(2)
  await expect(page.getByText(/Mapping is a learner decision, not verification/i)).toBeVisible()
  await expect.poll(async () => (await operationsState(page))?.importStatements.every((item: { decision: string }) => item.decision === 'untrusted')).toBe(true)
  await expect.poll(async () => (await learningState(page))?.evidence.length).toBe(0)
})

test('canonical curriculum updates stay pending until an explicit acceptance action', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/canonical-updates')
  await expect.poll(async () => (await operationsState(page))?.updateDecision).toBe('pending')
  await expect.poll(async () => (await operationsState(page))?.goalVersion).toBe('2026.07')
  await expect(page.getByLabel(/Local goal pinned to 2026\.07/i)).toBeVisible()
  await expect(page.getByText(/nothing changes until you explicitly accept a selection/i)).toBeVisible()
  await page.evaluate(() => {
    const value = JSON.parse(localStorage.getItem('yuno.operations.state.v1') || '{}')
    delete value.goalVersion
    localStorage.setItem('yuno.operations.state.v1', JSON.stringify(value))
  })
  await page.reload()
  await expect.poll(async () => (await operationsState(page))?.updateDecision).toBe('pending')
  await expect.poll(async () => (await operationsState(page))?.goalVersion).toBe('2026.07')
  await page.getByRole('checkbox', { name: /Select Dead-letter recovery/i }).uncheck()
  await page.getByRole('radio', { name: /Adopt the new canonical wording/i }).check()
  await page.getByRole('checkbox', { name: /Approve this exact local selection/i }).check()
  await page.getByRole('button', { name: /Accept selected/i }).click()
  await expect(page.getByText(/2 selected changes accepted locally/i)).toBeVisible()
  await expect(page.getByText(/No server or canonical source was mutated/i)).toBeVisible()
  await expect.poll(async () => {
    const state = await operationsState(page)
    return { decision: state?.updateDecision, goalVersion: state?.goalVersion, updates: state?.acceptedUpdates, conflict: state?.acceptedConflictResolution }
  }).toEqual({ decision: 'accepted', goalVersion: '2026.08', updates: ['visibility', 'idempotency'], conflict: 'canonical-adopted' })
  await expect(page.getByLabel(/Local goal pinned to 2026\.08/i)).toBeVisible()
  await page.reload()
  await expect.poll(async () => {
    const state = await operationsState(page)
    return { goalVersion: state?.goalVersion, updates: state?.acceptedUpdates, conflict: state?.acceptedConflictResolution }
  }).toEqual({ goalVersion: '2026.08', updates: ['visibility', 'idempotency'], conflict: 'canonical-adopted' })
  await expect(page.getByRole('checkbox', { name: /Select Dead-letter recovery/i })).not.toBeChecked()
  await expect(page.getByRole('radio', { name: /Adopt the new canonical wording/i })).toBeChecked()
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

  await open(page, '/app/practice')
  const hint = page.getByRole('button', { name: /Request hint/i })
  await hint.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByText(/Name the failure window first/i)).toBeVisible()

  await open(page, '/app/topic-studio')
  await expect(page.getByRole('button', { name: /Lesson tools/i })).toBeVisible()
  const notesTab = page.getByRole('tab', { name: /Notes/i })
  await notesTab.focus()
  await page.keyboard.press('ArrowRight')
  await expect(page.getByRole('tab', { name: /Resources/i })).toHaveAttribute('aria-selected', 'true')
  await page.keyboard.press('ArrowRight')
  await expect(page.getByRole('tab', { name: /Help/i })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByText(/Topic help is unavailable/i)).toBeVisible()

  const courseContent = page.getByRole('button', { name: /Course content/i })
  await courseContent.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('dialog', { name: /Course content/i })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog', { name: /Course content/i })).toHaveCount(0)
  await expect(courseContent).toBeFocused()
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
  const deleteImports = page.getByRole('button', { name: /Delete imports/i }).first()
  await deleteImports.click()
  const dialog = page.getByRole('alertdialog', { name: /Delete all imported material/i })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: /Cancel/i }).click()
  await expect(deleteImports).toBeFocused()
})

test('reduced-motion preference suppresses non-essential motion', async ({ page, diagnostics }) => {
  void diagnostics
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await open(page, '/app/jobs')
  const longestMotionMs = await page.evaluate(() => {
    const times = (value: string) => value.split(',').map(token => token.trim().endsWith('ms') ? parseFloat(token) : parseFloat(token) * 1000)
    return Math.max(0, ...Array.from(document.querySelectorAll('[data-app="yuno-learning"] *')).flatMap(element => {
      const style = getComputedStyle(element)
      return [...times(style.animationDuration), ...times(style.transitionDuration)]
    }))
  })
  expect(longestMotionMs).toBeLessThanOrEqual(0.01)
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

  await open(page, '/app/interview-hub?mode=questions')
  expect(new URL(page.url()).pathname).toBe('/app/interview-hub')
  await expect(page.locator('[data-app="yuno-learning"]')).toHaveAttribute('data-mode', 'questions')
  await expect(modeDetail).toBeVisible()
  await expect(modeDetail).toHaveAttribute('data-mode', 'questions')

  await open(page, '/app/interview-hub?mode=bogus')
  await expect(page.getByRole('heading', { level: 1, name: /Choose the mode you need/i })).toBeVisible()
  await expect(page.locator('[data-app="yuno-learning"]')).not.toHaveAttribute('data-mode')
  await expect(modeDetail).toHaveCount(0)
  await expect(notFound).toHaveCount(0)

  await open(page, '/app/interview-hub')
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
    await open(page, '/app/mock')
    await expect(page.locator('header.app-header')).toHaveCount(0)
    await expect(page.locator('.app-course-band')).toHaveCount(0)
    await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
  }
})

// Deliberately does not take the `diagnostics` fixture: aborting the API reads
// is the point of the test, and a blocked request is a console error by design.
test('a failed backend read shows the route failure state with retry, and leaves not-found unaffected', async ({ page }) => {
  await page.route('**/api/v1/**', route => route.abort())

  await open(page, '/app/reports')
  const failure = page.locator('[data-route-state="failure"]')
  await expect(failure).toBeVisible()
  await expect(failure.getByRole('button', { name: 'Retry' })).toBeVisible()
  // The shell itself survives: the failure replaces the page body only.
  await expect(page.locator('header.app-header')).toBeVisible()

  // Recovery reconciles the authoritative GET resource (spec §2.1).
  await page.unroute('**/api/v1/**')
  await failure.getByRole('button', { name: 'Retry' }).click()
  await expect(page.getByText(/No terminal mock report is available/i)).toBeVisible()
  await expect(page.locator('[data-route-state]')).toHaveCount(0)

  // Not-found is unaffected by backend errors.
  await page.route('**/api/v1/**', route => route.abort())
  await page.goto('/app/home')
  await expect(page.getByRole('heading', { name: /That learning view does not exist/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /Open My learning/i })).toBeVisible()
})
