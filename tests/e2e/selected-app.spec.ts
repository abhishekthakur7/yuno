import { expect, test as base, type Page, type Request } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import type { DiagnosticPreviewEdit, DiagnosticSession, DiagnosticSetup } from '../../src/shared/api/diagnostics'
import type { Assessment, EvidenceDetail, GoalProgress, Source } from '../../src/shared/api/evidence'
import type { GoalCreate, GoalWorkspace, LearnerProfile, ProfileUpdate, ResumeDestination } from '../../src/shared/api/profile-goals'
import type { OwnerSettings, OwnerSettingsPatch } from '../../src/shared/api/settings'

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
const roadmapTopics = [
  ['delivery-contract', 'Model the delivery contract before choosing a pattern'],
  ['commit-window', 'Trace the commit-before-acknowledgement failure window'],
  ['idempotency-retry', 'Implement an idempotency boundary under concurrent retries'],
] as const

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
      if (message.type() === 'error' && !message.text().includes('409 (Conflict)')) diagnostics.consoleErrors.push(message.text())
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
  let previewEdits: DiagnosticPreviewEdit[] = []
  let imports: Array<Record<string, unknown>> = []
  let importStatements: Array<Record<string, unknown>> = []
  let notebookEntries: Array<Record<string, unknown>> = []
  let evidenceRecords: EvidenceDetail[] = []
  let assessments: Assessment[] = []
  let ownerSettings: OwnerSettings = {
    progress_display: 'detailed',
    row_version: 1,
  }
  const evidenceSources: Source[] = [
    {
      id: 'source-e2e-withdrawn', origin: 'synthetic-fixture', source_type: 'documentation',
      title: 'Withdrawn evidence fixture advisory', publisher: 'Fixture publisher', canonical_url: null,
      license_status: 'synthetic', availability_status: 'withdrawn',
      created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z',
    },
  ]
  const progress: GoalProgress = {
    authoritative: false,
    effective_now: '2026-08-12T00:00:00Z',
    input_hash: 'progress-input-e2e',
    rule_version: 'fixture-v0',
    coverage: { classification: 'partial', definition: 'Breadth supported by qualified evidence.', supporting_evidence_refs: [], uncertainty: 'Fixture-only.' },
    proficiency: { classification: 'partial', definition: 'Capability demonstrated in context.', supporting_evidence_refs: [], uncertainty: 'Fixture-only.' },
    retention: { classification: 'unverified', definition: 'Durability across delayed recall.', supporting_evidence_refs: [], uncertainty: 'No delayed reassessment.' },
    readiness: { classification: 'partial', definition: 'Current support against the declared target.', supporting_evidence_refs: [], uncertainty: 'Not an interview or hiring prediction.' },
  }
  let reviewPreferences = {
    enabled: true,
    duration_minutes: 15,
    cadence: 'twice-weekly',
    retrieval_enabled: true,
    varied_context_enabled: true,
    scheduling_version: 'fixture-v0',
    row_version: 1,
    updated_at: '2026-08-12T00:00:00Z',
  }
  let reviewItems: Array<Record<string, unknown>> = [{
    id: 'review-e2e-1', goal_id: 'goal-default', topic_stable_id: 'idempotency-retry',
    prompt_ref: 'fixture-review-e2e-1', prompt_type: 'application',
    prompt: 'Apply the duplicate boundary to a redelivery after commit.',
    answer: 'Commit the business decision and duplicate marker atomically.',
    status: 'due', due_at: '2026-08-12T00:00:00Z', interval_label: 'fixture-due',
    context: 'The acknowledgement was lost after the durable business write.',
    scheduling_version: 'fixture-v0', failure_reference: null, row_version: 1,
    created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z',
  }]
  let projectedTopics = roadmapTopics.map(([stable_id, title]) => ({
    stable_id, title, subject: 'Java / Spring Boot · AWS', level_tag: 'Senior',
    target_capability: 'implement', scope_tags: ['java'], classification: 'unverified' as const,
    recommended_depth: 'Implementation', depth_override: null as string | null, is_skipped: false,
    has_transferred_evidence: false, explanation: 'Fixture projection', pending_proposals: [], conflicts: [],
  }))
  const correctedClassifications = new Map<string, 'likely-known' | 'partial' | 'unverified' | 'new'>()
  await page.route('**/api/v1/imports**', async route => {
    const request = route.request()
    const url = new URL(request.url())
    const parts = url.pathname.split('/')
    const importId = parts.at(-1)
    if (url.pathname.endsWith('/parse') || url.pathname.endsWith('/reprocess')) {
      const id = parts.at(-2)!
      const record = imports.find(item => item.id === id)
      if (record) {
        record.status = 'parsed-untrusted'
        record.parser_version = 'markdown-v1'
        record.row_version = Number(record.row_version) + 1
        if (importStatements.length === 0) importStatements = [
          { id: 'statement-1', import_id: id, sequence: 1, parser_version: 'markdown-v1', original_text: 'SQS may redeliver the same message after a durable commit.', original_hash: 'statement-hash-1', normalized_text: 'sqs may redeliver the same message after a durable commit', normalized_hash: 'normalized-hash-1', confidence: .98, duplicate_of_statement_id: null, trust_state: 'untrusted', mapping_state: 'unmapped', corrected_text: null, row_version: 1, created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z', mapping: null },
          { id: 'statement-2', import_id: id, sequence: 2, parser_version: 'markdown-v1', original_text: 'A lookup before a write does not arbitrate concurrent requests.', original_hash: 'statement-hash-2', normalized_text: 'a lookup before a write does not arbitrate concurrent requests', normalized_hash: 'normalized-hash-2', confidence: .94, duplicate_of_statement_id: null, trust_state: 'untrusted', mapping_state: 'unmapped', corrected_text: null, row_version: 1, created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z', mapping: null },
        ]
      }
      await route.fulfill({ status: 202, json: { job_id: 'import-job-1', kind: url.pathname.endsWith('/parse') ? 'parse_import' : 'reprocess_import', status: 'queued', enqueued_at: '2026-08-12T00:00:00Z', deduplicated: false } })
      return
    }
    if (url.pathname.endsWith('/statements')) {
      await route.fulfill({ json: importStatements.filter(item => item.import_id === parts.at(-2)) })
      return
    }
    if (request.method() === 'POST' && url.pathname.endsWith('/imports')) {
      const body = request.postDataJSON() as { goal_id: string; import_type: string; original_content: string }
      const created = { id: `import-${imports.length + 1}`, ...body, original_hash: 'exact-original-hash', parser_version: 'pending', status: 'selected', failure_code: null, failure_reference: null, row_version: 1, created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z' }
      imports = [created, ...imports]
      await route.fulfill({ status: 201, json: created })
      return
    }
    if (importId?.startsWith('import-')) {
      await route.fulfill({ json: imports.find(item => item.id === importId) })
      return
    }
    await route.fulfill({ json: imports.filter(item => !url.searchParams.get('goal_id') || item.goal_id === url.searchParams.get('goal_id')) })
  })
  await page.route('**/api/v1/import-statements/**', async route => {
    const request = route.request()
    const parts = new URL(request.url()).pathname.split('/')
    const action = parts.at(-1)!
    const statementId = parts.at(-2)!
    const index = importStatements.findIndex(item => item.id === statementId)
    const current = importStatements[index]!
    if (action === 'map') {
      const body = request.postDataJSON() as { goal_id: string; topic_id: string }
      importStatements[index] = { ...current, mapping_state: 'mapped', row_version: Number(current.row_version) + 1, mapping: { ...body, graph_version_id: 'graph-1', decision: 'approved', accepted_at: '2026-08-12T00:01:00Z', revoked_at: null } }
    } else if (action === 'verify') importStatements[index] = { ...current, trust_state: 'verified', row_version: Number(current.row_version) + 1 }
    else if (action === 'dismiss') importStatements[index] = { ...current, trust_state: 'dismissed', row_version: Number(current.row_version) + 1 }
    if (action === 'map') await route.fulfill({ json: { statement: importStatements[index], mapping: importStatements[index]!.mapping, topic_imports_hash: { goal_id: 'goal-default', topic_id: 'delivery-contract', graph_version_id: 'graph-1', imports_hash: 'mapped-imports-hash', updated_at: '2026-08-12T00:01:00Z' } } })
    else await route.fulfill({ json: importStatements[index] })
  })
  await page.route('**/api/v1/notebook/**', async route => {
    const request = route.request()
    const entryId = new URL(request.url()).pathname.split('/').at(-1)!
    const index = notebookEntries.findIndex(item => item.id === entryId)
    if (index < 0) {
      await route.fulfill({ status: 404, json: { message: 'Not found' } })
      return
    }
    if (request.method() === 'PATCH') {
      notebookEntries[index] = {
        ...notebookEntries[index],
        ...(request.postDataJSON() as Record<string, unknown>),
        row_version: Number(notebookEntries[index]!.row_version) + 1,
        updated_at: '2026-08-12T00:02:00Z',
      }
      await route.fulfill({ json: notebookEntries[index] })
      return
    }
    notebookEntries.splice(index, 1)
    await route.fulfill({ status: 204, body: '' })
  })
  await page.route('**/api/v1/reviews/**', async route => {
    const request = route.request()
    const parts = new URL(request.url()).pathname.split('/')
    const reviewId = parts.at(-2)!
    const index = reviewItems.findIndex(item => item.id === reviewId)
    if (index < 0) {
      await route.fulfill({ status: 404, json: { message: 'Not found' } })
      return
    }
    if (parts.at(-1) === 'attempts') {
      const body = request.postDataJSON() as { response: string; confidence?: string }
      const answer = String(reviewItems[index]!.answer)
      reviewItems[index] = {
        ...reviewItems[index], status: 'completed', row_version: Number(reviewItems[index]!.row_version) + 1,
        updated_at: '2026-08-12T00:02:00Z',
      }
      await route.fulfill({ status: 201, json: {
        id: 'review-attempt-e2e-1', goal_id: reviewItems[index]!.goal_id,
        review_item_id: reviewId, response: body.response, confidence: body.confidence ?? null,
        feedback: null, correction: null, next_interval_label: null,
        context_variation: null, context_result: null, scheduling_version: 'fixture-v0',
        created_at: '2026-08-12T00:02:00Z', review_status: 'completed', revealed_answer: answer,
      } })
      return
    }
    reviewItems[index] = {
      ...reviewItems[index], status: 'dismissed', row_version: Number(reviewItems[index]!.row_version) + 1,
      updated_at: '2026-08-12T00:02:00Z',
    }
    await route.fulfill({ json: { ...reviewItems[index], answer: null } })
  })
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
    if (path.at(-1) === 'overlay-proposals') {
      await route.fulfill({ json: [] })
      return
    }
    if (path.at(-1) === 'notebook') {
      const scopedGoalId = path.at(-2)!
      if (route.request().method() === 'POST') {
        const body = route.request().postDataJSON() as Record<string, unknown>
        const entry = {
          id: `notebook-entry-${notebookEntries.length + 1}`, goal_id: scopedGoalId,
          ...body, evidence_id: body.evidence_id ?? null, source_id: body.source_id ?? null,
          row_version: 1, created_at: '2026-08-12T00:01:00Z', updated_at: '2026-08-12T00:01:00Z',
        }
        notebookEntries = [entry, ...notebookEntries]
        await route.fulfill({ status: 201, json: entry })
        return
      }
      await route.fulfill({ json: notebookEntries.filter(item => item.goal_id === scopedGoalId) })
      return
    }
    if (path.at(-1) === 'review-preferences') {
      const scopedGoalId = path.at(-2)!
      if (route.request().method() === 'PATCH') {
        const body = route.request().postDataJSON() as Record<string, unknown>
        reviewPreferences = {
          ...reviewPreferences,
          ...body,
          row_version: reviewPreferences.row_version + 1,
          updated_at: '2026-08-12T00:02:00Z',
        }
        if (body.enabled === false) {
          reviewItems = reviewItems.map(item => item.goal_id === scopedGoalId && (item.status === 'ready' || item.status === 'due')
            ? { ...item, status: 'disabled', row_version: Number(item.row_version) + 1 }
            : item)
        }
      }
      await route.fulfill({ json: { goal_id: scopedGoalId, ...reviewPreferences } })
      return
    }
    if (path.at(-1) === 'reviews') {
      const scopedGoalId = path.at(-2)!
      await route.fulfill({ json: {
        goal_id: scopedGoalId,
        enabled: reviewPreferences.enabled,
        scheduling_version: reviewPreferences.scheduling_version,
        items: reviewItems.filter(item => item.goal_id === scopedGoalId).map(item => ({ ...item, answer: null })),
      } })
      return
    }
    if (path.at(-1) === 'layers' && path.includes('topics')) {
      const scopedGoalId = path.at(-4)!
      const topicId = path.at(-2)!
      await route.fulfill({ json: {
        goal_id: scopedGoalId, graph_version_id: 'graph-1', topic_id: topicId,
        conversation_scope: `${scopedGoalId}:${topicId}`,
        layers: ['Essential', 'Implementation', 'Internals', 'Production', 'Alternatives', 'Failures', 'Interview', 'Sources'].map((layer, index) => ({
          layer, state: 'ready', revision_id: `${topicId}-${layer}`, markdown_hash: `hash-${topicId}-${layer}`,
          markdown: `# ${layer}\n\nApproved fixture content for ${topicId}.`,
          checkpoint: {
            scenario: `Apply ${topicId} under a declared failure constraint.`, constraints: ['Keep the durable boundary explicit.'],
            target_capability: 'implement', expected_artifact: 'A reviewed implementation or design decision.', estimated_minutes: 30 + index,
            rubric: ['Names the boundary and trade-off.'], assumptions: ['The approved fixture graph applies.'],
            evidence_criterion: 'Submit the artifact and explain the decision.', limitation: 'Static review cannot prove runtime behavior.',
          },
        })),
      } })
      return
    }
    const goalId = path.at(-2)
    if (path.at(-1) === 'roadmap') {
      await route.fulfill({ json: {
        goal_id: goalId,
        graph_version_id: 'graph-1',
        projection_version: 'projection-e2e-v1',
        state: 'ready',
        topics: projectedTopics,
      } })
      return
    }
    const command = path.at(-1)
    if (requestIsRoadmapCommand(command) && route.request().method() === 'POST') {
      const body = route.request().postDataJSON() as Record<string, unknown>
      if (command === 'depth-overrides') {
        projectedTopics = projectedTopics.map(topic => topic.stable_id === body.topic_stable_id ? { ...topic, depth_override: String(body.depth) } : topic)
      } else if (command === 'skip-decisions') {
        projectedTopics = projectedTopics.map(topic => topic.stable_id === body.topic_stable_id ? { ...topic, is_skipped: Boolean(body.skipped) } : topic)
      } else if (command === 'order-constraints') {
        const before = projectedTopics.findIndex(topic => topic.stable_id === body.before_topic_id)
        const after = projectedTopics.findIndex(topic => topic.stable_id === body.after_topic_id)
        if (before >= 0 && after >= 0) {
          const [moved] = projectedTopics.splice(before, 1)
          const target = projectedTopics.findIndex(topic => topic.stable_id === body.after_topic_id)
          projectedTopics.splice(target, 0, moved!)
        }
      } else if (command === 'corrections') {
        correctedClassifications.set(String(body.topic_stable_id), body.classification as 'likely-known' | 'partial' | 'unverified' | 'new')
      }
      await route.fulfill({ json: { checkpoint_saved: true, projection: { goal_id: goalId, graph_version_id: 'graph-1', projection_version: crypto.randomUUID(), state: 'ready', topics: projectedTopics } } })
      return
    }
    if (path.at(-1) === 'learning-states') {
      await route.fulfill({ json: roadmapTopics.map(([topic_stable_id]) => ({
        topic_stable_id, classification: 'unverified', corrected_classification: correctedClassifications.get(topic_stable_id) ?? null,
        recommended_depth: 'Implementation', origin: 'diagnostic', explanation: 'Fixture diagnostic state',
      })) })
      return
    }
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
    const request = route.request()
    if (request.url().endsWith('/active')) {
      await route.fulfill({ json: diagnostic })
      return
    }
    if (!diagnostic) {
      await route.fulfill({ status: 404, json: { message: 'Not found' } })
      return
    }
    if (request.url().endsWith('/roadmap-preview')) {
      if (request.method() === 'PUT') {
        previewEdits = (request.postDataJSON() as { edits?: DiagnosticPreviewEdit[] }).edits ?? []
      }
      await route.fulfill({ json: {
        session_id: diagnostic.id,
        captured_graph_version_id: diagnostic.captured_graph_version_id,
        state: 'roadmap-preview',
        answer_count: diagnostic.answers.length,
        diagnostic_skipped: diagnostic.diagnostic_skipped,
        projection_version: 'diagnostic-preview-e2e-v1',
        saved_edits: previewEdits,
        topic_recommendations: roadmapTopics.map(([stable_id, title]) => ({
          stable_id, title, classification: 'unverified', recommended_depth: 'Implementation',
          depth_override: null, is_skipped: false,
        })),
      } })
      return
    }
    if (request.url().endsWith('/confirm-goal')) {
      if (diagnostic.confirmed_goal_id) {
        await route.fulfill({ status: 409, json: { message: 'Diagnostic session already confirmed' } })
        return
      }
      const created = goalFixture({
        id: 'goal-confirmed',
        name: String(diagnostic.setup_inputs.goal_name),
        subject: String(diagnostic.setup_inputs.subject),
        resume_position: null,
        resume_destination: null,
      })
      goals = [...goals, created]
      profile = { ...profile, current_goal_id: created.id, profile_revision: profile.profile_revision + 1 }
      diagnostic = { ...diagnostic, state: 'confirmed', confirmed_goal_id: created.id, row_version: diagnostic.row_version + 1 }
      await route.fulfill({ status: 201, json: created })
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
  await page.route('**/api/v1/goals/*/evidence', async route => {
    const request = route.request()
    const goalId = new URL(request.url()).pathname.split('/').at(-2)!
    if (request.method() === 'POST') {
      const body = request.postDataJSON() as {
        topic_stable_id: string; evidence_type: string; capability: string; summary: string;
        origin: string; content: string; content_version: string
      }
      const created: EvidenceDetail = {
        id: `evidence-e2e-${evidenceRecords.length + 1}`, goal_id: goalId,
        topic_stable_id: body.topic_stable_id, evidence_type: body.evidence_type,
        capability: body.capability, summary: body.summary, origin: body.origin,
        payload_hash: `payload-hash-e2e-${evidenceRecords.length + 1}`,
        active_assessment_id: null, content: body.content, content_version: body.content_version,
        tombstoned: false, transfers: [], created_at: '2026-08-12T00:03:00Z',
      }
      evidenceRecords.push(created)
      await route.fulfill({ status: 201, json: evidenceSummary(created) })
      return
    }
    await route.fulfill({ json: evidenceRecords.filter(item => item.goal_id === goalId).map(evidenceSummary) })
  })
  await page.route('**/api/v1/evidence/**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname.split('/')
    const evidenceId = path.at(path.at(-1) === 'assess' ? -2 : -1)!
    const index = evidenceRecords.findIndex(item => item.id === evidenceId)
    if (index < 0) {
      await route.fulfill({ status: 404, json: { message: 'Evidence not found' } })
      return
    }
    if (path.at(-1) === 'assess' && request.method() === 'POST') {
      const body = request.postDataJSON() as Record<string, unknown>
      const assessment = assessmentFixture(`assessment-e2e-${assessments.length + 1}`, evidenceRecords[index]!, body)
      assessments.push(assessment)
      evidenceRecords[index] = { ...evidenceRecords[index]!, active_assessment_id: assessment.id }
      await route.fulfill({ status: 202, json: { job_id: 'assessment-job-e2e', kind: 'assess_evidence', status: 'succeeded', enqueued_at: '2026-08-12T00:04:00Z', deduplicated: false } })
      return
    }
    await route.fulfill({ json: evidenceRecords[index] })
  })
  await page.route('**/api/v1/assessments/**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname.split('/')
    const action = path.at(-1)
    const assessmentId = path.at(action === 'disputes' || action === 'reevaluate' ? -2 : -1)!
    const index = assessments.findIndex(item => item.id === assessmentId)
    if (index < 0) {
      await route.fulfill({ status: 404, json: { message: 'Assessment not found' } })
      return
    }
    if (action === 'disputes' && request.method() === 'POST') {
      const body = request.postDataJSON() as { reason: string }
      const dispute = {
        id: `dispute-e2e-${assessments[index]!.disputes.length + 1}`,
        reason: body.reason, status: 'requested' as const, requested_at: '2026-08-12T00:05:00Z',
        resolved_at: null, resolution_note: null, reevaluation: null,
      }
      assessments[index] = { ...assessments[index]!, disputes: [...assessments[index]!.disputes, dispute] }
      await route.fulfill({ status: 201, json: { id: dispute.id, assessment_id: assessmentId, goal_id: assessments[index]!.goal_id, reason: dispute.reason, status: dispute.status, requested_at: dispute.requested_at } })
      return
    }
    if (action === 'reevaluate' && request.method() === 'POST') {
      const { dispute_id: disputeId } = request.postDataJSON() as { dispute_id: string }
      assessments[index] = {
        ...assessments[index]!,
        disputes: assessments[index]!.disputes.map(item => item.id === disputeId ? {
          ...item,
          reevaluation: { id: 'reevaluation-e2e-1', dispute_id: disputeId, status: 'requested', job_id: 'reevaluation-job-e2e', resulting_assessment_id: null, failure_reference: null, requested_at: '2026-08-12T00:06:00Z', completed_at: null },
        } : item),
      }
      await route.fulfill({ status: 202, json: { job_id: 'reevaluation-job-e2e', kind: 'reevaluate_assessment', status: 'queued', enqueued_at: '2026-08-12T00:06:00Z', deduplicated: false } })
      return
    }
    await route.fulfill({ json: assessments[index] })
  })
  await page.route('**/api/v1/sources/*', async route => {
    const sourceId = new URL(route.request().url()).pathname.split('/').at(-1)
    const source = evidenceSources.find(item => item.id === sourceId)
    await route.fulfill(source ? { json: source } : { status: 404, json: { message: 'Source not found' } })
  })
  await page.route('**/api/v1/goals/*/progress', async route => {
    const goalId = new URL(route.request().url()).pathname.split('/').at(-2)!
    await route.fulfill({ json: {
      ...progress,
      coverage: { ...progress.coverage, supporting_evidence_refs: evidenceRecords.filter(item => item.goal_id === goalId).map(item => item.id) },
    } })
  })
  await page.route('**/api/v1/settings', async route => {
    const request = route.request()
    if (request.method() === 'PATCH') {
      if (Number(request.headers()['if-match']) !== ownerSettings.row_version) {
        await route.fulfill({ status: 412, json: { code: 'precondition_failed', message: 'Settings changed; reload and retry.' } })
        return
      }
      const body = request.postDataJSON() as OwnerSettingsPatch
      ownerSettings = {
        ...ownerSettings,
        ...body,
        row_version: ownerSettings.row_version + 1,
      }
    }
    await route.fulfill({ json: ownerSettings })
  })
})

function evidenceSummary({ content: _content, content_version: _contentVersion, tombstoned: _tombstoned, transfers: _transfers, ...summary }: EvidenceDetail) {
  return summary
}

function assessmentFixture(id: string, evidence: EvidenceDetail, input: Record<string, unknown>): Assessment {
  return {
    id, evidence_id: evidence.id, goal_id: evidence.goal_id, run_id: null,
    rubric_id: String(input.rubric_id), rubric_version: String(input.rubric_version),
    task_ref: String(input.task_ref), assumptions: (input.assumptions as string[] | undefined) ?? [],
    requested_capability: String(input.requested_capability),
    source_refs: ['source-e2e-withdrawn'], provenance_refs: ['provenance-e2e-1'],
    role: typeof input.role === 'string' ? input.role : null, level: typeof input.level === 'string' ? input.level : null,
    evaluation_method: String(input.evaluation_method), state: 'feedback-ready',
    dimensions: [{ dimension_id: 'failure-boundary', outcome: 'pass', rationale: 'The decision names the durable duplicate boundary.', evidence_refs: [evidence.id] }],
    facts: ['A durable idempotency decision is present.'], trade_offs: ['Retention bounds storage against replay coverage.'],
    citations: ['source-e2e-withdrawn'], ambiguities: [],
    feedback: 'The submitted decision supports a bounded idempotency conclusion.',
    cross_question_candidate: 'How does the boundary behave after acknowledgement loss?',
    revision_invitation: 'Defend the same boundary under concurrent retries.', warnings: [],
    limitation_labels: ['Static review cannot prove runtime behavior.'], predecessor_assessment_id: null,
    derivation_excluded: false, disputes: [], created_at: '2026-08-12T00:04:00Z',
  }
}

function requestIsRoadmapCommand(value: string | undefined): value is 'corrections' | 'order-constraints' | 'skip-decisions' | 'depth-overrides' {
  return value === 'corrections' || value === 'order-constraints' || value === 'skip-decisions' || value === 'depth-overrides'
}

async function open(page: Page, route: string) {
  await page.goto(route)
  await expect(page.locator('[data-app="yuno-learning"]')).toBeVisible()
}

function generatedLayerResponse(overrides: Record<string, unknown> = {}) {
  return {
    layer: 'Essential', state: 'ready', revision_id: null, markdown: 'Generated ready body.', markdown_hash: 'generated-ready-hash', checkpoint: null,
    artifact_id: 'artifact-e2e-1', content_origin: 'generated', generation: { job_id: 'generation-job-e2e-1', status: 'succeeded', retryable: false, failure_reference: null }, stale_reason: null,
    ...overrides,
  }
}

function artifactProvenanceFixture() {
  const source = (id: string, title: string, availability_status: string) => ({ id, origin: 'synthetic-fixture', source_type: 'documentation', title, publisher: 'Fixture publisher', canonical_url: null, license_status: 'synthetic', availability_status, created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z' })
  return {
    artifact_id: 'artifact-e2e-1', current_snapshot_hash: 'snapshot-hash-e2e', stale: true, stale_reasons: ['personalization-snapshot-mismatch'], refs: [],
    baked_snapshot: { id: 'snapshot-e2e-1', evidence_state_hash: 'evidence-hash-e2e', profile_hash: 'profile-hash-e2e', provider: 'fixture-provider', model: 'fixture-model', generated_at: '2026-08-12T00:00:00Z', schema_version: 'generate-result-v1', contract_version: 'fixture-v0', prompt_template_version: 'fixture-v0', snapshot_hash: 'snapshot-hash-e2e' },
    claims: [
      { id: 'claim-e2e-sensitive', claim_text: 'This version-dependent claim needs direct support.', claim_type: 'time-or-version-dependent', sensitive: true, citations: [{ id: 'citation-e2e-1', source: source('source-e2e-active', 'Primary fixture specification', 'available'), source_snapshot_id: 'source-snapshot-e2e-1', locator: 'Section 4', support_kind: 'direct', note: null }, { id: 'citation-e2e-2', source: source('source-e2e-withdrawn', 'Withdrawn fixture advisory', 'withdrawn'), source_snapshot_id: 'source-snapshot-e2e-2', locator: 'Archived section', support_kind: 'historical', note: null }] },
      { id: 'claim-e2e-routine', claim_text: 'Routine self-contained explanation.', claim_type: 'routine', sensitive: false, citations: [] },
    ],
  }
}

async function learningState(page: Page) {
  return page.evaluate(() => {
    const key = Object.keys(localStorage).filter(item => item.startsWith('yuno.learning.state.v1.') && item !== 'yuno.learning.state.v1.setup').at(-1)
    return JSON.parse(key ? localStorage.getItem(key) || 'null' : 'null')
  })
}

async function apiEvidence(page: Page, goalId = 'goal-default') {
  return page.evaluate(id => fetch(`/api/v1/goals/${id}/evidence`).then(response => response.json()), goalId) as Promise<Array<{ id: string; active_assessment_id: string | null }>>
}

async function hasClientEvidenceSlice(page: Page) {
  return page.evaluate(() => {
    const key = Object.keys(localStorage).find(item => item.startsWith('yuno.learning.state.v1.') && item !== 'yuno.learning.state.v1.setup')
    const value = JSON.parse(key ? localStorage.getItem(key) || 'null' : 'null')
    return Boolean(value && Object.prototype.hasOwnProperty.call(value, 'evidence'))
  })
}

async function seedAssessedEvidence(page: Page) {
  return page.evaluate(async () => {
    const evidenceResponse = await fetch('/api/v1/goals/goal-default/evidence', {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': 'evidence-e2e' },
      body: JSON.stringify({
        topic_stable_id: 'idempotency-retry', evidence_type: 'answer', capability: 'implement',
        summary: 'A bounded idempotency decision is supported.', origin: 'learner-submit',
        content: 'Use a durable request key and retain the result across redelivery.', content_version: 'v1',
      }),
    })
    const evidence = await evidenceResponse.json()
    await fetch(`/api/v1/evidence/${evidence.id}/assess`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': 'assessment-e2e' },
      body: JSON.stringify({
        rubric_id: 'rubric-e2e', rubric_version: 'v1', task_ref: 'idempotency-checkpoint',
        assumptions: ['Redelivery can follow a committed write.'], requested_capability: 'implement',
        source_refs: ['source-e2e-withdrawn'], provenance_refs: ['provenance-e2e-1'],
        role: 'backend', level: 'senior', evaluation_method: 'static',
      }),
    })
    const records = await fetch('/api/v1/goals/goal-default/evidence').then(response => response.json())
    return records.at(-1) as { id: string; active_assessment_id: string }
  })
}

async function learningApiSnapshot(page: Page, evidenceId: string, assessmentId: string) {
  return page.evaluate(async ({ evidenceId: itemId, assessmentId: reviewId }) => Promise.all([
    fetch('/api/v1/goals/goal-default/evidence').then(response => response.json()),
    fetch(`/api/v1/evidence/${itemId}`).then(response => response.json()),
    fetch(`/api/v1/assessments/${reviewId}`).then(response => response.json()),
    fetch('/api/v1/goals/goal-default/progress').then(response => response.json()),
  ]), { evidenceId, assessmentId })
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

test('malformed bounded draft storage falls back field by field without runtime errors', async ({ page, diagnostics }) => {
  void diagnostics
  await open(page, '/app/settings')
  await page.evaluate(() => {
    localStorage.setItem('yuno.learning.state.v1.goal-default', JSON.stringify({
      version: 1,
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
      practice: learning?.practice,
      mockPriorTurns: learning?.mock.priorTurns.length,
      mockReport: learning?.mock.reportKind,
      hasEvidence: Boolean(learning && Object.prototype.hasOwnProperty.call(learning, 'evidence')),
    }
  }).toEqual({
    practice: { questionIndex: 0, draft: '', hintRequested: false, mode: 'answering', attempts: [] },
    mockPriorTurns: 2,
    mockReport: null,
    hasEvidence: false,
  })
  await expect.poll(async () => {
    const operations = await operationsState(page)
    return { owner: operations?.owner, hasReviewState: 'review' in operations, hasImportState: 'importSource' in operations || 'importStatements' in operations, updates: operations?.acceptedUpdates }
  }).toEqual({
    owner: { name: 'Aditi Rao', role: 'Senior backend engineer' },
    hasReviewState: false,
    hasImportState: false,
    updates: [],
  })
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
  await expect(page.getByText('Regenerated body after explicit action.')).toBeVisible({ timeout: 5_000 })
})

test('Topic Studio static checks do not create client-side evidence', async ({ page, diagnostics }) => {
  void diagnostics
  await page.setViewportSize({ width: 1366, height: 768 })
  await open(page, '/app/topic-studio')
  const openLab = page.getByRole('button', { name: /Open implementation lab/i })
  const openLabBox = await openLab.boundingBox()
  expect(openLabBox).not.toBeNull()
  expect((openLabBox?.y ?? 0) + (openLabBox?.height ?? 0), 'primary lesson action is in the first viewport').toBeLessThanOrEqual(768)
  await openLab.click()
  await expect(page.getByRole('textbox', { name: /Java code/i })).toBeInViewport()
  await expect.poll(async () => (await apiEvidence(page)).length).toBe(0)
  await page.getByRole('button', { name: 'Run static checks', exact: true }).click()
  await expect(page.getByText(/Carries a stable request key/i)).toBeVisible()
  await expect.poll(async () => (await learningState(page))?.runResult?.status).toBeTruthy()
  await expect.poll(() => hasClientEvidenceSlice(page)).toBe(false)
  await expect.poll(async () => (await apiEvidence(page)).length).toBe(0)
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
  await expect.poll(async () => {
    const state = await operationsState(page)
    return 'importSource' in state || 'importStatements' in state
  }).toBe(false)
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
  const resetPages = page.getByRole('button', { name: /Reset local pages/i }).first()
  await resetPages.click()
  const dialog = page.getByRole('alertdialog', { name: /Reset operational pages/i })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: /Cancel/i }).click()
  await expect(resetPages).toBeFocused()
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
