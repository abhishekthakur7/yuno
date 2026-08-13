import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as AlertDialog from '@radix-ui/react-alert-dialog'
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronRight,
  Clock3,
  Database,
  Download,
  FileDiff,
  FileText,
  History,
  Import,
  Info,
  RefreshCcw,
  Search,
  Settings2,
  ShieldAlert,
  SlidersHorizontal,
  UserRound,
  X,
} from 'lucide-react'
import type { ImportStatement, JobRef } from '../../shared/api/imports'
import { useImports } from '../../shared/use-imports'
import { useProfileGoals } from '../../shared/use-profile-goals'
import { useRoadmap } from '../../shared/use-roadmap'
import { useReviewPreferences } from '../../shared/use-notebook-review'
import { useEvidence } from '../../shared/use-evidence'
import { useOwnerSettings } from '../../shared/use-settings'
import { useSearch } from '../../shared/use-search'
import { useProviderSettings } from '../../shared/use-provider-settings'
import { useDataOperations } from '../../shared/use-data-operations'
import type { GoalWorkspace } from '../../shared/api/profile-goals'
import type { ReviewPreferencesPatch } from '../../shared/api/notebook-review'
import { deleteInterviewSessionBody } from '../../shared/api/interview'
import { cancelJob, jobsQueryOptions, retryJob } from '../../shared/api/jobs'
import { acceptCanonicalUpdate, canonicalUpdateQueryOptions, decideCanonicalUpdate, type CanonicalUpdateItem, type CanonicalUpdateResolution } from '../../shared/api/canonical-updates'
import { ApiError } from '../../shared/api/queries'
import { JobConnectionStatus } from '../../shared/job-events'
import './operations.css'

export type OperationalPage = 'evidence' | 'imports' | 'canonical-updates' | 'search' | 'jobs' | 'settings'

type Navigate = (page: string) => void

function Button({ children, tone = 'primary', ...props }: React.ComponentPropsWithRef<'button'> & { tone?: 'primary' | 'secondary' | 'quiet' | 'danger' }) {
  return <button className={`so-button so-button--${tone}`} {...props}>{children}</button>
}

function PageHead({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: React.ReactNode }) {
  return <header className="so-page-head"><div><span className="so-eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action}</header>
}

function Disclosure({ children }: { children: React.ReactNode }) {
  return <aside className="so-disclosure"><Info size={18} aria-hidden="true" /><div>{children}</div></aside>
}

export function EvidencePage({ navigate }: { navigate: Navigate }) {
  const { currentGoal } = useProfileGoals()
  const workspace = useEvidence(currentGoal?.id ?? null)
  const ownerSettings = useOwnerSettings()
  const latestEvidence = workspace.evidence.data?.at(-1)
  const assessment = workspace.assessment.data
  const olderEvidence = (workspace.evidence.data ?? []).slice(0, -1).reverse()
  const limitation = assessment?.limitation_labels[0] ?? assessment?.warnings[0] ?? 'This conclusion is limited to the submitted artifact and evaluation method.'
  const nextAction = assessment?.revision_invitation ?? (latestEvidence ? 'Defend the same decision in a new failure scenario.' : 'Open Topic Studio and review the current artifact. Static checks do not create evidence.')
  const unavailableSources = workspace.sources.data.filter(source => source.availability_status === 'withdrawn' || source.availability_status === 'unavailable')
  const latestDispute = assessment?.disputes.at(-1)
  const disputes = workspace.assessmentHistory.data.flatMap(item => item.disputes)
  const evidenceFailed = workspace.evidence.isError
  const evidencePending = workspace.evidence.isPending && !workspace.evidence.data
  const assessmentPending = Boolean(workspace.assessmentId) && workspace.assessment.isPending
  return <>
    <PageHead eyebrow="Evidence · resilient order fulfillment" title="What your work supports" description="Conclusions are qualified by the artifact, rubric, and review method—not by lesson consumption." />
    <section className={`so-hero-card so-evidence-hero ${latestEvidence ? '' : 'is-unavailable'}`} aria-labelledby="so-conclusion">
      <div className="so-status-icon">{latestEvidence ? <Check size={24} /> : <FileText size={24} />}</div>
      <div><span className="so-kicker">{latestEvidence ? 'Latest submitted conclusion' : evidencePending ? 'Evidence loading' : 'Evidence unavailable'}</span><h2 id="so-conclusion">{evidenceFailed ? 'Evidence could not be loaded.' : evidencePending ? 'Loading submitted evidence…' : assessment?.feedback ?? latestEvidence?.summary ?? 'No submitted lab evidence is available yet.'}</h2><p><strong>Limitation:</strong> {evidenceFailed ? 'No conclusion can be drawn until the evidence list is available.' : evidencePending ? 'No evidence conclusion is inferred before the server read completes.' : latestEvidence ? limitation : 'Only an explicit submission creates an evidence record. No progress or qualification is inferred from a draft.'}</p></div>
      <div className="so-next"><span>Next useful action</span><strong>{evidenceFailed ? 'Retry the evidence list while the rest of this page remains usable.' : evidencePending ? 'Keep this page open while the submitted-evidence read completes.' : nextAction}</strong>{evidenceFailed ? <Button tone="secondary" onClick={() => void workspace.evidence.refetch()}>Retry evidence</Button> : !evidencePending && <Button tone="secondary" onClick={() => navigate(latestEvidence ? 'practice' : 'topic-studio')}>{latestEvidence ? 'Open transfer check' : 'Open Topic Studio'} <ArrowRight size={16} /></Button>}</div>
    </section>
    {unavailableSources.length > 0 && <aside className="so-warning so-tombstone-warning" role="alert"><AlertTriangle size={20} /><div><strong>Tombstoned source warning: cited source withdrawn or unavailable</strong><p>{unavailableSources.map(source => source.title).join(', ')} remains in provenance history, but its content may no longer be inspected.</p></div></aside>}
    <details className="so-details"><summary><span><History size={18} /> Rubric, state, and assumptions <small>Dimensions, ambiguity, limits, and evaluation method</small></span><ChevronRight size={18} /></summary><div className="so-inspection">{workspace.assessment.isError ? <RegionFailure label="Assessment detail" retry={() => void workspace.assessment.refetch()} /> : assessmentPending ? <p>Loading assessment detail…</p> : assessment ? <><dl className="so-facts"><dt>Assessment state</dt><dd>{assessment.state}</dd></dl>{assessment.state === 'ambiguity-unresolved' && <aside className="so-warning"><AlertTriangle size={18} /><div><strong>Ambiguity unresolved</strong><p>This uncertainty is shown explicitly and carries no readiness penalty.</p></div></aside>}<h3>Ambiguities</h3>{assessment.ambiguities.length ? <ul>{assessment.ambiguities.map(item => <li key={item}>{item}</li>)}</ul> : <p>No unresolved ambiguities recorded.</p>}<div className="so-rubric">{assessment.dimensions.map(dimension => <article key={dimension.dimension_id}><Check size={17} /><div><strong>{dimension.dimension_id} · {dimension.outcome}</strong><p>{dimension.rationale}</p></div></article>)}</div><h3>Assumptions</h3>{assessment.assumptions.length ? <ul>{assessment.assumptions.map(item => <li key={item}>{item}</li>)}</ul> : <p>No assumptions recorded.</p>}</> : <p>No assessment is attached to this evidence.</p>}</div></details>
    <details className="so-details"><summary><span><History size={18} /> Sources and provenance <small>Citations, artifact, and authority</small></span><ChevronRight size={18} /></summary><div className="so-inspection">{workspace.detail.isError ? <RegionFailure label="Evidence provenance" retry={() => void workspace.detail.refetch()} /> : workspace.detail.isPending && latestEvidence ? <p>Loading evidence provenance…</p> : latestEvidence ? <><dl className="so-facts"><dt>Record</dt><dd>{latestEvidence.id}</dd><dt>Origin</dt><dd>{latestEvidence.origin}</dd><dt>Payload hash</dt><dd>{latestEvidence.payload_hash}</dd><dt>Method</dt><dd>{assessmentPending ? 'Loading assessment method…' : assessment?.evaluation_method ?? 'No assessment available'}</dd><dt>Citations</dt><dd>{assessmentPending ? 'Loading citations…' : assessment?.citations.join(', ') || 'None'}</dd><dt>Provenance refs</dt><dd>{assessmentPending ? 'Loading provenance references…' : assessment?.provenance_refs.join(', ') || 'None'}</dd></dl>{workspace.sources.isError ? <RegionFailure label="Cited sources" retry={() => void workspace.sources.refetch()} /> : workspace.sources.isPending ? <p>Loading cited sources…</p> : workspace.sources.data.map(source => <p key={source.id}><strong>{source.title}</strong> · {source.availability_status} {source.availability_status !== 'withdrawn' && <Button tone="quiet" disabled={workspace.sourceRetrieval.isPending} onClick={() => workspace.sourceRetrieval.mutate(source.id)}>Retrieve current snapshot</Button>}</p>)}{workspace.sourceRetrieval.isError && <p className="so-error" role="alert">{workspace.sourceRetrieval.error instanceof ApiError && workspace.sourceRetrieval.error.status === 412 ? 'Waiting for disclosure. Accept the current source-network disclosure in Settings, then retry.' : 'Source retrieval did not start. Retry from this explicit control.'}</p>}{workspace.sourceJob.data && <p role="status">Source retrieval {workspace.sourceJob.data.status}{workspace.sourceJob.data.status === 'failed' && workspace.sourceJob.data.retryable ? ' · retry available from Jobs' : ''}.</p>}</> : <p>No submitted artifact exists, so there is no evidence provenance to inspect.</p>}</div></details>
    <details className="so-details"><summary><span><History size={18} /> Transfer lineage <small>Goal-to-goal derivation</small></span><ChevronRight size={18} /></summary><div className="so-timeline">{workspace.detail.isError ? <RegionFailure label="Transfer lineage" retry={() => void workspace.detail.refetch()} /> : workspace.detail.isPending && latestEvidence ? <p>Loading transfer lineage…</p> : workspace.detail.data?.transfers.length ? workspace.detail.data.transfers.map(item => <article key={item.id}><span>{item.classification} · {item.target_goal_id}</span><strong>{item.learning_state_id}</strong><p>{item.rationale}</p></article>) : <p>No transfer lineage is recorded.</p>}</div></details>
    <details className="so-details"><summary><span><History size={18} /> Disputes and re-evaluation <small>Append-only correction history</small></span><ChevronRight size={18} /></summary><div className="so-timeline">{workspace.assessmentHistory.isError ? <RegionFailure label="Assessment history" retry={() => void workspace.assessmentHistory.refetch()} /> : workspace.assessmentHistory.isPending ? <p>Loading disputes and re-evaluation history…</p> : disputes.length ? disputes.map(dispute => <article key={dispute.id}><span>{dispute.requested_at} · {dispute.status}</span><strong>{dispute.reason}</strong><p>{dispute.reevaluation ? `Re-evaluation: ${dispute.reevaluation.status}` : 'No re-evaluation requested.'}</p></article>) : <p>No disputes or re-evaluations are recorded.</p>}</div></details>
    <details className="so-details"><summary><span><History size={18} /> Evidence and assessment history <small>{olderEvidence.length} older evidence record{olderEvidence.length === 1 ? '' : 's'} · {workspace.assessmentHistory.data.length} assessment revision{workspace.assessmentHistory.data.length === 1 ? '' : 's'}</small></span><ChevronRight size={18} /></summary><div className="so-timeline">{workspace.assessmentHistory.isError ? <RegionFailure label="Assessment history" retry={() => void workspace.assessmentHistory.refetch()} /> : workspace.assessmentHistory.isPending ? <p>Loading assessment history…</p> : workspace.assessmentHistory.data.length ? workspace.assessmentHistory.data.map((item, index) => <article key={item.id}><span>{item.created_at} · {item.state}</span><strong>{item.feedback}</strong><p>Assessment {item.id}{item.predecessor_assessment_id ? ` · predecessor ${item.predecessor_assessment_id}` : ' · original assessment'}</p><div className="so-rubric">{item.dimensions.map(dimension => <article key={`${item.id}-${dimension.dimension_id}`}><Check size={15} /><div><strong>{dimension.dimension_id} · {dimension.outcome}</strong><p>{dimension.rationale}</p></div></article>)}</div>{index === 0 && <span className="so-chip so-chip--green">Current</span>}</article>) : <p>No assessment history is available.</p>}{olderEvidence.map(item => <article key={item.id}><span>{item.created_at} · evidence</span><strong>{item.summary}</strong><p>{item.evidence_type} · {item.capability}</p></article>)}</div></details>
    <ProgressDisclosure progress={workspace.progress} display={ownerSettings.settings.data?.progress_display ?? null} settings={ownerSettings.settings} />
    {latestEvidence && assessment && <section className="so-panel so-dispute"><div><span className="so-kicker">Correction and dispute</span><h2>{latestDispute ? 'Assessment dispute recorded' : 'Something about this assessment is wrong?'}</h2><p>The original assessment is preserved. Unresolved ambiguity does not lower readiness.</p>{workspace.dispute.isError && <p className="so-error" role="alert">The dispute was not recorded. Nothing changed; try again.</p>}{workspace.reevaluate.isError && <p className="so-error" role="alert">Re-evaluation could not be requested. The dispute and assessment remain preserved; try again.</p>}</div>{latestDispute && !latestDispute.reevaluation ? <Button tone="secondary" disabled={workspace.reevaluate.isPending} onClick={() => workspace.reevaluate.mutate({ assessmentId: assessment.id, disputeId: latestDispute.id })}>Request re-evaluation</Button> : <Button tone="secondary" disabled={Boolean(latestDispute) || workspace.dispute.isPending} onClick={() => workspace.dispute.mutate({ assessmentId: assessment.id, reason: 'The learner requested correction and re-evaluation.' })}>{latestDispute ? latestDispute.reevaluation ? `Re-evaluation ${latestDispute.reevaluation.status}` : 'Dispute recorded' : workspace.dispute.isError ? 'Retry dispute' : 'Record dispute'}</Button>}</section>}
  </>
}

type ProgressQuery = ReturnType<typeof useEvidence>['progress']
type SettingsQuery = ReturnType<typeof useOwnerSettings>['settings']
function ProgressDisclosure({ progress, display, settings }: { progress: ProgressQuery; display: 'simple' | 'detailed' | null; settings: SettingsQuery }) {
  return <details className="so-details" data-progress-display={display ?? 'loading'}><summary><span><History size={18} /> Learning progress <small>{display === 'detailed' ? 'Classifications, definitions, uncertainty, and evidence links' : display === 'simple' ? 'Condensed classifications' : 'Loading display preference'}</small></span><ChevronRight size={18} /></summary><div className="so-inspection">{settings.isError ? <RegionFailure label="Progress display preference" retry={() => void settings.refetch()} /> : display === null ? <p>Loading progress display preference…</p> : progress.isError ? <RegionFailure label="Learning progress" retry={() => void progress.refetch()} /> : progress.data ? <div className="so-rubric">{(['coverage', 'proficiency', 'retention', 'readiness'] as const).map(key => <article key={key}><Check size={17} /><div><strong>{key} · {progress.data![key].classification}</strong>{display === 'detailed' && <><p>{progress.data![key].definition}</p><p>Uncertainty: {progress.data![key].uncertainty}</p><p>Evidence: {progress.data![key].supporting_evidence_refs.join(', ') || 'None'}</p></>}</div></article>)}</div> : <p>Loading progress…</p>}</div></details>
}

function RegionFailure({ label, retry }: { label: string; retry: () => void }) {
  return <div className="so-region-failure" role="alert"><p>{label} could not be loaded. Other evidence regions remain available.</p><Button tone="secondary" onClick={retry}>Retry {label.toLowerCase()}</Button></div>
}

function ImportStatementReview({ statement, topics, goalId, workspace }: { statement: ImportStatement; topics: { stable_id: string; title: string }[]; goalId: string; workspace: ReturnType<typeof useImports> }) {
  const [correctedText, setCorrectedText] = useState(statement.corrected_text ?? statement.original_text)
  const [topicId, setTopicId] = useState(statement.mapping?.topic_id ?? '')
  const busy = workspace.correct.isPending || workspace.map.isPending || workspace.verify.isPending || workspace.dismiss.isPending
  const decisionError = workspace.correct.isError || workspace.map.isError || workspace.verify.isError || workspace.dismiss.isError
  return <article className={statement.trust_state === 'dismissed' ? 'is-muted' : ''}>
    <div className="so-statement-number">{statement.sequence}</div>
    <div>
      <div className="so-provenance-chips"><span className="so-chip">{statement.trust_state}</span><span className="so-chip so-chip--gray">{statement.mapping_state}</span>{statement.duplicate_of_statement_id && <span className="so-chip so-chip--amber">Duplicate</span>}</div>
      <p className="so-original">“{statement.original_text}”</p>
      <dl className="so-import-provenance"><dt>Original hash</dt><dd>{statement.original_hash}</dd><dt>Normalized hash</dt><dd>{statement.normalized_hash}</dd><dt>Parser</dt><dd>{statement.parser_version} · confidence {Math.round(statement.confidence * 100)}%</dd>{statement.duplicate_of_statement_id && <><dt>Duplicate of</dt><dd>{statement.duplicate_of_statement_id}</dd></>}</dl>
      <label>Corrected wording<textarea disabled={busy || statement.trust_state === 'dismissed'} value={correctedText} onChange={(event) => setCorrectedText(event.target.value)} /></label>
      <Button tone="quiet" disabled={busy || statement.trust_state === 'dismissed' || !correctedText.trim() || correctedText === (statement.corrected_text ?? statement.original_text)} onClick={() => workspace.correct.mutate({ statement, body: { corrected_text: correctedText } })}>Save correction</Button>
      <label>Map to an approved topic in this goal<select disabled={busy || statement.trust_state === 'dismissed' || statement.mapping_state === 'duplicate'} value={topicId} onChange={(event) => setTopicId(event.target.value)}><option value="">Not mapped</option>{topics.map(topic => <option key={topic.stable_id} value={topic.stable_id}>{topic.title}</option>)}</select></label>
      {statement.mapping && <p className="so-help">Mapped to {statement.mapping.topic_id} against graph {statement.mapping.graph_version_id}. This is a personal association only.</p>}
      {decisionError && <p className="so-error" role="alert">That decision was not saved. The statement remains unchanged; retry when ready.</p>}
    </div>
    <div className="so-row-actions">
      <Button tone="quiet" disabled={busy || !topicId || statement.trust_state === 'dismissed' || statement.mapping_state === 'duplicate'} onClick={() => workspace.map.mutate({ statement, body: { goal_id: goalId, topic_id: topicId } })}>Map</Button>
      <Button tone="quiet" disabled={busy || statement.trust_state !== 'untrusted'} onClick={() => workspace.verify.mutate(statement)}><Check size={15} /> Verify as mine</Button>
      <Button tone="quiet" disabled={busy || statement.trust_state === 'dismissed'} onClick={() => workspace.dismiss.mutate(statement)}><X size={15} /> Dismiss</Button>
    </div>
  </article>
}

export function ImportsPage() {
  const { currentGoal } = useProfileGoals()
  const roadmap = useRoadmap(currentGoal?.id ?? null)
  const [selectedImportId, setSelectedImportId] = useState<string | null>(null)
  const workspace = useImports(currentGoal?.id ?? null, selectedImportId)
  const [source, setSource] = useState('')
  const [importType, setImportType] = useState<'markdown' | 'plain_text'>('markdown')
  const [job, setJob] = useState<JobRef | null>(null)
  const imports = workspace.imports.data ?? []
  useEffect(() => {
    if (!selectedImportId && imports[0]) setSelectedImportId(imports[0].id)
  }, [imports, selectedImportId])
  const selected = workspace.selectedImport.data
  const topics = (roadmap.roadmap.data?.topics ?? []).map(topic => ({ stable_id: topic.stable_id, title: topic.title }))
  const saveAndParse = async () => {
    if (!currentGoal || !source) return
    const created = await workspace.create.mutateAsync({ goal_id: currentGoal.id, import_type: importType, original_content: source })
    setSelectedImportId(created.id)
    setSource('')
    const accepted = await workspace.parse.mutateAsync(created.id)
    setJob(accepted)
  }
  return <>
    <PageHead eyebrow="Import review" title="Bring notes in as untrusted material" description="The server preserves your exact original and parses it asynchronously. No import action creates canonical truth, evidence, completion, or a new topic." />
    {!currentGoal ? <div className="so-empty"><FileText size={28} /><h2>Select a current goal first</h2><p>Imports need a goal so every mapping can be checked against that goal’s approved graph.</p></div> : <>
      <section className="so-panel so-import-box"><label htmlFor="so-import-source"><span className="so-kicker">New original</span><strong>Paste Markdown or plain text</strong></label><label>Format<select value={importType} onChange={(event) => setImportType(event.target.value as 'markdown' | 'plain_text')}><option value="markdown">Markdown</option><option value="plain_text">Plain text</option></select></label><textarea id="so-import-source" value={source} onChange={(event) => setSource(event.target.value)} placeholder={'# Messaging notes\n- SQS may redeliver messages.'} /><div className="so-inline-actions"><span>The exact text is immutable after saving.</span><Button disabled={!source || workspace.create.isPending || workspace.parse.isPending} onClick={() => void saveAndParse()}><Import size={17} /> {workspace.create.isPending || workspace.parse.isPending ? 'Saving and queueing…' : 'Save and queue parse'}</Button></div>{(workspace.create.isError || workspace.parse.isError) && <p className="so-error" role="alert">The original or parse job could not be saved. Review the text and retry.</p>}</section>
      {job && <div className="so-decision-banner" aria-live="polite"><Clock3 size={18} /><div><strong>Parse job {job.status}</strong><p>Job {job.job_id} ({job.kind}) was accepted at {job.enqueued_at}{job.deduplicated ? ' and matched an existing active job' : ''}. This receipt does not claim parsing completed.</p></div><Button tone="secondary" onClick={() => void workspace.refreshSelected()}>Refresh import</Button></div>}
      <JobConnectionStatus ids={[job?.job_id]} />
      {workspace.imports.isPending ? <div className="so-empty"><Clock3 size={28} /><h2>Loading imports…</h2></div> : workspace.imports.isError ? <div className="so-empty"><AlertTriangle size={28} /><h2>Imports unavailable</h2><p>No local fixture was substituted.</p><Button tone="secondary" onClick={() => void workspace.imports.refetch()}>Retry</Button></div> : imports.length === 0 ? <div className="so-empty"><FileText size={28} /><h2>No imports yet</h2><p>Save an exact original above to queue server-side parsing.</p></div> : <>
        <section className="so-panel so-import-picker"><label htmlFor="so-import-picker"><span className="so-kicker">Saved originals</span><strong>Choose an import to inspect</strong></label><select id="so-import-picker" value={selectedImportId ?? ''} onChange={(event) => { setSelectedImportId(event.target.value); setJob(null) }}>{imports.map(item => <option key={item.id} value={item.id}>{item.import_type} · {item.status} · {item.original_hash.slice(0, 12)}</option>)}</select></section>
        {workspace.selectedImport.isPending ? <div className="so-empty"><Clock3 size={28} /><h2>Loading preserved original…</h2></div> : workspace.selectedImport.isError || !selected ? <div className="so-empty"><AlertTriangle size={28} /><h2>Original unavailable</h2><Button tone="secondary" onClick={() => void workspace.selectedImport.refetch()}>Retry</Button></div> : <section className="so-panel so-import-original"><div className="so-panel-head"><div><FileText size={20} /><h2>Preserved original</h2></div><span className={`so-chip ${selected.status === 'failed' || selected.status === 'cancelled' ? 'so-chip--amber' : 'so-chip--gray'}`}>{selected.status}</span></div><textarea readOnly aria-label="Preserved original text" value={selected.original_content} /><dl className="so-facts"><dt>SHA-256</dt><dd>{selected.original_hash}</dd><dt>Parser</dt><dd>{selected.parser_version ?? 'Not parsed yet'}</dd><dt>Failure</dt><dd>{selected.failure_code ? `${selected.failure_code}${selected.failure_reference ? ` · ${selected.failure_reference}` : ''}` : 'None reported'}</dd></dl><div className="so-inline-actions"><span>Original content remains inspectable even if parsing fails.</span>{selected.status === 'failed' || selected.status === 'cancelled' ? <Button tone="secondary" disabled={workspace.parse.isPending} onClick={() => workspace.parse.mutate(selected.id, { onSuccess: setJob })}>Retry parse</Button> : <Button tone="secondary" disabled={workspace.reprocess.isPending} onClick={() => workspace.reprocess.mutate(selected.id, { onSuccess: setJob })}>Reprocess unmapped</Button>}</div></section>}
        {workspace.statements.isPending ? <div className="so-empty"><Clock3 size={28} /><h2>Loading statements…</h2></div> : workspace.statements.isError ? <div className="so-empty"><AlertTriangle size={28} /><h2>Statements unavailable</h2><p>The original remains preserved.</p><Button tone="secondary" onClick={() => void workspace.statements.refetch()}>Retry</Button></div> : (workspace.statements.data ?? []).length === 0 ? <div className="so-empty"><FileText size={28} /><h2>No statements available</h2><p>The parse may still be queued, may have failed, or may have produced no statements. Refresh the import to inspect its current status.</p></div> : <section aria-labelledby="so-review-title"><div className="so-section-head"><div><span className="so-kicker">Parsed as untrusted</span><h2 id="so-review-title">Review {(workspace.statements.data ?? []).length} ordered statements</h2></div><span>{(workspace.statements.data ?? []).filter(item => item.trust_state !== 'untrusted').length} decided</span></div><div className="so-statement-list">{(workspace.statements.data ?? []).map(statement => <ImportStatementReview key={statement.id} statement={statement} topics={topics} goalId={currentGoal.id} workspace={workspace} />)}</div><Disclosure><strong>Mapping and verification are personal decisions, not factual or editorial authority.</strong><p>Imported material cannot alter canonical lessons, create evidence, establish completion, or expand the approved graph.</p></Disclosure></section>}
      </>}
    </>}
  </>
}

export function CanonicalUpdatesPage() {
  const { currentGoal } = useProfileGoals()
  const queryClient = useQueryClient()
  const update = useQuery(canonicalUpdateQueryOptions(currentGoal?.id ?? null))
  const proposal = update.data?.proposal ?? null
  const [selected, setSelected] = useState<string[]>([])
  const [resolutions, setResolutions] = useState<Record<string, CanonicalUpdateResolution>>({})
  const [approvalConfirmed, setApprovalConfirmed] = useState(false)
  const [transition, setTransition] = useState<'accepted' | 'postponed' | 'dismissed' | 'stale' | null>(null)
  const [acceptedTopics, setAcceptedTopics] = useState<string[]>([])
  const [acceptedVersion, setAcceptedVersion] = useState<string | null>(null)
  const idempotencyKeys = useRef(new Map<string, string>())
  const idempotencyKeyFor = (intent: string) => {
    const existing = idempotencyKeys.current.get(intent)
    if (existing) return existing
    const created = crypto.randomUUID()
    idempotencyKeys.current.set(intent, created)
    return created
  }
  useEffect(() => {
    if (!proposal) return
    setSelected(proposal.items.filter(item => item.selected).map(item => item.id))
    setResolutions(Object.fromEntries(proposal.items.map(item => [item.id, item.chosen_resolution ?? item.recommended_resolution])))
    setApprovalConfirmed(false)
  }, [proposal?.id, proposal?.diff_hash])
  const changeSelection = (id: string, checked: boolean) => {
    setApprovalConfirmed(false)
    setSelected((current) => checked ? [...current, id] : current.filter((item) => item !== id))
  }
  const acceptMutation = useMutation({
    mutationFn: async () => {
      const body = {
        confirmed: true as const,
        items: proposal!.items.map(item => ({
        item_id: item.id,
        selected: selected.includes(item.id),
        resolution: selected.includes(item.id) ? (resolutions[item.id] ?? item.recommended_resolution) : 'retain-local',
      })),
      }
      const intent = `accept:${proposal!.id}:${JSON.stringify(body)}`
      return acceptCanonicalUpdate(proposal!.id, body, idempotencyKeyFor(intent))
    },
    onSuccess: async response => {
      setAcceptedTopics(proposal!.items.filter(item => selected.includes(item.id)).map(item => item.title))
      setAcceptedVersion(update.data?.target_version?.version_label ?? response.goal_graph_version_id)
      setTransition('accepted')
      setApprovalConfirmed(false)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['goals'] }),
        queryClient.invalidateQueries({ queryKey: ['goals', currentGoal?.id, 'roadmap'] }),
        queryClient.invalidateQueries({ queryKey: ['goals', currentGoal?.id, 'topics'] }),
        queryClient.invalidateQueries({ queryKey: ['imports'] }),
        queryClient.invalidateQueries({ queryKey: ['search'] }),
      ])
    },
    onError: async (error) => {
      if (error instanceof ApiError && error.status === 409) {
        setTransition('stale')
        setApprovalConfirmed(false)
        await update.refetch()
      }
    },
  })
  const decisionMutation = useMutation({
    mutationFn: (decision: 'postpone' | 'dismiss') => {
      const intent = `decision:${proposal!.id}:${decision}`
      return decideCanonicalUpdate(proposal!.id, decision, idempotencyKeyFor(intent))
    },
    onSuccess: response => { setTransition(response.status); setApprovalConfirmed(false) },
  })
  const recordNonAcceptance = (decision: 'postpone' | 'dismiss') => decisionMutation.mutate(decision)
  const items = proposal?.items ?? []
  const state = transition ?? update.data?.state
  const decisionClosed = state === 'accepted' || state === 'postponed' || state === 'dismissed' || proposal?.status === 'accepted'
  const pinLabel = transition === 'accepted' ? acceptedVersion : update.data?.base_version.version_label
  if (!currentGoal) return <><PageHead eyebrow="Published curriculum update" title="Review changes before they reach this goal" description="Select a current goal to inspect its canonical update." /><div className="so-empty"><FileDiff size={28} /><h2>No current goal selected</h2><p>Select a goal before reviewing published curriculum changes.</p></div></>
  if (update.isPending) return <><PageHead eyebrow="Published curriculum update" title="Review changes before they reach this goal" description="Loading the current base-to-latest diff." /><div className="so-empty"><Clock3 size={28} /><h2>Loading canonical update…</h2></div></>
  if (update.isError || !update.data) return <><PageHead eyebrow="Published curriculum update" title="Review changes before they reach this goal" description="The current update could not be loaded." /><div className="so-empty"><AlertTriangle size={28} /><h2>Canonical update unavailable</h2><p>No local fixture was substituted.</p><Button tone="secondary" onClick={() => void update.refetch()}>Retry</Button></div></>
  if (update.data.state === 'empty' && transition !== 'accepted') return <><PageHead eyebrow="Published curriculum update" title="Review changes before they reach this goal" description={`This goal is pinned to ${update.data.base_version.version_label}, the latest approved version.`} action={<div className="so-version" aria-label={`Goal pinned to ${update.data.base_version.version_label}`}><span>Pinned</span><ArrowRight size={17} /><strong>{update.data.base_version.version_label}</strong></div>} /><div className="so-empty"><Check size={28} /><h2>No canonical update available</h2><p>This goal already uses the latest approved curriculum graph.</p><Button tone="secondary" onClick={() => void update.refetch()}>Refresh</Button></div></>
  return <>
    <PageHead eyebrow="Published curriculum update" title="Review changes before they reach this goal" description={`This goal is pinned to ${update.data.base_version.version_label}. Version ${update.data.target_version?.version_label ?? pinLabel} is available, but nothing changes until you explicitly accept a selection.`} action={<div className="so-version" aria-label={`Goal pinned to ${pinLabel}`}><span>Pinned</span><ArrowRight size={17} /><strong>{pinLabel}</strong></div>} />
    {(state === 'accepted' || state === 'postponed' || state === 'dismissed') && <div className="so-decision-banner"><Check size={18} /><div><strong>{state === 'accepted' ? `${acceptedTopics.length} selected change${acceptedTopics.length === 1 ? '' : 's'} accepted` : `Update ${state}`}</strong>{state === 'accepted' ? <><p>Accepted: {acceptedTopics.join(', ') || 'none'}.</p><p>The goal now uses the target canonical version; retained personal wording was recorded as target-version overlay state.</p></> : <p>This decision is persisted and the proposal is closed. The current goal version and personal overlay remain unchanged.</p>}</div></div>}
    {state === 'stale' && <div className="so-warning" role="alert"><AlertTriangle size={19} /><div><strong>The proposal changed before acceptance</strong><p>The current base-to-latest diff was recomputed. Review it again before confirming.</p></div><Button tone="secondary" onClick={() => void update.refetch()}>Refresh</Button></div>}
    {(acceptMutation.isError && state !== 'stale' || decisionMutation.isError) && <div className="so-warning" role="alert"><AlertTriangle size={19} /><div><strong>The decision was not saved</strong><p>The goal pin and overlay remain unchanged. Review the current proposal and try again.</p></div></div>}
    <section className="so-update-summary"><article><strong>{items.length}</strong><span>changes</span></article><article><strong>{items.filter(item => item.conflict_type).length}</strong><span>overlay conflicts</span></article><article><strong>{items.filter(item => item.conflict_type === 'local-state-on-deleted-topic').length}</strong><span>archived local topics</span></article><p>Acceptance atomically moves this goal’s server version pin and records retained selections. It never edits or publishes canonical content.</p></section>
    <div className="so-diff-list">{items.map((item) => <CanonicalUpdateRow key={item.id} item={item} base={update.data.base_version.version_label} target={update.data.target_version?.version_label ?? ''} selected={selected.includes(item.id)} resolution={resolutions[item.id] ?? item.recommended_resolution} disabled={decisionClosed} onSelect={checked => changeSelection(item.id, checked)} onResolve={resolution => { setResolutions(current => ({ ...current, [item.id]: resolution })); setApprovalConfirmed(false) }} />)}</div>
    <div className="so-approval"><label><input type="checkbox" checked={approvalConfirmed} disabled={items.length === 0 || decisionClosed} onChange={(event) => setApprovalConfirmed(event.target.checked)} /><span><strong>Approve this exact local selection</strong><small>I reviewed every selected change, conflict resolution, and unselected retention. Nothing updates until I press “Accept selected.”</small></span></label></div>
    <div className="so-sticky-actions"><span>{decisionClosed ? 'Decision persisted · proposal closed' : `${selected.length} of ${items.length} selected · ${selected.filter(id => items.find(item => item.id === id)?.conflict_type).length} conflicts selected`}</span><div><Button tone="quiet" disabled={decisionMutation.isPending || decisionClosed} onClick={() => recordNonAcceptance('dismiss')}>Dismiss</Button><Button tone="secondary" disabled={decisionMutation.isPending || decisionClosed} onClick={() => recordNonAcceptance('postpone')}>Postpone</Button><Button tone="secondary" disabled={decisionClosed} onClick={() => { setSelected(items.map(item => item.id)); setApprovalConfirmed(false) }}>Select all</Button><Button disabled={items.length === 0 || !approvalConfirmed || acceptMutation.isPending || decisionClosed} onClick={() => acceptMutation.mutate()}>{acceptMutation.isPending ? 'Accepting…' : 'Accept selected'}</Button></div></div>
  </>
}

function CanonicalUpdateRow({ item, base, target, selected, resolution, disabled, onSelect, onResolve }: { item: CanonicalUpdateItem; base: string; target: string; selected: boolean; resolution: CanonicalUpdateResolution; disabled: boolean; onSelect: (checked: boolean) => void; onResolve: (resolution: CanonicalUpdateResolution) => void }) {
  const archived = item.conflict_type === 'local-state-on-deleted-topic'
  return <article><label className="so-select-change"><input type="checkbox" disabled={disabled} checked={selected} onChange={event => onSelect(event.target.checked)} /><span className="so-sr-only">Select {item.title}</span></label><div><span className="so-kicker">{item.title}</span><div className="so-diff"><div><span>{base}</span><p>{item.summary}</p></div><div><span>{target}</span><p>{item.change_type === 'deleted' ? 'Removed from the published canonical graph.' : item.resolution_explanation}</p></div></div><p className="so-impact"><Info size={15} /> {item.impact}</p>{archived && <p className="so-archived-topic"><strong>Archived local topic</strong> — acceptance keeps this topic and its evidence/overlay history explicitly archived instead of silently hiding it.</p>}{item.conflict_type && selected && <fieldset className="so-conflict" disabled={disabled}><legend>{archived ? 'Resolve removed topic conflict' : 'Resolve wording conflict'}</legend><label><input type="radio" name={`resolution-${item.id}`} checked={resolution === 'overlay-wins'} onChange={() => onResolve('overlay-wins')} /><span><strong>{archived ? 'Keep as an archived local topic' : 'Keep my overlay wording'}</strong><small>{archived ? 'The published topic remains removed while its learner evidence and personal state stay available in an explicit local archive.' : 'The goal retains your wording for this topic against the target version.'}</small></span></label>{!archived && <label><input type="radio" name={`resolution-${item.id}`} checked={resolution === 'accept-canonical'} onChange={() => onResolve('accept-canonical')} /><span><strong>Adopt the new canonical wording</strong><small>Your overlay wording is replaced for this goal by the target canonical wording.</small></span></label>}</fieldset>}</div></article>
}

const SEARCH_KIND_LABELS: Record<string, string> = {
  'canonical-topic': 'Topic',
  'canonical-content': 'Content',
  'generated-artifact': 'Generated',
  'notebook-entry': 'Notebook',
  evidence: 'Evidence',
}

export function SearchPage({ navigate }: { navigate: Navigate }) {
  const { currentGoal } = useProfileGoals()
  const [query, setQuery] = useState('')
  const [submitted, setSubmitted] = useState('')
  const search = useSearch(currentGoal?.id ?? null, submitted)
  const status = search.status.data
  const results = search.results.data?.results ?? []
  const degraded = search.results.data?.degraded ?? false
  const statusUnavailable = search.status.isError
  const needsAttention = status && status.status !== 'ready'
  const servingActiveIndex = Boolean(status?.active_generation) && (status?.status === 'rebuilding' || status?.status === 'failed')
  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitted(query.trim())
  }
  const openResult = (entityType: string) => navigate(entityType === 'evidence' ? 'evidence' : 'topic-studio')
  return <>
    <PageHead eyebrow="Course and content search" title="Find a lesson, reading, review, or evidence record" description="Search approved and owned content in the current goal. Search stays local and does not retrieve external sources." />
    <form className="so-search" role="search" onSubmit={submit}><Search size={20} /><label className="so-sr-only" htmlFor="so-search-input">Search current goal content</label><input id="so-search-input" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Try “idempotency” or “dead letter”" /><Button type="submit" disabled={!query.trim() || !currentGoal}>Search</Button></form>
    <p className="so-sr-only" aria-live="polite">{search.results.isFetching ? `Searching for ${submitted}` : submitted && search.results.data ? `${results.length} search result${results.length === 1 ? '' : 's'}${degraded ? ' from the degraded fallback' : ''}` : ''}</p>
    {needsAttention && <div className="so-warning" role="status"><AlertTriangle size={19} /><div><strong>{status.status === 'rebuilding' ? 'Search index is rebuilding' : status.status === 'stale' ? 'Search index is stale' : status.status === 'failed' ? 'Search index rebuild failed' : 'Search index is unavailable'}</strong><p>{servingActiveIndex ? 'Search continues using the prior active index while this state is resolved.' : `Search uses the deterministic owned-content fallback while the index is ${status.status}.`} Source watermark: {status.source_watermark || 'not yet built'}{status.rebuild_job_id ? ` · Rebuild job: ${status.rebuild_job_id}` : ''}{status.failure_reference ? ` · Failure: ${status.failure_reference}` : ''}.</p></div>{status.status !== 'rebuilding' && <Button tone="secondary" disabled={search.rebuild.isPending} onClick={() => search.rebuild.mutate()}><RefreshCcw className={search.rebuild.isPending ? 'so-spin' : ''} size={16} /> {search.rebuild.isPending ? 'Starting…' : 'Rebuild index'}</Button>}</div>}
    {statusUnavailable && <div className="so-warning" role="alert"><AlertTriangle size={19} /><div><strong>Search index status unavailable</strong><p>The index state could not be verified. Retry the status check before relying on indexed results.</p></div><Button tone="secondary" onClick={() => void search.status.refetch()}>Retry status</Button></div>}
    {search.rebuild.isError && <div className="so-warning" role="alert"><AlertTriangle size={19} /><div><strong>Rebuild did not start</strong><p>The current index state is unchanged. Try again.</p></div></div>}
    {search.results.isError && <RegionFailure label="Search results" retry={() => void search.results.refetch()} />}
    {!currentGoal ? <div className="so-empty"><Search size={29} /><h2>No current goal selected</h2><p>Select a goal before searching owned course content.</p></div> : !submitted ? <div className="so-empty"><Search size={29} /><h2>Search your current goal</h2><p>Results include approved topics and content, generated artifacts, notebook entries, and eligible evidence metadata.</p></div> : search.results.isPending ? <div className="so-empty"><Clock3 size={29} /><h2>Searching…</h2><p>Checking content owned by this goal.</p></div> : !search.results.isError && results.length === 0 ? <div className="so-empty"><Search size={29} /><h2>No results for “{submitted}”</h2><p>Try another title, body, or tag term.</p></div> : results.length > 0 && <section><div className="so-section-head"><div><span className="so-kicker">{degraded ? 'Degraded fallback results' : 'Indexed results'}</span><h2>{results.length} match{results.length === 1 ? '' : 'es'} for “{submitted}”</h2></div><span>{degraded ? `Fallback · ${search.results.data?.index_status}` : 'Current goal only'}</span></div><div className="so-results">{results.map((item) => <button key={`${item.entity_type}-${item.entity_id}`} onClick={() => openResult(item.entity_type)}><span className="so-chip">{SEARCH_KIND_LABELS[item.entity_type] ?? item.entity_type}</span><strong>{item.title}</strong><small>{item.topic_stable_id ? `Topic ${item.topic_stable_id}` : item.tags || item.entity_id}{item.degraded ? ' · degraded' : ''}</small><ChevronRight size={19} /></button>)}</div></section>}
  </>
}

export function JobsPage({ navigate = () => undefined }: { navigate?: Navigate }) {
  const queryClient = useQueryClient()
  const jobs = useQuery(jobsQueryOptions())
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ['jobs'] })
  const cancel = useMutation({ mutationFn: cancelJob, onSuccess: refresh })
  const retry = useMutation({ mutationFn: retryJob, onSuccess: refresh })
  const [substitutionRef, setSubstitutionRef] = useState('')
  const records = jobs.data?.jobs ?? []
  const activeJobIds = records.filter(job => ['queued', 'running', 'cancel-requested'].includes(job.status)).map(job => job.job_id)
  return <>
    <PageHead eyebrow="Operations" title="Jobs and local activity" description="Inspect the durable interactive and background lanes, retry recoverable failures, and cancel active work." />
    <JobConnectionStatus ids={activeJobIds} always />
    {jobs.isError && <RegionFailure label="Jobs" retry={() => void jobs.refetch()} />}
    {jobs.data && <div className="so-hard-disclosure"><Clock3 size={24} /><div><strong>Durable worker connected</strong><p>Pending cap {jobs.data.pending_job_cap}; background work promotes after {jobs.data.background_age_promotion_seconds} seconds. Live updates reconcile against authoritative job reads.</p></div></div>}
    <section className="so-panel"><div className="so-panel-head"><div><span className="so-kicker">Two reserved lanes</span><h2>{records.length} persisted job{records.length === 1 ? '' : 's'}</h2></div><span>Interactive + background</span></div>
      {(cancel.isError || retry.isError) && <p className="so-error" role="alert">The job action failed. Review the diagnostic and required retry inputs, then try again.</p>}
      {jobs.isLoading ? <p>Loading jobs…</p> : records.length === 0 ? <div className="so-empty"><Clock3 size={29} /><h2>No jobs yet</h2><p>Generation, evaluation, imports, and indexing appear here when queued.</p></div> : <div className="so-results">{records.map((job) => { const isRunner = job.kind === 'java_runner'; return <article key={job.job_id}><span className="so-chip">{job.lane ?? 'background'}</span><strong>{job.kind}</strong><p><span aria-hidden="true">●</span> {job.status}</p><small>{job.job_id}</small><dl className="so-facts"><dt>Attempt</dt><dd>{job.attempt}</dd><dt>Started</dt><dd>{job.started_at ?? 'Not started'}</dd><dt>Terminal</dt><dd>{job.terminal_at ?? 'Not terminal'}</dd><dt>Result</dt><dd>{job.result_ref ?? 'None'}</dd><dt>Hash</dt><dd>{job.result_hash ?? 'None'}</dd><dt>Diagnostic</dt><dd>{job.diagnostic ?? 'None'}</dd></dl>{isRunner && <p>Controlled subprocess execution only. This is not a sandbox or hostile-code isolation, and it is not proof of production or AWS behavior.</p>}{job.status === 'failed' && job.retryable && !isRunner && <label>Substitution reference<input value={substitutionRef} onChange={(event) => setSubstitutionRef(event.target.value)} placeholder="Required for interview-turn retries" /></label>}<div>{['queued', 'running', 'cancel-requested'].includes(job.status) && <Button tone="secondary" onClick={() => cancel.mutate(job.job_id)}>Cancel</Button>}{job.status === 'failed' && job.retryable && (isRunner ? <Button tone="secondary" onClick={() => navigate('topic-studio')}>Confirm and run again in Topic Studio</Button> : <Button tone="secondary" onClick={() => retry.mutate({ jobId: job.job_id, substitutionRef: substitutionRef || null, confirmationRef: null })}>Retry</Button>)}</div></article> })}</div>}
    </section>
  </>
}

function GlobalProfileSettings() {
  const workspace = useProfileGoals()
  const profile = workspace.profile.data
  const [experience, setExperience] = useState('')
  const [strengths, setStrengths] = useState('')
  const [weaknesses, setWeaknesses] = useState('')

  useEffect(() => {
    if (!profile) return
    setExperience(profile.experience ?? '')
    setStrengths(profile.strengths ?? '')
    setWeaknesses(profile.weaknesses ?? '')
  }, [profile])

  if (workspace.profile.isPending) return <section className="so-panel" aria-live="polite"><div className="so-panel-head"><div><UserRound size={20} /><h2>Global learner profile</h2></div></div><p>Loading profile…</p></section>
  if (!profile || workspace.profile.isError) return <section className="so-panel" aria-live="polite"><div className="so-panel-head"><div><UserRound size={20} /><h2>Global learner profile</h2></div></div><p>The profile is unavailable. Goal-scoped data was not substituted.</p><Button tone="secondary" onClick={() => void workspace.profile.refetch()}>Retry</Button></section>

  const unchanged = experience === (profile.experience ?? '') && strengths === (profile.strengths ?? '') && weaknesses === (profile.weaknesses ?? '')
  return <section className="so-panel" aria-labelledby="so-global-profile-title"><div className="so-panel-head"><div><UserRound size={20} /><h2 id="so-global-profile-title">Global learner profile</h2></div><span className="so-chip so-chip--gray">All goals</span></div><label>Experience<textarea value={experience} onChange={(event) => setExperience(event.target.value)} /></label><label>Strengths<textarea value={strengths} onChange={(event) => setStrengths(event.target.value)} /></label><label>Weaknesses or gaps<textarea value={weaknesses} onChange={(event) => setWeaknesses(event.target.value)} /></label><p className="so-help">This profile is global. Progress, evidence, and roadmap decisions remain isolated inside each goal.</p>{workspace.saveProfile.isError && <p className="so-error" role="alert">The profile changed or could not be saved. Reload the latest revision and try again.</p>}<Button disabled={unchanged || workspace.saveProfile.isPending} onClick={() => workspace.saveProfile.mutate({ update: { experience: experience || null, strengths: strengths || null, weaknesses: weaknesses || null }, revision: profile.profile_revision })}>{workspace.saveProfile.isPending ? 'Saving…' : workspace.saveProfile.isSuccess && unchanged ? 'Saved' : 'Save profile'}</Button></section>
}

function CurrentGoalSettings({ workspace }: { workspace: ReturnType<typeof useProfileGoals> }) {
  const goal = workspace.currentGoal
  const [name, setName] = useState('')
  const [context, setContext] = useState('')
  const [targetLevel, setTargetLevel] = useState<'Mid-level' | 'Senior' | 'Staff'>('Senior')
  const [targetCapability, setTargetCapability] = useState<'know' | 'understand' | 'choose' | 'implement' | 'diagnose' | 'defend'>('implement')
  useEffect(() => {
    if (!goal) return
    setName(goal.name)
    setContext(goal.path === 'learn' ? goal.subject ?? '' : goal.role ?? '')
    setTargetLevel(goal.target_level)
    setTargetCapability(goal.target_capability)
  }, [goal])
  if (workspace.goals.isPending || workspace.profile.isPending) return <section className="so-panel"><div className="so-panel-head"><div><SlidersHorizontal size={20} /><h2>Current goal</h2></div></div><p>Loading current goal settings…</p></section>
  if (!goal) return <section className="so-panel"><div className="so-panel-head"><div><SlidersHorizontal size={20} /><h2>Current goal</h2></div></div><p>Select an active goal to edit its settings.</p></section>
  const originalContext = goal.path === 'learn' ? goal.subject ?? '' : goal.role ?? ''
  const unchanged = name === goal.name && context === originalContext && targetLevel === goal.target_level && targetCapability === goal.target_capability
  const save = () => workspace.saveGoal.mutate({ goal, patch: {
    name: name.trim(),
    ...(goal.path === 'learn' ? { subject: context.trim() || null } : { role: context.trim() || null }),
    target_level: targetLevel,
    target_capability: targetCapability,
  } })
  const stale = workspace.saveGoal.error instanceof ApiError && [409, 412].includes(workspace.saveGoal.error.status)
  return <section className="so-panel"><div className="so-panel-head"><div><SlidersHorizontal size={20} /><h2>Current goal</h2></div><span className="so-chip so-chip--gray">{goal.path === 'learn' ? 'Learning' : 'Interview'}</span></div>
    <label>Goal name<input type="text" value={name} onChange={(event) => setName(event.target.value)} /></label>
    <label>{goal.path === 'learn' ? 'Subject' : 'Role'}<input type="text" value={context} onChange={(event) => setContext(event.target.value)} /></label>
    <label>Target level<select value={targetLevel} onChange={(event) => setTargetLevel(event.target.value as typeof targetLevel)}><option>Mid-level</option><option>Senior</option><option>Staff</option></select></label>
    <label>Target capability<select value={targetCapability} onChange={(event) => setTargetCapability(event.target.value as typeof targetCapability)}><option value="know">Know</option><option value="understand">Understand</option><option value="choose">Choose</option><option value="implement">Implement</option><option value="diagnose">Diagnose</option><option value="defend">Defend</option></select></label>
    <p className="so-help">This edit applies only to the current goal. Its server revision protects concurrent changes.</p>
    {workspace.saveGoal.isError && <p className="so-error" role="alert">{stale ? 'The goal changed before this save. The latest revision was reloaded; review it before saving again.' : 'The current goal was not saved. Review the values and try again.'}</p>}
    {workspace.saveGoal.isSuccess && unchanged && <p className="so-help" role="status">Current goal settings saved.</p>}
    <Button disabled={!name.trim() || unchanged || workspace.saveGoal.isPending} onClick={save}>{workspace.saveGoal.isPending ? 'Saving…' : 'Save current goal'}</Button>
  </section>
}

export function ReviewPreferencesPanel({ goalId }: { goalId: string | null }) {
  const review = useReviewPreferences(goalId)
  const preferences = review.preferences.data
  const save = (patch: Partial<ReviewPreferencesPatch>) => {
    if (preferences) review.save.mutate({ current: preferences, patch })
  }
  if (!goalId) return <section className="so-panel so-settings-wide"><div className="so-panel-head"><div><Clock3 size={20} /><h2>Optional review</h2></div></div><p>Select a current goal to configure its review queue.</p><p className="so-help">Review preferences belong to one goal and never block its roadmap.</p></section>
  if (review.preferences.isPending) return <section className="so-panel so-settings-wide" aria-live="polite"><div className="so-panel-head"><div><Clock3 size={20} /><h2>Optional review</h2></div></div><p>Loading review preferences…</p></section>
  if (!preferences || review.preferences.isError) return <section className="so-panel so-settings-wide" role="alert"><div className="so-panel-head"><div><Clock3 size={20} /><h2>Optional review</h2></div></div><p>Review preferences are unavailable. No browser defaults were substituted.</p><Button tone="secondary" onClick={() => void review.preferences.refetch()}>Retry</Button></section>
  return <section className="so-panel so-settings-wide"><div className="so-panel-head"><div><Clock3 size={20} /><h2>Optional review</h2></div><label className="so-switch"><input type="checkbox" checked={preferences.enabled} disabled={review.save.isPending} onChange={(event) => save({ enabled: event.target.checked })} /><span>{preferences.enabled ? 'Enabled' : 'Disabled'}</span></label></div><div className="so-review-controls" aria-disabled={!preferences.enabled}><label>Session length<select disabled={!preferences.enabled || review.save.isPending} value={preferences.duration_minutes} onChange={(event) => save({ duration_minutes: Number(event.target.value) })}><option value={10}>10 minutes</option><option value={15}>15 minutes</option><option value={25}>25 minutes</option></select></label><label>Cadence<select disabled={!preferences.enabled || review.save.isPending} value={preferences.cadence} onChange={(event) => save({ cadence: event.target.value as NonNullable<ReviewPreferencesPatch['cadence']> })}><option value="once-weekly">Once a week</option><option value="twice-weekly">Twice a week</option><option value="three-times-weekly">Three times a week</option></select></label><label className="so-check"><input type="checkbox" disabled={!preferences.enabled || review.save.isPending} checked={preferences.retrieval_enabled} onChange={(event) => save({ retrieval_enabled: event.target.checked })} /> Retrieval prompts</label><label className="so-check"><input type="checkbox" disabled={!preferences.enabled || review.save.isPending} checked={preferences.varied_context_enabled} onChange={(event) => save({ varied_context_enabled: event.target.checked })} /> Varied contexts</label></div><p className="so-help">Disabling or dismissing review never blocks the roadmap and carries no readiness penalty. Scheduling rules: {preferences.scheduling_version}.</p>{review.save.isPending && <p className="so-help" role="status">Saving review preferences…</p>}{review.save.isSuccess && <p className="so-help" role="status">Review preferences saved.</p>}{review.save.isError && <p className="so-error" role="alert">Preferences were not saved. Reload the latest revision and try again.</p>}</section>
}

function ProviderNetworkPanel({ ownerSettings }: { ownerSettings: ReturnType<typeof useOwnerSettings> }) {
  const provider = useProviderSettings()
  const disclosures = provider.disclosures.data ?? []
  const capabilities = provider.capabilities.data ?? []
  const busy = provider.accept.isPending || provider.revoke.isPending
  const selectionChange = ownerSettings.save.variables && 'provider_selection' in ownerSettings.save.variables
  const selectionSaving = ownerSettings.save.isPending && selectionChange
  const selectionError = ownerSettings.save.isError && selectionChange
  const selectionSaved = ownerSettings.save.isSuccess && selectionChange
  return <section className="so-panel so-settings-wide"><div className="so-panel-head"><div><Database size={20} /><h2>Providers and network</h2></div><span className="so-chip so-chip--gray">Disclosure gated</span></div>
    {(provider.disclosures.isError || provider.capabilities.isError) && <RegionFailure label="Provider and network settings" retry={() => void Promise.all([provider.disclosures.refetch(), provider.capabilities.refetch()])} />}
    <div className="so-network-grid">
      <article><strong>Model providers</strong>{provider.capabilities.isPending ? <p>Checking configured provider capabilities…</p> : capabilities.length ? <ul>{capabilities.map(item => <li key={item.provider}><strong>{item.provider} · {item.state}</strong>{item.model && <span> · {item.model}</span>}<p>{item.reason ?? 'Executable, supported version, command surface, and local CLI authentication are configured.'} {item.recovery_action}</p></li>)}</ul> : <p>No provider capabilities reported.</p>}{ownerSettings.settings.data && <label>Preferred provider<select value={ownerSettings.settings.data.provider_selection ?? ''} disabled={ownerSettings.save.isPending} onChange={(event) => ownerSettings.save.mutate({ provider_selection: event.target.value ? event.target.value as 'codex' | 'claude' : null })}><option value="">No provider selected</option>{capabilities.map(item => <option key={item.provider} value={item.provider} disabled={item.state !== 'configured'}>{item.provider} · {item.state}</option>)}</select></label>}<Button tone="quiet" disabled={provider.refreshCapabilities.isPending} onClick={() => provider.refreshCapabilities.mutate()}>{provider.refreshCapabilities.isPending ? 'Refreshing…' : 'Refresh provider status'}</Button>{selectionSaving && <p role="status">Saving provider selection…</p>}{selectionSaved && <p role="status">Provider selection saved.</p>}{selectionError && <p className="so-error" role="alert">That provider is not configured. Refresh status or select an available provider.</p>}{provider.refreshCapabilities.isError && <p className="so-error" role="alert">Provider status could not be refreshed. No prior status was replaced.</p>}<p className="so-help">Disclosure acceptance is not provider authentication. Sign-in is completed only in each provider’s local CLI.</p></article>
      <article><strong>Source retrieval</strong><p>External authoritative sources may be retrieved only after the current source-network disclosure is accepted.</p></article>
      <article><strong>Local runner</strong><p>Controlled local subprocess execution does not use a provider disclosure and is not a hostile-code sandbox.</p></article>
    </div>
    {disclosures.map(disclosure => { const accepted = Boolean(disclosure.accepted_at && !disclosure.revoked_at); return <div className="so-data-actions" key={`${disclosure.category}-${disclosure.disclosure_version}`}><div><strong>{disclosure.operation}</strong><p>{disclosure.destination} · Sends: {disclosure.data_categories.join(', ')} · Version {disclosure.disclosure_version}. {accepted ? `Accepted ${disclosure.accepted_at}.` : 'Not accepted; future network enqueues in this category are blocked.'}</p></div><Button tone={accepted ? 'danger' : 'secondary'} disabled={busy} onClick={() => accepted ? provider.revoke.mutate(disclosure) : provider.accept.mutate(disclosure)}>{accepted ? 'Revoke' : 'Accept disclosure'}</Button></div> })}
    {(provider.accept.isError || provider.revoke.isError) && <p className="so-error" role="alert">The disclosure state was not changed. Reload its current version and try again.</p>}
    <p className="so-help">Acceptance is recorded before a gated network job may be enqueued. Revocation blocks future enqueues without changing completed requests or results.</p>
  </section>
}

function SensitiveBodyDeletionPanel({ goal }: { goal: GoalWorkspace | null }) {
  const imports = useImports(goal?.id ?? null, null)
  const [importToDelete, setImportToDelete] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState('')
  const [sessionDeleteOpen, setSessionDeleteOpen] = useState(false)
  const importDeleteTriggerRef = useRef<HTMLButtonElement | null>(null)
  const sessionDeleteTriggerRef = useRef<HTMLButtonElement>(null)
  const interviewDelete = useMutation({ mutationFn: deleteInterviewSessionBody })
  useEffect(() => {
    if (imports.removeBody.isSuccess) setImportToDelete(null)
  }, [imports.removeBody.isSuccess])
  useEffect(() => {
    if (interviewDelete.isSuccess) {
      setSessionDeleteOpen(false)
      setSessionId('')
    }
  }, [interviewDelete.isSuccess])
  const liveImports = (imports.imports.data ?? []).filter(item => Boolean(item.original_content))
  return <section className="so-panel so-settings-wide"><div className="so-panel-head"><div><ShieldAlert size={20} /><h2>Delete sensitive bodies</h2></div></div>
    <div className="so-data-actions"><div><strong>Import originals and reviewed text</strong><p>Delete an import’s original and statement text while retaining hashes, decisions, parser version, IDs, timestamps, and audit facts.</p><p><strong>This is irreversible.</strong> There is no undelete or recovery window and no Yuno-managed backup. External OS or user backups may retain deleted data.</p>{imports.removeBody.isSuccess && <p role="status">The selected import body was deleted.</p>}{imports.removeBody.isError && <p className="so-error" role="alert">The import body was not deleted. Reload its current state and try again.</p>}</div><div>{liveImports.length === 0 ? <p>No retained import bodies for the current goal.</p> : liveImports.map(item => <Button key={item.id} tone="danger" disabled={imports.removeBody.isPending} onClick={(event) => { imports.removeBody.reset(); importDeleteTriggerRef.current = event.currentTarget; setImportToDelete(item.id) }}>Delete import {item.id}</Button>)}</div></div>
    <div className="so-data-actions"><div><strong>Interview transcript and session bodies</strong><p>Enter a Practice or Mock session ID to remove transcript turns, drafts, answers, and feedback while retaining minimal IDs, state, versions, timestamps, hashes, and audit facts.</p><p><strong>This is irreversible.</strong> There is no undelete or recovery window and no Yuno-managed backup. External OS or user backups may retain deleted data.</p>{interviewDelete.isSuccess && <p role="status">The interview session body was deleted.</p>}{interviewDelete.isError && <p className="so-error" role="alert">The interview session body was not deleted. Check the owner-scoped session ID and try again.</p>}</div><div><label>Interview session ID<input value={sessionId} onChange={(event) => setSessionId(event.target.value)} /></label><Button ref={sessionDeleteTriggerRef} tone="danger" disabled={!sessionId.trim() || interviewDelete.isPending} onClick={() => { interviewDelete.reset(); setSessionDeleteOpen(true) }}>Delete session body</Button></div></div>
    <AlertDialog.Root open={importToDelete !== null} onOpenChange={(open) => !open && setImportToDelete(null)}><AlertDialog.Portal><AlertDialog.Overlay className="so-dialog-overlay" /><AlertDialog.Content className="so-dialog" onCloseAutoFocus={(event) => { event.preventDefault(); importDeleteTriggerRef.current?.focus() }}><AlertDialog.Title>Delete this import body?</AlertDialog.Title><AlertDialog.Description>This permanently removes the original and reviewed text. There is no undelete, recovery window, or Yuno-managed backup. External backups may retain a copy.</AlertDialog.Description><div><AlertDialog.Cancel asChild><Button tone="secondary">Cancel</Button></AlertDialog.Cancel><Button tone="danger" disabled={!importToDelete || imports.removeBody.isPending} onClick={() => importToDelete && imports.removeBody.mutate(importToDelete)}>Confirm import body deletion</Button></div></AlertDialog.Content></AlertDialog.Portal></AlertDialog.Root>
    <AlertDialog.Root open={sessionDeleteOpen} onOpenChange={setSessionDeleteOpen}><AlertDialog.Portal><AlertDialog.Overlay className="so-dialog-overlay" /><AlertDialog.Content className="so-dialog" onCloseAutoFocus={(event) => { event.preventDefault(); sessionDeleteTriggerRef.current?.focus() }}><AlertDialog.Title>Delete this interview session body?</AlertDialog.Title><AlertDialog.Description>This permanently removes transcript turns, drafts, answers, and feedback. There is no undelete, recovery window, or Yuno-managed backup. External backups may retain a copy.</AlertDialog.Description><div><AlertDialog.Cancel asChild><Button tone="secondary">Cancel</Button></AlertDialog.Cancel><Button tone="danger" disabled={!sessionId.trim() || interviewDelete.isPending} onClick={() => interviewDelete.mutate(sessionId.trim())}>Confirm session body deletion</Button></div></AlertDialog.Content></AlertDialog.Portal></AlertDialog.Root>
  </section>
}

function DataOperationsPanel({ goal }: { goal: GoalWorkspace | null }) {
  const operations = useDataOperations(goal?.id ?? null)
  const ownerSettings = useOwnerSettings()
  const policy = ownerSettings.dataLifecyclePolicy.data
  const [deleteOpen, setDeleteOpen] = useState(false)
  const deleteTriggerRef = useRef<HTMLButtonElement>(null)
  const impact = operations.preflight.data
  const exportOperation = operations.exportStatus.data
  const deleteOperation = operations.deleteStatus.data
  useEffect(() => {
    if (operations.confirmDelete.isSuccess) setDeleteOpen(false)
  }, [operations.confirmDelete.isSuccess])
  const preflight = () => {
    operations.preflight.reset()
    operations.confirmDelete.reset()
    operations.preflight.mutate()
    setDeleteOpen(true)
  }
  const mib = (bytes: number) => `${bytes / (1024 * 1024)} MiB`
  return <section className="so-panel so-settings-wide"><div className="so-panel-head"><div><Download size={20} /><h2>Local data</h2></div></div>
    <div className="so-data-actions"><div><strong>Versioned Yuno export</strong><p>Create a durable export job for {goal ? goal.name : 'all goals'}. Unavailable or tombstoned content is represented as unavailable, never fabricated. Raw imports, transcripts, quarantined provider output, and runner bodies are excluded.</p>{policy && !policy.export_available && <span className="so-warning" role="status">Portable export is disabled until the required privacy review passes.</span>}{operations.startExport.isError && <span className="so-error" role="alert">Export is unavailable or did not start. No partial package was retained.</span>}{exportOperation && <p role="status">Export {exportOperation.status} · {exportOperation.format} {exportOperation.version}{exportOperation.failure_reference ? ` · ${exportOperation.failure_reference}` : ''}{exportOperation.status === 'complete' ? ' · package ready for 24 hours' : ''}</p>}{exportOperation?.status === 'complete' && exportOperation.download_available && exportOperation.filename && <a className="so-button so-button--secondary" href={`/api/v1/exports/${exportOperation.id}/download`} download={exportOperation.filename}><Download size={16} /> Download {exportOperation.filename}</a>}{exportOperation?.status === 'expired' && <span className="so-error" role="alert">The local export package expired. Create a fresh export to download it.</span>}{operations.exportStatus.isError && <span className="so-error" role="alert">Export status could not be loaded.</span>}</div><Button tone="secondary" disabled={!policy?.export_available || operations.startExport.isPending || ['queued', 'running'].includes(exportOperation?.status ?? '')} onClick={() => operations.startExport.mutate()}><Download size={16} /> {operations.startExport.isPending ? 'Starting…' : exportOperation?.status === 'failed' || exportOperation?.status === 'expired' ? 'Create fresh export' : 'Create export'}</Button></div>
    <div className="so-data-actions"><div><strong>Delete current goal</strong><p>{goal ? `Preview every cross-goal evidence tombstone and dependent LearningState downgrade before deleting ${goal.name}.` : 'Select a current goal before requesting destructive deletion.'}</p><p><strong>Deletion is irreversible.</strong> There is no undelete or recovery window. No Yuno-managed backup exists. External OS, filesystem, VM, or user-created backups may retain deleted data until their own expiry.</p><p>This is application-level deletion, not forensic media sanitization. Yuno provides no remote support access, automatic upload, telemetry forwarding, or support credential.</p>{deleteOperation && <p role="status">Delete {deleteOperation.status}{deleteOperation.failure_reference ? ` · ${deleteOperation.failure_reference}` : ''}{deleteOperation.cleanup_failure_classifications?.length ? ` · ${deleteOperation.cleanup_failure_classifications.join(', ')}` : ''}{deleteOperation.status === 'cleanup-pending' ? ` · ${deleteOperation.cleanup_pending_count ?? 0} external cleanup item${deleteOperation.cleanup_pending_count === 1 ? '' : 's'} remaining` : ''}</p>}</div><Button ref={deleteTriggerRef} tone="danger" disabled={!goal || operations.preflight.isPending || ['queued', 'running', 'cleanup-pending', 'cleanup-failed', 'complete'].includes(deleteOperation?.status ?? '')} onClick={preflight}><ShieldAlert size={16} /> {operations.preflight.isPending ? 'Calculating…' : deleteOperation?.status === 'failed' ? 'Retry delete' : 'Preview deletion'}</Button></div>
    <details className="so-details"><summary><span><Database size={18} /> Data limits and retention <small>Approved IDK-010 policy 1.0, enforced by the local server</small></span><ChevronRight size={18} /></summary><div className="so-inspection">{ownerSettings.dataLifecyclePolicy.isError ? <RegionFailure label="Data lifecycle policy" retry={() => void ownerSettings.dataLifecyclePolicy.refetch()} /> : !policy ? <p>Loading enforced data limits…</p> : <>
      <p><strong>Imports:</strong> {mib(policy.import_original_max_bytes)} each, {policy.import_retained_owner_limit} retained per owner, {policy.import_statements_per_import_limit.toLocaleString()} statements per import, and {policy.import_unreviewed_owner_limit.toLocaleString()} unreviewed statements per owner.</p>
      <p><strong>Evidence and generated content:</strong> {mib(policy.evidence_payload_max_bytes)} per evidence payload and {policy.evidence_retained_owner_limit.toLocaleString()} retained records; {mib(policy.generated_body_max_bytes)} per generated body and {policy.generated_retained_owner_limit.toLocaleString()} retained artifacts.</p>
      <p><strong>Interview sessions:</strong> {policy.interview_turns_per_session_limit.toLocaleString()} turns and {mib(policy.interview_bytes_per_session_limit)} per session; {policy.interview_sessions_owner_limit} sessions per owner.</p>
      <p><strong>Runner:</strong> {policy.runner_input_files_limit} inputs / {mib(policy.runner_input_bytes_limit)}; {mib(policy.runner_stdout_bytes_limit)} per output stream and {mib(policy.runner_output_bytes_limit)} per run; {mib(policy.runner_temp_bytes_limit)} / {policy.runner_temp_files_limit.toLocaleString()} temporary files.</p>
      <p><strong>Pending work:</strong> {policy.overlay_proposal_pending_cap} overlay proposals per goal and {policy.pending_job_cap} queued or running jobs per owner.</p>
      <p><strong>Expiry:</strong> abandoned diagnostics and inactive draft/active interviews after {policy.diagnostic_abandoned_retention_days} days; terminal job operations after {policy.terminal_job_retention_days} days; SSE events after {policy.job_event_retention_days} days or the newest {policy.job_event_owner_limit.toLocaleString()} events, whichever is smaller; runner output after {policy.runner_output_retention_days} days; crash workspaces after {policy.runner_workspace_retention_seconds / 3600} hour.</p>
      <p><strong>Exports and logs:</strong> packages expire after {policy.export_package_retention_seconds / 3600} hours and operation metadata/hash after {policy.export_operation_retention_days} days. Logs expire after {policy.structured_log_retention_days} days and use {policy.structured_log_file_count} local files of at most {mib(policy.structured_log_file_max_bytes)} each ({mib(policy.structured_log_total_max_bytes)} total).</p>
    </>}</div></details>
    {operations.preflight.isError && !deleteOpen && <p className="so-error" role="alert">The deletion impact could not be calculated. Nothing was deleted.</p>}
    <AlertDialog.Root open={deleteOpen} onOpenChange={setDeleteOpen}><AlertDialog.Portal><AlertDialog.Overlay className="so-dialog-overlay" /><AlertDialog.Content className="so-dialog" onCloseAutoFocus={(event) => { event.preventDefault(); deleteTriggerRef.current?.focus() }}><AlertDialog.Title>Delete {goal?.name ?? 'this goal'}?</AlertDialog.Title><AlertDialog.Description>This deletion is irreversible, with no undelete or recovery window. No Yuno-managed backup exists; external OS or user backups may retain deleted data. The impact snapshot must still match at confirmation.</AlertDialog.Description>
      {operations.preflight.isPending ? <p>Calculating immutable impact snapshot…</p> : impact ? <><dl className="so-facts"><dt>Snapshot</dt><dd>{impact.snapshot_id}</dd><dt>Cross-goal evidence tombstones</dt><dd>{impact.evidence_ids.length ? impact.evidence_ids.join(', ') : 'None'}</dd><dt>Dependent LearningState downgrades</dt><dd>{impact.learning_state_ids.length ? impact.learning_state_ids.join(', ') : 'None'}</dd></dl><p>This operation is durable and runs as a background job. Failure cannot leave a partial downgrade.</p></> : <p role="alert">The impact preview is unavailable. Close and retry.</p>}
      {operations.staleDeleteImpact && <div className="so-warning" role="alert"><AlertTriangle size={18} /><div><strong>Deletion impact changed</strong><p>Nothing was queued. Refresh and review the new snapshot before confirming.</p></div></div>}
      {operations.confirmDelete.isError && !operations.staleDeleteImpact && <p className="so-error" role="alert">Delete did not start. Nothing was deleted.</p>}
      <div><AlertDialog.Cancel asChild><Button tone="secondary" disabled={operations.confirmDelete.isPending}>Cancel</Button></AlertDialog.Cancel>{operations.staleDeleteImpact ? <Button tone="secondary" onClick={operations.refreshPreflight}>Refresh impact</Button> : <Button tone="danger" disabled={!impact || operations.confirmDelete.isPending} onClick={() => impact && operations.confirmDelete.mutate(impact)}>{operations.confirmDelete.isPending ? 'Starting…' : 'Confirm deletion'}</Button>}</div>
    </AlertDialog.Content></AlertDialog.Portal></AlertDialog.Root>
  </section>
}

export function SettingsPage({ navigate }: { navigate: Navigate }) {
  const workspace = useProfileGoals()
  const { currentGoal } = workspace
  const imports = useImports(currentGoal?.id ?? null, null).imports
  const ownerSettings = useOwnerSettings()
  return <>
    <PageHead eyebrow="Profile, preferences, and data" title="Settings" description="Your learner profile, accessibility, provider selection, and progress display apply across every goal. Review preferences remain goal-specific." />
    <div className="so-settings-grid">
      <GlobalProfileSettings />
      <CurrentGoalSettings workspace={workspace} />
      <section className="so-panel"><div className="so-panel-head"><div><SlidersHorizontal size={20} /><h2>Progress display</h2></div></div>{ownerSettings.settings.isError ? <RegionFailure label="Progress display preference" retry={() => void ownerSettings.settings.refetch()} /> : ownerSettings.settings.data ? <fieldset className="so-choice-list"><legend>Choose the default view</legend><label><input type="radio" name="progress" disabled={ownerSettings.saveProgressDisplay.isPending} checked={ownerSettings.settings.data.progress_display === 'detailed'} onChange={() => ownerSettings.saveProgressDisplay.mutate('detailed')} /><span><strong>Detailed</strong><small>Coverage, proficiency, retention, readiness, definitions, uncertainty, and evidence links.</small></span></label><label><input type="radio" name="progress" disabled={ownerSettings.saveProgressDisplay.isPending} checked={ownerSettings.settings.data.progress_display === 'simple'} onChange={() => ownerSettings.saveProgressDisplay.mutate('simple')} /><span><strong>Simple</strong><small>Condensed presentation only; underlying server evidence, assessments, and progress data remain unchanged.</small></span></label></fieldset> : <p>Loading progress display preference…</p>}{ownerSettings.saveProgressDisplay.isError && <p className="so-error" role="alert">The progress display preference was not saved. Your prior setting and all learning data remain unchanged; try again.</p>}</section>
      <ReviewPreferencesPanel goalId={currentGoal?.id ?? null} />
      <section className="so-panel"><div className="so-panel-head"><div><Settings2 size={20} /><h2>Accessibility</h2></div></div>{ownerSettings.settings.data ? <label className="so-toggle-row"><span><strong>Reduce motion</strong><small>Suppress non-essential transitions across operational pages.</small></span><input type="checkbox" disabled={ownerSettings.save.isPending} checked={ownerSettings.settings.data.accessibility.reduced_motion} onChange={(event) => ownerSettings.save.mutate({ accessibility: { reduced_motion: event.target.checked } })} /></label> : ownerSettings.settings.isError ? <RegionFailure label="Accessibility settings" retry={() => void ownerSettings.settings.refetch()} /> : <p>Loading accessibility settings…</p>}<p className="so-help">Your operating-system reduced-motion preference is also respected, even when this setting is off.</p>{ownerSettings.save.isError && ownerSettings.save.variables && 'accessibility' in ownerSettings.save.variables && <p className="so-error" role="alert">{ownerSettings.save.error instanceof ApiError && ownerSettings.save.error.status === 422 ? 'Invalid accessibility setting. The prior server value remains active.' : 'The setting was not saved. Reload the latest revision and try again.'}</p>}</section>
      <section className="so-panel"><div className="so-panel-head"><div><Import size={20} /><h2>Imports</h2></div></div>{!currentGoal ? <p>Select a current goal to review its imports.</p> : imports.isPending ? <p>Loading the current goal’s server imports…</p> : imports.isError ? <><p role="alert">The imports summary is unavailable. No browser count was substituted.</p><Button tone="secondary" onClick={() => void imports.refetch()}>Retry summary</Button></> : <p>{imports.data?.length ?? 0} preserved import{imports.data?.length === 1 ? '' : 's'} for {currentGoal.name}; {(imports.data ?? []).filter(item => item.status === 'failed' || item.status === 'cancelled').length} need attention.</p>}<Button tone="secondary" onClick={() => navigate('imports')}>Review imports <ArrowRight size={16} /></Button></section>
      <ProviderNetworkPanel ownerSettings={ownerSettings} />
      <SensitiveBodyDeletionPanel goal={currentGoal} />
      <DataOperationsPanel goal={currentGoal} />
    </div>
  </>
}

export function OperationalPageView({ page, navigate }: { page: OperationalPage; navigate: Navigate }) {
  const ownerSettings = useOwnerSettings()
  const pages: Record<OperationalPage, React.ReactNode> = {
    evidence: <EvidencePage navigate={navigate} />,
    imports: <ImportsPage />,
    'canonical-updates': <CanonicalUpdatesPage />,
    search: <SearchPage navigate={navigate} />,
    jobs: <JobsPage navigate={navigate} />,
    settings: <SettingsPage navigate={navigate} />,
  }
  return <main className={`so-page ${ownerSettings.settings.data?.accessibility?.reduced_motion ? 'so-reduced-motion' : ''}`}>{pages[page]}</main>
}

export default OperationalPageView
