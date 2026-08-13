import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CanonicalUpdatesPage, ImportsPage, SearchPage, SettingsPage } from './OperationalPages'

const profile = { experience: null, strengths: null, weaknesses: null, current_goal_id: 'goal-1', profile_revision: 1, updated_at: '2026-08-12T00:00:00Z' }
const goal = { id: 'goal-1', name: 'Reliable consumers', path: 'learn', subject: 'Distributed systems', role: null, target_level: 'Senior', target_capability: 'implement', graph_version_id: 'graph-1', status: 'active', resume_position: null, resume_destination: '/app/learn-roadmap', dismissed_recommendation_keys: [], last_accessed_at: null, row_version: 1, created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z' }
const record = { id: 'import-1', goal_id: 'goal-1', import_type: 'markdown', original_content: '# Exact original\n- SQS may redeliver.', original_hash: 'original-sha-256', parser_version: 'markdown-v1', status: 'learner-review', failure_code: null, failure_reference: null, created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z' }
const statement = { id: 'statement-1', import_id: 'import-1', sequence: 1, parser_version: 'markdown-v1', original_text: 'SQS may redeliver.', original_hash: 'statement-original-hash', normalized_text: 'sqs may redeliver', normalized_hash: 'normalized-hash', confidence: .95, duplicate_of_statement_id: null, trust_state: 'untrusted', mapping_state: 'unmapped', corrected_text: null, row_version: 1, created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z', mapping: null }
const roadmap = { goal_id: 'goal-1', graph_version_id: 'graph-1', projection_version: 'projection-1', state: 'ready', topics: [{ stable_id: 'approved-topic', title: 'Approved delivery topic', subject: 'Queues', level_tag: 'Senior', target_capability: 'implement', scope_tags: [], classification: 'unverified', recommended_depth: 'Implementation', depth_override: null, is_skipped: false, has_transferred_evidence: false, explanation: '', pending_proposals: [], conflicts: [] }] }

function json(value: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }))
}

function requestFrom(input: RequestInfo | URL, init?: RequestInit) {
  return input instanceof Request ? input : new Request(new URL(String(input), 'http://localhost'), init)
}

function renderImports() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}><ImportsPage /></QueryClientProvider>)
}

function renderCanonicalUpdates() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}><CanonicalUpdatesPage /></QueryClientProvider>)
}

function renderSearch(navigate = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return { navigate, ...render(<QueryClientProvider client={client}><SearchPage navigate={navigate} /></QueryClientProvider>) }
}

function renderSettings(navigate = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return { navigate, ...render(<QueryClientProvider client={client}><SettingsPage navigate={navigate} /></QueryClientProvider>) }
}

const settings = { progress_display: 'detailed', accessibility: { reduced_motion: false }, provider_selection: null, row_version: 1 }
const lifecyclePolicy = {
  policy_version: '1.0', import_original_max_bytes: 10485760, import_retained_owner_limit: 100,
  import_statements_per_import_limit: 10000, import_unreviewed_owner_limit: 50000,
  evidence_payload_max_bytes: 10485760, evidence_retained_owner_limit: 10000,
  generated_body_max_bytes: 2097152, generated_retained_owner_limit: 5000,
  interview_turns_per_session_limit: 1000, interview_bytes_per_session_limit: 10485760,
  interview_sessions_owner_limit: 200, runner_input_files_limit: 100,
  runner_input_bytes_limit: 10485760, runner_stdout_bytes_limit: 1048576,
  runner_stderr_bytes_limit: 1048576, runner_output_bytes_limit: 2097152,
  runner_temp_bytes_limit: 268435456, runner_temp_files_limit: 10000,
  overlay_proposal_pending_cap: 25, pending_job_cap: 100,
  diagnostic_abandoned_retention_days: 30, interview_inactive_retention_days: 30,
  terminal_job_retention_days: 30, job_event_retention_days: 7, job_event_owner_limit: 10000,
  runner_output_retention_days: 7, runner_workspace_retention_seconds: 3600,
  export_package_retention_seconds: 86400, export_operation_retention_days: 30,
  structured_log_file_count: 5, structured_log_file_max_bytes: 10485760,
  structured_log_total_max_bytes: 52428800, structured_log_retention_days: 14,
  export_format: 'yuno-portable-export', export_version: '1.0', export_available: true, recovery_window_days: 0,
  yuno_managed_backups: false, remote_support_access: false,
}
const reviewPreferences = { goal_id: 'goal-1', enabled: true, duration_minutes: 15, cadence: 'twice-weekly', retrieval_enabled: true, varied_context_enabled: true, scheduling_version: 'review-v1', row_version: 1, updated_at: '2026-08-13T00:00:00Z' }

function settingsRead(request: Request) {
  if (request.url.endsWith('/profile')) return json(profile)
  if (request.url.endsWith('/goals')) return json([goal])
  if (request.url.includes('/imports?')) return json([])
  if (request.url.endsWith('/goals/goal-1/review-preferences')) return json(reviewPreferences)
  if (request.url.endsWith('/settings/data-lifecycle-policy')) return json(lifecyclePolicy)
  if (request.url.endsWith('/settings') && request.method === 'GET') return json(settings)
  if (request.url.endsWith('/provider-capabilities')) return json([{ provider: 'codex', state: 'configured', reason: null, adapter_version: '1', contract_version: '1' }, { provider: 'claude', state: 'unavailable', reason: 'Not configured', adapter_version: null, contract_version: null }])
  if (request.url.endsWith('/disclosures')) return json([{ id: null, category: 'provider-generation', operation: 'Provider generation', destination: 'Selected model provider', data_categories: ['prompt reference', 'operation metadata'], disclosure_version: 'provider-network-v1', accepted_at: null, revoked_at: null }])
  return null
}

afterEach(() => vi.unstubAllGlobals())

describe('server-backed goal search', () => {
  it('shows the real stale state and labels deterministic fallback results as degraded', async () => {
    const navigate = vi.fn()
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([goal])
      if (request.url.endsWith('/search-index/status')) return json({ status: 'stale', source_watermark: 'watermark-42', active_generation: 'generation-1', rebuild_job_id: null, failure_reference: null, updated_at: '2026-08-13T00:00:00Z' })
      if (request.url.includes('/search?')) {
        const url = new URL(request.url)
        expect(url.searchParams.get('q')).toBe('idempotency')
        expect(url.searchParams.get('goal_id')).toBe('goal-1')
        return json({ results: [{ entity_type: 'evidence', entity_id: 'evidence-1', goal_id: 'goal-1', topic_stable_id: 'topic-1', title: 'Idempotency boundary evidence', body: 'Atomic write', tags: 'retry', degraded: true }], empty: false, degraded: true, index_status: 'stale' })
      }
      return json({}, 404)
    }))
    renderSearch(navigate)

    expect(await screen.findByText('Search index is stale')).toBeInTheDocument()
    expect(screen.getByText(/Source watermark: watermark-42/)).toBeInTheDocument()
    expect(screen.queryByText(/Bundled index may be stale/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Implement an idempotency boundary under concurrent retries/)).not.toBeInTheDocument()
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search current goal content' }), 'idempotency')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    expect(await screen.findByText('Degraded fallback results')).toBeInTheDocument()
    expect(screen.getByText('Idempotency boundary evidence')).toBeInTheDocument()
    expect(screen.getByText(/Topic topic-1 · degraded/)).toBeInTheDocument()
    await userEvent.click(screen.getByText('Idempotency boundary evidence'))
    expect(navigate).toHaveBeenCalledWith('evidence')
  })

  it('announces a rebuilding index with its job and keeps empty fallback results explicit', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([goal])
      if (request.url.endsWith('/search-index/status')) return json({ status: 'rebuilding', source_watermark: 'watermark-41', active_generation: 'generation-1', rebuild_job_id: 'job-7', failure_reference: null, updated_at: '2026-08-13T00:00:00Z' })
      if (request.url.includes('/search?')) return json({ results: [], empty: true, degraded: false, index_status: 'rebuilding' })
      return json({}, 404)
    }))
    renderSearch()

    expect(await screen.findByText('Search index is rebuilding')).toBeInTheDocument()
    expect(screen.getByText(/continues using the prior active index/)).toBeInTheDocument()
    expect(screen.getByText(/Rebuild job: job-7/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Rebuild index' })).not.toBeInTheDocument()
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search current goal content' }), 'missing')
    await userEvent.click(screen.getByRole('button', { name: 'Search' }))
    expect(await screen.findByText('No results for “missing”')).toBeInTheDocument()
  })
})

describe('server-backed settings and data lifecycle', () => {
  it('persists current-goal settings with its row revision', async () => {
    let goalPatch: { body: unknown; ifMatch: string | null } | null = null
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      const read = settingsRead(request)
      if (read) return read
      if (request.url.endsWith('/goals/goal-1') && request.method === 'PATCH') {
        goalPatch = { body: await request.json(), ifMatch: request.headers.get('If-Match') }
        return json({ ...goal, name: 'Reliable delivery systems', subject: 'Distributed delivery', target_level: 'Staff', target_capability: 'diagnose', row_version: 2 })
      }
      return json({}, 404)
    }))
    renderSettings()
    const name = await screen.findByRole('textbox', { name: 'Goal name' })
    await userEvent.clear(name)
    await userEvent.type(name, 'Reliable delivery systems')
    await userEvent.clear(screen.getByRole('textbox', { name: 'Subject' }))
    await userEvent.type(screen.getByRole('textbox', { name: 'Subject' }), 'Distributed delivery')
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Target level' }), 'Staff')
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Target capability' }), 'diagnose')
    await userEvent.click(screen.getByRole('button', { name: 'Save current goal' }))
    await waitFor(() => expect(goalPatch).not.toBeNull())
    expect(goalPatch!.ifMatch).toBe('1')
    expect(goalPatch!.body).toEqual({ name: 'Reliable delivery systems', subject: 'Distributed delivery', target_level: 'Staff', target_capability: 'diagnose' })
    expect(await screen.findByText('Current goal settings saved.')).toBeInTheDocument()
  })

  it('reloads the current goal and surfaces a stale revision failure', async () => {
    let goalReads = 0
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/goals')) {
        goalReads += 1
        return json([{ ...goal, ...(goalReads > 1 ? { name: 'Concurrent goal name', row_version: 2 } : {}) }])
      }
      const read = settingsRead(request)
      if (read) return read
      if (request.url.endsWith('/goals/goal-1') && request.method === 'PATCH') return json({ code: 'precondition_failed', message: 'Goal changed' }, 412)
      return json({}, 404)
    }))
    renderSettings()
    const name = await screen.findByRole('textbox', { name: 'Goal name' })
    await userEvent.clear(name)
    await userEvent.type(name, 'My stale edit')
    await userEvent.click(screen.getByRole('button', { name: 'Save current goal' }))
    expect(await screen.findByText(/goal changed before this save/i)).toBeInTheDocument()
    await waitFor(() => expect(name).toHaveValue('Concurrent goal name'))
    expect(goalReads).toBeGreaterThan(1)
  })

  it('persists reduced motion with If-Match, manages disclosure, and removes prototype local actions', async () => {
    let settingsPatch: { body: unknown; ifMatch: string | null } | null = null
    let disclosureAccepted = false
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      const read = settingsRead(request)
      if (read) return read
      if (request.url.endsWith('/settings') && request.method === 'PATCH') {
        settingsPatch = { body: await request.json(), ifMatch: request.headers.get('If-Match') }
        return json({ ...settings, accessibility: { reduced_motion: true }, row_version: 2 })
      }
      if (request.url.endsWith('/disclosures/provider-generation/accept')) {
        disclosureAccepted = true
        return json({ id: 'disclosure-1', category: 'provider-generation', operation: 'Provider generation', destination: 'Selected model provider', data_categories: ['prompt reference', 'operation metadata'], disclosure_version: 'provider-network-v1', accepted_at: '2026-08-13T00:01:00Z', revoked_at: null })
      }
      return json({}, 404)
    }))
    renderSettings()

    const reducedMotion = await screen.findByRole('checkbox', { name: /Reduce motion/i })
    await userEvent.click(reducedMotion)
    await waitFor(() => expect(settingsPatch).not.toBeNull())
    expect(settingsPatch!.body).toEqual({ accessibility: { reduced_motion: true } })
    expect(settingsPatch!.ifMatch).toBe('1')
    await userEvent.click(await screen.findByRole('button', { name: 'Accept disclosure' }))
    await waitFor(() => expect(disclosureAccepted).toBe(true))
    expect(screen.queryByRole('button', { name: /Export JSON/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Reset local pages/i })).not.toBeInTheDocument()
  })

  it('exposes the approved limits, lifecycle guarantees, and local export download', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      const read = settingsRead(request)
      if (read) return read
      if (request.url.endsWith('/exports') && request.method === 'POST') return json({ job_id: 'export-1', kind: 'export_data', status: 'queued', enqueued_at: '2026-08-13T00:01:00Z', deduplicated: false, attempt: 0 }, 202)
      if (request.url.endsWith('/exports/export-1')) return json({ id: 'export-1', goal_id: 'goal-1', status: 'complete', format: 'yuno-portable-export', version: '1.0', filename: 'yuno-export-v1-20260813T000200Z.json', package_hash: 'package-sha256', package_expires_at: '2026-08-14T00:02:00Z', metadata_expires_at: '2026-09-12T00:02:00Z', completed_at: '2026-08-13T00:02:00Z', download_available: true, job_id: 'export-1', result_ref: 'ExportOperation:export-1', failure_reference: null, created_at: '2026-08-13T00:01:00Z', updated_at: '2026-08-13T00:02:00Z' })
      return json({}, 404)
    }))
    renderSettings()
    await userEvent.click(await screen.findByRole('button', { name: 'Create export' }))
    expect(await screen.findByText(/Export complete · yuno-portable-export 1.0/)).toBeInTheDocument()
    const download = screen.getByRole('link', { name: /Download yuno-export-v1-20260813T000200Z.json/ })
    expect(download).toHaveAttribute('href', '/api/v1/exports/export-1/download')
    await userEvent.click(screen.getByText(/Data limits and retention/))
    expect(screen.getByText(/10 MiB each, 100 retained per owner/)).toBeInTheDocument()
    expect(screen.getByText(/5 local files of at most 10 MiB each \(50 MiB total\)/)).toBeInTheDocument()
    expect(screen.getByText(/Deletion is irreversible/)).toBeInTheDocument()
    expect(screen.getAllByText(/no Yuno-managed backup/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/no remote support access/i)).toBeInTheDocument()
  })

  it('keeps export disabled until the privacy review passes', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/settings/data-lifecycle-policy')) return json({ ...lifecyclePolicy, export_available: false })
      const read = settingsRead(request)
      if (read) return read
      return json({}, 404)
    }))
    renderSettings()
    expect(await screen.findByText(/Portable export is disabled until the required privacy review passes/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create export' })).toBeDisabled()
  })

  it('requires irreversible confirmation before deleting import and interview bodies', async () => {
    const deleted: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.includes('/imports?')) return json([record])
      if (request.method === 'DELETE' && request.url.endsWith('/imports/import-1')) {
        deleted.push('import-1')
        return new Response(null, { status: 204 })
      }
      if (request.method === 'DELETE' && request.url.endsWith('/interview-runs/run-1')) {
        deleted.push('run-1')
        return new Response(null, { status: 204 })
      }
      const read = settingsRead(request)
      if (read) return read
      return json({}, 404)
    }))
    renderSettings()

    await userEvent.click(await screen.findByRole('button', { name: 'Delete import import-1' }))
    const importDialog = screen.getByRole('alertdialog', { name: 'Delete this import body?' })
    expect(within(importDialog).getByText(/no undelete, recovery window, or Yuno-managed backup/i)).toBeInTheDocument()
    await userEvent.click(within(importDialog).getByRole('button', { name: 'Confirm import body deletion' }))
    await waitFor(() => expect(deleted).toContain('import-1'))

    await userEvent.type(screen.getByRole('textbox', { name: 'Interview session ID' }), 'run-1')
    await userEvent.click(screen.getByRole('button', { name: 'Delete session body' }))
    const sessionDialog = screen.getByRole('alertdialog', { name: 'Delete this interview session body?' })
    expect(within(sessionDialog).getByText(/transcript turns, drafts, answers, and feedback/i)).toBeInTheDocument()
    await userEvent.click(within(sessionDialog).getByRole('button', { name: 'Confirm session body deletion' }))
    await waitFor(() => expect(deleted).toEqual(['import-1', 'run-1']))
  })

  it('requires a refreshed impact after stale delete confirmation and restores trigger focus on cancel', async () => {
    let preflights = 0
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      const read = settingsRead(request)
      if (read) return read
      if (request.url.endsWith('/goals/goal-1/delete-preflight')) {
        preflights += 1
        return json({ operation_id: `delete-${preflights}`, snapshot_id: `snapshot-${preflights}`, goal_id: 'goal-1', evidence_ids: ['cross-goal-evidence'], learning_state_ids: ['dependent-state'], status: 'preflight', created_at: '2026-08-13T00:01:00Z' })
      }
      if (request.url.endsWith('/goals/goal-1/delete')) return json({ code: 'delete_impact_stale', message: 'Impact changed' }, 409)
      return json({}, 404)
    }))
    renderSettings()
    const trigger = await screen.findByRole('button', { name: 'Preview deletion' })
    await userEvent.click(trigger)
    expect(await screen.findByText('cross-goal-evidence')).toBeInTheDocument()
    expect(screen.getByText('dependent-state')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Confirm deletion' }))
    expect(await screen.findByText('Deletion impact changed')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Refresh impact' }))
    expect(await screen.findByText('snapshot-2')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    await waitFor(() => expect(trigger).toHaveFocus())
  })

  it('polls a completed delete and refreshes profile and goals', async () => {
    let profileReads = 0
    let goalReads = 0
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/profile')) { profileReads += 1; return json(profile) }
      if (request.url.endsWith('/goals')) { goalReads += 1; return json([goal]) }
      const read = settingsRead(request)
      if (read) return read
      if (request.url.endsWith('/goals/goal-1/delete-preflight')) return json({ operation_id: 'delete-complete', snapshot_id: 'snapshot-complete', goal_id: 'goal-1', evidence_ids: [], learning_state_ids: [], status: 'preflight', created_at: '2026-08-13T00:01:00Z' })
      if (request.url.endsWith('/goals/goal-1/delete')) return json({ job_id: 'delete-complete', kind: 'delete_goal', status: 'queued', enqueued_at: '2026-08-13T00:01:00Z', deduplicated: false, attempt: 0 }, 202)
      if (request.url.endsWith('/delete-operations/delete-complete')) return json({ id: 'delete-complete', goal_id: 'goal-1', snapshot_id: 'snapshot-complete', evidence_ids: [], learning_state_ids: [], status: 'cleanup-failed', cleanup_pending_count: 1, cleanup_failure_classifications: ['cleanup-permission-denied'], job_id: 'delete-complete', failure_reference: null, created_at: '2026-08-13T00:01:00Z', updated_at: '2026-08-13T00:02:00Z' })
      return json({}, 404)
    }))
    renderSettings()
    const trigger = await screen.findByRole('button', { name: 'Preview deletion' })
    await userEvent.click(trigger)
    await userEvent.click(await screen.findByRole('button', { name: 'Confirm deletion' }))
    expect(await screen.findByText(/Delete cleanup-failed · cleanup-permission-denied/)).toBeInTheDocument()
    await waitFor(() => {
      expect(profileReads).toBeGreaterThan(1)
      expect(goalReads).toBeGreaterThan(1)
      expect(trigger).toHaveFocus()
    })
  })
})

describe('server-backed import review', () => {
  it('shows exact provenance and maps only to topics returned by the current roadmap', async () => {
    let mapping: { body: unknown; idempotencyKey: string | null; ifMatch: string | null } | null = null
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([goal])
      if (request.url.endsWith('/goals/goal-1/roadmap')) return json(roadmap)
      if (request.url.includes('/imports?')) return json([record])
      if (request.url.endsWith('/imports/import-1')) return json(record)
      if (request.url.endsWith('/imports/import-1/statements')) return json([statement])
      if (request.url.endsWith('/import-statements/statement-1/map') && request.method === 'POST') {
        mapping = { body: await request.json(), idempotencyKey: request.headers.get('Idempotency-Key'), ifMatch: request.headers.get('If-Match') }
        const mapped = { ...statement, mapping_state: 'mapped', mapping: { goal_id: 'goal-1', topic_id: 'approved-topic', graph_version_id: 'graph-1', decision: 'approved', accepted_at: '2026-08-12T00:01:00Z', revoked_at: null } }
        return json({ statement: mapped, mapping: mapped.mapping, topic_imports_hash: { goal_id: 'goal-1', topic_id: 'approved-topic', graph_version_id: 'graph-1', imports_hash: 'mapped-imports-hash', updated_at: '2026-08-12T00:01:00Z' } })
      }
      return json({}, 404)
    }))
    renderImports()

    expect(await screen.findByRole('textbox', { name: 'Preserved original text' })).toHaveValue(record.original_content)
    expect(screen.getByText(record.original_hash)).toBeInTheDocument()
    expect(screen.getByText(statement.normalized_hash)).toBeInTheDocument()
    expect(screen.getByText(/markdown-v1 · confidence 95%/)).toBeInTheDocument()
    const card = screen.getByText(`“${statement.original_text}”`).closest('article')!
    const topicSelect = within(card).getByRole('combobox', { name: /Map to an approved topic/i })
    expect(within(topicSelect).getAllByRole('option').map(option => option.textContent)).toEqual(['Not mapped', 'Approved delivery topic'])
    await userEvent.selectOptions(topicSelect, 'approved-topic')
    await userEvent.click(within(card).getByRole('button', { name: 'Map' }))
    await waitFor(() => expect(mapping).not.toBeNull())
    expect(mapping!.body).toEqual({ goal_id: 'goal-1', topic_id: 'approved-topic' })
    expect(mapping!.idempotencyKey).toBeTruthy()
    expect(mapping!.ifMatch).toBe('1')
    expect(screen.getByText(/cannot alter canonical lessons, create evidence, establish completion/i)).toBeInTheDocument()
  })

  it('preserves a failed import and exposes retry without claiming the queued job completed', async () => {
    const failed = { ...record, status: 'failed', parser_version: null, failure_code: 'parse_failed', failure_reference: 'failure-ref' }
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([goal])
      if (request.url.endsWith('/goals/goal-1/roadmap')) return json(roadmap)
      if (request.url.includes('/imports?')) return json([failed])
      if (request.url.endsWith('/imports/import-1/statements')) return json([])
      if (request.url.endsWith('/imports/import-1/parse') && request.method === 'POST') return json({ job_id: 'job-1', kind: 'import-parse', status: 'queued', enqueued_at: '2026-08-12T00:02:00Z', deduplicated: false }, 202)
      if (request.url.endsWith('/imports/import-1')) return json(failed)
      return json({}, 404)
    }))
    renderImports()

    expect(await screen.findByText('parse_failed · failure-ref')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Preserved original text' })).toHaveValue(record.original_content)
    await userEvent.click(screen.getByRole('button', { name: 'Retry parse' }))
    expect(await screen.findByText('Parse job queued')).toBeInTheDocument()
    expect(screen.getByText(/receipt does not claim parsing completed/i)).toBeInTheDocument()
  })
})

describe('server-backed canonical updates', () => {
  const update = {
    state: 'conflict-needs-resolution', goal_id: 'goal-1',
    base_version: { id: 'graph-1', version_label: '2026.07' }, target_version: { id: 'graph-2', version_label: '2026.08' },
    proposal: { id: 'proposal-1', status: 'awaiting', diff_hash: 'direct-v1-v2', items: [
      { id: 'visibility', entity_type: 'content', change_type: 'modified', topic_id: 'visibility', title: 'Visibility timeout and retry budgets', summary: 'Choose a timeout longer than expected processing.', impact: 'Refines the production checklist.', conflict_type: null, selected: true, recommended_resolution: 'accept-canonical', chosen_resolution: 'accept-canonical', resolution_explanation: 'Choose from measured latency and bound renewal.' },
      { id: 'idempotency', entity_type: 'content', change_type: 'modified', topic_id: 'idempotency', title: 'Idempotency boundary', summary: 'Store the message ID before the business write.', impact: 'Conflicts with your unique-constraint overlay.', conflict_type: 'overlay-conflict', selected: true, recommended_resolution: 'overlay-wins', chosen_resolution: 'overlay-wins', resolution_explanation: 'Make the business decision and duplicate marker atomic.' },
      { id: 'removed-topic', entity_type: 'topic', change_type: 'deleted', topic_id: 'removed-topic', title: 'Legacy retry loop', summary: 'A locally annotated topic existed in the base graph.', impact: 'This topic carries learner evidence.', conflict_type: 'local-state-on-deleted-topic', selected: true, recommended_resolution: 'overlay-wins', chosen_resolution: 'overlay-wins', resolution_explanation: 'Retain the personal state as an archived local topic.' },
    ] },
  } as const

  it('keeps selection as a client draft and sends every complete resolution only after confirmation', async () => {
    let acceptance: { body: unknown } | null = null
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([goal])
      if (request.url.endsWith('/goals/goal-1/canonical-update')) return json(update)
      if (request.url.endsWith('/canonical-update-proposals/proposal-1/accept')) {
        acceptance = { body: await request.json() }
        return json({ proposal_id: 'proposal-1', status: 'accepted', goal_id: 'goal-1', base_version_id: 'graph-1', target_version_id: 'graph-2', goal_graph_version_id: 'graph-2', accepted_at: '2026-08-13T00:00:00Z', invalidation_state: 'dispatched', reprocess_job: null })
      }
      return json({}, 404)
    }))
    renderCanonicalUpdates()

    expect(await screen.findByLabelText('Goal pinned to 2026.07')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Keep my overlay wording/i })).toBeChecked()
    expect(screen.getByRole('radio', { name: /Keep as an archived local topic/i })).toBeChecked()
    expect(screen.queryByRole('radio', { name: /Adopt the upstream removal/i })).not.toBeInTheDocument()
    expect(screen.getByText(/Archived local topic/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('checkbox', { name: /Select Visibility timeout/i }))
    expect(acceptance).toBeNull()
    await userEvent.click(screen.getAllByRole('radio', { name: /Adopt the new canonical wording/i })[0]!)
    await userEvent.click(screen.getByRole('checkbox', { name: /Approve this exact local selection/i }))
    await userEvent.click(screen.getByRole('button', { name: /Accept selected/i }))

    await waitFor(() => expect(acceptance).not.toBeNull())
    expect(acceptance!.body).toEqual({ confirmed: true, items: [
      { item_id: 'visibility', selected: false, resolution: 'retain-local' },
      { item_id: 'idempotency', selected: true, resolution: 'accept-canonical' },
      { item_id: 'removed-topic', selected: true, resolution: 'overlay-wins' },
    ] })
    expect(await screen.findByText(/2 selected changes accepted/i)).toBeInTheDocument()
  })

  it.each(['postpone', 'dismiss'] as const)('%ss without moving the visible pin', async decision => {
    let posted: { body: unknown; key: string | null } | null = null
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([goal])
      if (request.url.endsWith('/goals/goal-1/canonical-update')) return json(update)
      if (request.url.endsWith('/canonical-update-proposals/proposal-1/decision')) {
        posted = { body: await request.json(), key: request.headers.get('Idempotency-Key') }
        return json({ proposal_id: 'proposal-1', status: decision === 'postpone' ? 'postponed' : 'dismissed', decided_at: '2026-08-13T00:00:00Z' })
      }
      return json({}, 404)
    }))
    renderCanonicalUpdates()
    await screen.findByLabelText('Goal pinned to 2026.07')
    await userEvent.click(screen.getByRole('button', { name: decision === 'postpone' ? 'Postpone' : 'Dismiss' }))
    await waitFor(() => expect(posted?.body).toEqual({ decision, reason: null }))
    expect(posted!.key).toBeTruthy()
    expect(screen.getByLabelText('Goal pinned to 2026.07')).toBeInTheDocument()
    expect(await screen.findByText(`Update ${decision === 'postpone' ? 'postponed' : 'dismissed'}`)).toBeInTheDocument()
  })

  it('permits an explicitly confirmed all-retained selection', async () => {
    let submitted: { items: Array<{ selected: boolean; resolution: string }> } | null = null
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([goal])
      if (request.url.endsWith('/goals/goal-1/canonical-update')) return json(update)
      if (request.url.endsWith('/canonical-update-proposals/proposal-1/accept')) {
        submitted = await request.json() as typeof submitted
        return json({ proposal_id: 'proposal-1', status: 'accepted', goal_id: 'goal-1', base_version_id: 'graph-1', target_version_id: 'graph-2', goal_graph_version_id: 'graph-2', accepted_at: '2026-08-13T00:00:00Z', invalidation_state: 'dispatched', reprocess_job: null })
      }
      return json({}, 404)
    }))
    renderCanonicalUpdates()
    await screen.findByLabelText('Goal pinned to 2026.07')
    for (const checkbox of screen.getAllByRole('checkbox', { name: /^Select / })) await userEvent.click(checkbox)
    await userEvent.click(screen.getByRole('checkbox', { name: /Approve this exact local selection/i }))
    await userEvent.click(screen.getByRole('button', { name: /Accept selected/i }))
    await waitFor(() => expect(submitted).not.toBeNull())
    expect(submitted!.items).toHaveLength(update.proposal.items.length)
    expect(submitted!.items.every(item => !item.selected && item.resolution === 'retain-local')).toBe(true)
  })

  it('refetches and requires renewed confirmation after a stale 409', async () => {
    let reads = 0
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([goal])
      if (request.url.endsWith('/goals/goal-1/canonical-update')) { reads += 1; return json(reads === 1 ? update : { ...update, proposal: { ...update.proposal, id: 'proposal-2', diff_hash: 'recomputed-direct-diff' } }) }
      if (request.url.endsWith('/canonical-update-proposals/proposal-1/accept')) return json({ code: 'proposal_stale', message: 'Fetch the current base-to-latest diff.' }, 409)
      return json({}, 404)
    }))
    renderCanonicalUpdates()
    await screen.findByLabelText('Goal pinned to 2026.07')
    await userEvent.click(screen.getByRole('checkbox', { name: /Approve this exact local selection/i }))
    await userEvent.click(screen.getByRole('button', { name: /Accept selected/i }))
    expect(await screen.findByText(/proposal changed before acceptance/i)).toBeInTheDocument()
    expect(reads).toBeGreaterThanOrEqual(2)
    expect(screen.getByRole('checkbox', { name: /Approve this exact local selection/i })).not.toBeChecked()
  })

  it('reuses the same idempotency key when an unchanged acceptance intent is retried', async () => {
    const keys: Array<string | null> = []
    const bodies: unknown[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const request = requestFrom(input, init)
      if (request.url.endsWith('/profile')) return json(profile)
      if (request.url.endsWith('/goals')) return json([goal])
      if (request.url.endsWith('/goals/goal-1/canonical-update')) return json(update)
      if (request.url.endsWith('/canonical-update-proposals/proposal-1/accept')) {
        keys.push(request.headers.get('Idempotency-Key'))
        bodies.push(await request.json())
        if (keys.length === 1) return json({ message: 'Temporary failure' }, 503)
        return json({ proposal_id: 'proposal-1', status: 'accepted', goal_id: 'goal-1', base_version_id: 'graph-1', target_version_id: 'graph-2', goal_graph_version_id: 'graph-2', accepted_at: '2026-08-13T00:00:00Z', invalidation_state: 'dispatched', reprocess_job: null })
      }
      return json({}, 404)
    }))
    renderCanonicalUpdates()
    await screen.findByLabelText('Goal pinned to 2026.07')
    await userEvent.click(screen.getByRole('checkbox', { name: /Approve this exact local selection/i }))
    await userEvent.click(screen.getByRole('button', { name: /Accept selected/i }))
    expect(await screen.findByText(/decision was not saved/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Accept selected/i }))
    await waitFor(() => expect(keys.length).toBe(2))
    expect(keys[0]).toBeTruthy()
    expect(keys[1]).toBe(keys[0])
    expect(bodies[1]).toEqual(bodies[0])
  })
})
