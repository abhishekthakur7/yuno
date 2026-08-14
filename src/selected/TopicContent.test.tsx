import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { ArtifactProvenanceSummary, SourceSnapshot, TopicLayerContent } from '../shared/api/learning-content'
import { TopicLayerPanel } from './core/CorePages'

const layer = (patch: Partial<TopicLayerContent> = {}): TopicLayerContent => ({
  layer: 'Essential', state: 'ready', revision_id: null, markdown: 'Original generated body.', markdown_hash: 'body-hash', checkpoint: null,
  artifact_id: 'artifact-1', content_origin: 'generated', generation: null, stale_reason: null, ...patch,
})

// citation-1: has a snapshot with a canonical URL, retrieved_at, and version_label — the full-data case.
// citation-2: withdrawn source with no canonical_url and a snapshot whose version_label is null.
// citation-3: source_snapshot_id is null — the "no snapshot exists" case.
const provenance: ArtifactProvenanceSummary = {
  artifact_id: 'artifact-1', baked_snapshot: { id: 'snapshot-1', evidence_state_hash: 'evidence-hash', profile_hash: 'profile-hash', provider: 'fixture', model: 'deterministic-v1', generated_at: '2026-08-12T00:00:00Z', prompt_template_version: 'fixture-v0', schema_version: 'generate-result-v1', contract_version: 'fixture-v0', snapshot_hash: 'snapshot-hash' }, current_snapshot_hash: 'snapshot-hash', stale: false, stale_reasons: [], refs: [],
  claims: [
    { id: 'claim-sensitive', claim_text: 'A version-dependent behavior changed.', claim_type: 'time-or-version-dependent', sensitive: true, citations: [
      { id: 'citation-1', locator: 'Section 4', support_kind: 'direct', note: null, source_snapshot_id: 'source-snapshot-1', source: { id: 'source-active', origin: 'fixture', source_type: 'specification', title: 'Primary specification', publisher: 'Standards body', canonical_url: 'https://example.test/spec', license_status: 'synthetic', availability_status: 'available', created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z' } },
      { id: 'citation-2', locator: 'Archived section', support_kind: 'historical', note: null, source_snapshot_id: 'source-snapshot-2', source: { id: 'source-withdrawn', origin: 'fixture', source_type: 'advisory', title: 'Withdrawn advisory', publisher: 'Vendor', canonical_url: null, license_status: 'synthetic', availability_status: 'withdrawn', created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z' } },
      { id: 'citation-3', locator: 'Front page', support_kind: 'direct', note: null, source_snapshot_id: null, source: { id: 'source-live-only', origin: 'fixture', source_type: 'advisory', title: 'Live-only reference', publisher: 'Community', canonical_url: 'https://example.test/live', license_status: 'link-only', availability_status: 'available', created_at: '2026-08-12T00:00:00Z', updated_at: '2026-08-12T00:00:00Z' } },
    ] },
    { id: 'claim-routine', claim_text: 'Routine explanatory content.', claim_type: 'routine', sensitive: false, citations: [] },
  ],
}

const provenanceSnapshots = new Map<string, SourceSnapshot>([
  ['source-snapshot-1', { id: 'source-snapshot-1', source_id: 'source-active', retrieved_at: '2026-08-10T00:00:00Z', content_ref: 'ref-1', content_hash: 'hash-1', status: 'complete', version_label: 'PostgreSQL 16' }],
  ['source-snapshot-2', { id: 'source-snapshot-2', source_id: 'source-withdrawn', retrieved_at: '2026-01-01T00:00:00Z', content_ref: 'ref-2', content_hash: 'hash-2', status: 'complete', version_label: null }],
])

function panel(content: TopicLayerContent | undefined, overrides: Partial<React.ComponentProps<typeof TopicLayerPanel>> = {}) {
  const props: React.ComponentProps<typeof TopicLayerPanel> = {
    layerName: 'Essential', layer: content, checkpointNumber: 1, isPending: false, isError: false, onRetry: vi.fn(), onGenerate: vi.fn(), onRegenerate: vi.fn(), actionPending: false, actionError: false, anchorId: undefined, ...overrides,
  }
  const { container } = render(<TopicLayerPanel {...props} />)
  return { ...props, container }
}

describe('generated topic content presentation', () => {
  it('moves from absent to generating without inventing a body', async () => {
    const props = panel(layer({ state: 'absent', artifact_id: null, markdown: null, markdown_hash: null }))
    expect(screen.queryByText('Original generated body.')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Generate Essential' }))
    expect(props.onGenerate).toHaveBeenCalledOnce()

    panel(layer({ state: 'generating', markdown: null, markdown_hash: null, generation: { job_id: 'job-1', status: 'running', failure_reference: null, retryable: true } }))
    expect(screen.getByRole('heading', { name: 'Generating Essential' })).toBeInTheDocument()
    expect(screen.queryByText('Original generated body.')).not.toBeInTheDocument()
  })

  it('keeps the stale body visible and regenerates only after explicit action', async () => {
    const props = panel(layer({ state: 'stale', stale_reason: 'personalization-snapshot-mismatch' }))
    expect(screen.getByText('Original generated body.')).toBeInTheDocument()
    expect(screen.getByText(/existing content remains visible and unchanged/i)).toBeInTheDocument()
    expect(props.onRegenerate).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Regenerate' }))
    expect(props.onRegenerate).toHaveBeenCalledWith('artifact-1')
    panel(layer({ state: 'stale', stale_reason: 'personalization-snapshot-mismatch', generation: { job_id: 'job-2', status: 'queued', failure_reference: null, retryable: true } }))
    expect(screen.getAllByText('Original generated body.')).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Generating…' })).toBeDisabled()
  })

  it('retains the prior body after a failed attempt and offers retry', async () => {
    const props = panel(layer({ generation: { job_id: 'job-failed', status: 'failed', failure_reference: 'generation-ref-1', retryable: true } }))
    expect(screen.getByText('Original generated body.')).toBeInTheDocument()
    expect(screen.getByText('generation-ref-1')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Retry generation' }))
    expect(props.onRegenerate).toHaveBeenCalledWith('artifact-1')
  })

  it('reports a failed first generation without publishing partial content', async () => {
    const props = panel(layer({ state: 'unavailable', markdown: null, markdown_hash: null, generation: { job_id: 'job-failed', status: 'failed', failure_reference: 'generation-ref-2', retryable: true } }))
    expect(screen.queryByText('Original generated body.')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Essential generation failed' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Retry generation' }))
    expect(props.onRegenerate).toHaveBeenCalledWith('artifact-1')
  })

  it('expands artifact-scoped citations, routine provenance, and withdrawn warnings', async () => {
    panel(layer(), { provenance, provenanceSnapshots })
    await userEvent.click(screen.getByText('About this content'))
    expect(screen.getByText('A version-dependent behavior changed.')).toBeInTheDocument()
    expect(screen.getByText('Primary specification')).toBeInTheDocument()
    expect(screen.getByText(/Section 4/)).toBeInTheDocument()
    expect(screen.getByText('Routine explanatory content.')).toBeInTheDocument()
    expect(screen.getByText(/Routine claim · no citation required/i)).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Withdrawn advisory is withdrawn')
  })

  it('renders citation attribution per IDK-003 §7: canonical URL as a link, snapshot fields, and the verbatim no-snapshot fallback', async () => {
    const { container } = panel(layer(), { provenance, provenanceSnapshots })
    await userEvent.click(screen.getByText('About this content'))

    // Field 3 — canonical URL is an actual link (citation-1), never a broken anchor for a null canonical_url (citation-2).
    const link = screen.getByRole('link', { name: 'https://example.test/spec' })
    expect(link).toHaveAttribute('href', 'https://example.test/spec')

    // Field 4 — retrieval timestamp of the referenced snapshot (citation-1).
    expect(screen.getByText('2026-08-10T00:00:00Z')).toBeInTheDocument()
    // Field 6 — version label, present for citation-1's snapshot.
    expect(screen.getByText('PostgreSQL 16')).toBeInTheDocument()

    // citation-2's snapshot has a null version_label: the row is omitted, not rendered empty or "null".
    // Only citation-1 contributes a "Version label" row.
    expect(screen.getAllByText('Version label')).toHaveLength(1)
    // citation-2's source has a null canonical_url: no link is rendered for it (only citation-1's and citation-3's links exist).
    expect(screen.getAllByRole('link')).toHaveLength(2)

    // Field 4 fallback — citation-3 has source_snapshot_id: null, so the verbatim IDK-003:97 string is shown.
    expect(screen.getByText('not yet retrieved — citation references the live source only')).toBeInTheDocument()

    // Ruling B — the raw license_status enum is never rendered, anywhere.
    expect(container.textContent).not.toContain('synthetic')
    expect(container.textContent).not.toContain('link-only')
  })
})
