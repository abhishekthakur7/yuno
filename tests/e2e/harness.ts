import { expect, test as base, type Page, type Request } from '@playwright/test'
import { createHash } from 'node:crypto'
import type { DiagnosticPreviewEdit, DiagnosticSession, DiagnosticSetup } from '../../src/shared/api/diagnostics'
import type { Assessment, EvidenceDetail, GoalProgress, Source } from '../../src/shared/api/evidence'
import type { HandsOnWorkspace } from '../../src/shared/api/hands-on'
import type { GoalCreate, GoalWorkspace, LearnerProfile, ProfileUpdate, ResumeDestination } from '../../src/shared/api/profile-goals'
import type { InterviewBundle, InterviewQuestion, InterviewRefresher, MockRun, PracticeRun } from '../../src/shared/api/interview'
import type { DataLifecyclePolicy, OwnerSettings, OwnerSettingsPatch } from '../../src/shared/api/settings'

export { expect }

export const routes = [
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

export const viewports = [
  { width: 1440, height: 1000 },
  { width: 1366, height: 768 },
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
] as const

export const roadmapTopics = [
  ['delivery-contract', 'Model the delivery contract before choosing a pattern'],
  ['commit-window', 'Trace the commit-before-acknowledgement failure window'],
  ['idempotency-retry', 'Implement an idempotency boundary under concurrent retries'],
] as const

export type GoalPatch = { set_current?: boolean; resume_position?: string; resume_destination?: ResumeDestination; dismiss_recommendation_key?: string }

export const defaultProfile: LearnerProfile = {
  experience: null,
  strengths: null,
  weaknesses: null,
  current_goal_id: 'goal-default',
  profile_revision: 1,
  updated_at: '2026-08-12T00:00:00Z',
}

type Diagnostics = { consoleErrors: string[]; pageErrors: string[]; externalRequests: string[] }

function isLocalRequest(request: Request) {
  const url = new URL(request.url())
  return ['data:', 'blob:'].includes(url.protocol) || ['localhost', '127.0.0.1', '::1', '[::1]'].includes(url.hostname.toLowerCase())
}

export const test = base.extend<{ diagnostics: Diagnostics; apiMocks: void }>({
  // Deliberately an auto fixture, not a module-level `test.beforeEach`: a top-level hook in
  // an imported module binds only to whichever spec file first triggers this module's
  // once-only ESM evaluation, so a second spec file importing this harness would silently
  // lose every API mock and hit the real backend. An auto fixture binds to the `test` object
  // itself, so it applies to every spec file that imports it, regardless of load order.
  apiMocks: [
    async ({ page }, use) => {
      await installApiMocks(page)
      await use()
    },
    { auto: true },
  ],
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

export function goalFixture(overrides: Partial<GoalWorkspace> = {}): GoalWorkspace {
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

export async function open(page: Page, route: string) {
  await page.goto(route)
  await expect(page.locator('[data-app="yuno-learning"]')).toBeVisible()
}

export function generatedLayerResponse(overrides: Record<string, unknown> = {}) {
  return {
    layer: 'Essential', state: 'ready', revision_id: null, markdown: 'Generated ready body.', markdown_hash: 'generated-ready-hash', checkpoint: null,
    artifact_id: 'artifact-e2e-1', content_origin: 'generated', generation: { job_id: 'generation-job-e2e-1', status: 'succeeded', retryable: false, failure_reference: null }, stale_reason: null,
    ...overrides,
  }
}

// Real production vocabulary per docs/decisions/IDK-003-source-licensing-and-snapshot-policy.md:160-161
// (the synthetic placeholder 'synthetic' is not a legal `license_status` value).
export const SOURCE_SNAPSHOT_SUPPORTING = { id: 'source-snapshot-e2e-1', source_id: 'source-e2e-active', retrieved_at: '2026-08-11T00:00:00Z', version_label: 'v2026.08', content_hash: 'snapshot-content-hash-e2e-1', content_ref: 'snapshot-content-ref-e2e-1', status: 'active' }

export function artifactProvenanceFixture() {
  const source = (id: string, title: string, availability_status: string, canonical_url: string | null, license_status: string) => ({ id, origin: 'synthetic-fixture', source_type: 'documentation', title, publisher: 'Fixture publisher', canonical_url, license_status, availability_status, created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z' })
  return {
    artifact_id: 'artifact-e2e-1', current_snapshot_hash: 'snapshot-hash-e2e', stale: true, stale_reasons: ['personalization-snapshot-mismatch'], refs: [],
    baked_snapshot: { id: 'snapshot-e2e-1', evidence_state_hash: 'evidence-hash-e2e', profile_hash: 'profile-hash-e2e', provider: 'fixture-provider', model: 'fixture-model', generated_at: '2026-08-12T00:00:00Z', schema_version: 'generate-result-v1', contract_version: 'fixture-v0', prompt_template_version: 'fixture-v0', snapshot_hash: 'snapshot-hash-e2e' },
    claims: [
      // citation-e2e-1: resolvable snapshot (SOURCE_SNAPSHOT_SUPPORTING) + non-null canonical_url -> exercises the anchor and the resolved retrieval timestamp/version rows.
      // citation-e2e-2: source_snapshot_id: null + canonical_url: null -> exercises the verbatim fallback string and the anchor-omission path.
      { id: 'claim-e2e-sensitive', claim_text: 'This version-dependent claim needs direct support.', claim_type: 'time-or-version-dependent', sensitive: true, citations: [{ id: 'citation-e2e-1', source: source('source-e2e-active', 'Primary fixture specification', 'available', 'https://fixture.example/specs/primary', 'approved-open-license'), source_snapshot_id: SOURCE_SNAPSHOT_SUPPORTING.id, locator: 'Section 4', support_kind: 'direct', note: null }, { id: 'citation-e2e-2', source: source('source-e2e-withdrawn', 'Withdrawn fixture advisory', 'withdrawn', null, 'approved-link-only'), source_snapshot_id: null, locator: 'Archived section', support_kind: 'historical', note: null }] },
      { id: 'claim-e2e-routine', claim_text: 'Routine self-contained explanation.', claim_type: 'routine', sensitive: false, citations: [] },
    ],
  }
}

export async function apiEvidence(page: Page, goalId = 'goal-default') {
  return page.evaluate(id => fetch(`/api/v1/goals/${id}/evidence`).then(response => response.json()), goalId) as Promise<Array<{ id: string; active_assessment_id: string | null }>>
}

export async function seedAssessedEvidence(page: Page) {
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

export async function learningApiSnapshot(page: Page, evidenceId: string, assessmentId: string) {
  return page.evaluate(async ({ evidenceId: itemId, assessmentId: reviewId }) => Promise.all([
    fetch('/api/v1/goals/goal-default/evidence').then(response => response.json()),
    fetch(`/api/v1/evidence/${itemId}`).then(response => response.json()),
    fetch(`/api/v1/assessments/${reviewId}`).then(response => response.json()),
    fetch('/api/v1/goals/goal-default/progress').then(response => response.json()),
  ]), { evidenceId, assessmentId })
}

export async function fillGoalBasics(page: Page, name = 'Resilient order fulfillment') {
  await page.getByRole('textbox', { name: 'Goal name' }).fill(name)
  await page.getByRole('textbox', { name: 'Subject' }).fill('Java / Spring Boot · AWS')
  // IDK-004 §4: no level is preselected, so onboarding tests must make an explicit choice
  // before submission is enabled.
  await page.getByRole('combobox', { name: /Target level/i }).selectOption('Senior')
}

export async function skipOptionalSetup(page: Page) {
  await page.getByRole('button', { name: /Skip to roadmap preview/i }).click()
  await expect(page.getByRole('heading', { level: 1, name: /Create a goal from this roadmap/i })).toBeVisible()
}

export async function expectNoHorizontalOverflow(page: Page, label: string) {
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

export async function longestMotionMs(page: Page) {
  return page.evaluate(() => {
    const times = (value: string) => value.split(',').map(token => token.trim().endsWith('ms') ? parseFloat(token) : parseFloat(token) * 1000)
    return Math.max(0, ...Array.from(document.querySelectorAll('[data-app="yuno-learning"] *')).flatMap(element => {
      const style = getComputedStyle(element)
      return [...times(style.animationDuration), ...times(style.transitionDuration)]
    }))
  })
}

export async function installApiMocks(page: Page) {
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
      scenario_id: null,
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
  let providerDisclosureAccepted = false
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
      license_status: 'approved-link-only', availability_status: 'withdrawn',
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
  await page.route('**/api/v1/jobs/practice-job-*', async route => {
    const jobId = new URL(route.request().url()).pathname.split('/').at(-1)!
    await route.fulfill({ json: {
      job_id: jobId, kind: 'evaluate_practice_answer', status: 'succeeded',
      enqueued_at: '2026-08-12T00:07:00Z', deduplicated: false, lane: 'interactive',
      retryable: false, failure_reference: null, result_ref: `PracticeResult:${jobId}`,
      result_hash: `practice-result-hash-${jobId}`,
    } })
  })
  await page.route('**/api/v1/jobs/mock-final-evaluation-e2e-1', route => route.fulfill({ json: {
    job_id: 'mock-final-evaluation-e2e-1', kind: 'evaluate_mock_final', status: 'running',
    enqueued_at: '2026-08-12T00:08:00Z', deduplicated: false, lane: 'interactive',
    retryable: false, failure_reference: null, result_ref: null, result_hash: null,
  } }))
  await page.route('**/api/v1/jobs/*generation-job-e2e-1', route => {
    const jobId = new URL(route.request().url()).pathname.split('/').at(-1)!
    return route.fulfill({ json: {
      job_id: jobId, kind: 'generate_topic_content', status: 'running',
      enqueued_at: '2026-08-12T00:02:00Z', deduplicated: false, lane: 'background',
      retryable: true, failure_reference: null, result_ref: null, result_hash: null,
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
  // Registered after the '**/api/v1/sources/*' route above so it wins on the longer path
  // (Playwright: "the most recently registered route takes precedence"). Only
  // 'source-e2e-active' (artifactProvenanceFixture's citation-e2e-1) has a resolvable
  // source_snapshot_id, so it is the only id with a matching snapshot below.
  await page.route('**/api/v1/sources/*/snapshots', async route => {
    const sourceId = new URL(route.request().url()).pathname.split('/').at(-2)
    await route.fulfill({ json: sourceId === SOURCE_SNAPSHOT_SUPPORTING.source_id ? [SOURCE_SNAPSHOT_SUPPORTING] : [] })
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
    { provider: 'codex', state: 'configured', reason: null, recovery_action: null, model: 'gpt-5.6-terra', adapter_version: 'codex-cli-adapter-v1', contract_version: 'codex-jsonl-agent-message-v1' },
    { provider: 'claude', state: 'authentication-unavailable', reason: 'The CLI did not confirm local authentication and configuration.', recovery_action: 'Complete the CLI\'s local sign-in, then refresh.', model: null, adapter_version: null, contract_version: null },
  ] }))
  await page.route('**/api/v1/disclosures/provider-generation/accept', async route => {
    providerDisclosureAccepted = true
    await route.fulfill({ json: { id: 'provider-disclosure-e2e', category: 'provider-generation', operation: 'Provider generation', destination: 'Selected model provider', data_categories: ['prompt reference', 'operation metadata'], disclosure_version: 'provider-network-v1', accepted_at: '2026-08-13T00:01:00Z', revoked_at: null } })
  })
  await page.route('**/api/v1/disclosures', route => route.fulfill({ json: [
    { id: providerDisclosureAccepted ? 'provider-disclosure-e2e' : null, category: 'provider-generation', operation: 'Provider generation', destination: 'Selected model provider', data_categories: ['prompt reference', 'operation metadata'], disclosure_version: 'provider-network-v1', accepted_at: providerDisclosureAccepted ? '2026-08-13T00:01:00Z' : null, revoked_at: null },
    { id: null, category: 'source-retrieval', operation: 'Explicit authoritative source retrieval', destination: 'Approved canonical URL', data_categories: ['source URL', 'operation metadata'], disclosure_version: 'source-network-v1', accepted_at: null, revoked_at: null },
  ] }))

  return {
    get profile() { return profile },
    get goals() { return goals },
    get diagnostic() { return diagnostic },
    get previewEdits() { return previewEdits },
    get imports() { return imports },
    get importStatements() { return importStatements },
    get notebookEntries() { return notebookEntries },
    get evidenceRecords() { return evidenceRecords },
    get assessments() { return assessments },
    get handsOnWorkspace() { return handsOnWorkspace },
    get canonicalDecision() { return canonicalDecision },
    get canonicalAccepted() { return canonicalAccepted },
    canonicalItems,
    get ownerSettings() { return ownerSettings },
    get providerDisclosureAccepted() { return providerDisclosureAccepted },
    lifecyclePolicy,
    evidenceSources,
    progress,
    get reviewPreferences() { return reviewPreferences },
    get reviewItems() { return reviewItems },
    get interviewBundles() { return interviewBundles },
    interviewRefreshers,
    interviewQuestions,
    get practiceRun() { return practiceRun },
    get mockRun() { return mockRun },
    get projectedTopics() { return projectedTopics },
    correctedClassifications,
  }
}
