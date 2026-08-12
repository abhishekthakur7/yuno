import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CanonicalUpdatesPage, ImportsPage } from './OperationalPages'

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

afterEach(() => vi.unstubAllGlobals())

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
