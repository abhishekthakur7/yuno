import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ImportsPage } from './OperationalPages'

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
