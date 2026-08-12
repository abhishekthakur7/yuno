import { useEffect, useMemo, useState } from 'react'
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
import { useLearningState } from '../../shared/state'
import type { ImportStatement, JobRef } from '../../shared/api/imports'
import { useImports } from '../../shared/use-imports'
import { useProfileGoals } from '../../shared/use-profile-goals'
import { useRoadmap } from '../../shared/use-roadmap'
import { useReviewPreferences } from '../../shared/use-notebook-review'
import type { ReviewPreferencesPatch } from '../../shared/api/notebook-review'
import './operations.css'

export type OperationalPage = 'evidence' | 'imports' | 'canonical-updates' | 'search' | 'jobs' | 'settings'

type Navigate = (page: string) => void
interface OperationsState {
  version: 1
  goalVersion: '2026.07' | '2026.08'
  owner: { name: string; role: string }
  progress: 'detailed' | 'simple'
  reducedMotion: boolean
  updateDecision: 'pending' | 'accepted' | 'postponed' | 'dismissed'
  acceptedUpdates: string[]
  acceptedConflictResolution: 'overlay-kept' | 'canonical-adopted' | null
  disputedEvidenceId: string | null
}

const STORAGE_KEY = 'yuno.operations.state.v1'

const DEFAULT_STATE: OperationsState = {
  version: 1,
  goalVersion: '2026.07',
  owner: { name: 'Aditi Rao', role: 'Senior backend engineer' },
  progress: 'detailed',
  reducedMotion: false,
  updateDecision: 'pending',
  acceptedUpdates: [],
  acceptedConflictResolution: null,
  disputedEvidenceId: null,
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

function hydrateOperationsState(value: unknown): OperationsState | null {
  if (!isRecord(value) || value.version !== 1) return null
  const owner = isRecord(value.owner) ? value.owner : {}
  return {
    version: 1,
    goalVersion: value.goalVersion === '2026.08' ? '2026.08' : DEFAULT_STATE.goalVersion,
    owner: {
      name: typeof owner.name === 'string' ? owner.name : DEFAULT_STATE.owner.name,
      role: typeof owner.role === 'string' ? owner.role : DEFAULT_STATE.owner.role,
    },
    progress: value.progress === 'simple' || value.progress === 'detailed' ? value.progress : DEFAULT_STATE.progress,
    reducedMotion: typeof value.reducedMotion === 'boolean' ? value.reducedMotion : DEFAULT_STATE.reducedMotion,
    updateDecision: value.updateDecision === 'accepted' || value.updateDecision === 'postponed' || value.updateDecision === 'dismissed' || value.updateDecision === 'pending' ? value.updateDecision : DEFAULT_STATE.updateDecision,
    acceptedUpdates: isStringArray(value.acceptedUpdates) ? value.acceptedUpdates : DEFAULT_STATE.acceptedUpdates,
    acceptedConflictResolution: value.acceptedConflictResolution === 'overlay-kept' || value.acceptedConflictResolution === 'canonical-adopted' || value.acceptedConflictResolution === null ? value.acceptedConflictResolution : DEFAULT_STATE.acceptedConflictResolution,
    disputedEvidenceId: typeof value.disputedEvidenceId === 'string' || value.disputedEvidenceId === null ? value.disputedEvidenceId : DEFAULT_STATE.disputedEvidenceId,
  }
}

const UPDATE_ROWS = [
  { id: 'visibility', topic: 'Visibility timeout and retry budgets', before: 'Choose a timeout longer than expected processing.', after: 'Choose from measured processing latency, then bound renewal and retry behavior.', impact: 'Refines the production checklist and adds an explicit failure case.', conflict: false },
  { id: 'idempotency', topic: 'Idempotency boundary', before: 'Store the message ID before applying the business write.', after: 'Make the business decision and duplicate marker atomic; treat a prior read as an optimization.', impact: 'Conflicts with your “unique constraint wins” overlay; choose which wording this local goal keeps.', conflict: true },
  { id: 'dlq', topic: 'Dead-letter recovery', before: 'Inspect and replay poison messages.', after: 'Quarantine, diagnose, and replay with the duplicate boundary intact.', impact: 'Adds one review prompt; does not mark the topic complete.', conflict: false },
] as const

const SEARCH_ITEMS = [
  { kind: 'Lesson', title: 'Implement an idempotency boundary under concurrent retries', path: 'Section 2 · Control duplicates and ordering', text: 'atomic write unique constraint duplicate retry Spring Boot', lessonId: 'idempotency-retry' },
  { kind: 'Reading', title: 'Trace the commit-and-acknowledgement failure window', path: 'Section 1 · Frame the failure boundary', text: 'SQS acknowledgement redelivery commit failure', lessonId: 'commit-window' },
  { kind: 'Review', title: 'Diagnose poison messages and dead-letter recovery', path: 'Section 2 · Production layer', text: 'DLQ dead letter replay quarantine', lessonId: 'dead-letter' },
] as const

function loadState(): OperationsState {
  const parse = (raw: string | null): unknown => {
    if (!raw) return null
    try { return JSON.parse(raw) as unknown } catch { return null }
  }
  const current = hydrateOperationsState(parse(window.localStorage.getItem(STORAGE_KEY)))
  if (current) return current
  return DEFAULT_STATE
}

function useOperationsState() {
  const [state, setState] = useState<OperationsState>(loadState)
  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  }, [state])
  return [state, setState] as const
}

function Button({ children, tone = 'primary', ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { tone?: 'primary' | 'secondary' | 'quiet' | 'danger' }) {
  return <button className={`so-button so-button--${tone}`} {...props}>{children}</button>
}

function PageHead({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: React.ReactNode }) {
  return <header className="so-page-head"><div><span className="so-eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action}</header>
}

function Disclosure({ children }: { children: React.ReactNode }) {
  return <aside className="so-disclosure"><Info size={18} aria-hidden="true" /><div>{children}</div></aside>
}

function EvidencePage({ state, setState, navigate }: { state: OperationsState; setState: React.Dispatch<React.SetStateAction<OperationsState>>; navigate: Navigate }) {
  const { state: learning } = useLearningState()
  const latestEvidence = learning.evidence.at(-1)
  const olderEvidence = learning.evidence.slice(0, -1).reverse()
  const latestPractice = learning.practice.attempts.at(-1)
  const latestIsDisputed = Boolean(latestEvidence && state.disputedEvidenceId === latestEvidence.id)
  return <>
    <PageHead eyebrow="Evidence · resilient order fulfillment" title="What your work supports" description="Conclusions are qualified by the artifact, rubric, and review method—not by lesson consumption." />
    <section className={`so-hero-card so-evidence-hero ${latestEvidence ? '' : 'is-unavailable'}`} aria-labelledby="so-conclusion">
      <div className="so-status-icon">{latestEvidence ? <Check size={24} /> : <FileText size={24} />}</div>
      <div><span className="so-kicker">{latestEvidence ? 'Latest submitted conclusion' : 'Evidence unavailable'}</span><h2 id="so-conclusion">{latestEvidence?.conclusion ?? 'No submitted lab evidence is available yet.'}</h2><p>{latestEvidence?.limitation ?? 'Running checks can preview local feedback, but only an explicit submission creates an evidence record. No progress or qualification is inferred from a draft.'}</p></div>
      <div className="so-next"><span>Next useful action</span><strong>{latestEvidence ? 'Defend the same boundary in a new failure scenario.' : 'Open Topic Studio, review the artifact, and submit it when it represents your decision.'}</strong><Button tone="secondary" onClick={() => navigate(latestEvidence ? 'practice' : 'topic-studio')}>{latestEvidence ? 'Open transfer check' : 'Open Topic Studio'} <ArrowRight size={16} /></Button></div>
    </section>
    {latestPractice && <section className="so-panel so-practice-summary"><div><span className="so-kicker">Latest guided-practice attempt</span><h2>{latestPractice.facts[0] ?? 'A practice response was saved.'}</h2><p>{latestPractice.tradeoffs[0] ?? 'Open practice to inspect and repair the response.'}</p></div><Button tone="secondary" onClick={() => navigate('practice')}>Review practice <ArrowRight size={16} /></Button></section>}
    <details className="so-details"><summary><span><History size={18} /> Inspect provenance <small>Method, artifact, and authority</small></span><ChevronRight size={18} /></summary><div className="so-inspection">{latestEvidence ? <dl className="so-facts"><dt>Record</dt><dd>{latestEvidence.id}</dd><dt>Artifact</dt><dd>Learner-submitted code ({latestEvidence.artifact.length} characters)</dd><dt>Review</dt><dd>{latestEvidence.kind === 'static-review' ? 'Deterministic browser static review' : latestEvidence.kind}</dd><dt>Authority</dt><dd>Learner evidence; not canonical content or runtime proof</dd></dl> : <p>No submitted artifact exists, so there is no evidence provenance to inspect.</p>}</div></details>
    <details className="so-details"><summary><span><History size={18} /> Evidence history <small>{olderEvidence.length ? `${olderEvidence.length} older submitted record${olderEvidence.length === 1 ? '' : 's'}` : 'No older submitted records'}</small></span><ChevronRight size={18} /></summary><div className="so-timeline">{olderEvidence.length ? olderEvidence.map((item) => <article key={item.id}><span>{item.id}</span><strong>{item.conclusion}</strong><p>{item.limitation}</p></article>) : <p>No older submitted evidence is available.</p>}</div></details>
    {latestEvidence && <section className="so-panel so-dispute"><div><span className="so-kicker">Correction and dispute</span><h2>{latestIsDisputed ? 'Re-evaluation requested' : 'Something about this assessment is wrong?'}</h2><p>{latestIsDisputed ? 'The original assessment is preserved. This local prototype cannot perform a real re-evaluation, so the request is recorded as unresolved without a readiness penalty.' : 'This local request does not overwrite the submitted evidence. Unresolved ambiguity does not lower readiness.'}</p></div><Button tone="secondary" disabled={latestIsDisputed} onClick={() => setState((s) => ({ ...s, disputedEvidenceId: latestEvidence.id }))}>{latestIsDisputed ? 'Request recorded' : 'Request re-evaluation'}</Button></section>}
  </>
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
      {workspace.imports.isPending ? <div className="so-empty"><Clock3 size={28} /><h2>Loading imports…</h2></div> : workspace.imports.isError ? <div className="so-empty"><AlertTriangle size={28} /><h2>Imports unavailable</h2><p>No local fixture was substituted.</p><Button tone="secondary" onClick={() => void workspace.imports.refetch()}>Retry</Button></div> : imports.length === 0 ? <div className="so-empty"><FileText size={28} /><h2>No imports yet</h2><p>Save an exact original above to queue server-side parsing.</p></div> : <>
        <section className="so-panel so-import-picker"><label htmlFor="so-import-picker"><span className="so-kicker">Saved originals</span><strong>Choose an import to inspect</strong></label><select id="so-import-picker" value={selectedImportId ?? ''} onChange={(event) => { setSelectedImportId(event.target.value); setJob(null) }}>{imports.map(item => <option key={item.id} value={item.id}>{item.import_type} · {item.status} · {item.original_hash.slice(0, 12)}</option>)}</select></section>
        {workspace.selectedImport.isPending ? <div className="so-empty"><Clock3 size={28} /><h2>Loading preserved original…</h2></div> : workspace.selectedImport.isError || !selected ? <div className="so-empty"><AlertTriangle size={28} /><h2>Original unavailable</h2><Button tone="secondary" onClick={() => void workspace.selectedImport.refetch()}>Retry</Button></div> : <section className="so-panel so-import-original"><div className="so-panel-head"><div><FileText size={20} /><h2>Preserved original</h2></div><span className={`so-chip ${selected.status === 'failed' || selected.status === 'cancelled' ? 'so-chip--amber' : 'so-chip--gray'}`}>{selected.status}</span></div><textarea readOnly aria-label="Preserved original text" value={selected.original_content} /><dl className="so-facts"><dt>SHA-256</dt><dd>{selected.original_hash}</dd><dt>Parser</dt><dd>{selected.parser_version ?? 'Not parsed yet'}</dd><dt>Failure</dt><dd>{selected.failure_code ? `${selected.failure_code}${selected.failure_reference ? ` · ${selected.failure_reference}` : ''}` : 'None reported'}</dd></dl><div className="so-inline-actions"><span>Original content remains inspectable even if parsing fails.</span>{selected.status === 'failed' || selected.status === 'cancelled' ? <Button tone="secondary" disabled={workspace.parse.isPending} onClick={() => workspace.parse.mutate(selected.id, { onSuccess: setJob })}>Retry parse</Button> : <Button tone="secondary" disabled={workspace.reprocess.isPending} onClick={() => workspace.reprocess.mutate(selected.id, { onSuccess: setJob })}>Reprocess unmapped</Button>}</div></section>}
        {workspace.statements.isPending ? <div className="so-empty"><Clock3 size={28} /><h2>Loading statements…</h2></div> : workspace.statements.isError ? <div className="so-empty"><AlertTriangle size={28} /><h2>Statements unavailable</h2><p>The original remains preserved.</p><Button tone="secondary" onClick={() => void workspace.statements.refetch()}>Retry</Button></div> : (workspace.statements.data ?? []).length === 0 ? <div className="so-empty"><FileText size={28} /><h2>No statements available</h2><p>The parse may still be queued, may have failed, or may have produced no statements. Refresh the import to inspect its current status.</p></div> : <section aria-labelledby="so-review-title"><div className="so-section-head"><div><span className="so-kicker">Parsed as untrusted</span><h2 id="so-review-title">Review {(workspace.statements.data ?? []).length} ordered statements</h2></div><span>{(workspace.statements.data ?? []).filter(item => item.trust_state !== 'untrusted').length} decided</span></div><div className="so-statement-list">{(workspace.statements.data ?? []).map(statement => <ImportStatementReview key={statement.id} statement={statement} topics={topics} goalId={currentGoal.id} workspace={workspace} />)}</div><Disclosure><strong>Mapping and verification are personal decisions, not factual or editorial authority.</strong><p>Imported material cannot alter canonical lessons, create evidence, establish completion, or expand the approved graph.</p></Disclosure></section>}
      </>}
    </>}
  </>
}

function CanonicalUpdatesPage({ state, setState }: { state: OperationsState; setState: React.Dispatch<React.SetStateAction<OperationsState>> }) {
  const [selected, setSelected] = useState<string[]>(state.updateDecision === 'accepted' ? state.acceptedUpdates : UPDATE_ROWS.map((row) => row.id))
  const [overlayWins, setOverlayWins] = useState(state.acceptedConflictResolution !== 'canonical-adopted')
  const [approvalConfirmed, setApprovalConfirmed] = useState(false)
  const decided = state.updateDecision !== 'pending'
  const selectedTopics = state.acceptedUpdates.map((id) => UPDATE_ROWS.find((row) => row.id === id)?.topic).filter(Boolean)
  const changeSelection = (id: string, checked: boolean) => {
    setApprovalConfirmed(false)
    setSelected((current) => checked ? [...current, id] : current.filter((item) => item !== id))
  }
  const accept = () => {
    if (!approvalConfirmed || selected.length === 0) return
    setState((s) => ({
      ...s,
      goalVersion: '2026.08',
      updateDecision: 'accepted',
      acceptedUpdates: selected,
      acceptedConflictResolution: selected.includes('idempotency') ? (overlayWins ? 'overlay-kept' : 'canonical-adopted') : null,
    }))
  }
  const recordNonAcceptance = (decision: 'postponed' | 'dismissed') => setState((s) => ({ ...s, updateDecision: decision, acceptedUpdates: [], acceptedConflictResolution: null }))
  return <>
    <PageHead eyebrow="Published curriculum update" title="Review changes before they reach this goal" description={`This browser’s local goal is pinned to ${state.goalVersion}. ${state.goalVersion === '2026.07' ? 'Version 2026.08 is available, but nothing changes until you explicitly accept a selection.' : 'The accepted local version choice is stored only in this browser; no server or canonical source was changed.'}`} action={<div className="so-version" aria-label={`Local goal pinned to ${state.goalVersion}`}><span>Pinned locally</span><ArrowRight size={17} /><strong>{state.goalVersion}</strong></div>} />
    {decided && <div className="so-decision-banner"><Check size={18} /><div><strong>{state.updateDecision === 'accepted' ? `${state.acceptedUpdates.length} selected change${state.acceptedUpdates.length === 1 ? '' : 's'} accepted locally` : `Update ${state.updateDecision}`}</strong>{state.updateDecision === 'accepted' ? <><p>Accepted: {selectedTopics.join(', ') || 'none'}.</p><p>{state.acceptedConflictResolution === 'overlay-kept' ? 'Conflict resolution: learner overlay kept.' : state.acceptedConflictResolution === 'canonical-adopted' ? 'Conflict resolution: new canonical wording adopted for this local goal.' : 'No selected change required conflict resolution.'} No server or canonical source was mutated.</p></> : <p>The current goal version remains unchanged.</p>}</div><Button tone="quiet" onClick={() => { setApprovalConfirmed(false); setState((s) => ({ ...s, updateDecision: 'pending' })) }}>Review again</Button></div>}
    <section className="so-update-summary"><article><strong>3</strong><span>topic changes</span></article><article><strong>1</strong><span>overlay conflict</span></article><article><strong>0</strong><span>topics hidden</span></article><p>Acceptance moves this browser’s persisted local goal version pin; it does not publish, edit canonical content, or persist to a server.</p></section>
    <div className="so-diff-list">{UPDATE_ROWS.map((row) => <article key={row.id}><label className="so-select-change"><input type="checkbox" checked={selected.includes(row.id)} onChange={(event) => changeSelection(row.id, event.target.checked)} /><span className="so-sr-only">Select {row.topic}</span></label><div><span className="so-kicker">{row.topic}</span><div className="so-diff"><div><span>2026.07</span><p>{row.before}</p></div><div><span>2026.08</span><p>{row.after}</p></div></div><p className="so-impact"><Info size={15} /> {row.impact}</p>{row.conflict && selected.includes(row.id) && <fieldset className="so-conflict"><legend>Resolve wording conflict</legend><label><input type="radio" name="overlay-resolution" checked={overlayWins} onChange={() => { setOverlayWins(true); setApprovalConfirmed(false) }} /><span><strong>Keep my overlay wording</strong><small>The local goal retains your wording for this topic.</small></span></label><label><input type="radio" name="overlay-resolution" checked={!overlayWins} onChange={() => { setOverlayWins(false); setApprovalConfirmed(false) }} /><span><strong>Adopt the new canonical wording</strong><small>The overlay wording is replaced for this local goal only.</small></span></label></fieldset>}</div></article>)}</div>
    <div className="so-approval"><label><input type="checkbox" checked={approvalConfirmed} disabled={selected.length === 0} onChange={(event) => setApprovalConfirmed(event.target.checked)} /><span><strong>Approve this exact local selection</strong><small>I reviewed the selected changes{selected.includes('idempotency') ? ` and chose to ${overlayWins ? 'keep my overlay' : 'adopt the new wording'}` : ''}. Nothing updates until I press “Accept selected.”</small></span></label></div>
    <div className="so-sticky-actions"><span>{selected.length} of {UPDATE_ROWS.length} selected{selected.includes('idempotency') ? ` · ${overlayWins ? 'overlay kept' : 'canonical wording adopted'}` : ' · no conflict selected'}</span><div><Button tone="quiet" onClick={() => recordNonAcceptance('dismissed')}>Dismiss</Button><Button tone="secondary" onClick={() => recordNonAcceptance('postponed')}>Postpone</Button><Button tone="secondary" onClick={() => { setSelected(UPDATE_ROWS.map((row) => row.id)); setApprovalConfirmed(false) }}>Select all</Button><Button disabled={selected.length === 0 || !approvalConfirmed} onClick={accept}>Accept selected</Button></div></div>
  </>
}

function SearchPage({ navigate }: { navigate: Navigate }) {
  const { state: learning } = useLearningState()
  const [query, setQuery] = useState('')
  const [submitted, setSubmitted] = useState('')
  const [stale, setStale] = useState(true)
  const items = useMemo(() => [...SEARCH_ITEMS, ...learning.evidence.map((item) => ({ kind: 'Evidence', title: item.conclusion, path: `Evidence · ${item.id}`, text: `${item.artifact} ${item.limitation}`, lessonId: null }))], [learning.evidence])
  const results = useMemo(() => items.filter((item) => `${item.title} ${item.text}`.toLowerCase().includes(submitted.toLowerCase())), [items, submitted])
  return <>
    <PageHead eyebrow="Course and content search" title="Find a lesson, reading, review, or evidence record" description="Search uses this bundled local fixture. It is deterministic and makes no network, vector, semantic, or source-retrieval claim." />
    <form className="so-search" onSubmit={(event) => { event.preventDefault(); setSubmitted(query.trim()) }}><Search size={20} /><label className="so-sr-only" htmlFor="so-search-input">Search course content</label><input id="so-search-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Try “idempotency” or “dead letter”" /><Button type="submit">Search</Button></form>
    {stale && <div className="so-warning"><AlertTriangle size={19} /><div><strong>Bundled index may be stale</strong><p>Bundled course entries represent graph 2026.07. Submitted evidence results come directly from this application’s local learner state.</p></div><Button tone="secondary" onClick={() => setStale(false)}><X size={16} /> Dismiss notice</Button></div>}
    {!submitted ? <div className="so-empty"><Search size={29} /><h2>Search your current local course</h2><p>Results include titles and fixture keywords only. No remote sources are queried.</p></div> : results.length === 0 ? <div className="so-empty"><Search size={29} /><h2>No results for “{submitted}”</h2><p>Try a topic term such as retry, acknowledgement, idempotency, or DLQ.</p></div> : <section><div className="so-section-head"><div><span className="so-kicker">Local results</span><h2>{results.length} match{results.length === 1 ? '' : 'es'} for “{submitted}”</h2></div><span>Bundled entries + submitted evidence</span></div><div className="so-results">{results.map((item) => <button key={`${item.kind}-${item.path}`} onClick={() => navigate(item.kind === 'Evidence' ? 'evidence' : 'topic-studio')}><span className="so-chip">{item.kind}</span><strong>{item.title}</strong><small>{item.path}</small><ChevronRight size={19} /></button>)}</div></section>}
  </>
}

function JobsPage() {
  return <>
    <PageHead eyebrow="Operations" title="Jobs and local activity" description="There is no worker, durable queue, SSE stream, provider process, or runner connected to this application prototype." />
    <div className="so-hard-disclosure"><ShieldAlert size={24} /><div><strong>No live job system is connected</strong><p>This page does not invent job records or imply that checking, generation, importing, or indexing ran outside the browser.</p></div></div>
    <section className="so-panel"><div className="so-panel-head"><div><span className="so-kicker">Connection status</span><h2>Unavailable by design</h2></div><span>Local prototype boundary</span></div><div className="so-connection-grid"><article><span className="so-status-dot is-off" /><div><strong>Worker and durable queue</strong><p>Not connected; no job records are available.</p></div></article><article><span className="so-status-dot is-off" /><div><strong>SSE or polling</strong><p>Not connected; no status feed exists.</p></div></article><article><span className="so-status-dot is-off" /><div><strong>Model provider</strong><p>Not configured or invoked.</p></div></article><article><span className="so-status-dot is-off" /><div><strong>Java runner</strong><p>No compile or test process exists.</p></div></article></div></section>
  </>
}

function ConfirmDialog({ trigger, title, description, confirm, onConfirm, reducedMotion }: { trigger: React.ReactNode; title: string; description: string; confirm: string; onConfirm: () => void; reducedMotion: boolean }) {
  const motionClass = reducedMotion ? ' so-no-motion' : ''
  return <AlertDialog.Root><AlertDialog.Trigger asChild>{trigger}</AlertDialog.Trigger><AlertDialog.Portal><AlertDialog.Overlay className={`so-dialog-overlay${motionClass}`} /><AlertDialog.Content className={`so-dialog${motionClass}`}><AlertDialog.Title>{title}</AlertDialog.Title><AlertDialog.Description>{description}</AlertDialog.Description><div><AlertDialog.Cancel asChild><Button tone="secondary">Cancel</Button></AlertDialog.Cancel><AlertDialog.Action asChild><Button tone="danger" onClick={onConfirm}>{confirm}</Button></AlertDialog.Action></div></AlertDialog.Content></AlertDialog.Portal></AlertDialog.Root>
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

function SettingsPage({ state, setState, navigate }: { state: OperationsState; setState: React.Dispatch<React.SetStateAction<OperationsState>>; navigate: Navigate }) {
  const { currentGoal } = useProfileGoals()
  const imports = useImports(currentGoal?.id ?? null, null).imports
  const exportData = () => {
    const blob = new Blob([JSON.stringify({ exportedAt: new Date().toISOString(), scope: 'application prototype local operations state', ...state }, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'yuno-local-export.json'; anchor.click(); URL.revokeObjectURL(url)
  }
  return <>
    <PageHead eyebrow="Profile, preferences, and data" title="Settings" description="Your learner profile applies across every goal. Review preferences are saved per goal; display and accessibility choices remain local to this browser." />
    <div className="so-settings-grid">
      <GlobalProfileSettings />
      <section className="so-panel"><div className="so-panel-head"><div><SlidersHorizontal size={20} /><h2>Progress display</h2></div></div><fieldset className="so-choice-list"><legend>Choose the default view</legend><label><input type="radio" name="progress" checked={state.progress === 'detailed'} onChange={() => setState((s) => ({ ...s, progress: 'detailed' }))} /><span><strong>Detailed</strong><small>Coverage, proficiency, retention, readiness, definitions, and evidence links.</small></span></label><label><input type="radio" name="progress" checked={state.progress === 'simple'} onChange={() => setState((s) => ({ ...s, progress: 'simple' }))} /><span><strong>Simple</strong><small>Condensed display only; underlying local fixture data is not deleted.</small></span></label></fieldset></section>
      <ReviewPreferencesPanel goalId={currentGoal?.id ?? null} />
      <section className="so-panel"><div className="so-panel-head"><div><Settings2 size={20} /><h2>Accessibility</h2></div></div><label className="so-toggle-row"><span><strong>Reduce motion</strong><small>Suppress non-essential transitions in these pages.</small></span><input type="checkbox" checked={state.reducedMotion} onChange={(event) => setState((s) => ({ ...s, reducedMotion: event.target.checked }))} /></label><p className="so-help">Your operating-system reduced-motion preference is also respected.</p></section>
      <section className="so-panel"><div className="so-panel-head"><div><Import size={20} /><h2>Imports</h2></div></div>{!currentGoal ? <p>Select a current goal to review its imports.</p> : imports.isPending ? <p>Loading the current goal’s server imports…</p> : imports.isError ? <><p role="alert">The imports summary is unavailable. No browser count was substituted.</p><Button tone="secondary" onClick={() => void imports.refetch()}>Retry summary</Button></> : <p>{imports.data?.length ?? 0} preserved import{imports.data?.length === 1 ? '' : 's'} for {currentGoal.name}; {(imports.data ?? []).filter(item => item.status === 'failed' || item.status === 'cancelled').length} need attention.</p>}<Button tone="secondary" onClick={() => navigate('imports')}>Review imports <ArrowRight size={16} /></Button></section>
      <section className="so-panel so-settings-wide"><div className="so-panel-head"><div><Database size={20} /><h2>Providers and network</h2></div><span className="so-chip so-chip--gray">Not connected</span></div><div className="so-network-grid"><article><strong>Model providers</strong><p>No Codex, Claude, or other provider adapter is configured or invoked by these pages.</p></article><article><strong>Source retrieval</strong><p>No external documentation or citation source is fetched.</p></article><article><strong>Local runner</strong><p>No Java process, subprocess sandbox, or execution service is present.</p></article></div><p className="so-help">This prototype makes no strict-offline guarantee for the wider application; these operational pages themselves use bundled data and localStorage.</p></section>
      <section className="so-panel so-settings-wide"><div className="so-panel-head"><div><Download size={20} /><h2>Local data</h2></div></div><div className="so-data-actions"><div><strong>Export local JSON</strong><p>Downloads local display, accessibility, dispute, and update-decision state. Server imports and goal review preferences are not included.</p></div><Button tone="secondary" onClick={exportData}><Download size={16} /> Export JSON</Button></div><div className="so-data-actions"><div><strong>Reset operational pages</strong><p>Returns only local display, accessibility, dispute, and update-decision state to defaults. Server imports and goal review preferences remain intact.</p></div><ConfirmDialog reducedMotion={state.reducedMotion} trigger={<Button tone="danger"><RefreshCcw size={16} /> Reset local pages</Button>} title="Reset operational pages?" description="Local display, accessibility, dispute, and canonical update choices will be replaced with fixture defaults. Server imports and goal review preferences remain intact." confirm="Reset pages" onConfirm={() => { window.localStorage.removeItem(STORAGE_KEY); setState(DEFAULT_STATE) }} /></div></section>
    </div>
  </>
}

export function OperationalPageView({ page, navigate }: { page: OperationalPage; navigate: Navigate }) {
  const [state, setState] = useOperationsState()
  const pages: Record<OperationalPage, React.ReactNode> = {
    evidence: <EvidencePage state={state} setState={setState} navigate={navigate} />,
    imports: <ImportsPage />,
    'canonical-updates': <CanonicalUpdatesPage state={state} setState={setState} />,
    search: <SearchPage navigate={navigate} />,
    jobs: <JobsPage />,
    settings: <SettingsPage state={state} setState={setState} navigate={navigate} />,
  }
  return <main className={`so-page ${state.reducedMotion ? 'so-reduced-motion' : ''}`}>{pages[page]}</main>
}

export default OperationalPageView
