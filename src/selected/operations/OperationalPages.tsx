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
  Trash2,
  UserRound,
  X,
} from 'lucide-react'
import { useLearningState } from '../../shared/state'
import { useProfileGoals } from '../../shared/use-profile-goals'
import './operations.css'

export type OperationalPage = 'evidence' | 'imports' | 'canonical-updates' | 'search' | 'jobs' | 'settings'

type Navigate = (page: string) => void
type ImportDecision = 'untrusted' | 'mapped' | 'dismissed' | 'corrected'

interface ImportStatement {
  id: string
  original: string
  correction: string
  decision: ImportDecision
  topic: string
}

interface OperationsState {
  version: 1
  goalVersion: '2026.07' | '2026.08'
  owner: { name: string; role: string }
  progress: 'detailed' | 'simple'
  reducedMotion: boolean
  review: { enabled: boolean; duration: number; cadence: string; retrieval: boolean; variedContext: boolean }
  importSource: string
  importStatements: ImportStatement[]
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
  review: { enabled: true, duration: 15, cadence: 'Twice a week', retrieval: true, variedContext: true },
  importSource: '',
  importStatements: [],
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
  const review = isRecord(value.review) ? value.review : {}
  const importStatements = Array.isArray(value.importStatements)
    ? value.importStatements.filter((item): item is ImportStatement => isRecord(item)
      && typeof item.id === 'string'
      && typeof item.original === 'string'
      && typeof item.correction === 'string'
      && (item.decision === 'untrusted' || item.decision === 'mapped' || item.decision === 'dismissed' || item.decision === 'corrected')
      && typeof item.topic === 'string')
    : DEFAULT_STATE.importStatements
  return {
    version: 1,
    goalVersion: value.goalVersion === '2026.08' ? '2026.08' : DEFAULT_STATE.goalVersion,
    owner: {
      name: typeof owner.name === 'string' ? owner.name : DEFAULT_STATE.owner.name,
      role: typeof owner.role === 'string' ? owner.role : DEFAULT_STATE.owner.role,
    },
    progress: value.progress === 'simple' || value.progress === 'detailed' ? value.progress : DEFAULT_STATE.progress,
    reducedMotion: typeof value.reducedMotion === 'boolean' ? value.reducedMotion : DEFAULT_STATE.reducedMotion,
    review: {
      enabled: typeof review.enabled === 'boolean' ? review.enabled : DEFAULT_STATE.review.enabled,
      duration: typeof review.duration === 'number' && Number.isFinite(review.duration) ? review.duration : DEFAULT_STATE.review.duration,
      cadence: typeof review.cadence === 'string' ? review.cadence : DEFAULT_STATE.review.cadence,
      retrieval: typeof review.retrieval === 'boolean' ? review.retrieval : DEFAULT_STATE.review.retrieval,
      variedContext: typeof review.variedContext === 'boolean' ? review.variedContext : DEFAULT_STATE.review.variedContext,
    },
    importSource: typeof value.importSource === 'string' ? value.importSource : DEFAULT_STATE.importSource,
    importStatements,
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

function parseImport(source: string): ImportStatement[] {
  return source.split(/\n+/).map((line) => line.trim().replace(/^[-*+#>\d.()\s]+/, '').trim()).filter((line) => line.length > 8).map((line, index) => ({ id: `statement-${index + 1}`, original: line, correction: line, decision: 'untrusted', topic: '' }))
}

function ImportsPage({ state, setState }: { state: OperationsState; setState: React.Dispatch<React.SetStateAction<OperationsState>> }) {
  const updateStatement = (id: string, patch: Partial<ImportStatement>) => setState((s) => ({ ...s, importStatements: s.importStatements.map((item) => item.id === id ? { ...item, ...patch } : item) }))
  return <>
    <PageHead eyebrow="Local import review" title="Bring notes in as untrusted material" description="Markdown and plain text stay on this device in this prototype. Parsing proposes statements; it never creates truth, evidence, or completion." />
    <section className="so-panel so-import-box"><label htmlFor="so-import-source"><span className="so-kicker">Original source</span><strong>Paste Markdown or plain text</strong></label><textarea id="so-import-source" value={state.importSource} onChange={(event) => setState((s) => ({ ...s, importSource: event.target.value }))} placeholder={'# Messaging notes\n- SQS may redeliver messages.\n- Acknowledgement should happen after the durable decision.'} /><div className="so-inline-actions"><span>The original is preserved exactly for inspection.</span><Button disabled={!state.importSource.trim()} onClick={() => setState((s) => ({ ...s, importStatements: parseImport(s.importSource) }))}><Import size={17} /> Parse locally</Button></div></section>
    {state.importStatements.length === 0 ? <div className="so-empty"><FileText size={28} /><h2>No statements to review</h2><p>Paste notes above, then run the deterministic local parser. Headings and short fragments are ignored.</p></div> : <section aria-labelledby="so-review-title"><div className="so-section-head"><div><span className="so-kicker">Parsed as untrusted</span><h2 id="so-review-title">Review {state.importStatements.length} proposed statements</h2></div><span>{state.importStatements.filter((item) => item.decision !== 'untrusted').length} decided</span></div><div className="so-statement-list">{state.importStatements.map((item) => <article key={item.id} className={item.decision === 'dismissed' ? 'is-muted' : ''}><div className="so-statement-number">{item.id.replace('statement-', '')}</div><div><span className="so-chip">{item.decision}</span><p className="so-original">“{item.original}”</p>{item.decision === 'corrected' && <label>Corrected wording<textarea value={item.correction} onChange={(event) => updateStatement(item.id, { correction: event.target.value })} /></label>}<label>Map to topic<select disabled={item.decision === 'dismissed'} value={item.topic} onChange={(event) => updateStatement(item.id, { topic: event.target.value, decision: event.target.value ? 'mapped' : 'untrusted' })}><option value="">Not mapped</option><option value="delivery-contract">Message delivery contract</option><option value="idempotency-retry">Idempotency under retries</option><option value="dead-letter">Dead-letter recovery</option></select></label></div><div className="so-row-actions">{item.decision === 'dismissed' ? <Button tone="quiet" onClick={() => updateStatement(item.id, { decision: item.topic ? 'mapped' : 'untrusted' })}>Restore</Button> : <><Button tone="quiet" onClick={() => updateStatement(item.id, { decision: 'corrected' })}>Correct</Button><Button tone="quiet" onClick={() => updateStatement(item.id, { decision: 'dismissed' })}><X size={15} /> Dismiss</Button></>}</div></article>)}</div><Disclosure><strong>Mapping is a learner decision, not verification.</strong><p>Mapped text may inform a future proposal only after review. It remains personal imported material and does not alter canonical lessons or progress.</p></Disclosure></section>}
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

function SettingsPage({ state, setState, navigate }: { state: OperationsState; setState: React.Dispatch<React.SetStateAction<OperationsState>>; navigate: Navigate }) {
  const exportData = () => {
    const blob = new Blob([JSON.stringify({ exportedAt: new Date().toISOString(), scope: 'application prototype local operations state', ...state }, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'yuno-local-export.json'; anchor.click(); URL.revokeObjectURL(url)
  }
  return <>
    <PageHead eyebrow="Profile, preferences, and data" title="Settings" description="Your learner profile applies across every goal. Goal progress and evidence remain isolated; other prototype preferences on this page are local to this browser." />
    <div className="so-settings-grid">
      <GlobalProfileSettings />
      <section className="so-panel"><div className="so-panel-head"><div><SlidersHorizontal size={20} /><h2>Progress display</h2></div></div><fieldset className="so-choice-list"><legend>Choose the default view</legend><label><input type="radio" name="progress" checked={state.progress === 'detailed'} onChange={() => setState((s) => ({ ...s, progress: 'detailed' }))} /><span><strong>Detailed</strong><small>Coverage, proficiency, retention, readiness, definitions, and evidence links.</small></span></label><label><input type="radio" name="progress" checked={state.progress === 'simple'} onChange={() => setState((s) => ({ ...s, progress: 'simple' }))} /><span><strong>Simple</strong><small>Condensed display only; underlying local fixture data is not deleted.</small></span></label></fieldset></section>
      <section className="so-panel so-settings-wide"><div className="so-panel-head"><div><Clock3 size={20} /><h2>Optional review</h2></div><label className="so-switch"><input type="checkbox" checked={state.review.enabled} onChange={(event) => setState((s) => ({ ...s, review: { ...s.review, enabled: event.target.checked } }))} /><span>{state.review.enabled ? 'Enabled' : 'Disabled'}</span></label></div><div className="so-review-controls" aria-disabled={!state.review.enabled}><label>Session length<select disabled={!state.review.enabled} value={state.review.duration} onChange={(event) => setState((s) => ({ ...s, review: { ...s.review, duration: Number(event.target.value) } }))}><option value={10}>10 minutes</option><option value={15}>15 minutes</option><option value={25}>25 minutes</option></select></label><label>Cadence<select disabled={!state.review.enabled} value={state.review.cadence} onChange={(event) => setState((s) => ({ ...s, review: { ...s.review, cadence: event.target.value } }))}><option>Once a week</option><option>Twice a week</option><option>Three times a week</option></select></label><label className="so-check"><input type="checkbox" disabled={!state.review.enabled} checked={state.review.retrieval} onChange={(event) => setState((s) => ({ ...s, review: { ...s.review, retrieval: event.target.checked } }))} /> Retrieval prompts</label><label className="so-check"><input type="checkbox" disabled={!state.review.enabled} checked={state.review.variedContext} onChange={(event) => setState((s) => ({ ...s, review: { ...s.review, variedContext: event.target.checked } }))} /> Varied contexts</label></div><p className="so-help">Disabling or dismissing review never blocks the roadmap and carries no readiness penalty.</p></section>
      <section className="so-panel"><div className="so-panel-head"><div><Settings2 size={20} /><h2>Accessibility</h2></div></div><label className="so-toggle-row"><span><strong>Reduce motion</strong><small>Suppress non-essential transitions in these pages.</small></span><input type="checkbox" checked={state.reducedMotion} onChange={(event) => setState((s) => ({ ...s, reducedMotion: event.target.checked }))} /></label><p className="so-help">Your operating-system reduced-motion preference is also respected.</p></section>
      <section className="so-panel"><div className="so-panel-head"><div><Import size={20} /><h2>Imports</h2></div></div><p>{state.importStatements.length} parsed statement{state.importStatements.length === 1 ? '' : 's'} stored in this browser.</p><Button tone="secondary" onClick={() => navigate('imports')}>Review imports <ArrowRight size={16} /></Button></section>
      <section className="so-panel so-settings-wide"><div className="so-panel-head"><div><Database size={20} /><h2>Providers and network</h2></div><span className="so-chip so-chip--gray">Not connected</span></div><div className="so-network-grid"><article><strong>Model providers</strong><p>No Codex, Claude, or other provider adapter is configured or invoked by these pages.</p></article><article><strong>Source retrieval</strong><p>No external documentation or citation source is fetched.</p></article><article><strong>Local runner</strong><p>No Java process, subprocess sandbox, or execution service is present.</p></article></div><p className="so-help">This prototype makes no strict-offline guarantee for the wider application; these operational pages themselves use bundled data and localStorage.</p></section>
      <section className="so-panel so-settings-wide"><div className="so-panel-head"><div><Download size={20} /><h2>Local data</h2></div></div><div className="so-data-actions"><div><strong>Export local JSON</strong><p>Downloads this prototype’s profile, preferences, import text, review decisions, and update decision.</p></div><Button tone="secondary" onClick={exportData}><Download size={16} /> Export JSON</Button></div><div className="so-data-actions"><div><strong>Delete imported material</strong><p>Removes original import text and parsed statements from this browser.</p></div><ConfirmDialog reducedMotion={state.reducedMotion} trigger={<Button tone="danger"><Trash2 size={16} /> Delete imports</Button>} title="Delete all imported material?" description="This removes the preserved original and every parsed statement from this browser. This prototype has no recovery service." confirm="Delete imports" onConfirm={() => setState((s) => ({ ...s, importSource: '', importStatements: [] }))} /></div><div className="so-data-actions"><div><strong>Reset operational pages</strong><p>Returns these operational pages to fixture defaults. Other application data is outside this control.</p></div><ConfirmDialog reducedMotion={state.reducedMotion} trigger={<Button tone="danger"><RefreshCcw size={16} /> Reset local pages</Button>} title="Reset operational pages?" description="Profile, preferences, disputes, import material, and canonical update choices stored by these pages will be replaced with fixture defaults." confirm="Reset pages" onConfirm={() => { window.localStorage.removeItem(STORAGE_KEY); setState(DEFAULT_STATE) }} /></div></section>
    </div>
  </>
}

export function OperationalPageView({ page, navigate }: { page: OperationalPage; navigate: Navigate }) {
  const [state, setState] = useOperationsState()
  const pages: Record<OperationalPage, React.ReactNode> = {
    evidence: <EvidencePage state={state} setState={setState} navigate={navigate} />,
    imports: <ImportsPage state={state} setState={setState} />,
    'canonical-updates': <CanonicalUpdatesPage state={state} setState={setState} />,
    search: <SearchPage navigate={navigate} />,
    jobs: <JobsPage />,
    settings: <SettingsPage state={state} setState={setState} navigate={navigate} />,
  }
  return <main className={`so-page ${state.reducedMotion ? 'so-reduced-motion' : ''}`}>{pages[page]}</main>
}

export default OperationalPageView
