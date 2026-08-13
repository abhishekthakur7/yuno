import { expect, test as base, type Page, type Request } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { createHash } from 'node:crypto'
import type { DiagnosticPreviewEdit, DiagnosticSession, DiagnosticSetup } from '../../src/shared/api/diagnostics'
import type { Assessment, EvidenceDetail, GoalProgress, Source } from '../../src/shared/api/evidence'
import type { HandsOnWorkspace } from '../../src/shared/api/hands-on'
import type { GoalCreate, GoalWorkspace, LearnerProfile, ProfileUpdate, ResumeDestination } from '../../src/shared/api/profile-goals'
import type { InterviewBundle, InterviewQuestion, InterviewRefresher, MockRun, PracticeRun } from '../../src/shared/api/interview'
import type { DataLifecyclePolicy, OwnerSettings, OwnerSettingsPatch } from '../../src/shared/api/settings'

const routes = [
  ['/', /Continue Resilient order fulfillment/i],
  ['/app/onboarding', /Shape your classroom/i],
  ['/app/learn-roadmap', /Your editable roadmap/i],
  ['/app/topic-studio', /Implement an idempotency boundary/i],
  ['/app/interview-hub', /Choose the mode you need/i],
  ['/app/practice', /No practice question is selected/i],
  ['/app/mock?bundleId=bundle-e2e-1&bundleItemId=bundle-item-technical', /durable idempotency boundary/i],
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

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`
  if (value !== null && typeof value === 'object') {
    return `{${Object.entries(value).sort(([left], [right]) => left.localeCompare(right)).map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`).join(',')}}`
  }
  return JSON.stringify(value) ?? 'null'
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, '__YUNO_E2E_PRACTICE__', {
      configurable: true,
      value: { rubric_id: 'practice-rubric-e2e', rubric_version: 'fixture-v0' },
    })
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
  let handsOnWorkspace: HandsOnWorkspace = {
    work_id: null,
    goal_id: 'goal-default',
    topic_id: 'idempotency-retry',
    scenario: {
      title: 'Idempotency boundary hands-on scenario',
      prompt: 'Create and defend a solution for the approved idempotency boundary topic.',
      role: 'Software Engineer',
      level: 'Senior',
      constraints: ['Address the approved topic boundary.', 'State assumptions and trade-offs explicitly.'],
      status: 'fixture',
      source: 'fixture-pending-idk-009',
    },
    artifacts: [],
    reviews: [],
    cross_questions: [],
  }
  let canonicalDecision: 'postponed' | 'dismissed' | null = null
  let canonicalAccepted = false
  const canonicalItems = [
    { id: 'visibility', entity_type: 'content', change_type: 'modified', topic_id: 'visibility', title: 'Visibility timeout and retry budgets', summary: 'Choose a timeout longer than expected processing.', impact: 'Refines the production checklist and adds an explicit failure case.', conflict_type: null, selected: true, recommended_resolution: 'accept-canonical', chosen_resolution: 'accept-canonical', resolution_explanation: 'Choose from measured processing latency, then bound renewal and retry behavior.' },
    { id: 'idempotency', entity_type: 'content', change_type: 'modified', topic_id: 'idempotency', title: 'Idempotency boundary', summary: 'Store the message ID before applying the business write.', impact: 'Conflicts with your “unique constraint wins” overlay; choose which wording this goal keeps.', conflict_type: 'overlay-conflict', selected: true, recommended_resolution: 'overlay-wins', chosen_resolution: 'overlay-wins', resolution_explanation: 'Make the business decision and duplicate marker atomic; treat a prior read as an optimization.' },
    { id: 'dlq', entity_type: 'content', change_type: 'modified', topic_id: 'dlq', title: 'Dead-letter recovery', summary: 'Inspect and replay poison messages.', impact: 'Adds one review prompt; does not mark the topic complete.', conflict_type: null, selected: true, recommended_resolution: 'accept-canonical', chosen_resolution: 'accept-canonical', resolution_explanation: 'Quarantine, diagnose, and replay with the duplicate boundary intact.' },
    { id: 'legacy-retry', entity_type: 'topic', change_type: 'deleted', topic_id: 'legacy-retry', title: 'Legacy retry loop', summary: 'A locally annotated retry topic existed in the base graph.', impact: 'Carries learner evidence and must not silently disappear.', conflict_type: 'local-state-on-deleted-topic', selected: true, recommended_resolution: 'overlay-wins', chosen_resolution: 'overlay-wins', resolution_explanation: 'Retain personal state as an archived local topic.' },
  ]
  let ownerSettings: OwnerSettings = {
    progress_display: 'detailed',
    accessibility: { reduced_motion: false },
    provider_selection: null,
    row_version: 1,
  }
  const lifecyclePolicy: DataLifecyclePolicy = {
    policy_version: '1.0', import_original_max_bytes: 10_485_760, import_retained_owner_limit: 100,
    import_statements_per_import_limit: 10_000, import_unreviewed_owner_limit: 50_000,
    evidence_payload_max_bytes: 10_485_760, evidence_retained_owner_limit: 10_000,
    generated_body_max_bytes: 2_097_152, generated_retained_owner_limit: 5_000,
    interview_turns_per_session_limit: 1_000, interview_bytes_per_session_limit: 10_485_760,
    interview_sessions_owner_limit: 200, runner_input_files_limit: 100,
    runner_input_bytes_limit: 10_485_760, runner_stdout_bytes_limit: 1_048_576,
    runner_stderr_bytes_limit: 1_048_576, runner_output_bytes_limit: 2_097_152,
    runner_temp_bytes_limit: 268_435_456, runner_temp_files_limit: 10_000,
    overlay_proposal_pending_cap: 25, pending_job_cap: 100,
    diagnostic_abandoned_retention_days: 30, interview_inactive_retention_days: 30,
    terminal_job_retention_days: 30, job_event_retention_days: 7, job_event_owner_limit: 10_000,
    runner_output_retention_days: 7, runner_workspace_retention_seconds: 3_600,
    export_package_retention_seconds: 86_400, export_operation_retention_days: 30,
    structured_log_file_count: 5, structured_log_file_max_bytes: 10_485_760,
    structured_log_total_max_bytes: 52_428_800, structured_log_retention_days: 14,
    export_format: 'yuno-portable-export', export_version: '1.0', export_available: true, recovery_window_days: 0,
    yuno_managed_backups: false, remote_support_access: false,
  }
  await page.route('**/api/v1/runner/capabilities', route => route.fulfill({ json: {
    enabled: false,
    disabled_reason: 'Runner posture is awaiting approval.',
    environment_policy_version: 'blocked-unapproved',
    limits_config_version: null,
    limitation: 'Controlled subprocess execution only. This is not a sandbox or hostile-code isolation, and it is not proof of production or AWS behavior.',
    capabilities: [],
  } }))
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
  let interviewBundles: InterviewBundle[] = [{
    id: 'bundle-e2e-1', goal_id: 'goal-default', name: 'Senior backend interview', generic_role: 'Backend Engineer', target_level: 'Senior', origin: 'recommended', copy_source_id: null, status: 'active', row_version: 1,
    created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z',
    items: [
      { id: 'bundle-item-technical', bundle_id: 'bundle-e2e-1', subject: 'technical', topic_stable_id: 'idempotency-retry', question: 'Where is the durable idempotency boundary?', position: 0, is_optional: false, included: true },
      { id: 'bundle-item-behavioral', bundle_id: 'bundle-e2e-1', subject: 'behavioral', topic_stable_id: null, question: 'Tell me about a difficult trade-off.', position: 1, is_optional: true, included: true },
      { id: 'bundle-item-leadership', bundle_id: 'bundle-e2e-1', subject: 'leadership', topic_stable_id: null, question: 'How did you align a team?', position: 2, is_optional: true, included: true },
    ],
  }]
  const interviewRefreshers: InterviewRefresher[] = [{ artifact_id: 'artifact-e2e-1', state: 'stale', subject: 'Messaging', layer: 'Production', content: 'Revisit the durable decision before acknowledgement.', source_ref: 'source-e2e-1', source_title: 'Approved messaging guide', evidence_gap_ref: 'evidence-gap-e2e-1', evidence_gap: 'Recovery after commit was not yet supported.' }]
  const interviewQuestions: InterviewQuestion[] = [{ id: 'question-e2e-1', bundle_id: 'bundle-e2e-1', subject: 'technical', topic_stable_id: 'idempotency-retry', question: 'Where is the durable idempotency boundary?', position: 0, included: true }]
  let practiceRun: PracticeRun | null = null
  let mockRun: MockRun | null = null
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
    if (request.method() === 'DELETE' && importId?.startsWith('import-')) {
      const record = imports.find(item => item.id === importId)
      if (record) record.original_content = ''
      importStatements = importStatements.filter(item => item.import_id !== importId)
      await route.fulfill({ status: 204, body: '' })
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
  await page.route('**/api/v1/interview-bundles**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname.split('/')
    const copy = path.at(-1) === 'copy'
    const bundleId = path.at(copy ? -2 : -1)
    if (request.method() === 'GET' && bundleId === 'interview-bundles') {
      await route.fulfill({ json: interviewBundles })
      return
    }
    if (request.method() === 'POST' && bundleId === 'interview-bundles') {
      const body = request.postDataJSON() as Omit<InterviewBundle, 'id' | 'copy_source_id' | 'status' | 'row_version' | 'created_at' | 'updated_at'>
      const created = { ...body, id: `bundle-e2e-${interviewBundles.length + 1}`, copy_source_id: null, status: 'active', row_version: 1, created_at: '2026-08-12T00:03:00Z', updated_at: '2026-08-12T00:03:00Z', items: body.items.map((item, index) => ({ ...item, id: `bundle-created-item-${index}`, bundle_id: `bundle-e2e-${interviewBundles.length + 1}` })) } as InterviewBundle
      interviewBundles = [...interviewBundles, created]
      await route.fulfill({ status: 201, json: created })
      return
    }
    const index = interviewBundles.findIndex(bundle => bundle.id === bundleId)
    if (index < 0) {
      await route.fulfill({ status: 404, json: { message: 'Not found' } })
      return
    }
    const current = interviewBundles[index]!
    if (copy) {
      const body = request.postDataJSON() as { name: string }
      const copied: InterviewBundle = { ...current, id: `bundle-e2e-${interviewBundles.length + 1}`, name: body.name, copy_source_id: current.id, row_version: 1, items: current.items.map((item, itemIndex) => ({ ...item, id: `bundle-copy-item-${itemIndex}`, bundle_id: `bundle-e2e-${interviewBundles.length + 1}` })) }
      interviewBundles = [...interviewBundles, copied]
      await route.fulfill({ status: 201, json: copied })
      return
    }
    if (request.method() === 'PATCH') {
      const body = request.postDataJSON() as { name?: string; generic_role?: string; target_level?: InterviewBundle['target_level']; items?: Array<{ id: string; included: boolean }> }
      const included = new Map(body.items?.map(item => [item.id, item.included]) ?? [])
      interviewBundles[index] = { ...current, ...body, items: current.items.map(item => included.has(item.id) ? { ...item, included: included.get(item.id)! } : item), row_version: current.row_version + 1, updated_at: '2026-08-12T00:04:00Z' }
      await route.fulfill({ json: interviewBundles[index] })
      return
    }
    if (request.method() === 'DELETE') {
      interviewBundles.splice(index, 1)
      await route.fulfill({ status: 204, body: '' })
      return
    }
    await route.fulfill({ json: current })
  })
  await page.route('**/api/v1/interview-runs**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname.split('/')
    const action = path.at(-1)
    if (request.method() === 'DELETE' && action !== 'interview-runs') {
      await route.fulfill({ status: 204, body: '' })
      return
    }
    if (request.method() === 'POST' && action === 'interview-runs') {
      const body = request.postDataJSON() as { mode?: string; goal_id: string; bundle_id: string; bundle_item_id: string; rubric_id: string; rubric_version: string; requested_capability: string }
      if (body.mode === 'Mock') {
        mockRun = {
          id: 'mock-run-e2e-1', goal_id: body.goal_id, bundle_id: body.bundle_id,
          bundle_item_id: body.bundle_item_id, mode: 'Mock', state: 'answering', draft: '',
          question: interviewQuestions[0]!.question, active_job_id: null, final_assessment_id: null,
          failure_reference: null, retryable: false,
          created_at: '2026-08-12T00:05:00Z', updated_at: '2026-08-12T00:05:00Z',
          turns: [{ id: 'mock-question-e2e-1', turn_number: 1, kind: 'question', body: interviewQuestions[0]!.question, answer_turn_id: null, created_at: '2026-08-12T00:05:00Z' }],
        }
        await route.fulfill({ status: 201, json: mockRun }); return
      }
      practiceRun = { ...body, id: 'practice-run-e2e-1', mode: 'Practice', state: 'ready', question: interviewQuestions[0]!.question, active_job_id: null, failure_reference: null, retryable: false, created_at: '2026-08-12T00:05:00Z', updated_at: '2026-08-12T00:05:00Z', turns: [{ id: 'practice-question-e2e-1', turn_number: 1, kind: 'question', body: interviewQuestions[0]!.question, answer_turn_id: null, created_at: '2026-08-12T00:05:00Z' }], results: [] }
      await route.fulfill({ status: 201, json: practiceRun }); return
    }
    if (mockRun && path.includes(String(mockRun.id))) {
      if (request.method() === 'POST' && action === 'pause') {
        const body = request.postDataJSON() as { draft: string }
        mockRun = { ...mockRun, state: 'paused', draft: body.draft, updated_at: '2026-08-12T00:06:00Z' }
        await route.fulfill({ json: mockRun }); return
      }
      if (request.method() === 'POST' && action === 'resume') {
        mockRun = { ...mockRun, state: 'answering', updated_at: '2026-08-12T00:07:00Z' }
        await route.fulfill({ json: mockRun }); return
      }
      if (request.method() === 'POST' && action === 'complete') {
        const body = request.postDataJSON() as { draft: string }
        mockRun = {
          ...mockRun, state: 'completing', draft: body.draft,
          active_job_id: 'mock-final-evaluation-e2e-1', updated_at: '2026-08-12T00:08:00Z',
          turns: [...mockRun.turns, { id: 'mock-answer-e2e-1', turn_number: 2, kind: 'answer', body: body.draft, answer_turn_id: null, created_at: '2026-08-12T00:08:00Z' }],
        }
        await route.fulfill({ status: 202, json: { job_id: 'mock-final-evaluation-e2e-1', kind: 'evaluate_mock', status: 'queued', enqueued_at: '2026-08-12T00:08:00Z', deduplicated: false } }); return
      }
      if (action === 'report' && mockRun.state === 'completed') {
        await route.fulfill({ json: {
          run_id: mockRun.id, goal_id: mockRun.goal_id, state: 'completed', transcript: mockRun.turns,
          assessment: {
            id: 'mock-assessment-e2e-1', goal_id: mockRun.goal_id, evidence_id: 'mock-evidence-e2e-1', run_id: mockRun.id,
            rubric_id: 'mock-rubric-e2e-1', rubric_version: 'v1', state: 'feedback-ready', task_ref: 'mock-terminal', requested_capability: 'implement', role: 'backend', level: 'senior', evaluation_method: 'interactive',
            assumptions: ['Redelivery follows a committed write.'], source_refs: [], provenance_refs: ['mock-provider-e2e-1'],
            facts: ['The durable write precedes acknowledgement.'], trade_offs: ['Failing closed reduces write-path availability.'], citations: [], ambiguities: [],
            feedback: 'The transcript identifies the durable idempotency boundary.', cross_question_candidate: null,
            revision_invitation: 'Test the boundary during acknowledgement loss.', warnings: [], limitation_labels: ['Terminal Mock transcript only.'],
            predecessor_assessment_id: null, derivation_excluded: false, created_at: '2026-08-12T00:09:00Z',
            dimensions: [{ dimension_id: 'boundary', outcome: 'pass', rationale: 'The answer names the atomic boundary.', evidence_refs: ['mock-evidence-e2e-1'] }], disputes: [],
          },
        } }); return
      }
      if (request.method() === 'GET' && request.url().includes('finish=1')) {
        mockRun = { ...mockRun, state: 'completed', active_job_id: null, final_assessment_id: 'mock-assessment-e2e-1', updated_at: '2026-08-12T00:09:00Z' }
        await route.fulfill({ json: mockRun }); return
      }
      if (action === 'hints' || action === 'report') {
        await route.fulfill({ status: 409, json: { message: 'Mock feedback is withheld until terminal completion.', code: 'mock_feedback_withheld' } }); return
      }
      await route.fulfill({ json: mockRun }); return
    }
    if (!practiceRun) { await route.fulfill({ status: 404, json: { message: 'Not found' } }); return }
    if (action === 'hints') {
      practiceRun = { ...practiceRun, state: 'answering', turns: [...practiceRun.turns, { id: 'practice-hint-e2e-1', turn_number: practiceRun.turns.length + 1, kind: 'hint', body: 'Name the failure window first. Which durable key survives the retry?', answer_turn_id: null, created_at: '2026-08-12T00:06:00Z' }] }
      await route.fulfill({ json: practiceRun }); return
    }
    if (action === 'answers') {
      const answer = (request.postDataJSON() as { answer: string }).answer
      const answerTurn = { id: `practice-answer-e2e-${practiceRun.turns.filter(turn => turn.kind === 'answer').length + 1}`, turn_number: practiceRun.turns.length + 1, kind: 'answer' as const, body: answer, answer_turn_id: null, created_at: '2026-08-12T00:07:00Z' }
      practiceRun = { ...practiceRun, state: 'feedback-ready', turns: [...practiceRun.turns, answerTurn], results: [...practiceRun.results, { id: `practice-result-e2e-${practiceRun.results.length + 1}`, answer_turn_id: answerTurn.id, assessment_id: 'assessment-e2e-1', visible_at: '2026-08-12T00:07:00Z', facts: ['The durable decision precedes acknowledgement.'], trade_offs: ['Retention must cover the replay horizon.'], dimensions: [{ dimension_id: 'boundary', name: 'Failure boundary', outcome: 'supported', rationale: 'The answer names an atomic durable key.' }], feedback: 'The answer identifies the failure boundary.', cross_question_candidate: 'How would key retention change under a longer replay horizon?' }] }
      await route.fulfill({ status: 202, json: { job_id: `practice-job-${practiceRun.results.length}`, kind: 'evaluate_practice', status: 'queued', enqueued_at: '2026-08-12T00:07:00Z', deduplicated: false } }); return
    }
    await route.fulfill({ json: practiceRun })
  })
  await page.route('**/api/v1/canonical/versions', route => route.fulfill({ json: [{ id: 'graph-1', created_at: '', manifest_version: '1', published_at: '', supersedes_version_id: null, version_label: 'v1' }] }))
  await page.route('**/api/v1/canonical-update-proposals/**', async route => {
    const request = route.request()
    const idempotencyKey = request.headers()['idempotency-key']
    if (!idempotencyKey) {
      await route.fulfill({ status: 400, json: { code: 'missing_idempotency_key', message: 'Idempotency-Key is required.' } })
      return
    }
    if (request.url().endsWith('/decision')) {
      const body = request.postDataJSON() as { decision?: string; reason?: unknown }
      if (!['postpone', 'dismiss'].includes(body.decision ?? '') || body.reason !== null || Object.keys(body).sort().join(',') !== 'decision,reason') {
        await route.fulfill({ status: 422, json: { code: 'invalid_decision', message: 'Decision body must be exact.' } })
        return
      }
      canonicalDecision = body.decision === 'postpone' ? 'postponed' : 'dismissed'
      await route.fulfill({ json: { proposal_id: 'canonical-proposal-e2e', status: canonicalDecision, decided_at: '2026-08-13T00:00:00Z' } })
      return
    }
    const body = request.postDataJSON() as { confirmed?: unknown; items?: Array<{ item_id?: unknown; selected?: unknown; resolution?: unknown }> }
    const submittedIds = body.items?.map(item => item.item_id) ?? []
    const expectedIds = canonicalItems.map(item => item.id)
    const legalResolutions = new Set(['accept-canonical', 'overlay-wins', 'retain-local'])
    const exactItems = body.items?.length === canonicalItems.length && [...submittedIds].sort().join(',') === [...expectedIds].sort().join(',') && new Set(submittedIds).size === expectedIds.length
    const completeItems = body.items?.every(item => typeof item.selected === 'boolean' && typeof item.resolution === 'string' && legalResolutions.has(item.resolution) && Object.keys(item).sort().join(',') === 'item_id,resolution,selected')
    if (body.confirmed !== true || !exactItems || !completeItems || Object.keys(body).sort().join(',') !== 'confirmed,items') {
      await route.fulfill({ status: 422, json: { code: 'invalid_acceptance', message: 'Acceptance must be confirmed and submit every merge item exactly once with a legal resolution.' } })
      return
    }
    canonicalAccepted = true
    canonicalDecision = null
    goals = goals.map(goal => goal.id === 'goal-default' ? { ...goal, graph_version_id: 'graph-2', row_version: goal.row_version + 1 } : goal)
    await route.fulfill({ json: { proposal_id: 'canonical-proposal-e2e', status: 'accepted', goal_id: 'goal-default', base_version_id: 'graph-1', target_version_id: 'graph-2', goal_graph_version_id: 'graph-2', accepted_at: '2026-08-13T00:01:00Z', invalidation_state: 'dispatched', reprocess_job: null } })
  })
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
    if (path.at(-1) === 'delete-preflight') {
      const goalId = path.at(-2)!
      await route.fulfill({ json: { operation_id: 'delete-operation-e2e', snapshot_id: 'delete-snapshot-e2e', goal_id: goalId, evidence_ids: ['cross-goal-evidence-e2e'], learning_state_ids: ['dependent-state-e2e'], status: 'preflight', created_at: '2026-08-13T00:00:00Z' } })
      return
    }
    if (path.at(-1) === 'canonical-update') {
      await route.fulfill({ json: canonicalAccepted ? { state: 'empty', goal_id: 'goal-default', base_version: { id: 'graph-2', version_label: '2026.08' }, target_version: null, proposal: null } : { state: canonicalDecision ?? 'conflict-needs-resolution', goal_id: 'goal-default', base_version: { id: 'graph-1', version_label: '2026.07' }, target_version: { id: 'graph-2', version_label: '2026.08' }, proposal: { id: 'canonical-proposal-e2e', status: canonicalDecision ?? 'awaiting', diff_hash: 'direct-graph-1-graph-2', items: canonicalItems } } })
      return
    }
    if (path.at(-1) === 'hands-on' && path.includes('topics')) {
      await route.fulfill({ json: handsOnWorkspace })
      return
    }
    if (path.at(-1) === 'submit' && path.at(-2) === 'hands-on') {
      const body = route.request().postDataJSON() as { artifact: string; cross_question_response?: { question_id: string; response: string } }
      const revisionNumber = handsOnWorkspace.artifacts.length + 1
      const artifactId = `hands-on-artifact-e2e-${revisionNumber}`
      const evidenceId = `hands-on-evidence-e2e-${revisionNumber}`
      const assessmentId = `hands-on-assessment-e2e-${revisionNumber}`
      const reviewId = `hands-on-review-e2e-${revisionNumber}`
      const questionId = `hands-on-question-e2e-${revisionNumber}`
      const createdAt = `2026-08-12T00:${String(10 + revisionNumber).padStart(2, '0')}:00Z`
      const evidence: EvidenceDetail = {
        id: evidenceId, goal_id: 'goal-default', topic_stable_id: 'idempotency-retry',
        evidence_type: 'hands-on-artifact', capability: 'implement',
        summary: `Idempotency boundary hands-on revision ${revisionNumber}`, origin: 'hands-on-submit',
        payload_hash: `hands-on-payload-e2e-${revisionNumber}`, active_assessment_id: assessmentId,
        content: body.artifact, content_version: `revision-${revisionNumber}`,
        tombstoned: false, transfers: [], created_at: createdAt,
      }
      const assessment = assessmentFixture(assessmentId, evidence, {
        rubric_id: 'hands-on-rubric-e2e', rubric_version: 'fixture-hands-on-v1',
        task_ref: `hands-on:work-e2e:revision:${revisionNumber}`,
        assumptions: handsOnWorkspace.scenario.constraints, requested_capability: 'implement',
        role: handsOnWorkspace.scenario.role, level: handsOnWorkspace.scenario.level,
        evaluation_method: 'static',
      })
      evidenceRecords.push(evidence)
      assessments.push(assessment)
      handsOnWorkspace = {
        ...handsOnWorkspace,
        work_id: 'hands-on-work-e2e',
        artifacts: [...handsOnWorkspace.artifacts, {
          id: artifactId, revision_number: revisionNumber, content: body.artifact,
          content_hash: `hands-on-content-hash-e2e-${revisionNumber}`,
          response_to_question_id: body.cross_question_response?.question_id ?? null,
          cross_question_response: body.cross_question_response?.response ?? null,
          evidence_id: evidenceId, created_at: createdAt,
        }],
        reviews: [...handsOnWorkspace.reviews, {
          id: reviewId, artifact_id: artifactId, assessment_id: assessmentId,
          rubric_id: 'hands-on-rubric-e2e', rubric_version: 'fixture-hands-on-v1',
          rubric_status: 'fixture', review_mode: 'static',
          limitation: `Static review of revision ${revisionNumber} cannot compile or execute this artifact.`,
          feedback: assessment.feedback, created_at: createdAt,
        }],
        cross_questions: [...handsOnWorkspace.cross_questions, {
          id: questionId, review_id: reviewId, artifact_id: artifactId,
          question: 'Which assumption breaks after a committed write is redelivered?',
          target_gap: 'post-commit redelivery', created_at: createdAt,
        }],
      }
      await route.fulfill({ status: 202, json: {
        job_id: `hands-on-review-job-e2e-${revisionNumber}`,
        kind: 'review_hands_on_artifact', status: 'succeeded', enqueued_at: createdAt,
        deduplicated: false, lane: 'interactive', retryable: false,
        failure_reference: null, result_ref: `HandsOnReview:${reviewId}`, result_hash: `review-hash-${revisionNumber}`,
      } })
      return
    }
    if (path.at(-1) === 'conversation' && path.includes('topics')) {
      await route.fulfill({ json: [] })
      return
    }
    if (path.at(-1) === 'refreshers') {
      await route.fulfill({ json: interviewRefreshers })
      return
    }
    if (path.at(-1) === 'questions') {
      await route.fulfill({ json: interviewQuestions })
      return
    }
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
  await page.route('**/api/v1/jobs/hands-on-review-job-e2e-*', async route => {
    const jobId = new URL(route.request().url()).pathname.split('/').at(-1)!
    await route.fulfill({ json: {
      job_id: jobId, kind: 'review_hands_on_artifact', status: 'succeeded',
      enqueued_at: '2026-08-12T00:11:00Z', deduplicated: false, lane: 'interactive',
      retryable: false, failure_reference: null, result_ref: 'HandsOnReview:hands-on-review-e2e-1',
      result_hash: 'hands-on-review-hash-e2e',
    } })
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
        ...(body.progress_display ? { progress_display: body.progress_display } : {}),
        ...(body.accessibility ? { accessibility: body.accessibility } : {}),
        ...('provider_selection' in body ? { provider_selection: body.provider_selection ?? null } : {}),
        row_version: ownerSettings.row_version + 1,
      }
    }
    await route.fulfill({ json: ownerSettings })
  })
  await page.route('**/api/v1/settings/data-lifecycle-policy', route => route.fulfill({ json: lifecyclePolicy }))
  const canonicalData = '{"goals":[],"profile":[]}'
  const dataDigest = createHash('sha256').update(canonicalData).digest('hex')
  const canonicalExport = `{"data":${canonicalData},"exported_at":"2026-08-13T00:02:00.000000Z","format":"yuno-portable-export","integrity":{"algorithm":"sha256","digest":"${dataDigest}"},"product":"Yuno","scope":{"goal_id":"goal-default","kind":"goal"},"version":"1.0"}`
  await page.route('**/api/v1/exports**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path.endsWith('/download')) {
      await route.fulfill({
        status: 200,
        body: canonicalExport,
        contentType: 'application/json; charset=utf-8',
        headers: {
          'Content-Disposition': 'attachment; filename="yuno-export-v1-20260813T000200Z.json"',
          'Content-Length': String(Buffer.byteLength(canonicalExport)),
        },
      })
      return
    }
    if (request.method() === 'POST') {
      await route.fulfill({ status: 202, json: { job_id: 'export-e2e', kind: 'export_data', status: 'queued', enqueued_at: '2026-08-13T00:01:00Z', deduplicated: false, attempt: 0 } })
      return
    }
    await route.fulfill({ json: {
      id: 'export-e2e', goal_id: 'goal-default', status: 'complete', format: 'yuno-portable-export', version: '1.0',
      filename: 'yuno-export-v1-20260813T000200Z.json', package_hash: createHash('sha256').update(canonicalExport).digest('hex'),
      completed_at: '2026-08-13T00:02:00.000000Z', package_expires_at: '2026-08-14T00:02:00.000000Z',
      metadata_expires_at: '2026-09-12T00:02:00.000000Z', download_available: true, job_id: 'export-e2e',
      result_ref: 'ExportOperation:export-e2e', failure_reference: null,
      created_at: '2026-08-13T00:01:00.000000Z', updated_at: '2026-08-13T00:02:00.000000Z',
    } })
  })
  await page.route('**/api/v1/provider-capabilities', route => route.fulfill({ json: [
    { provider: 'codex', state: 'unavailable', reason: 'Not configured', adapter_version: null, contract_version: null },
    { provider: 'claude', state: 'unavailable', reason: 'Not configured', adapter_version: null, contract_version: null },
  ] }))
  await page.route('**/api/v1/disclosures', route => route.fulfill({ json: [
    { id: null, category: 'provider-generation', operation: 'Provider generation', destination: 'Selected model provider', data_categories: ['prompt reference', 'operation metadata'], disclosure_version: 'provider-network-v1', accepted_at: null, revoked_at: null },
    { id: null, category: 'source-retrieval', operation: 'Explicit authoritative source retrieval', destination: 'Approved canonical URL', data_categories: ['source URL', 'operation metadata'], disclosure_version: 'source-network-v1', accepted_at: null, revoked_at: null },
  ] }))
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

async function apiEvidence(page: Page, goalId = 'goal-default') {
  return page.evaluate(id => fetch(`/api/v1/goals/${id}/evidence`).then(response => response.json()), goalId) as Promise<Array<{ id: string; active_assessment_id: string | null }>>
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

async function fillGoalBasics(page: Page, name = 'Resilient order fulfillment') {
  await page.getByRole('textbox', { name: 'Goal name' }).fill(name)
  await page.getByRole('textbox', { name: 'Subject' }).fill('Java / Spring Boot · AWS')
}

async function skipOptionalSetup(page: Page) {
  await page.getByRole('button', { name: /Skip to roadmap preview/i }).click()
  await expect(page.getByRole('heading', { level: 1, name: /Create a goal from this roadmap/i })).toBeVisible()
}

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

  await open(page, '/app/practice?bundleId=bundle-e2e-1&bundleItemId=question-e2e-1')
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
  const previewDeletion = page.getByRole('button', { name: /Preview deletion/i }).first()
  await previewDeletion.click()
  const dialog = page.getByRole('alertdialog', { name: /Delete Resilient order fulfillment/i })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: /Cancel/i }).click()
  await expect(previewDeletion).toBeFocused()
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
