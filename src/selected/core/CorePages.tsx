import { forwardRef, useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import * as AlertDialog from '@radix-ui/react-alert-dialog'
import * as Dialog from '@radix-ui/react-dialog'
import * as Tabs from '@radix-ui/react-tabs'
import {
  AlertTriangle, Archive, ArrowDown, ArrowLeft, ArrowRight, ArrowUp, BookOpen, Check, ChevronDown, Circle,
  Clock3, Code2, FileText, HelpCircle, History, Lightbulb, ListTree, MessageSquareText,
  LockKeyhole, NotebookPen, Pause, Play, RefreshCcw, Settings2, ShieldCheck, X,
} from 'lucide-react'
import {
  CURRENT_LESSON_ID,
  type Depth,
} from '../../shared/model'
import { ApiError, canonicalVersionsQueryOptions } from '../../shared/api/queries'
import { goalDestination, resumePage, useProfileGoals } from '../../shared/use-profile-goals'
import type { GoalCreate, GoalWorkspace } from '../../shared/api/profile-goals'
import { useDiagnostic, type DiagnosticConfidence, type DiagnosticPreviewEdit, type DiagnosticSetup } from '../../shared/use-diagnostic'
import { useRoadmap } from '../../shared/use-roadmap'
import {
  TOPIC_LAYERS,
  type ArtifactProvenanceSummary,
  type SourceSnapshot,
  type TopicCheckpoint,
  type TopicLayerContent,
  type TopicLayerName,
} from '../../shared/api/learning-content'
import { useArtifactProvenance, useTopicContent, useTopicConversation } from '../../shared/use-topic-content'
import { useNotebookReview } from '../../shared/use-notebook-review'
import { useGoalEvidenceReport } from '../../shared/use-evidence'
import { useOwnerSettings } from '../../shared/use-settings'
import { useInterview, useMockReport, useMockRun, usePracticeRun } from '../../shared/use-interview'
import type { InterviewBundle, InterviewLevel, InterviewQuestion, InterviewRefresher } from '../../shared/api/interview'
import type { ReviewAttempt, ReviewItem } from '../../shared/api/notebook-review'
import { HandsOnLab } from './HandsOnLab'
import { roadmapQueryOptions, type LearnerCorrection, type OverlayProposal, type OverlayProposalDecision } from '../../shared/api/roadmap'
import { JobConnectionStatus } from '../../shared/job-events'
import type { Job } from '../../shared/api/jobs'
import type { InterviewMode, InterviewSelection } from '../app-model'
import './core.css'

export type CorePage = 'home' | 'onboarding' | 'learn-roadmap' | 'topic-studio' | 'interview-hub' | 'practice' | 'mock' | 'reports'

type Navigate = (page: CorePage | string, mode?: InterviewMode, selection?: InterviewSelection) => void
type PageProps = { navigate: Navigate; selection?: InterviewSelection }
const DEPTHS: readonly Depth[] = ['Essential', 'Implementation', 'Production', 'Interview']

// role-competency-copy-v1 — approved verbatim in docs/decisions/IDK-004-role-level-competencies.md §2.
// One versioned copy registry (IDK-004 §5) shared by onboarding, goal Settings, and Interview Prep role/level controls.
export const ROLE_LEVEL_COPY_VERSION = 'role-competency-copy-v1'
export const ROLE_LEVEL_HEADING = 'Choose the scope you want to practice'
export const ROLE_LEVEL_AUDIENCE_NOTE = 'Yuno is for backend engineers who have already shipped software. It does not include an absolute-beginner track.'
export const ROLE_LEVEL_TITLE_VARIATION_HELPER = 'Titles vary across companies. Choose the description closest to the scope you want to practice—not necessarily your current title. You can change it later. This choice changes scenario breadth and evaluation expectations; it does not validate a title or predict hiring, promotion, or job performance.'
export const TARGET_CAPABILITY_HELPER = 'Level sets the scope of practice. Capability sets what you want to demonstrate now. Choose one; you can edit it before confirming the goal and later in Settings.'
export const ROLE_LEVEL_COPY: Record<GoalCreate['target_level'], { label: string; description: string }> = {
  'Mid-level': {
    label: 'Mid-level backend engineer',
    description: 'Work within a bounded service or data path, with attention to correctness, testability, direct failures, and local operational consequences.',
  },
  Senior: {
    label: 'Senior backend engineer',
    description: 'Work across an end-to-end multi-service and data flow, including partial failure, rollout, recovery, observability, and alternatives under constraints.',
  },
  Staff: {
    label: 'Staff-level backend engineer',
    description: 'Work across systems and teams, including decision boundaries, migration and rollback, second-order failure, capacity, cost, ownership, governance, and exceptions.',
  },
}

function providerStartFailure(error: unknown, action: string) {
  if (error instanceof ApiError && error.status === 412) return `Waiting for disclosure. Accept the current provider-network disclosure in Settings, then ${action}.`
  if (error instanceof ApiError && error.status === 503) return `The selected provider is unavailable or misconfigured. Review provider status in Settings, then ${action}.`
  return `The provider-backed action did not start. ${action[0]!.toUpperCase()}${action.slice(1)}.`
}

function ProviderJobStatus({ label, job, retry, retrying = false }: { label: string; job: Job | undefined; retry?: () => void; retrying?: boolean }) {
  if (!job) return null
  const detail = {
    queued: 'The request is queued. Your submitted response is preserved.',
    running: 'The provider is working. Unvalidated output remains hidden.',
    succeeded: 'Validated results were published by the server.',
    failed: job.retryable ? 'The request failed safely. Your response is preserved and can be retried.' : 'The request failed safely. Your response is preserved.',
    'cancel-requested': 'Cancellation is in progress. Your submitted response remains preserved.',
    cancelled: 'The request was cancelled. No partial result was published.',
  }[job.status]
  const alert = job.status === 'failed'
  return <aside className="sb-neutral" role={alert ? 'alert' : 'status'} data-provider-job-state={job.status}><Clock3 /><div><strong>{label} {job.status}</strong><p>{detail}</p>{job.status === 'failed' && job.retryable && retry && <Button tone="quiet" disabled={retrying} onClick={retry}>{retrying ? 'Retrying…' : `Retry ${label.toLowerCase()}`}</Button>}</div></aside>
}

const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { tone?: 'primary' | 'secondary' | 'quiet' }>(function Button({ children, tone = 'primary', className = '', ...props }, ref) {
  return <button ref={ref} className={`sb-button sb-button--${tone} ${className}`} {...props}>{children}</button>
})

function PageIntro({ eyebrow, title, children, action }: { eyebrow: string; title: string; children: ReactNode; action?: ReactNode }) {
  return <header className="sb-page-intro"><div><span className="sb-eyebrow">{eyebrow}</span><h1>{title}</h1><p>{children}</p></div>{action}</header>
}

function WorkspaceState({ state, navigate, retry }: { state: 'loading' | 'empty' | 'locked' | 'unavailable'; navigate: Navigate; retry: () => void }) {
  if (state === 'loading') {
    return <main className="sb-page sb-workspace-state" aria-live="polite"><RefreshCcw aria-hidden="true" /><h1>Loading My learning</h1><p>Fetching your goals.</p></main>
  }
  if (state === 'empty') {
    return <main className="sb-page sb-workspace-state" data-workspace-state="empty"><BookOpen aria-hidden="true" /><h1>No learning goals yet</h1><p>Set up a Learn or Interview Prep goal.</p><Button onClick={() => navigate('onboarding')}>Set up a goal <ArrowRight size={16} /></Button></main>
  }
  const locked = state === 'locked'
  return <main className="sb-page sb-workspace-state" data-workspace-state={state} aria-live="polite"><LockKeyhole aria-hidden="true" /><h1>{locked ? 'My learning is locked' : 'My learning is unavailable'}</h1><p>{locked ? 'The selected goal is being updated.' : 'Your goals could not be loaded.'}</p><Button onClick={retry}>Retry</Button></main>
}

function GoalCard({ goal, current, navigate, workspace }: { goal: GoalWorkspace; current: boolean; navigate: Navigate; workspace: ReturnType<typeof useProfileGoals> }) {
  const open = async () => {
    if (!current) await workspace.switchGoal.mutateAsync(goal)
    navigate(goalDestination(goal))
  }

  return <article className={`sb-course-row ${current ? 'is-current' : ''}`}>
    <div className="sb-course-icon"><BookOpen /></div>
    <div>
      <span className="sb-chip">{current ? 'Current' : 'Active'}</span>
      <h3>{goal.name}</h3>
      <p>{goal.subject ?? goal.role ?? (goal.path === 'learn' ? 'Learn' : 'Interview Prep')} · {goal.target_level}</p>
      <small>{goal.resume_position ? `Resume: ${goal.resume_position}` : 'No saved position yet'} · target capability: {goal.target_capability}</small>
    </div>
    <div className="sb-goal-actions">
      {!current && <Button tone="secondary" disabled={workspace.switchGoal.isPending} onClick={() => workspace.switchGoal.mutate(goal)}>Make current</Button>}
      <Button tone="quiet" disabled={workspace.switchGoal.isPending} onClick={() => void open()} aria-label={`Open ${goal.name}`}>Open <ArrowRight size={16} /></Button>
      <AlertDialog.Root>
        <AlertDialog.Trigger asChild><Button tone="quiet" aria-label={`Archive ${goal.name}`}><Archive size={16} /> Archive</Button></AlertDialog.Trigger>
        <AlertDialog.Portal>
          <AlertDialog.Overlay className="sb-overlay" />
          <AlertDialog.Content className="sb-alert">
            <AlertDialog.Title>Archive {goal.name}?</AlertDialog.Title>
            <AlertDialog.Description>This removes the goal from your active workspaces without moving its saved state.</AlertDialog.Description>
            <div><AlertDialog.Cancel asChild><Button tone="secondary">Cancel</Button></AlertDialog.Cancel><AlertDialog.Action asChild><Button onClick={() => workspace.archive.mutate(goal)}>Archive goal</Button></AlertDialog.Action></div>
          </AlertDialog.Content>
        </AlertDialog.Portal>
      </AlertDialog.Root>
    </div>
  </article>
}

export function Home({ navigate }: PageProps) {
  const workspace = useProfileGoals()
  const canonicalVersions = useQuery(canonicalVersionsQueryOptions())
  const resumeRoadmap = useQuery(roadmapQueryOptions(workspace.currentGoal?.id ?? null))
  const error = workspace.goals.error ?? workspace.profile.error
  const errorStatus = error instanceof ApiError ? error.status : null

  if (workspace.goals.isPending || workspace.profile.isPending) {
    return <WorkspaceState state="loading" navigate={navigate} retry={() => void workspace.refresh()} />
  }
  if (error) {
    return <WorkspaceState state={errorStatus === 423 ? 'locked' : 'unavailable'} navigate={navigate} retry={() => void workspace.refresh()} />
  }
  if (workspace.profile.data?.current_goal_id && !workspace.currentGoal) {
    return <WorkspaceState state="unavailable" navigate={navigate} retry={() => void workspace.refresh()} />
  }
  if (workspace.activeGoals.length === 0) {
    return <WorkspaceState state="empty" navigate={navigate} retry={() => void workspace.refresh()} />
  }

  const currentGoal = workspace.currentGoal
  const refreshing = workspace.goals.isFetching || workspace.profile.isFetching
  const latestGraph = canonicalVersions.data?.[0]
  const canonicalStale = Boolean(currentGoal && latestGraph && currentGoal.graph_version_id !== latestGraph.id)
  const recommendationKey = currentGoal ? `goal-entry:${currentGoal.path}:${currentGoal.target_capability}` : null
  const recommendationVisible = currentGoal && recommendationKey && !currentGoal.dismissed_recommendation_keys.includes(recommendationKey)
  const resumeTitle = resumeRoadmap.data?.topics.find(topic => topic.stable_id === currentGoal?.resume_position)?.title ?? currentGoal?.resume_position ?? null
  const actionError = workspace.switchGoal.error ?? workspace.archive.error ?? workspace.dismissRecommendation.error ?? workspace.recordNavigation.error
  const resume = () => {
    if (!currentGoal?.resume_position) return
    navigate(resumePage(currentGoal))
  }
  return <main className="sb-page sb-home" data-workspace-state={canonicalStale ? 'stale' : 'ready'}>
    <PageIntro eyebrow="Your goal workspaces" title={currentGoal ? `Continue ${currentGoal.name}` : 'Choose a learning goal'} action={<Button tone="quiet" onClick={() => navigate('onboarding')}>Set up another goal <ArrowRight size={17} /></Button>}>
      Resume saved work or open another goal.
    </PageIntro>
    {canonicalStale && <p className="sb-stale-note" role="status">A newer approved curriculum is available. This goal stays pinned until you review it.</p>}
    {refreshing && <p className="sb-refreshing-note" role="status">Refreshing goals…</p>}
    {canonicalVersions.isError && <div className="sb-action-error" role="alert"><span>Could not check for curriculum updates.</span><Button tone="secondary" onClick={() => void canonicalVersions.refetch()}>Retry</Button></div>}
    {actionError && <div className="sb-action-error" role="alert"><span>The goal action was not saved.</span><Button tone="secondary" onClick={() => void workspace.refresh()}>Reload goals</Button></div>}
    {currentGoal?.resume_position && <section className="sb-resume" aria-labelledby="sb-resume-title">
      <div className="sb-resume-art"><History size={28} /><span>Historical Resume</span><strong>Saved position</strong></div>
      <div><span className="sb-kicker">Resume from your last position</span><h2 id="sb-resume-title">{resumeTitle}</h2><p>{currentGoal.name}</p><div className="sb-meta"><span><Clock3 size={15} /> Last saved learning position</span><span>Kept separately from recommendations</span></div></div>
      <Button onClick={resume}><Play size={17} /> Resume</Button>
    </section>}
    {recommendationVisible && <section className="sb-recommend" aria-labelledby="sb-recommend-title">
      <div className="sb-round-icon"><Lightbulb size={20} /></div><div><span className="sb-kicker">Recommended next</span><h2 id="sb-recommend-title">Review the {currentGoal.path === 'learn' ? 'learning roadmap' : 'interview preparation hub'}</h2><p>Suggested for your {currentGoal.target_capability} target. Your saved Resume position will not change.</p></div>
      <Button tone="secondary" onClick={() => navigate(goalDestination(currentGoal))}>Open</Button>
      <button className="sb-icon-button" disabled={workspace.dismissRecommendation.isPending} onClick={() => workspace.dismissRecommendation.mutate({ goal: currentGoal, key: recommendationKey })} aria-label="Dismiss recommended next item"><X size={18} /></button>
    </section>}
    <section className="sb-library" aria-labelledby="sb-library-title"><div className="sb-section-title"><div><span className="sb-kicker">Active workspaces</span><h2 id="sb-library-title">Your goals</h2></div><span>{workspace.activeGoals.length} active</span></div>
      {workspace.activeGoals.map((goal) => <GoalCard key={goal.id} goal={goal} current={goal.id === currentGoal?.id} navigate={navigate} workspace={workspace} />)}
    </section>
  </main>
}

export function Onboarding({ navigate }: PageProps) {
  const workspace = useProfileGoals()
  const canonicalVersions = useQuery(canonicalVersionsQueryOptions())
  const diagnostic = useDiagnostic()
  const [path, setPath] = useState<'Learn' | 'Interview Prep'>('Learn')
  // IDK-004 §4: first-use setup has no preselected level; the learner must make and confirm
  // an explicit selection before continuing. An empty string is "unselected," never a default level.
  const [targetLevel, setTargetLevel] = useState<GoalCreate['target_level'] | ''>('')
  const [goalName, setGoalName] = useState('')
  const [subjectOrRole, setSubjectOrRole] = useState('')
  const [targetCapability, setTargetCapability] = useState<GoalCreate['target_capability']>('implement')
  const [diagnosticChoice, setDiagnosticChoice] = useState<'skip' | 'take'>('skip')
  const [seed, setSeed] = useState('')
  const [answer, setAnswer] = useState('')
  const [confidence, setConfidence] = useState<DiagnosticConfidence>('medium')
  const [previewEdits, setPreviewEdits] = useState<DiagnosticPreviewEdit[]>([])
  const [previewOrder, setPreviewOrder] = useState<string[]>([])
  const [jumpedPreviewTopic, setJumpedPreviewTopic] = useState<string | null>(null)
  const previewSaveQueue = useRef<Promise<unknown>>(Promise.resolve())
  const answerIdempotencyKey = useRef(crypto.randomUUID())
  const graphVersion = canonicalVersions.data?.[0]
  const session = diagnostic.session.data
  const preview = session?.state === 'roadmap-preview'
  const seedResolved = Boolean(session?.seed_skipped || session?.untrusted_seed_text)
  const activeQuestionRef = session?.next_question?.ref
  const persistedPreviewPath = session?.setup_inputs.path === 'interview_prep' ? 'Interview Prep' : 'Learn'
  const persistedPreviewLevel = typeof session?.setup_inputs.target_level === 'string' ? session.setup_inputs.target_level : targetLevel

  useEffect(() => setAnswer(''), [activeQuestionRef])
  useEffect(() => {
    if (preview && !diagnostic.preview.data && !diagnostic.preview.isPending) {
      diagnostic.preview.mutate(session.id)
    }
  }, [preview, session?.id])
  useEffect(() => {
    const data = diagnostic.preview.data
    if (!data) return
    setPreviewEdits((data.saved_edits ?? []) as DiagnosticPreviewEdit[])
    setPreviewOrder(data.topic_recommendations.map((item) => String(item.stable_id)))
  }, [diagnostic.preview.data?.projection_version])

  const openPreview = async (current: NonNullable<typeof session>) => {
    const previewSession = current.state === 'roadmap-preview'
      ? current
      : await diagnostic.patch.mutateAsync({ session: current, patch: { action: 'open_roadmap_preview' } })
    await diagnostic.preview.mutateAsync(previewSession.id)
  }
  const beginDiagnostic = async () => {
    if (!graphVersion || !targetLevel) return
    const input: DiagnosticSetup = {
      path: path === 'Learn' ? 'learn' : 'interview_prep',
      target_level: targetLevel,
      target_capability: targetCapability,
      graph_version_id: graphVersion.id,
      ...(path === 'Learn' ? { subject: subjectOrRole.trim() } : { role: subjectOrRole.trim() }),
      setup_inputs: { goal_name: goalName.trim() },
    }
    let current = await diagnostic.create.mutateAsync(input)
    current = await diagnostic.patch.mutateAsync({
      session: current,
      patch: seed ? { untrusted_seed_text: seed } : { action: 'skip_notes' },
    })
    if (diagnosticChoice === 'skip') {
      current = await diagnostic.patch.mutateAsync({ session: current, patch: { action: 'skip_diagnostic' } })
      await openPreview(current)
    }
  }
  const patchSession = async (action: 'resume' | 'skip_diagnostic' | 'retry') => {
    if (!session) return
    const updated = await diagnostic.patch.mutateAsync({ session, patch: { action } })
    if (action === 'skip_diagnostic') await openPreview(updated)
  }
  const pauseAndExit = async () => {
    if (!session) return
    await diagnostic.patch.mutateAsync({ session, patch: { action: 'pause' } })
    navigate('home')
  }
  const resolveSeed = async (skip: boolean) => {
    if (!session) return
    await diagnostic.patch.mutateAsync({
      session,
      patch: skip ? { action: 'skip_notes' } : { untrusted_seed_text: seed },
    })
  }
  const submitAnswer = async () => {
    if (!session || !answer.trim()) return
    const updated = await diagnostic.answer.mutateAsync({ session, answer, confidence, idempotencyKey: answerIdempotencyKey.current })
    answerIdempotencyKey.current = crypto.randomUUID()
    if (!updated.next_question) await openPreview(updated)
  }
  const createWorkspace = async () => {
    if (!session) return
    await previewSaveQueue.current.catch(() => undefined)
    diagnostic.confirm.mutate({ session, edits: previewEdits }, { onSuccess: async (goal) => {
      const refreshedProfile = await workspace.profile.refetch()
      if (refreshedProfile.data?.current_goal_id === goal.id) await workspace.goals.refetch()
      else await workspace.switchGoal.mutateAsync(goal)
      diagnostic.clear()
      navigate(goalDestination(goal))
    } })
  }
  const diagnosticError = diagnostic.create.error ?? diagnostic.patch.error ?? diagnostic.answer.error ?? diagnostic.preview.error ?? diagnostic.savePreview.error ?? diagnostic.confirm.error ?? diagnostic.session.error
  const working = diagnostic.create.isPending || diagnostic.patch.isPending || diagnostic.answer.isPending || diagnostic.preview.isPending || diagnostic.savePreview.isPending || diagnostic.confirm.isPending

  const previewTopics = (diagnostic.preview.data?.topic_recommendations ?? []) as Array<{
    stable_id: string; title: string; classification: string; recommended_depth: string;
    depth_override: string | null; is_skipped: boolean
  }>
  const orderedPreviewTopics = previewOrder
    .map((id) => previewTopics.find((topic) => topic.stable_id === id))
    .filter((topic): topic is (typeof previewTopics)[number] => Boolean(topic))
  const savePreviewEdits = (next: DiagnosticPreviewEdit[]) => {
    if (!session) return
    setPreviewEdits(next)
    previewSaveQueue.current = previewSaveQueue.current
      .catch(() => undefined)
      .then(() => diagnostic.savePreview.mutateAsync({ sessionId: session.id, edits: next }))
  }
  const replacePreviewEdit = (edit: DiagnosticPreviewEdit) => {
    const next = previewEdits.filter((item) => !(item.entry_type === edit.entry_type && item.topic_stable_id === edit.topic_stable_id))
    savePreviewEdits([...next, edit])
  }
  const confirmPreviewEdit = (message: string, edit: DiagnosticPreviewEdit) => {
    if (window.confirm(message)) replacePreviewEdit(edit)
  }
  const movePreviewTopic = (index: number, direction: -1 | 1) => {
    const target = index + direction
    if (target < 0 || target >= previewOrder.length) return
    const topic = orderedPreviewTopics[index]
    if (!topic || !window.confirm(`Move ${topic.title} ${direction < 0 ? 'earlier' : 'later'}?`)) return
    const nextOrder = [...previewOrder]
    const displaced = nextOrder[target]
    nextOrder[target] = nextOrder[index]!
    nextOrder[index] = displaced!
    setPreviewOrder(nextOrder)
    const nonOrder = previewEdits.filter((item) => item.entry_type !== 'order_constraint')
    const constraints: DiagnosticPreviewEdit[] = nextOrder.slice(0, -1).map((before, position) => ({
      topic_stable_id: null,
      entry_type: 'order_constraint',
      value: { before_topic_id: before, after_topic_id: nextOrder[position + 1]! },
      reason: 'Learner preview ordering',
    }))
    savePreviewEdits([...nonOrder, ...constraints])
  }
  const jumpToPreviewTopic = (topicId: string) => {
    setJumpedPreviewTopic(topicId)
    requestAnimationFrame(() => {
      const topic = document.getElementById(`preview-topic-${topicId}`)
      topic?.scrollIntoView({ block: 'center' })
      topic?.focus()
    })
  }

  if (diagnostic.sessionId && diagnostic.session.isPending) {
    return <main className="sb-page sb-workspace-state" aria-live="polite"><RefreshCcw aria-hidden="true" /><h1>Resuming your setup</h1><p>Loading saved diagnostic answers.</p></main>
  }

  if (session && !preview) {
    return <main className="sb-page sb-onboarding"><section className="sb-card">
      <PageIntro eyebrow="Goal setup · diagnostic" title={session.state === 'paused' ? 'Your diagnostic is paused' : session.state === 'failed' ? 'Your answers are safe' : 'Short adaptive diagnostic'}>
        {session.state === 'paused' ? 'Resume when you are ready, or skip this optional step.' : session.state === 'failed' ? 'Retry from the same saved answers. Nothing needs to be re-entered.' : 'Each saved response and confidence level selects the next question reproducibly.'}
      </PageIntro>
      <div className="sb-diagnostic">
        <div className="sb-diagnostic-status" role="status"><strong>{session.answers.length} {session.answers.length === 1 ? 'answer' : 'answers'} saved on this device’s server</strong><span>State: {session.state}</span></div>
        {!seedResolved && <section className="sb-diagnostic-question" aria-labelledby="sb-seed-recovery-title">
          <span className="sb-kicker">Optional setup</span><h2 id="sb-seed-recovery-title">Save or skip your untrusted {session.setup_inputs.path === 'interview_prep' ? 'questions' : 'notes'}</h2>
          <label>Untrusted seed<textarea value={seed} onChange={(event) => setSeed(event.target.value)} /></label>
          <small>This text is stored verbatim for later review in Imports. It is never evidence, completion, or canonical truth.</small>
          <div><Button tone="secondary" disabled={working} onClick={() => void resolveSeed(true)}>Skip this optional step</Button><Button disabled={working || !seed.trim()} onClick={() => void resolveSeed(false)}>Save untrusted seed</Button></div>
        </section>}
        {session.untrusted_seed_text && <aside className="sb-untrusted-seed"><strong>Untrusted seed · review later in Imports</strong><pre>{session.untrusted_seed_text}</pre><small>Stored verbatim. It is not evidence, completion, or canonical truth.</small></aside>}
        {session.answers.length > 0 && <details className="sb-saved-answers"><summary>Review saved answers</summary><ol>{session.answers.map((saved) => <li key={saved.id}><strong>{saved.question_ref}</strong><p>{saved.answer}</p><small>Confidence: {saved.confidence}</small></li>)}</ol></details>}
        {seedResolved && (session.state === 'in-progress' || session.state === 'resumed') && session.next_question && <div className="sb-diagnostic-question">
          <span className="sb-kicker">Question {session.answers.length + 1}</span><h2>{session.next_question.prompt}</h2>
          <label>Your answer<textarea value={answer} onChange={(event) => setAnswer(event.target.value)} /></label>
          <label>Confidence<select value={confidence} onChange={(event) => setConfidence(event.target.value as DiagnosticConfidence)}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></label>
          <div><Button tone="secondary" disabled={working} onClick={() => void pauseAndExit()}><Pause size={16} /> Pause and exit</Button><Button disabled={working || !answer.trim()} onClick={() => void submitAnswer()}>Save answer <ArrowRight size={16} /></Button></div>
        </div>}
        {seedResolved && (session.state === 'in-progress' || session.state === 'resumed') && !session.next_question && <Button disabled={working} onClick={() => void openPreview(session)}>Continue to roadmap preview <ArrowRight size={16} /></Button>}
        {seedResolved && session.state === 'paused' && <div className="sb-diagnostic-actions"><Button disabled={working} onClick={() => void patchSession('resume')}><Play size={16} /> Resume diagnostic</Button><Button tone="secondary" disabled={working} onClick={() => void patchSession('skip_diagnostic')}>Skip diagnostic</Button><Button tone="quiet" onClick={() => navigate('home')}>Keep paused and exit</Button></div>}
        {seedResolved && session.state === 'failed' && <div className="sb-diagnostic-actions"><p>{session.failure_reference ?? session.failure_code ?? 'The diagnostic service failed after saving your previous answers.'}</p><Button disabled={working} onClick={() => void patchSession('retry')}><RefreshCcw size={16} /> Retry with saved answers</Button><Button tone="secondary" disabled={working} onClick={() => void patchSession('skip_diagnostic')}>Skip diagnostic</Button></div>}
        {seedResolved && session.state === 'skipped' && <Button disabled={working} onClick={() => void openPreview(session)}>Continue to roadmap preview <ArrowRight size={16} /></Button>}
        {seedResolved && (session.state === 'in-progress' || session.state === 'resumed') && <Button className="sb-skip-diagnostic" tone="quiet" disabled={working} onClick={() => void patchSession('skip_diagnostic')}>Skip the rest of this diagnostic</Button>}
        {diagnosticError && <div className="sb-action-error" role="alert"><span>Your saved answers are unchanged. Try the action again.</span></div>}
      </div>
    </section></main>
  }
  return <main className="sb-page sb-onboarding">
    {!preview ? <section className="sb-card">
      <PageIntro eyebrow="Goal setup · 1 of 2" title="Shape your classroom"><span>For experienced backend engineers. Set the target; every inferred state remains editable.</span></PageIntro>
      <div className="sb-form-grid">
        <fieldset><legend>Primary path</legend><div className="sb-segments">{(['Learn', 'Interview Prep'] as const).map(value => <button type="button" key={value} className={path === value ? 'is-selected' : ''} aria-pressed={path === value} onClick={() => setPath(value)}>{value === 'Learn' ? <BookOpen size={18} /> : <MessageSquareText size={18} />}{value}</button>)}</div></fieldset>
        <fieldset className="sb-wide"><legend>{ROLE_LEVEL_HEADING}</legend><small>{ROLE_LEVEL_AUDIENCE_NOTE}</small>
          <label>Target level<select id="sb-onboarding-target-level" aria-describedby="sb-onboarding-target-level-helper sb-onboarding-target-level-description" value={targetLevel} onChange={e => setTargetLevel(e.target.value as typeof targetLevel)}><option value="" /><option value="Mid-level">{ROLE_LEVEL_COPY['Mid-level'].label}</option><option value="Senior">{ROLE_LEVEL_COPY.Senior.label}</option><option value="Staff">{ROLE_LEVEL_COPY.Staff.label}</option></select></label>
          <small id="sb-onboarding-target-level-helper">{ROLE_LEVEL_TITLE_VARIATION_HELPER}</small>
          {targetLevel && <small id="sb-onboarding-target-level-description">{ROLE_LEVEL_COPY[targetLevel].description}</small>}
        </fieldset>
        <label>{path === 'Learn' ? 'Subject' : 'Role'}<input value={subjectOrRole} onChange={(event) => setSubjectOrRole(event.target.value)} /></label>
        <label>Target capability<select aria-describedby="sb-onboarding-target-capability-helper" value={targetCapability} onChange={(event) => setTargetCapability(event.target.value as GoalCreate['target_capability'])}><option value="know">Know</option><option value="understand">Understand</option><option value="choose">Choose</option><option value="implement">Implement</option><option value="diagnose">Diagnose</option><option value="defend">Defend</option></select><small id="sb-onboarding-target-capability-helper">{TARGET_CAPABILITY_HELPER}</small></label>
        <label className="sb-wide">Goal name<input value={goalName} onChange={e => setGoalName(e.target.value)} /></label>
        <fieldset className="sb-wide"><legend>Starting evidence · optional</legend><label className="sb-radio"><input type="radio" name="sb-diagnostic" checked={diagnosticChoice === 'take'} onChange={() => setDiagnosticChoice('take')} /><span><strong>Take a short diagnostic</strong><small>Questions adapt to your saved responses and confidence. This does not mark completion.</small></span></label><label className="sb-radio"><input type="radio" name="sb-diagnostic" checked={diagnosticChoice === 'skip'} onChange={() => setDiagnosticChoice('skip')} /><span><strong>Skip diagnostic</strong><small>Go directly to a conservative roadmap preview without a later forced retake.</small></span></label></fieldset>
        <label className="sb-wide">Optional {path === 'Learn' ? 'notes' : 'questions'} · untrusted seed<textarea value={seed} onChange={e => setSeed(e.target.value)} placeholder={path === 'Learn' ? 'Paste plain text or Markdown notes for later review.' : 'Paste questions you want to review later.'} /><small>Captured verbatim on the local server and visibly marked untrusted until you review it later in Imports. It is never treated as truth or evidence.</small><Button type="button" tone="quiet" onClick={() => setSeed('')}>Skip {path === 'Learn' ? 'notes' : 'questions'}</Button></label>
      </div>{diagnosticError && <div className="sb-action-error" role="alert"><span>Setup was not saved. You can retry without re-entering answers.</span></div>}<footer className="sb-card-footer"><Button tone="quiet" onClick={() => navigate('home')}><ArrowLeft size={16} /> Cancel</Button><Button onClick={() => void beginDiagnostic()} disabled={working || !graphVersion || !goalName.trim() || !subjectOrRole.trim() || !targetLevel}>{working ? 'Saving setup…' : diagnosticChoice === 'take' ? 'Start diagnostic' : 'Skip to roadmap preview'} <ArrowRight size={16} /></Button></footer>
    </section> : <section className="sb-card">
      <PageIntro eyebrow="Goal setup · 2 of 2" title="Create a goal from this roadmap" action={<Button tone="quiet" onClick={() => navigate('home')}><Pause size={16} /> Save and exit</Button>}>
        {persistedPreviewPath} · {persistedPreviewLevel} · inferred states are not completion.
      </PageIntro>
      <div className="sb-preview"><section><header><span>01</span><div><h2>Captured roadmap</h2><small>{orderedPreviewTopics.length} topics · saved on the server</small></div></header><ol>{orderedPreviewTopics.map((topic, topicIndex) => {
        const depthEdit = previewEdits.find((item) => item.entry_type === 'depth' && item.topic_stable_id === topic.stable_id)
        const skipEdit = previewEdits.find((item) => item.entry_type === 'skip' && item.topic_stable_id === topic.stable_id)
        const correctionEdit = previewEdits.find((item) => item.entry_type === 'correction' && item.topic_stable_id === topic.stable_id)
        const skipped = typeof skipEdit?.value.skipped === 'boolean' ? skipEdit.value.skipped : topic.is_skipped
        const depth = typeof depthEdit?.value.depth === 'string' ? depthEdit.value.depth : (topic.depth_override ?? topic.recommended_depth)
        const classification = typeof correctionEdit?.value.classification === 'string' ? correctionEdit.value.classification : topic.classification
        return <li id={`preview-topic-${topic.stable_id}`} key={topic.stable_id} tabIndex={-1} aria-current={jumpedPreviewTopic === topic.stable_id ? 'step' : undefined} className={`${skipped ? 'is-skipped' : ''} ${jumpedPreviewTopic === topic.stable_id ? 'is-current' : ''}`}><span>{topic.title}<small>Recommended: {topic.classification}</small></span><div className="sb-preview-controls"><Button tone="quiet" onClick={() => jumpToPreviewTopic(topic.stable_id)}>Jump</Button><label><span>Knowledge</span><select value={classification} onChange={event => confirmPreviewEdit(`Save ${event.target.value} for ${topic.title}?`, { topic_stable_id: topic.stable_id, entry_type: 'correction', value: { classification: event.target.value }, reason: 'Learner preview correction' })}><option value="likely-known">likely known</option><option value="partial">partial</option><option value="unverified">unverified</option><option value="new">new</option></select></label><label><span>Depth</span><select value={depth} onChange={event => confirmPreviewEdit(`Save ${event.target.value} depth for ${topic.title}?`, { topic_stable_id: topic.stable_id, entry_type: 'depth', value: { depth: event.target.value }, reason: 'Learner preview depth choice' })}>{DEPTHS.map(value => <option key={value}>{value}</option>)}</select><small>Recommended: {topic.recommended_depth}{topic.depth_override ? ` · Your override: ${topic.depth_override}` : ''}</small></label><Button tone="quiet" onClick={() => confirmPreviewEdit(`${skipped ? 'Restore' : 'Skip'} ${topic.title}?`, { topic_stable_id: topic.stable_id, entry_type: 'skip', value: { skipped: !skipped }, reason: 'Learner preview skip choice' })}>{skipped ? 'Restore' : 'Skip'}</Button><div className="sb-order"><button disabled={topicIndex === 0} onClick={() => movePreviewTopic(topicIndex, -1)} aria-label={`Move ${topic.title} earlier`}><ArrowUp size={16} /></button><button disabled={topicIndex === orderedPreviewTopics.length - 1} onClick={() => movePreviewTopic(topicIndex, 1)} aria-label={`Move ${topic.title} later`}><ArrowDown size={16} /></button></div></div></li>
      })}</ol></section></div>
      <footer className="sb-card-footer sb-approval"><span><ShieldCheck size={18} /> {diagnostic.confirm.isError ? 'Goal confirmation failed. Your preview is still saved.' : session ? 'Ready with the curriculum captured when setup began.' : 'No saved preview is available.'}</span><Button disabled={!session || working || orderedPreviewTopics.length === 0} onClick={() => void createWorkspace()}><Check size={17} /> {diagnostic.confirm.isPending ? 'Creating goal…' : 'Create goal from roadmap'}</Button></footer>
    </section>}
  </main>
}

export function Roadmap({ navigate }: PageProps) {
  const workspace = useProfileGoals()
  const goal = workspace.currentGoal
  const roadmap = useRoadmap(goal?.id ?? null, true)
  const [open, setOpen] = useState<ReadonlySet<string>>(() => new Set([CURRENT_LESSON_ID]))
  const toggle = (id: string) => setOpen(current => { const next = new Set(current); next.has(id) ? next.delete(id) : next.add(id); return next })
  const openLesson = (lessonId: string) => {
    if (!goal) return
    workspace.recordNavigation.mutate({ goal, position: lessonId, destination: '/app/topic-studio' }, { onSuccess: () => navigate('topic-studio') })
  }
  const confirmMutation = (message: string, mutate: () => void) => {
    if (window.confirm(message)) mutate()
  }
  const mutationError = roadmap.correction.error ?? roadmap.order.error ?? roadmap.skip.error ?? roadmap.depth.error
  const topics = roadmap.roadmap.data?.topics ?? []

  if (roadmap.roadmap.isPending) {
    return <main className="sb-page sb-workspace-state" aria-live="polite"><RefreshCcw aria-hidden="true" /><h1>Loading your roadmap</h1><p>Fetching the saved projection.</p></main>
  }
  if (!goal || (roadmap.roadmap.isError && !roadmap.roadmap.data)) {
    return <main className="sb-page sb-workspace-state" aria-live="polite"><LockKeyhole aria-hidden="true" /><h1>Your roadmap is unavailable</h1><p>The saved projection could not be loaded.</p><Button onClick={() => { void roadmap.roadmap.refetch(); void roadmap.learningStates.refetch() }}>Retry</Button></main>
  }

  return <main className="sb-page sb-roadmap"><PageIntro eyebrow="Saved personal overlay" title="Your editable roadmap" action={<Button onClick={() => navigate('topic-studio')}>Jump to current <ArrowRight size={16} /></Button>}>
    Jump, skip, reorder, or correct any inferred state. Changes are learner-owned and never claim mastery.
  </PageIntro>
  <div className="sb-roadmap-summary"><span><span className="sb-dot is-qualified" /> Pinned to {goal.graph_version_id}</span><span><span className="sb-dot is-current" /> Current checkpoint</span><span>Projection saved</span></div>
  {roadmap.roadmap.data?.state === 'stale-canonical-version' && <p className="sb-stale-note" role="status">A newer approved curriculum is available. This roadmap remains pinned until you review it.</p>}
  {roadmap.checkpointSaved && <p className="sb-refreshing-note" role="status">Checkpoint saved.</p>}
  {(roadmap.roadmap.isError || roadmap.learningStates.isError) && <div className="sb-action-error" role="alert"><span>The latest roadmap refresh failed. Your last accepted projection is still shown.</span><Button tone="secondary" onClick={() => { void roadmap.roadmap.refetch(); void roadmap.learningStates.refetch() }}>Retry</Button></div>}
  {mutationError && <div className="sb-action-error" role="alert">{mutationError instanceof ApiError ? mutationError.message : 'The roadmap change was rejected.'}</div>}
  <ProposalPanel roadmap={roadmap} />
  {topics.length === 0 && <section className="sb-roadmap-empty" aria-live="polite"><BookOpen aria-hidden="true" /><h2>No roadmap topics are available</h2><p>The approved graph for this goal has no topics to show.</p></section>}
  {topics.length > 0 && <section className="sb-roadmap-list" aria-label="Editable roadmap">{topics.map((topic, index) => {
    const learningState = roadmap.learningStates.data?.find(item => item.topic_stable_id === topic.stable_id)
    const classification = learningState?.corrected_classification ?? topic.classification
    const previous = topics[index - 1]
    const next = topics[index + 1]
    return <div key={topic.stable_id}>{index === 0 && <header className="sb-module-head"><span>01</span><strong>Saved roadmap</strong><small>{topics.length} topics</small></header>}
      <article className={`sb-roadmap-row ${goal.resume_position === topic.stable_id ? 'is-current' : ''} ${topic.is_skipped ? 'is-skipped' : ''}`}>
        <button className="sb-lesson-link" disabled={workspace.recordNavigation.isPending} onClick={() => openLesson(topic.stable_id)} aria-label={`${String(index + 1).padStart(2, '0')} ${topic.title}${topic.is_skipped ? ' · skipped' : ''}`}><span>{String(index + 1).padStart(2, '0')}</span><span><strong>{topic.title}</strong><small>{topic.subject} · capability: {topic.target_capability}{topic.is_skipped ? ' · Skipped' : ''}</small></span></button>
        <button className="sb-customize" aria-expanded={open.has(topic.stable_id)} aria-controls={`sb-controls-${topic.stable_id}`} onClick={() => toggle(topic.stable_id)}><Settings2 size={16} /> Customize</button>
        <div id={`sb-controls-${topic.stable_id}`} className={`sb-roadmap-controls ${open.has(topic.stable_id) ? 'is-open' : ''}`}>
          <label>Depth<select value={topic.depth_override ?? topic.recommended_depth} onChange={event => { const depth = event.target.value; confirmMutation(`Save ${depth} depth for ${topic.title}?`, () => roadmap.depth.mutate({ topic_stable_id: topic.stable_id, depth, reason: 'Learner roadmap choice' })) }}>{DEPTHS.map(value => <option key={value}>{value}</option>)}</select><small>Recommended: {topic.recommended_depth}{topic.depth_override ? ` · Your override: ${topic.depth_override}` : ''}</small></label>
          <label>Knowledge<select value={classification} onChange={event => { const value = event.target.value as LearnerCorrection['classification']; confirmMutation(`Save ${value} for ${topic.title}?`, () => roadmap.correction.mutate({ topic_stable_id: topic.stable_id, classification: value, correction_type: 'correction', reason: 'Learner roadmap correction' })) }}><option value="likely-known">likely known</option><option value="partial">partial</option><option value="unverified">unverified</option><option value="new">new</option></select></label>
          <Button tone="quiet" onClick={() => confirmMutation(`${topic.is_skipped ? 'Restore' : 'Skip'} ${topic.title}?`, () => roadmap.skip.mutate({ topic_stable_id: topic.stable_id, skipped: !topic.is_skipped, reason: 'Learner roadmap choice' }))}>{topic.is_skipped ? 'Restore' : 'Skip'}</Button>
          <div className="sb-order"><button disabled={!previous} onClick={() => previous && confirmMutation(`Move ${topic.title} earlier?`, () => roadmap.order.mutate({ before_topic_id: topic.stable_id, after_topic_id: previous.stable_id, reason: 'Learner roadmap order' }))} aria-label={`Move ${topic.title} earlier`}><ArrowUp size={16} /></button><button disabled={!next} onClick={() => next && confirmMutation(`Move ${topic.title} later?`, () => roadmap.order.mutate({ before_topic_id: next.stable_id, after_topic_id: topic.stable_id, reason: 'Learner roadmap order' }))} aria-label={`Move ${topic.title} later`}><ArrowDown size={16} /></button></div>
        </div>
      </article></div>
  })}</section>}
  </main>
}

function proposalLabel(type: OverlayProposal['proposal_type']) {
  if (type === 'bridge') return 'Bridge proposal'
  return `${type[0]!.toUpperCase()}${type.slice(1)} proposal`
}

function payloadText(value: unknown): string {
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return value.map(payloadText).filter(Boolean).join(', ')
  if (value && typeof value === 'object') return Object.entries(value).map(([key, item]) => `${key.replaceAll('_', ' ')}: ${payloadText(item)}`).join('; ')
  return ''
}

function ProposalPanel({ roadmap }: { roadmap: ReturnType<typeof useRoadmap> }) {
  const [reasons, setReasons] = useState<Record<string, string>>({})
  const proposals = roadmap.proposals.data ?? []
  const decide = (proposal: OverlayProposal, decision: OverlayProposalDecision) => {
    const reason = reasons[proposal.id]?.trim()
    roadmap.decideProposal.mutate({ proposal, input: { decision, ...(reason ? { reason } : {}) } })
  }
  const decisionError = roadmap.decideProposal.error
  const staleError = decisionError instanceof ApiError && decisionError.status === 409

  return <section className="sb-proposals" aria-labelledby="sb-proposals-title">
    <div className="sb-section-title"><div><span className="sb-kicker">Explicit approval required</span><h2 id="sb-proposals-title">Recommendations and bridges</h2></div>{!roadmap.proposals.isPending && !roadmap.proposals.isError && <span>{proposals.length} {proposals.length === 1 ? 'proposal' : 'proposals'}</span>}</div>
    <p className="sb-proposals-intro">These suggestions are annotations only. Your roadmap changes only when you accept a recommendation or add a bridge.</p>
    {roadmap.proposals.isPending && <div className="sb-proposal-state" aria-live="polite"><RefreshCcw aria-hidden="true" /><div><strong>Loading recommendations</strong><p>Fetching proposals without changing your roadmap.</p></div></div>}
    {roadmap.proposals.isError && <div className="sb-action-error" role="alert"><span>Recommendations could not be loaded. Your accepted roadmap is still available below.</span><Button tone="secondary" onClick={() => void roadmap.proposals.refetch()}>Retry</Button></div>}
    {decisionError && <div className="sb-action-error" role="alert"><span>{staleError ? 'This proposal is stale and was not applied. ' : ''}{decisionError instanceof ApiError ? decisionError.message : 'The proposal decision was not saved.'}</span><Button tone="secondary" onClick={() => void roadmap.proposals.refetch()}>Reload proposals</Button></div>}
    {!roadmap.proposals.isPending && !roadmap.proposals.isError && proposals.length === 0 && <div className="sb-proposal-state"><Lightbulb aria-hidden="true" /><div><strong>No recommendations waiting</strong><p>Your current accepted roadmap remains unchanged.</p></div></div>}
    <div className="sb-proposal-list">{proposals.map(proposal => {
      const knownKeys = new Set(['title', 'why', 'explanation', 'reason', 'relationship', 'proposed_placement'])
      const title = payloadText(proposal.payload.title) || proposalLabel(proposal.proposal_type)
      const why = payloadText(proposal.payload.why ?? proposal.payload.explanation ?? proposal.payload.reason)
      const details = Object.entries(proposal.payload).filter(([key, value]) => !knownKeys.has(key) && payloadText(value))
      const pending = proposal.state === 'awaiting-learner-decision'
      return <article key={proposal.id} className={`sb-proposal ${pending ? 'is-pending' : ''}`}>
        <header><div><span className="sb-chip">{proposalLabel(proposal.proposal_type)}</span><h3>{title}</h3></div><span className={`sb-proposal-status is-${proposal.state}`}>{proposal.state.replaceAll('-', ' ')}</span></header>
        {why && <p className="sb-proposal-why"><strong>Why this is suggested</strong>{why}</p>}
        {proposal.proposal_type === 'bridge' && <dl className="sb-proposal-facts">
          <div><dt>Relationship</dt><dd>{payloadText(proposal.payload.relationship) || 'Not specified'}</dd></div>
          <div><dt>Proposed placement</dt><dd>{payloadText(proposal.payload.proposed_placement) || 'Not specified'}</dd></div>
        </dl>}
        {details.length > 0 && <dl className="sb-proposal-facts">{details.map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{payloadText(value)}</dd></div>)}</dl>}
        <small className="sb-proposal-version">Generated against {proposal.generated_against_graph_version_id}{proposal.topic_stable_id ? ` · Topic ${proposal.topic_stable_id}` : ''}{proposal.deduplicated ? ' · Duplicate collapsed' : ''}</small>
        {proposal.state_reason && <p className="sb-proposal-reason" role={proposal.state === 'rejected-stale' ? 'alert' : undefined}><strong>{proposal.state === 'rejected-stale' ? 'Not applied' : 'Decision explanation'}</strong>{proposal.state_reason}</p>}
        {(proposal.decisions?.length ?? 0) > 0 && <details className="sb-proposal-history"><summary>Decision history ({proposal.decisions!.length})</summary><ol>{proposal.decisions!.map(item => <li key={item.id}><strong>{item.decision}</strong>{item.reason && <span> — {item.reason}</span>}<small>{item.decided_at}</small></li>)}</ol></details>}
        {pending && <div className="sb-proposal-decision"><label htmlFor={`proposal-reason-${proposal.id}`}>Optional reason<input id={`proposal-reason-${proposal.id}`} value={reasons[proposal.id] ?? ''} onChange={event => setReasons(current => ({ ...current, [proposal.id]: event.target.value }))} placeholder="Add context for this decision" /></label><div><Button disabled={roadmap.decideProposal.isPending} onClick={() => decide(proposal, proposal.proposal_type === 'bridge' ? 'add' : 'accept')}>{proposal.proposal_type === 'bridge' ? 'Add bridge' : 'Accept'}</Button><Button tone="secondary" disabled={roadmap.decideProposal.isPending} onClick={() => decide(proposal, 'postpone')}>Postpone</Button><Button tone="quiet" disabled={roadmap.decideProposal.isPending} onClick={() => decide(proposal, 'dismiss')}>Dismiss</Button></div><small>Nothing changes until you choose an action.</small></div>}
      </article>
    })}</div>
  </section>
}

function Curriculum({ navigate, close }: PageProps & { close?: () => void }) {
  const workspace = useProfileGoals()
  const goal = workspace.currentGoal
  const roadmap = useRoadmap(goal?.id ?? null)
  const openLesson = (lessonId: string) => {
    if (!goal) return
    workspace.recordNavigation.mutate({ goal, position: lessonId, destination: '/app/topic-studio' }, { onSuccess: () => { navigate('topic-studio'); close?.() } })
  }
  const topics = roadmap.roadmap.data?.topics ?? []
  return <div className="sb-curriculum"><header><div><span className="sb-kicker">Roadmap</span><strong>{topics.length} saved topics</strong></div><Button tone="quiet" onClick={() => navigate('learn-roadmap')}>Edit plan</Button></header><details open><summary><span>01 · Saved roadmap</span><ChevronDown size={16} /></summary>{topics.map(topic => <button key={topic.stable_id} disabled={!goal || workspace.recordNavigation.isPending} className={`${topic.stable_id === goal?.resume_position ? 'is-current' : ''} ${topic.is_skipped ? 'is-skipped' : ''}`} aria-current={topic.stable_id === goal?.resume_position ? 'step' : undefined} aria-label={`${topic.title}${topic.is_skipped ? ' · skipped' : ''}`} onClick={() => openLesson(topic.stable_id)}><span className="sb-mini-check"><Circle size={10} /></span><span><strong>{topic.title}</strong><small>{topic.recommended_depth} · {topic.classification}{topic.is_skipped ? ' · Skipped' : ''}</small></span></button>)}</details></div>
}

function Classroom({ children, navigate }: PageProps & { children: ReactNode }) {
  const [drawer, setDrawer] = useState(false)
  const drawerTriggerRef = useRef<HTMLButtonElement>(null)
  return <div className="sb-classroom"><div className="sb-classroom-main"><div className="sb-classroom-tools"><Button tone="quiet" onClick={() => navigate('learn-roadmap')}><ArrowLeft size={16} /> Roadmap</Button><Dialog.Root open={drawer} onOpenChange={setDrawer}><Dialog.Trigger asChild><Button ref={drawerTriggerRef} tone="quiet" className="sb-curriculum-trigger"><ListTree size={17} /> Course content</Button></Dialog.Trigger><Dialog.Portal><Dialog.Overlay className="sb-overlay" /><Dialog.Content className="sb-drawer" aria-describedby={undefined} onCloseAutoFocus={event => { event.preventDefault(); drawerTriggerRef.current?.focus() }}><Dialog.Title className="sb-sr-only">Course content</Dialog.Title><Dialog.Close className="sb-drawer-close" aria-label="Close course content"><X /></Dialog.Close><Curriculum navigate={navigate} close={() => setDrawer(false)} /></Dialog.Content></Dialog.Portal></Dialog.Root></div>{children}</div><aside className="sb-curriculum-rail" aria-label="Course content"><Curriculum navigate={navigate} /></aside>
  </div>
}

function ClassroomProgress({ navigate, previous, previousTarget, next, nextTarget, onPrevious, onNext }: PageProps & { previous: string; previousTarget?: CorePage | undefined; next: string; nextTarget?: CorePage | undefined; onPrevious?: (() => void) | undefined; onNext?: (() => void) | undefined }) {
  return <nav className="sb-classroom-progress" aria-label="Classroom progression"><button onClick={() => onPrevious ? onPrevious() : previousTarget && navigate(previousTarget)} aria-label={`Previous: ${previous}`}><ArrowLeft size={18} /><span><small>Previous</small><strong>{previous}</strong></span></button><button className="sb-progress-roadmap" onClick={() => navigate('learn-roadmap')}><ListTree size={17} /> Return to roadmap</button><button onClick={() => onNext ? onNext() : nextTarget && navigate(nextTarget)} aria-label={`Next: ${next}`}><span><small>Next</small><strong>{next}</strong></span><ArrowRight size={18} /></button></nav>
}

function TopicLayerTabs({ selected, onSelect }: { selected: TopicLayerName; onSelect: (layer: TopicLayerName) => void }) {
  return <nav className="sb-layer-tabs" aria-label="Topic layers">
    {TOPIC_LAYERS.map(layer => <button key={layer} className={selected === layer ? 'is-active' : ''} aria-current={selected === layer ? 'page' : undefined} onClick={() => onSelect(layer)}>{layer}</button>)}
  </nav>
}

function CheckpointContract({ checkpoint }: { checkpoint: TopicCheckpoint }) {
  const fields = [
    ['Target capability', checkpoint.target_capability],
    ['Expected artifact', checkpoint.expected_artifact],
    ['Constraints', checkpoint.constraints.join(' · ')],
    ['Rubric', checkpoint.rubric.join(' · ')],
    ['Assumptions', checkpoint.assumptions.join(' · ')],
    ['Evidence criterion', checkpoint.evidence_criterion],
    ['Material limitation', checkpoint.limitation],
  ] as const

  return <aside className="sb-checkpoint-contract">
    <strong>Checkpoint · {checkpoint.estimated_minutes} minutes</strong>
    <h3>{checkpoint.scenario}</h3>
    <dl>{fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
  </aside>
}

// Fallback wording pre-approved verbatim in docs/decisions/IDK-003-source-licensing-and-snapshot-policy.md:97.
const SNAPSHOT_NOT_YET_RETRIEVED = 'not yet retrieved — citation references the live source only'

function ArtifactProvenanceDetails({ provenance, isPending, isError, onRetry, snapshotsById }: { provenance: ArtifactProvenanceSummary | undefined; isPending: boolean; isError: boolean; onRetry: () => void; snapshotsById: Map<string, SourceSnapshot> }) {
  const sources = provenance ? [...new Map(provenance.claims.flatMap(claim => claim.citations).map(citation => [citation.source.id, citation.source])).values()] : []
  const unavailableSources = sources.filter(source => source.availability_status !== 'available')
  return <details className="sb-provenance"><summary>About this content</summary>
    {isPending ? <p role="status">Loading provenance…</p>
      : isError ? <div role="alert"><p>Provenance is unavailable.</p><Button tone="quiet" onClick={onRetry}>Retry provenance</Button></div>
        : provenance ? <div>
          {unavailableSources.length > 0 && <aside className="sb-source-warning" role="alert"><AlertTriangle size={18} /><div><strong>Source availability warning</strong><p>{unavailableSources.map(source => `${source.title} is ${source.availability_status}`).join(' · ')}. Last known provenance is retained.</p></div></aside>}
          <dl className="sb-provenance-meta"><div><dt>Generated</dt><dd>{provenance.baked_snapshot.generated_at}</dd></div><div><dt>Provider / model</dt><dd>{provenance.baked_snapshot.provider} / {provenance.baked_snapshot.model}</dd></div><div><dt>Prompt template</dt><dd>{provenance.baked_snapshot.prompt_template_version}</dd></div><div><dt>Contract</dt><dd>{provenance.baked_snapshot.contract_version} · {provenance.baked_snapshot.schema_version}</dd></div></dl>
          {provenance.claims.length === 0 ? <p>No claim-level citations are attached. Routine content remains self-contained.</p>
            : <ol className="sb-claim-list">{provenance.claims.map(claim => <li key={claim.id}><span className="sb-entry-kind">{claim.claim_type}</span><p>{claim.claim_text}</p>{claim.citations.length === 0 ? <small>Routine claim · no citation required</small> : <ul>{claim.citations.map(citation => {
              const snapshot = citation.source_snapshot_id ? snapshotsById.get(citation.source_snapshot_id) : undefined
              return <li key={citation.id}><strong>{citation.source.title}</strong>{citation.locator && <span> · {citation.locator}</span>}<small>{citation.source.publisher ?? 'Publisher unavailable'} · {citation.source.availability_status}</small>
                <dl className="sb-provenance-meta">
                  {citation.source.canonical_url && <div><dt>Canonical URL</dt><dd><a href={citation.source.canonical_url} target="_blank" rel="noreferrer">{citation.source.canonical_url}</a></dd></div>}
                  {citation.source_snapshot_id === null
                    ? <div><dt>Retrieval timestamp</dt><dd>{SNAPSHOT_NOT_YET_RETRIEVED}</dd></div>
                    : snapshot && <div><dt>Retrieval timestamp</dt><dd>{snapshot.retrieved_at}</dd></div>}
                  {snapshot?.version_label && <div><dt>Version label</dt><dd>{snapshot.version_label}</dd></div>}
                </dl>
              </li>
            })}</ul>}</li>)}</ol>}
        </div> : <p>No generated provenance is attached to this authored layer.</p>}
  </details>
}

export function TopicLayerPanel({
  layerName,
  layer,
  checkpointNumber,
  isPending,
  isError,
  onRetry,
  onGenerate,
  onRegenerate,
  actionPending,
  actionError,
  provenance,
  provenancePending = false,
  provenanceError = false,
  onRetryProvenance = () => undefined,
  provenanceSnapshots = new Map<string, SourceSnapshot>(),
  anchorId,
}: {
  layerName: TopicLayerName
  layer: TopicLayerContent | undefined
  checkpointNumber: number
  isPending: boolean
  isError: boolean
  onRetry: () => void
  onGenerate: () => void
  onRegenerate: (artifactId: string) => void
  actionPending: boolean
  actionError: unknown
  provenance?: ArtifactProvenanceSummary | undefined
  provenancePending?: boolean
  provenanceError?: boolean
  onRetryProvenance?: () => void
  provenanceSnapshots?: Map<string, SourceSnapshot>
  anchorId: string | undefined
}) {
  if (isPending) {
    return <section className="sb-layer-state" aria-live="polite"><RefreshCcw /><h2>Loading {layerName}</h2><p>Loading approved topic content.</p></section>
  }
  if (isError) {
    return <section className="sb-layer-state" data-layer-state="unavailable" aria-live="polite"><LockKeyhole /><h2>Topic content unavailable</h2><p>Notes and Help are still available.</p><Button onClick={onRetry}>Retry</Button></section>
  }
  const generation = layer?.generation ?? null
  const hasBody = Boolean(layer?.markdown)
  const stale = layer?.state === 'stale'
  const generating = layer?.state === 'generating' || generation?.status === 'queued' || generation?.status === 'running'
  const failed = generation?.status === 'failed' || generation?.status === 'quarantined'
  if (layer && hasBody && (layer.state === 'ready' || stale || generating || failed)) {
    return <section className="sb-reading" id={anchorId}>
      <span>{String(checkpointNumber).padStart(2, '0')}</span>
      <div>
        {stale && <aside className="sb-artifact-warning" role="status"><RefreshCcw size={18} /><div><strong>Generated before your latest correction or update</strong><p>The existing content remains visible and unchanged. Regenerate only when you choose.</p><Button disabled={actionPending || generating || !layer.artifact_id} onClick={() => layer.artifact_id && onRegenerate(layer.artifact_id)}>{generating ? 'Generating…' : actionPending ? 'Starting…' : 'Regenerate'}</Button></div></aside>}
        {generating && <aside className="sb-artifact-progress" role="status"><RefreshCcw className="sb-spin" size={18} /><div><strong>Generating updated content</strong><p>{stale || layer.markdown ? 'The previous body remains visible until generation succeeds.' : 'This can take a moment.'}</p></div></aside>}
        {failed && <aside className="sb-artifact-warning" role="alert"><LockKeyhole size={18} /><div><strong>Generation did not complete</strong><p>{generation?.failure_reference ?? 'The prior content remains available.'}</p><Button disabled={actionPending || !layer.artifact_id} onClick={() => layer.artifact_id && onRegenerate(layer.artifact_id)}>Retry generation</Button></div></aside>}
        {Boolean(actionError) && <p className="sb-tool-error" role="alert">{providerStartFailure(actionError, 'retry generation')} The visible content was not changed.</p>}
        <h2>{layer.layer}</h2>
        <div className="sb-layer-copy">{layer.markdown}</div>
        {layer.checkpoint && <CheckpointContract checkpoint={layer.checkpoint} />}
        {layer.artifact_id && <ArtifactProvenanceDetails provenance={provenance} isPending={provenancePending} isError={provenanceError} onRetry={onRetryProvenance} snapshotsById={provenanceSnapshots} />}
      </div>
    </section>
  }

  const state = layer?.state ?? 'absent'
  return <section className="sb-layer-state" data-layer-state={state} aria-live="polite">
    {generating ? <RefreshCcw className="sb-spin" /> : failed ? <LockKeyhole /> : <FileText />}
    <h2>{generating ? `Generating ${layerName}` : failed ? `${layerName} generation failed` : `No ${layerName} content yet`}</h2>
    <p>{generating ? 'The requested content is being prepared.' : failed ? generation?.failure_reference ?? 'Nothing partial was published.' : 'Generate content for this approved topic and goal.'}</p>
    {!generating && (failed && layer?.artifact_id ? <Button disabled={actionPending} onClick={() => onRegenerate(layer.artifact_id!)}>Retry generation</Button> : <Button disabled={actionPending} onClick={onGenerate}>{actionPending ? 'Starting…' : `Generate ${layerName}`}</Button>)}
    {Boolean(actionError) && <p className="sb-tool-error" role="alert">{providerStartFailure(actionError, 'retry generation')}</p>}
  </section>
}

function Topic({ navigate }: PageProps) {
  const workspace = useProfileGoals()
  const goal = workspace.currentGoal
  const roadmap = useRoadmap(goal?.id ?? null)
  const [selectedLayer, setSelectedLayer] = useState<TopicLayerName>('Essential')
  const roadmapTopics = (roadmap.roadmap.data?.topics ?? []).filter(topic => !topic.is_skipped)
  const roadmapIds = roadmapTopics.map(topic => topic.stable_id)
  const currentLessonId = goal?.resume_position && roadmapIds.includes(goal.resume_position) ? goal.resume_position : (roadmapIds[0] ?? CURRENT_LESSON_ID)
  const topicContent = useTopicContent(goal?.id ?? null, currentLessonId)
  const projectedTopic = roadmapTopics.find(topic => topic.stable_id === currentLessonId)
  const activeIds = roadmapIds.length ? roadmapIds : [CURRENT_LESSON_ID]
  const currentIndex = Math.max(0, activeIds.indexOf(currentLessonId))
  const previousId = currentIndex > 0 ? activeIds[currentIndex - 1] : null
  const nextId = activeIds[currentIndex + 1]
  const selectLesson = (id: string) => {
    if (!workspace.currentGoal) return
    workspace.recordNavigation.mutate({ goal: workspace.currentGoal, position: id, destination: '/app/topic-studio' }, { onSuccess: () => { window.scrollTo({ top: 0 }) } })
  }
  const activeLayer = topicContent.data?.layers.find(layer => layer.layer === selectedLayer)
  const provenance = useArtifactProvenance(activeLayer?.artifact_id ?? null)
  const sourcesLayer = topicContent.data?.layers.find(layer => layer.layer === 'Sources')
  const sourcesMarkdown = sourcesLayer?.state === 'ready' ? sourcesLayer.markdown : null
  // The Sources layer is itself a generated artifact (IDK-003 §7's "generated content" surface):
  // it has claims/citations behind it, resolved the same way as any other layer's provenance.
  const sourcesProvenance = useArtifactProvenance(sourcesLayer?.artifact_id ?? null)
  const title = projectedTopic?.title ?? currentLessonId
  const previousTitle = roadmapTopics.find(topic => topic.stable_id === previousId)?.title ?? previousId ?? 'Course roadmap'
  const nextTitle = roadmapTopics.find(topic => topic.stable_id === nextId)?.title ?? nextId ?? 'Guided practice'
  return <Classroom navigate={navigate}><article className="sb-topic">
    <PageIntro eyebrow={`Topic Studio · checkpoint ${currentIndex + 1} of ${activeIds.length}`} title={title} action={<div className="sb-topic-actions"><Button onClick={() => document.getElementById('sb-lesson-artifact')?.scrollIntoView({ block: 'start' })}>{currentLessonId === CURRENT_LESSON_ID ? 'Open implementation lab' : 'Open checkpoint'} <ArrowDown size={16} /></Button><Button tone="quiet" onClick={() => document.getElementById('sb-lesson-tools')?.scrollIntoView({ block: 'start' })}>Lesson tools <NotebookPen size={16} /></Button></div>}><span>{projectedTopic?.depth_override ?? projectedTopic?.recommended_depth ?? 'Essential'} · target capability: {projectedTopic?.target_capability ?? 'unverified'}</span></PageIntro>
    <JobConnectionStatus ids={(topicContent.data?.layers ?? []).map(layer => layer.generation?.job_id)} />
    <TopicLayerTabs selected={selectedLayer} onSelect={setSelectedLayer} />
    <TopicLayerPanel layerName={selectedLayer} layer={activeLayer} checkpointNumber={currentIndex + 1} isPending={topicContent.isPending} isError={topicContent.isError} onRetry={() => { void topicContent.refetch() }} onGenerate={() => topicContent.generate.mutate(selectedLayer)} onRegenerate={(artifactId) => topicContent.regenerate.mutate(artifactId)} actionPending={topicContent.generate.isPending || topicContent.regenerate.isPending} actionError={topicContent.generate.error ?? topicContent.regenerate.error} provenance={provenance.data} provenancePending={provenance.isPending} provenanceError={provenance.isError} onRetryProvenance={() => void provenance.refetch()} provenanceSnapshots={provenance.snapshotsById} anchorId={currentLessonId === CURRENT_LESSON_ID ? undefined : 'sb-lesson-artifact'} />
    <HandsOnLab goalId={goal?.id ?? null} topicId={currentLessonId} />
  </article><TopicTools goalId={goal?.id ?? null} topicId={currentLessonId} conversationScope={topicContent.data?.conversation_scope ?? null} sourcesMarkdown={sourcesMarkdown} sourcesProvenance={sourcesLayer?.artifact_id ? sourcesProvenance : null} /><ClassroomProgress navigate={navigate} previous={previousTitle} previousTarget={previousId ? undefined : 'learn-roadmap'} onPrevious={previousId ? () => selectLesson(previousId) : undefined} next={nextTitle} nextTarget={nextId ? undefined : 'practice'} onNext={nextId ? () => selectLesson(nextId) : undefined} /></Classroom>
}

export function TopicTools({ goalId, topicId, conversationScope, sourcesMarkdown, sourcesProvenance }: {
  goalId: string | null
  topicId: string
  conversationScope: string | null
  sourcesMarkdown: string | null
  // IDK-003 §7 names generated content as an attribution surface, and the
  // "Sources" layer this tab renders is a generated artifact like any other
  // (IDK-503 re-run gate 3, blocking finding 2). `null` means that layer has
  // no artifact yet, so there are no citations to attribute.
  sourcesProvenance: ReturnType<typeof useArtifactProvenance> | null
}) {
  const review = useNotebookReview(goalId)
  const tutor = useTopicConversation(goalId, topicId)
  const [tutorDraft, setTutorDraft] = useState('')
  const [entryMarkdown, setEntryMarkdown] = useState('')
  const [responses, setResponses] = useState<Record<string, string>>({})
  const [confidence, setConfidence] = useState<Record<string, 'low' | 'medium' | 'high' | ''>>({})
  const [revealed, setRevealed] = useState<Record<string, ReviewAttempt>>({})
  const entries = review.notebook.data ?? []
  const items = review.reviews.data?.items ?? []
  const saveEntry = () => {
    const markdown = entryMarkdown.trim()
    if (!markdown || !goalId) return
    review.createEntry.mutate({ entry_kind: 'user', markdown, topic_stable_id: topicId }, { onSuccess: () => setEntryMarkdown('') })
  }
  const submitAttempt = (item: ReviewItem) => {
    const response = responses[item.id]?.trim()
    if (!response) return
    const selectedConfidence = confidence[item.id]
    review.attempt.mutate({ itemId: item.id, body: { response, ...(selectedConfidence ? { confidence: selectedConfidence } : {}) } }, {
      onSuccess: (attempt) => setRevealed((current) => ({ ...current, [item.id]: attempt })),
    })
  }
  const sendTutorMessage = () => {
    const message = tutorDraft.trim()
    if (!message || !goalId) return
    tutor.send.mutate(message, { onSuccess: () => setTutorDraft('') })
  }
  return <Tabs.Root id="sb-lesson-tools" defaultValue="notes" className="sb-tools">
    <Tabs.List aria-label="Secondary lesson tools"><Tabs.Trigger value="notes"><NotebookPen size={16} /> Notes</Tabs.Trigger><Tabs.Trigger value="review"><Clock3 size={16} /> Review</Tabs.Trigger><Tabs.Trigger value="resources"><BookOpen size={16} /> Resources</Tabs.Trigger><Tabs.Trigger value="help"><HelpCircle size={16} /> Help</Tabs.Trigger></Tabs.List>
    <Tabs.Content value="notes">
      <div className="sb-tool-heading"><div><strong>Goal notebook</strong><span>Entries are saved to this goal. New entries are linked to this topic.</span></div></div>
      {!goalId ? <div className="sb-empty"><NotebookPen /><strong>Select a goal to use its notebook</strong></div>
        : review.notebook.isPending ? <div className="sb-tool-status" aria-live="polite">Loading notebook…</div>
          : review.notebook.isError ? <div className="sb-tool-status" role="alert">Notebook unavailable. <Button tone="quiet" onClick={() => void review.notebook.refetch()}>Retry</Button></div>
            : <>
              {entries.length === 0 ? <div className="sb-empty sb-empty--compact"><NotebookPen /><strong>No notebook entries yet</strong><span>Save a thought, decision, or question for this goal.</span></div>
                : <ol className="sb-notebook-list">{entries.map((entry) => <li key={entry.id}><header><span className="sb-entry-kind">{entry.entry_kind}</span>{entry.topic_stable_id && <small>Topic · {entry.topic_stable_id}</small>}{entry.evidence_id && <small>Evidence linked</small>}{entry.source_id && <small>Source linked</small>}</header><p>{entry.markdown}</p>{entry.entry_kind === 'user' && <Button tone="quiet" disabled={review.removeEntry.isPending} onClick={() => review.removeEntry.mutate(entry)}>Delete</Button>}</li>)}</ol>}
              <label htmlFor="sb-notebook-entry">Add a user entry</label><textarea id="sb-notebook-entry" value={entryMarkdown} onChange={(event) => setEntryMarkdown(event.target.value)} placeholder="Write Markdown notes for this topic…" />
              {review.createEntry.isError && <p className="sb-tool-error" role="alert">Entry was not saved. Your text is still here.</p>}
              <div className="sb-tool-actions"><Button disabled={!entryMarkdown.trim() || review.createEntry.isPending} onClick={saveEntry}>{review.createEntry.isPending ? 'Saving…' : 'Save entry'}</Button></div>
            </>}
    </Tabs.Content>
    <Tabs.Content value="review">
      <div className="sb-tool-heading"><div><strong>Optional review</strong><span>Recall, explain, or apply before the answer is revealed.</span></div></div>
      {!goalId ? <div className="sb-empty"><Clock3 /><strong>Select a goal to review</strong></div>
        : review.preferences.isPending || review.reviews.isPending ? <div className="sb-tool-status" aria-live="polite">Loading review queue…</div>
          : review.preferences.isError || review.reviews.isError ? <div className="sb-tool-status" role="alert">Review queue unavailable. <Button tone="quiet" onClick={() => { void review.preferences.refetch(); void review.reviews.refetch() }}>Retry</Button></div>
            : !review.preferences.data?.enabled ? <div className="sb-empty sb-empty--compact"><Clock3 /><strong>Review is disabled for this goal</strong><span>You can enable it in Settings. The roadmap remains available.</span></div>
              : items.length === 0 ? <div className="sb-empty sb-empty--compact"><Check /><strong>No reviews due</strong><span>Continue learning or return later. Review never blocks navigation.</span></div>
                : <ol className="sb-review-list">{items.map((item) => {
                  const result = revealed[item.id]
                  const actionable = item.status === 'ready' || item.status === 'due'
                  return <li key={item.id}><header><span className="sb-entry-kind">{item.prompt_type}</span><small>{item.status}</small></header><p className="sb-review-prompt">{item.prompt}</p>{item.context && <p className="sb-review-context">Context: {item.context}</p>}
                    {result ? <section className="sb-review-result" aria-live="polite"><strong>Answer</strong><p>{result.revealed_answer}</p>{result.feedback && <><strong>Feedback</strong><p>{result.feedback}</p></>}{result.correction && <><strong>Correction</strong><p>{result.correction}</p></>}</section>
                      : item.status === 'generation-failed' ? <div className="sb-tool-status" role="status"><strong>This prompt could not be generated.</strong>{item.failure_reference && <span> Reference: {item.failure_reference}.</span>} <span>{item.retryable ? 'The failure is retryable' : 'The failure is recorded'} and the roadmap remains available.</span> <Button tone="quiet" onClick={() => void review.reviews.refetch()}>Refresh queue</Button></div>
                        : !actionable ? <p className="sb-review-context">This item is not currently actionable. It does not block the roadmap or change readiness.</p>
                          : <><label htmlFor={`sb-review-${item.id}`}>Your response</label><textarea id={`sb-review-${item.id}`} value={responses[item.id] ?? ''} onChange={(event) => setResponses((current) => ({ ...current, [item.id]: event.target.value }))} /><label htmlFor={`sb-confidence-${item.id}`}>Confidence · optional</label><select id={`sb-confidence-${item.id}`} value={confidence[item.id] ?? ''} onChange={(event) => setConfidence((current) => ({ ...current, [item.id]: event.target.value as 'low' | 'medium' | 'high' | '' }))}><option value="">Not specified</option><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select><div className="sb-tool-actions"><Button tone="quiet" disabled={review.dismiss.isPending} onClick={() => review.dismiss.mutate(item.id)}>Dismiss</Button><Button disabled={!responses[item.id]?.trim() || review.attempt.isPending} onClick={() => submitAttempt(item)}>{review.attempt.isPending ? 'Submitting…' : 'Submit response'}</Button></div>{review.dismiss.isError && <p className="sb-tool-error" role="alert">The item was not dismissed. You can retry without a readiness penalty.</p>}{review.attempt.isError && <p className="sb-tool-error" role="alert">Response was not submitted. The answer remains hidden.</p>}</>}
                  </li>
                })}</ol>}
    </Tabs.Content>
    <Tabs.Content value="resources">{sourcesMarkdown
      ? <div className="sb-tool-content"><FileText size={18} /><div><strong>Approved sources</strong><p>{sourcesMarkdown}</p>{sourcesProvenance && <ArtifactProvenanceDetails provenance={sourcesProvenance.data} isPending={sourcesProvenance.isPending} isError={sourcesProvenance.isError} onRetry={() => void sourcesProvenance.refetch()} snapshotsById={sourcesProvenance.snapshotsById} />}</div></div>
      : <div className="sb-empty"><FileText /><strong>No approved sources yet</strong><span>Check the Sources layer after content is published.</span></div>}
    </Tabs.Content>
    <Tabs.Content value="help"><div className="sb-tool-heading" data-conversation-scope={conversationScope ?? undefined}><div><strong>{conversationScope ? 'Conversation attached to this topic' : 'Topic conversation unavailable'}</strong><span>{conversationScope ? 'Messages and tutor replies stay with this topic.' : 'Retry the topic content request to restore it.'}</span></div></div>
      {!conversationScope ? <div className="sb-empty"><MessageSquareText /><strong>Topic conversation unavailable</strong></div>
        : tutor.conversation.isPending ? <div className="sb-tool-status" aria-live="polite">Loading conversation…</div>
          : tutor.conversation.isError ? <div className="sb-tool-status" role="alert">Conversation unavailable. <Button tone="quiet" onClick={() => void tutor.conversation.refetch()}>Retry</Button></div>
            : <><ol className="sb-notebook-list" aria-label="Topic conversation">{(tutor.conversation.data ?? []).map(turn => <li key={turn.id}><header><span className="sb-entry-kind">{turn.role}</span></header><p>{turn.body}</p></li>)}</ol>
              {(tutor.conversation.data ?? []).length === 0 && <div className="sb-empty sb-empty--compact"><MessageSquareText /><strong>No messages yet</strong><span>Ask about this topic when you want focused help.</span></div>}
              <label htmlFor="sb-tutor-message">Ask the topic tutor</label><textarea id="sb-tutor-message" value={tutorDraft} onChange={event => setTutorDraft(event.target.value)} placeholder="Ask a question about this topic…" />
              {tutor.send.isError && <p className="sb-tool-error" role="alert">{providerStartFailure(tutor.send.error, 'retry the tutor message')}</p>}
              {tutor.activeJob.data && <p className="sb-tool-status" role="status">Tutor request {tutor.activeJob.data.status}{tutor.activeJob.data.status === 'failed' && tutor.activeJob.data.retryable ? ' · retry available from Jobs' : ''}.</p>}
              <div className="sb-tool-actions"><Button disabled={!tutorDraft.trim() || tutor.send.isPending} onClick={sendTutorMessage}>{tutor.send.isPending ? 'Sending…' : 'Send question'}</Button></div></>}
    </Tabs.Content>
  </Tabs.Root>
}

const INTERVIEW_ROLE_LEVELS: readonly { label: string; level: InterviewLevel }[] = [
  { label: ROLE_LEVEL_COPY['Mid-level'].label, level: 'Mid-level' },
  { label: ROLE_LEVEL_COPY.Senior.label, level: 'Senior' },
  { label: ROLE_LEVEL_COPY.Staff.label, level: 'Staff' },
]

function BundleEditor({ interview, goalId, selectedBundleId, onSelect }: {
  interview: ReturnType<typeof useInterview>
  goalId: string | null
  selectedBundleId: string | null
  onSelect: (bundleId: string | null) => void
}) {
  const bundles = interview.bundles.data ?? []
  const selected = bundles.find(bundle => bundle.id === selectedBundleId) ?? bundles.find(bundle => bundle.goal_id === goalId) ?? bundles[0] ?? null
  const [name, setName] = useState('')
  const [level, setLevel] = useState<InterviewLevel>('Senior')
  // IDK-004 §4 also governs this "recommended" bundle's creation: no level is preselected here either.
  const [createLevel, setCreateLevel] = useState<InterviewLevel | ''>('')

  useEffect(() => {
    if (!selected) return
    setName(selected.name)
    setLevel(selected.target_level)
    if (selectedBundleId !== selected.id) onSelect(selected.id)
  }, [onSelect, selected, selectedBundleId])

  const createBundle = () => {
    if (!createLevel) return
    interview.create.mutate({
      ...(goalId ? { goal_id: goalId } : {}),
      name: `${createLevel} backend interview`,
      generic_role: 'Backend Engineer',
      target_level: createLevel,
      origin: 'recommended',
      items: [
        { subject: 'technical', question: 'Explain a production trade-off and its failure boundary.', position: 0, is_optional: false, included: true },
        { subject: 'behavioral', question: 'Tell me about a difficult trade-off.', position: 1, is_optional: true, included: true },
        { subject: 'leadership', question: 'How did you align a team?', position: 2, is_optional: true, included: true },
      ],
    }, { onSuccess: bundle => onSelect(bundle.id) })
  }

  const save = () => {
    if (!selected || !name.trim()) return
    interview.update.mutate({ bundle: selected, patch: { name: name.trim(), generic_role: 'Backend Engineer', target_level: level } })
  }
  const toggle = (item: InterviewBundle['items'][number]) => {
    if (!selected || !item.is_optional) return
    interview.update.mutate({ bundle: selected, patch: { items: [{ id: item.id, included: !item.included }] } })
  }
  const actionError = interview.create.error ?? interview.update.error ?? interview.copy.error ?? interview.remove.error

  return <section className="sb-bundle-workspace" aria-labelledby="sb-bundle-title" data-interview-state={interview.bundles.isPending && !interview.bundles.data ? 'loading' : interview.bundles.isError && !interview.bundles.data ? 'unavailable' : bundles.length === 0 ? 'empty' : interview.bundles.isRefetchError ? 'unavailable' : 'ready'}>
    <header><div><span className="sb-kicker">Editable preparation</span><h2 id="sb-bundle-title">Interview bundles</h2><p>Role and level stay generic. Optional subjects never change the technical scope.</p></div>{bundles.length > 0 && <span>{bundles.length} {bundles.length === 1 ? 'bundle' : 'bundles'}</span>}</header>
    {interview.bundles.isPending && !interview.bundles.data ? <div className="sb-interview-status" aria-live="polite"><RefreshCcw /><strong>Loading interview bundles</strong><span>Your preparation choices remain independently reachable.</span></div>
      : interview.bundles.isError && !interview.bundles.data ? <div className="sb-interview-status" role="alert"><AlertTriangle /><strong>Interview bundles are unavailable</strong><span>No replacement bundle was synthesized.</span><Button tone="secondary" onClick={() => void interview.bundles.refetch()}>Retry bundles</Button></div>
        : bundles.length === 0 ? <div className="sb-interview-status"><HelpCircle /><strong>No interview bundle yet</strong><span>Create an editable recommended bundle. A Learn goal is not required.</span>
          <label>Role and level<select aria-label="Role and level" aria-describedby="sb-bundle-create-level-helper sb-bundle-create-level-description" value={createLevel} onChange={event => setCreateLevel(event.target.value as InterviewLevel | '')}><option value="" />{INTERVIEW_ROLE_LEVELS.map(option => <option key={option.level} value={option.level}>{option.label}</option>)}</select><small id="sb-bundle-create-level-helper">{ROLE_LEVEL_TITLE_VARIATION_HELPER}</small>{createLevel && <small id="sb-bundle-create-level-description">{ROLE_LEVEL_COPY[createLevel].description}</small>}</label>
          <Button disabled={interview.create.isPending || !createLevel} onClick={createBundle}>{interview.create.isPending ? 'Creating…' : 'Create recommended bundle'}</Button>
        </div>
          : selected && <div className="sb-bundle-editor">
            <nav aria-label="Interview bundles">{bundles.map(bundle => <button key={bundle.id} className={bundle.id === selected.id ? 'is-selected' : ''} aria-pressed={bundle.id === selected.id} onClick={() => onSelect(bundle.id)}><strong>{bundle.name}</strong><small>{INTERVIEW_ROLE_LEVELS.find(option => option.level === bundle.target_level)?.label ?? `${bundle.target_level} backend engineer`}</small></button>)}</nav>
            <form onSubmit={event => { event.preventDefault(); save() }}>
              <label>Bundle name<input value={name} onChange={event => setName(event.target.value)} /></label>
              <label>Role and level<select aria-label="Role and level" aria-describedby="sb-bundle-level-helper sb-bundle-level-description" value={level} onChange={event => setLevel(event.target.value as InterviewLevel)}>{INTERVIEW_ROLE_LEVELS.map(option => <option key={option.level} value={option.level}>{option.label}</option>)}</select><small id="sb-bundle-level-helper">{ROLE_LEVEL_TITLE_VARIATION_HELPER}</small><small id="sb-bundle-level-description">{ROLE_LEVEL_COPY[level].description}</small></label>
              <fieldset><legend>Subjects</legend>{selected.items.slice().sort((a, b) => a.position - b.position).map(item => <label key={item.id} className={!item.is_optional ? 'is-required' : ''}><input type="checkbox" checked={item.included} disabled={!item.is_optional || interview.update.isPending} onChange={() => toggle(item)} /><span><strong>{item.subject}</strong><small>{item.is_optional ? 'Optional · independently included' : 'Technical · required'}</small></span></label>)}</fieldset>
              <footer><Button type="submit" disabled={!name.trim() || interview.update.isPending}>{interview.update.isPending ? 'Saving…' : 'Save bundle'}</Button><Button type="button" tone="secondary" disabled={interview.copy.isPending} onClick={() => interview.copy.mutate({ bundleId: selected.id, body: { name: `${selected.name} copy` } }, { onSuccess: bundle => onSelect(bundle.id) })}>Copy bundle</Button><Button type="button" tone="quiet" disabled={interview.remove.isPending} onClick={() => { if (window.confirm(`Delete ${selected.name}?`)) interview.remove.mutate(selected, { onSuccess: () => onSelect(null) }) }}>Delete</Button></footer>
            </form>
          </div>}
    {interview.bundles.isFetching && interview.bundles.data && <p className="sb-refreshing-note" role="status">Refreshing interview bundles…</p>}
    {interview.bundles.isRefetchError && interview.bundles.data && <div className="sb-action-error" role="alert"><span>Interview bundles could not be refreshed. Previously loaded material is still available.</span><Button tone="secondary" onClick={() => void interview.bundles.refetch()}>Retry refresh</Button></div>}
    {actionError && <div className="sb-action-error" role="alert"><span>The bundle change was not saved. Previously loaded material is still available.</span><Button tone="secondary" onClick={() => void interview.refreshBundles()}>Reload bundles</Button></div>}
  </section>
}

function RefresherContent({ goalId, items, query }: { goalId: string | null; items: InterviewRefresher[]; query: ReturnType<typeof useInterview>['refreshers'] }) {
  const state = !goalId ? 'empty' : query.isPending && !query.data ? 'loading' : query.isError && !query.data ? 'unavailable' : items.length === 0 ? 'empty' : query.isRefetchError ? 'unavailable' : items.some(item => item.state === 'stale') ? 'stale' : items.every(item => item.state === 'unavailable') ? 'unavailable' : 'ready'
  return <section id="sb-interview-mode-content" className="sb-mode-content" tabIndex={-1} aria-labelledby="sb-refresher-content-title" data-interview-state={state}>
    <header><span className="sb-kicker">Source-linked review</span><h3 id="sb-refresher-content-title">Refresher artifacts</h3></header>
    {!goalId ? <div className="sb-interview-status"><BookOpen /><strong>No current goal selected</strong><span>Select any goal to see its refresher artifacts. Learn completion is never required.</span></div>
      : query.isPending && !query.data ? <div className="sb-interview-status" aria-live="polite"><RefreshCcw /><strong>Loading refresher artifacts</strong></div>
        : query.isError && !query.data ? <div className="sb-interview-status" role="alert"><AlertTriangle /><strong>Refresher artifacts are unavailable</strong><span>No source or evidence-gap link was fabricated.</span><Button tone="secondary" onClick={() => void query.refetch()}>Retry refreshers</Button></div>
          : items.length === 0 ? <div className="sb-interview-status"><BookOpen /><strong>No refresher artifacts yet</strong><span>Your bundle remains available while generated content is absent.</span></div>
            : <div className="sb-refresher-list">{items.map(item => <article key={item.artifact_id} data-artifact-state={item.state}>
              <header><span>{item.state}</span><h4>{item.subject}</h4></header>
              {item.content && <p className="sb-refresher-content">{item.content}</p>}
              <dl><dt>Layer</dt><dd>{item.layer}</dd><dt>Source</dt><dd>{item.source_title ?? item.source_ref ?? 'Unavailable'}</dd><dt>Evidence gap</dt><dd>{item.evidence_gap ?? item.evidence_gap_ref ?? 'Unavailable'}</dd></dl>
              {item.state === 'stale' && <p className="sb-stale-note" role="status">Stale · this artifact predates the current evidence snapshot.</p>}
              {item.state === 'unavailable' && <p className="sb-tool-error" role="status">Unavailable · authored bundle material is retained.</p>}
            </article>)}</div>}
    {query.isFetching && query.data && <p className="sb-refreshing-note" role="status">Refreshing artifacts…</p>}
    {query.isRefetchError && query.data && <div className="sb-action-error" role="alert"><span>Refresher artifacts could not be refreshed. Previously loaded material is still available.</span><Button tone="secondary" onClick={() => void query.refetch()}>Retry refresh</Button></div>}
  </section>
}

function QuestionsContent({ goalId, bundleId, items, query, navigate }: { goalId: string | null; bundleId: string | null; items: InterviewQuestion[]; query: ReturnType<typeof useInterview>['questions']; navigate: Navigate }) {
  const [selected, setSelected] = useState<string[]>([])
  const visible = bundleId ? items.filter(item => item.bundle_id === bundleId) : []
  const state = !goalId || !bundleId ? 'empty' : query.isPending && !query.data ? 'loading' : query.isError && !query.data ? 'unavailable' : visible.length === 0 ? 'empty' : query.isRefetchError ? 'unavailable' : 'ready'
  const toggle = (id: string) => setSelected(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id])
  useEffect(() => setSelected([]), [bundleId])
  return <section id="sb-interview-mode-content" className="sb-mode-content" tabIndex={-1} aria-labelledby="sb-questions-content-title" data-interview-state={state}>
    <header><span className="sb-kicker">Bundle-scoped selection</span><h3 id="sb-questions-content-title">Questions</h3><p>Select prompts, then choose where to answer them. Evaluation appears only after entering the appropriate run.</p></header>
    {!goalId ? <div className="sb-interview-status"><HelpCircle /><strong>No current goal selected</strong><span>Select any goal to load its questions. Learn completion is never required.</span></div>
      : !bundleId ? <div className="sb-interview-status"><HelpCircle /><strong>No bundle selected</strong><span>Create or select an interview bundle to choose questions.</span></div>
        : query.isPending && !query.data ? <div className="sb-interview-status" aria-live="polite"><RefreshCcw /><strong>Loading questions</strong></div>
          : query.isError && !query.data ? <div className="sb-interview-status" role="alert"><AlertTriangle /><strong>Questions are unavailable</strong><span>No feedback or evaluation was produced.</span><Button tone="secondary" onClick={() => void query.refetch()}>Retry questions</Button></div>
            : visible.length === 0 ? <div className="sb-interview-status"><HelpCircle /><strong>No questions in this bundle</strong><span>Edit the bundle or choose another one.</span></div>
              : <fieldset className="sb-question-selection"><legend>Select questions</legend>{visible.slice().sort((a, b) => a.position - b.position).map(item => <label key={item.id}><input type="checkbox" checked={selected.includes(item.id)} onChange={() => toggle(item.id)} /><span><strong>{item.subject}</strong>{item.question}</span></label>)}</fieldset>}
    {visible.length > 0 && <footer className="sb-question-handoff"><span>{selected.length} selected</span><Button disabled={selected.length === 0} onClick={() => { const item = visible.find(value => value.id === selected[0]); if (item) navigate('practice', undefined, { bundleId: item.bundle_id, bundleItemId: item.id }) }}>Open Guided practice <ArrowRight size={16} /></Button><Button tone="secondary" disabled={selected.length === 0} onClick={() => { const item = visible.find(value => value.id === selected[0]); if (item) navigate('mock', undefined, { bundleId: item.bundle_id, bundleItemId: item.id }) }}>Open Mock interview <ArrowRight size={16} /></Button></footer>}
    {query.isRefetchError && query.data && <div className="sb-action-error" role="alert"><span>Questions could not be refreshed. Previously loaded selections remain available.</span><Button tone="secondary" onClick={() => void query.refetch()}>Retry refresh</Button></div>}
  </section>
}

export function InterviewHub({ navigate, mode, selection }: PageProps & { mode?: InterviewMode }) {
  const workspace = useProfileGoals()
  const interview = useInterview(workspace.currentGoal?.id ?? null)
  const [selectedBundleId, setSelectedBundleId] = useState<string | null>(null)
  const choices = [
    { title: 'Refresher', text: 'Review the message delivery contract and evidence gaps.', meta: 'Focused reading', Icon: BookOpen, target: 'topic-studio', lessonId: 'delivery-contract', hubMode: 'refresher' as InterviewMode },
    { title: 'Question bank', text: 'Choose a scenario without completing the Learn path.', meta: 'Select included questions', Icon: HelpCircle, target: 'practice', hubMode: 'questions' as InterviewMode },
    { title: 'Guided practice', text: 'Request a hint, submit, inspect feedback, and repair.', meta: 'Hints on request', Icon: Code2, target: 'practice' },
    { title: 'Mock interview', text: selection?.runId ? 'Resume the exact server-saved draft.' : 'Answer without hints, rubrics, or evaluation until completion.', meta: selection?.runId ? 'Paused' : 'Neutral while active', Icon: MessageSquareText, target: 'mock' },
  ]
  const activeChoice = mode ? choices.find((choice) => choice.hubMode === mode) : undefined
  const openChoice = (choice: (typeof choices)[number], asMode?: InterviewMode) => {
    if (asMode) { navigate('interview-hub', asMode); return }
    if (choice.lessonId && workspace.currentGoal) {
      workspace.recordNavigation.mutate({ goal: workspace.currentGoal, position: choice.lessonId, destination: '/app/topic-studio' }, { onSuccess: () => navigate(choice.target) })
      return
    }
    navigate(choice.target, undefined, choice.title === 'Mock interview' && selection?.runId ? { runId: selection.runId } : undefined)
  }
  const openModeContent = () => document.getElementById('sb-interview-mode-content')?.focus()
  const bundleState = interview.bundles.isPending && !interview.bundles.data ? 'loading' : interview.bundles.isError && !interview.bundles.data ? 'unavailable' : interview.bundles.data?.length === 0 ? 'empty' : interview.bundles.isRefetchError ? 'unavailable' : 'ready'
  const rootState = (() => {
    if (!mode || bundleState !== 'ready') return bundleState
    if (!workspace.currentGoal) return 'empty'
    const query = mode === 'refresher' ? interview.refreshers : interview.questions
    if (query.isPending && !query.data) return 'loading'
    if (query.isError && !query.data || query.isRefetchError) return 'unavailable'
    if (!query.data?.length) return 'empty'
    if (mode === 'refresher' && interview.refreshers.data?.some(item => item.state === 'stale')) return 'stale'
    if (mode === 'refresher' && interview.refreshers.data?.every(item => item.state === 'unavailable')) return 'unavailable'
    return 'ready'
  })()
  const currentLevel = workspace.currentGoal?.target_level
  const eyebrow = currentLevel ? `Interview prep · ${ROLE_LEVEL_COPY[currentLevel].label}` : 'Interview prep'
  return <main className="sb-page sb-interview" data-interview-state={rootState}><PageIntro eyebrow={eyebrow} title="Choose the mode you need"><span>Generic product-company context; no company-specific or hiring-readiness claim.</span></PageIntro>
    {activeChoice && <section className="sb-mode-detail" data-testid="interview-mode-detail" data-mode={mode}>
      <span>{activeChoice.meta}</span>
      <activeChoice.Icon />
      <h2>{activeChoice.title}</h2>
      <p>{activeChoice.text}</p>
      <div>
        <Button onClick={openModeContent}>Open {activeChoice.title} <ArrowRight size={16} /></Button>
        <Button tone="quiet" onClick={() => navigate('interview-hub')}><ArrowLeft size={16} /> Back to Interview prep</Button>
      </div>
    </section>}
    <section className="sb-mode-list">{choices.map((choice, i) => <article key={choice.title} aria-current={choice.hubMode && choice.hubMode === mode ? 'true' : undefined}><span>0{i + 1}</span><choice.Icon /><div><h2>{choice.title}</h2><p>{choice.text}</p><small>{choice.meta}</small></div><button aria-label={`Open ${choice.title}`} onClick={() => openChoice(choice, choice.hubMode)}><ArrowRight /></button></article>)}</section><aside className="sb-neutral"><ShieldCheck /><div><strong>Mock stays evaluation-free while active</strong><p>Only one question and the response field are shown. Consolidated evidence appears after an explicit terminal completion.</p></div></aside>
    {mode === 'refresher' && <RefresherContent goalId={workspace.currentGoal?.id ?? null} items={interview.refreshers.data ?? []} query={interview.refreshers} />}
    {mode === 'questions' && <QuestionsContent goalId={workspace.currentGoal?.id ?? null} bundleId={selectedBundleId ?? interview.bundles.data?.find(bundle => bundle.goal_id === workspace.currentGoal?.id)?.id ?? interview.bundles.data?.[0]?.id ?? null} items={interview.questions.data ?? []} query={interview.questions} navigate={navigate} />}
    <BundleEditor interview={interview} goalId={workspace.currentGoal?.id ?? null} selectedBundleId={selectedBundleId} onSelect={setSelectedBundleId} />
  </main>
}

export function Practice({ navigate, selection }: PageProps) {
  const workspace = useProfileGoals()
  const goal = workspace.currentGoal
  const interview = useInterview(goal?.id ?? null)
  const question = interview.questions.data?.find(item => item.included && item.id === selection?.bundleItemId && item.bundle_id === selection.bundleId)
  const testScenario = typeof window === 'undefined' ? undefined : (window as Window & {
    __YUNO_E2E_PRACTICE__?: { rubric_id: string; rubric_version: string }
  }).__YUNO_E2E_PRACTICE__
  const [runId, setRunId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [repairing, setRepairing] = useState(false)
  const started = useRef(false)
  const practice = usePracticeRun(runId, setRunId)
  useEffect(() => {
    if (started.current || !goal || !question || !testScenario) return
    started.current = true
    practice.create.mutate({
      mode: 'Practice',
      goal_id: goal.id,
      bundle_id: question.bundle_id,
      bundle_item_id: question.id,
      rubric_id: testScenario.rubric_id,
      rubric_version: testScenario.rubric_version,
      requested_capability: goal.target_capability,
    })
  }, [goal, question, practice.create, testScenario])
  const run = practice.run.data
  const latestAnswer = [...(run?.turns ?? [])].reverse().find(turn => turn.kind === 'answer')
  const result = run?.results.at(-1)
  const earlier = (run?.turns ?? []).filter(turn => turn.kind === 'answer' && turn.id !== latestAnswer?.id).reverse()
  const hint = [...(run?.turns ?? [])].reverse().find(turn => turn.kind === 'hint')
  const practiceJob = practice.activeJob.data
  const evaluating = run?.state === 'submitted' || run?.state === 'evaluating' || practice.submit.isPending || ['queued', 'running', 'cancel-requested'].includes(practiceJob?.status ?? '')
  const providerError = practice.submit.error ?? practice.retry.error
  const submit = async () => {
    await practice.submit.mutateAsync(draft)
    setRepairing(false)
  }
  if (workspace.goals.isPending || interview.questions.isPending || practice.create.isPending || (runId && practice.run.isPending)) return <Classroom navigate={navigate}><article className="sb-practice" aria-live="polite"><PageIntro eyebrow="Guided practice" title="Loading a practice scenario"><span>Fetching your server-backed interview run.</span></PageIntro></article></Classroom>
  if (!goal || !question) return <Classroom navigate={navigate}><article className="sb-practice"><PageIntro eyebrow="Guided practice" title="No practice question is selected"><span>Choose an included question from Interview prep before starting.</span></PageIntro><Button onClick={() => navigate('interview-hub', 'questions')}>Choose questions</Button></article></Classroom>
  if (!testScenario) return <Classroom navigate={navigate}><article className="sb-practice"><PageIntro eyebrow="Guided practice unavailable" title="Approved practice content is not available yet"><span>Practice runs require an approved scenario and rubric configuration. No placeholder rubric or evaluative content is used.</span></PageIntro><Button onClick={() => navigate('interview-hub', 'questions')}>Review selected questions</Button></article></Classroom>
  if (practice.create.isError || practice.run.isError) return <Classroom navigate={navigate}><article className="sb-practice" role="alert"><PageIntro eyebrow="Guided practice unavailable" title="The run could not be loaded"><span>No feedback is inferred while the server read is unavailable.</span></PageIntro><Button onClick={() => { started.current = false; setRunId(null); void interview.questions.refetch() }}>Retry</Button></article></Classroom>
  return <Classroom navigate={navigate}><article className="sb-practice" aria-live="polite"><PageIntro eyebrow={`Guided practice · ${run?.state ?? 'ready'}`} title="Reason through the failure boundary"><span>Hints appear only when requested. Feedback appears only after submission and server evaluation.</span></PageIntro><JobConnectionStatus ids={[practiceJob?.job_id, run?.active_job_id]} /><ProviderJobStatus label="Practice evaluation" job={practiceJob} retry={() => practice.retry.mutate()} retrying={practice.retry.isPending} /><section className="sb-question"><span>Scenario</span><h2>{run?.question ?? question.question}</h2></section>
    {!result || repairing ? <section className="sb-answer"><label htmlFor="sb-answer">Your response</label><textarea id="sb-answer" value={draft} onChange={event => setDraft(event.target.value)} disabled={evaluating} placeholder="Name the failure window, protection, and cost…" /><div><Button tone="quiet" onClick={() => practice.hint.mutate()} disabled={!run || Boolean(hint) || practice.hint.isPending || evaluating}><Lightbulb size={16} /> {hint ? 'Hint requested' : 'Request hint'}</Button><Button disabled={!run || !draft.trim() || evaluating} onClick={() => void submit()}>{evaluating ? 'Evaluating…' : 'Submit response'}</Button></div>{hint && <aside className="sb-hint"><Lightbulb /><div><strong>Requested hint</strong><p>{hint.body}</p></div></aside>}{evaluating && <aside className="sb-neutral"><Clock3 /><div><strong>Evaluating submitted attempt</strong><p>The submitted answer is preserved. Feedback remains hidden until evaluation finishes.</p><Button tone="quiet" onClick={() => practice.cancel.mutate()} disabled={practice.cancel.isPending || practiceJob?.status === 'cancel-requested'}>{practice.cancel.isPending || practiceJob?.status === 'cancel-requested' ? 'Cancellation requested…' : 'Cancel evaluation'}</Button></div></aside>}</section> : <section className="sb-feedback"><span className="sb-kicker">Post-submission review</span><h2>{result.feedback}</h2><div className="sb-feedback-grid"><section><h3><Check size={17} /> Facts and corrections</h3>{result.facts.map(item => <p key={item}>{item}</p>)}</section><section><h3><Settings2 size={17} /> Trade-offs to defend</h3>{result.trade_offs.map(item => <p key={item}>{item}</p>)}</section></div>{result.dimensions.length > 0 && <section className="sb-practice-dimensions"><h3>Rubric dimensions</h3>{result.dimensions.map(dimension => <article key={dimension.dimension_id}><strong>{dimension.name} · {dimension.outcome}</strong><p>{dimension.rationale}</p></article>)}</section>}{result.cross_question_candidate && <aside className="sb-neutral"><HelpCircle /><div><strong>Adaptive follow-up</strong><p>{result.cross_question_candidate}</p></div></aside>}<details><summary>Your submitted response <ChevronDown /></summary><p>{latestAnswer?.body}</p></details><footer><Button tone="secondary" onClick={() => { setDraft(latestAnswer?.body ?? ''); setRepairing(true) }}><RefreshCcw size={16} /> Repair answer</Button><Button onClick={() => navigate('interview-hub', 'questions')}>Choose another question <ArrowRight size={16} /></Button></footer></section>}
    {providerError && <aside className="sb-neutral" role="alert"><AlertTriangle /><div><strong>Practice evaluation did not start</strong><p>{providerStartFailure(providerError, 'retry the evaluation')}</p></div></aside>}{run?.state === 'failed-recoverable' && !practiceJob && <aside className="sb-neutral" role="alert"><AlertTriangle /><div><strong>Evaluation failed</strong><p>Your submitted attempt is preserved. Retry resumes evaluation without resubmitting it.</p><Button onClick={() => practice.retry.mutate()} disabled={!run.retryable || practice.retry.isPending}>Retry evaluation</Button></div></aside>}{earlier.length > 0 && <details className="sb-history"><summary>Earlier attempts ({earlier.length}) <ChevronDown /></summary>{earlier.map(item => <article key={item.id}><strong>Attempt {item.turn_number}</strong><p>{item.body}</p></article>)}</details>}</article><ClassroomProgress navigate={navigate} previous="Topic studio" previousTarget="topic-studio" next="Interview prep" nextTarget="interview-hub" /></Classroom>
}

export function Mock({ navigate, selection }: PageProps) {
  const workspace = useProfileGoals()
  const [runId, setRunId] = useState<string | null>(selection?.runId ?? null)
  const [draft, setDraft] = useState('')
  const [exitOpen, setExitOpen] = useState(false)
  const [completeOpen, setCompleteOpen] = useState(false)
  const exitRef = useRef<HTMLButtonElement>(null)
  const completeRef = useRef<HTMLButtonElement>(null)
  const completeKey = useRef(crypto.randomUUID())
  const initializedRun = useRef<string | null>(null)
  const started = useRef(false)
  const mock = useMockRun(runId, id => { setRunId(id); navigate('mock', undefined, { runId: id }) })
  const goal = workspace.currentGoal
  useEffect(() => {
    if (started.current || runId || !goal || !selection?.bundleId || !selection.bundleItemId) return
    started.current = true
    mock.create.mutate({ mode: 'Mock', goal_id: goal.id, bundle_id: selection.bundleId, bundle_item_id: selection.bundleItemId, requested_capability: goal.target_capability })
  }, [goal, mock.create, runId, selection?.bundleId, selection?.bundleItemId])
  const run = mock.run.data
  useEffect(() => {
    if (!run || (initializedRun.current === run.id && run.state !== 'paused')) return
    initializedRun.current = run.id
    setDraft(run.draft)
  }, [run])
  useEffect(() => {
    if (run?.state === 'paused' && !mock.resume.isPending) mock.resume.mutate()
  }, [mock.resume, run?.state])
  const questions = run?.turns.filter(turn => turn.kind === 'question' || turn.kind === 'follow-up') ?? []
  const currentQuestion = questions.at(-1)
  const mockJob = mock.activeJob.data
  const busy = run?.state === 'follow-up' || run?.state === 'completing' || mock.answer.isPending || mock.complete.isPending || ['queued', 'running', 'cancel-requested'].includes(mockJob?.status ?? '')
  const providerError = mock.answer.error ?? mock.complete.error ?? mock.retry.error
  if (!runId && (!goal || !selection?.bundleId || !selection.bundleItemId)) return <main className="sb-mock-complete"><div><MessageSquareText /></div><span className="sb-eyebrow">Mock unavailable</span><h1>Choose a Mock question first.</h1><p>No placeholder question or evaluative content is shown.</p><Button onClick={() => navigate('interview-hub', 'questions')}>Choose questions <ArrowRight size={16} /></Button></main>
  if (mock.create.isPending || (runId && mock.run.isPending)) return <main className="sb-mock-complete" aria-live="polite"><div><Clock3 /></div><span className="sb-eyebrow">Mock interview</span><h1>Loading your focused session.</h1></main>
  if (mock.create.isError || mock.run.isError || !run) return <main className="sb-mock-complete" role="alert"><div><AlertTriangle /></div><span className="sb-eyebrow">Mock unavailable</span><h1>The interview run could not be loaded.</h1><p>No feedback or replacement question was inferred.</p><Button onClick={() => void mock.run.refetch()}>Retry</Button></main>
  if (run.state === 'completed') return <main className="sb-mock-complete"><div><Check /></div><span className="sb-eyebrow">Interview complete</span><h1>The active session has ended.</h1><p>Your server-stored transcript is fixed and cannot accept more answers.</p><ProviderJobStatus label="Mock final evaluation" job={mockJob} /><Button onClick={() => navigate('reports', undefined, { runId: run.id })}>Open report <ArrowRight size={16} /></Button></main>
  return <main className="sb-mock" data-mock-state={run.state}><header><div><span /> Mock {run.state}</div><strong>Question {currentQuestion?.turn_number ?? questions.length}</strong><button ref={exitRef} disabled={busy} onClick={() => setExitOpen(true)}><Pause size={16} /> Save &amp; exit</button></header><section><JobConnectionStatus ids={[mockJob?.job_id, run.active_job_id]} /><ProviderJobStatus label={run.state === 'completing' ? 'Mock final evaluation' : 'Mock next turn'} job={mockJob} retry={() => mock.retry.mutate()} retrying={mock.retry.isPending} /><div className="sb-interviewer"><span>{String(currentQuestion?.turn_number ?? questions.length).padStart(2, '0')}</span><div><strong>Interviewer</strong><small>{currentQuestion?.kind === 'follow-up' ? 'Adaptive follow-up' : 'Current question'}</small></div></div><h1>{currentQuestion?.body ?? run.question}</h1><label htmlFor="sb-mock-answer">Your response</label><textarea id="sb-mock-answer" value={draft} onChange={event => { setDraft(event.target.value); completeKey.current = crypto.randomUUID() }} disabled={busy} placeholder="Answer with your decision and reasoning…" autoFocus /><footer><span>Your draft is stored exactly when you save or complete. No hints or evaluation are available during the run.</span><div><Button tone="secondary" disabled={!draft.trim() || busy} onClick={() => mock.answer.mutate(draft, { onSuccess: () => { setDraft(''); completeKey.current = crypto.randomUUID() } })}>{busy && run.state === 'follow-up' ? 'Generating next question…' : 'Submit answer'}</Button><Button ref={completeRef} disabled={!draft.trim() || busy} onClick={() => setCompleteOpen(true)}>Complete interview</Button></div></footer>{providerError && <aside className="sb-neutral" role="alert"><AlertTriangle /><div><strong>The Mock provider action did not start</strong><p>{providerStartFailure(providerError, 'retry the Mock action')}</p></div></aside>}{(mock.pause.isError || mock.resume.isError || run.state === 'failed-recoverable' && !mockJob) && <aside className="sb-neutral" role="alert"><AlertTriangle /><div><strong>The Mock action could not be completed</strong><p>Your fixed transcript remains unchanged. Retry from the current server state.</p>{run.state === 'failed-recoverable' ? <Button tone="quiet" disabled={mock.retry.isPending} onClick={() => mock.retry.mutate()}>Retry Mock operation</Button> : <Button tone="quiet" onClick={() => void mock.run.refetch()}>Reload session</Button>}</div></aside>}</section>
    <Confirm open={exitOpen} onOpenChange={setExitOpen} title="Pause this mock?" description="Your exact response draft will be retained by the server. Resume it from Interview prep." trigger={exitRef} cancel="Keep answering" action="Save & exit" onAction={() => { void mock.pause.mutateAsync(draft).then(saved => navigate('interview-hub', undefined, { runId: saved.id })) }} />
    <Confirm open={completeOpen} onOpenChange={setCompleteOpen} title="Complete the interview?" description="This terminal action ends the active session. The transcript cannot accept more answers afterward." trigger={completeRef} cancel="Return to answer" action="Complete interview" onAction={() => { mock.complete.mutate({ draft, idempotencyKey: completeKey.current }) }} />
  </main>
}

function Confirm({ open, onOpenChange, title, description, trigger, cancel, action, onAction }: { open: boolean; onOpenChange: (x: boolean) => void; title: string; description: string; trigger: React.RefObject<HTMLButtonElement | null>; cancel: string; action: string; onAction: () => void }) {
  return <AlertDialog.Root open={open} onOpenChange={onOpenChange}><AlertDialog.Portal><AlertDialog.Overlay className="sb-overlay" /><AlertDialog.Content className="sb-alert" onCloseAutoFocus={e => { e.preventDefault(); trigger.current?.focus() }}><AlertDialog.Title>{title}</AlertDialog.Title><AlertDialog.Description>{description}</AlertDialog.Description><div><AlertDialog.Cancel asChild><Button tone="secondary">{cancel}</Button></AlertDialog.Cancel><AlertDialog.Action asChild><Button onClick={onAction}>{action}</Button></AlertDialog.Action></div></AlertDialog.Content></AlertDialog.Portal></AlertDialog.Root>
}

export function Reports({ navigate, selection }: PageProps) {
  const { currentGoal } = useProfileGoals()
  const runId = selection?.runId ?? null
  const mock = useMockRun(runId, () => undefined)
  const report = useMockReport(runId, mock.run.data?.state === 'completed')
  const learning = useGoalEvidenceReport(currentGoal?.id ?? null)
  const ownerSettings = useOwnerSettings()
  const evidence = learning.evidence.data ?? []
  const unavailableSources = [...new Map(learning.entries.flatMap(entry => entry.sources.unavailable).map(source => [source.id, source])).values()]
  const reportData = report.data
  const assessment = reportData?.assessment
  const reportPending = Boolean(runId) && (mock.run.isPending || (mock.run.data?.state === 'completed' && report.isPending))
  const nextAction = !assessment
    ? { eyebrow: reportPending ? 'Report loading' : 'Report unavailable', title: reportPending ? 'Loading the terminal report' : 'Complete the Mock interview before opening its report', detail: reportPending ? 'No conclusion is inferred until the terminal report read completes.' : 'No evaluative content is available for an active, paused, completing, failed, or unknown run.', label: selection?.runId ? 'Return to mock' : 'Choose a Mock question', target: selection?.runId ? 'mock' as CorePage : 'interview-hub' as CorePage }
    : learning.evidence.isError
      ? { eyebrow: 'Evidence unavailable', title: 'Retry the learning evidence region', detail: 'No learning conclusion is inferred while the evidence list is unavailable. Interview report content remains usable.', label: 'Retry evidence', target: 'reports' as CorePage }
      : learning.evidence.isPending
        ? { eyebrow: 'Learning evidence', title: 'Learning evidence is loading', detail: 'No learning conclusion is inferred before the server read completes. Interview report content remains usable.', label: 'Review interview prep', target: 'interview-hub' as CorePage }
      : evidence.length === 0
      ? { eyebrow: 'Next action', title: 'Review your current lab artifact', detail: 'This report contains no submitted lab evidence. Return to the implementation lab to inspect the draft; static browser checks do not submit evidence.', label: 'Open topic studio', target: 'topic-studio' as CorePage }
      : { eyebrow: 'Next action', title: 'Test the decision in guided practice', detail: `You have ${evidence.length} submitted lab evidence ${evidence.length === 1 ? 'entry' : 'entries'}. Practice attempts are stored by the server and remain available from Guided practice.`, label: 'Start guided practice', target: 'practice' as CorePage }
  const latestDispute = assessment?.disputes.at(-1)
  return <main className="sb-page sb-reports"><PageIntro eyebrow="Evidence report · mock interview" title={assessment?.feedback ?? (reportPending ? 'Loading the terminal Mock report.' : 'No terminal mock report is available.')} action={<Button tone="quiet" onClick={() => navigate('interview-hub')}><ArrowLeft size={16} /> Interview prep</Button>}><span>{assessment ? 'Conclusion from the immutable terminal assessment.' : 'No evaluation is shown before explicit terminal completion.'}</span></PageIntro>
    <section className="sb-report-next" aria-labelledby="sb-report-next-title"><div><span className="sb-eyebrow">{nextAction.eyebrow}</span><h2 id="sb-report-next-title">{assessment?.revision_invitation ?? nextAction.title}</h2><p>{nextAction.detail}</p></div>{learning.evidence.isError && assessment ? <Button onClick={() => void learning.evidence.refetch()}>{nextAction.label} <RefreshCcw size={16} /></Button> : <Button onClick={() => navigate(nextAction.target, undefined, selection?.runId ? { runId: selection.runId } : undefined)}>{nextAction.label} <ArrowRight size={16} /></Button>}</section>
    {!assessment && !reportPending && <section className="sb-report-gate" role="status"><span>Report gate</span><strong>{mock.run.data?.state === 'completing' ? 'Evaluating' : 'Unavailable'}</strong><p>The run is not terminal or its terminal assessment is unavailable. No evaluative payload is displayed.</p>{mock.run.data?.state === 'completed' && report.isError && <Button tone="secondary" onClick={() => void report.refetch()}>Retry report</Button>}</section>}
    {assessment && <><section className="sb-report-gate"><span>Assumptions</span><h2>Assumptions</h2>{assessment.assumptions.length ? <ul>{assessment.assumptions.map(item => <li key={item}>{item}</li>)}</ul> : <p>No assumptions recorded.</p>}</section>
    <section className="sb-report-grid"><article><h2>Facts and corrections</h2>{assessment.facts.length ? assessment.facts.map(item => <p key={item}><Check size={16} /> {item}</p>) : <p>No facts or corrections recorded.</p>}</article><article><h2>Trade-offs</h2>{assessment.trade_offs.length ? assessment.trade_offs.map(item => <p key={item}><Settings2 size={16} /> {item}</p>) : <p>No trade-offs recorded.</p>}</article></section>
    <section className="sb-report-gate"><span>Rubric dimensions</span><h2>Rubric dimensions</h2>{assessment.dimensions.length ? assessment.dimensions.map(dimension => <article key={dimension.dimension_id}><strong>{dimension.dimension_id} · {dimension.outcome}</strong><p>{dimension.rationale}</p></article>) : <p>No rubric dimensions recorded.</p>}</section>
    <section className="sb-report-gate"><span>Ambiguity</span><h2>Ambiguity</h2>{assessment.ambiguities.length ? <ul>{assessment.ambiguities.map(item => <li key={item}>{item}</li>)}</ul> : <p>No unresolved ambiguity recorded.</p>}</section>
    <details className="sb-report-detail" open><summary>Interview transcript <ChevronDown /></summary><div><section><h2>Interview transcript</h2>{reportData!.transcript.map(turn => <article key={turn.id}><span>{turn.kind === 'answer' ? 'You' : 'Interviewer'}</span><p>{turn.body}</p></article>)}</section></div></details>
    <details className="sb-report-detail" open><summary>Provenance <ChevronDown /></summary><div><aside><h2>Provenance</h2><dl><dt>Assessment</dt><dd>{assessment.id}</dd><dt>Method</dt><dd>{assessment.evaluation_method}</dd><dt>Citations</dt><dd>{assessment.citations.join(', ') || 'None'}</dd><dt>Provenance refs</dt><dd>{assessment.provenance_refs.join(', ') || 'None'}</dd><dt>Limitations</dt><dd>{assessment.limitation_labels.join(', ') || 'None'}</dd></dl></aside></div></details>
    <section className="sb-report-gate"><span>Correction and dispute</span><h2>{latestDispute ? 'Assessment dispute recorded' : 'Something about this assessment is wrong?'}</h2><p>The original assessment remains immutable.</p>{latestDispute && !latestDispute.reevaluation ? <Button tone="secondary" disabled={learning.reevaluate.isPending} onClick={() => learning.reevaluate.mutate({ assessmentId: assessment.id, disputeId: latestDispute.id })}>Request re-evaluation</Button> : <Button tone="secondary" disabled={Boolean(latestDispute) || learning.dispute.isPending} onClick={() => learning.dispute.mutate({ assessmentId: assessment.id, reason: 'The learner requested correction and re-evaluation.' })}>{latestDispute ? latestDispute.reevaluation ? `Re-evaluation ${latestDispute.reevaluation.status}` : 'Dispute recorded' : 'Record dispute'}</Button>}{(learning.dispute.isError || learning.reevaluate.isError) && <p role="alert">The request was not saved. The assessment remains unchanged.</p>}</section></>}
    {unavailableSources.length > 0 && <aside className="sb-neutral" role="alert"><AlertTriangle /><div><strong>Tombstoned source warning: cited source withdrawn or unavailable</strong><p>{unavailableSources.map(source => source.title).join(', ')} remains named in provenance history; it has not silently disappeared.</p></div></aside>}
    <details className="sb-report-detail"><summary>Submitted lab evidence ({evidence.length}) <ChevronDown /></summary><div className="sb-evidence-history">{learning.evidence.isError ? <ReportRegionFailure label="Evidence" retry={() => void learning.evidence.refetch()} /> : learning.evidence.isPending ? <p>Loading submitted lab evidence…</p> : learning.entries.length ? learning.entries.map(entry => <article key={entry.evidence.id}><strong>{entry.evidence.summary}</strong><p>{entry.evidence.evidence_type} · {entry.evidence.capability} · {entry.evidence.origin}</p>{entry.detail.isError ? <ReportRegionFailure label={`Evidence ${entry.evidence.id} detail`} retry={() => void entry.detail.refetch()} /> : entry.detail.isPending ? <p>Loading evidence detail…</p> : entry.detail.data ? <dl><dt>Content version</dt><dd>{entry.detail.data.content_version ?? 'Tombstoned'}</dd><dt>Transfer lineage</dt><dd>{entry.detail.data.transfers.length ? entry.detail.data.transfers.map(item => `${item.classification} → ${item.target_goal_id}`).join(', ') : 'None'}</dd></dl> : null}{entry.assessment.isError ? <ReportRegionFailure label={`Evidence ${entry.evidence.id} assessment`} retry={() => void entry.assessment.refetch()} /> : entry.assessment.isPending ? <p>Loading assessment…</p> : entry.assessment.data ? <section><h3>{entry.assessment.data.feedback}</h3><p>Assessment state: {entry.assessment.data.state}</p>{entry.assessment.data.ambiguities.length > 0 && <p>Ambiguities: {entry.assessment.data.ambiguities.join('; ')}. Unresolved ambiguity carries no readiness penalty.</p>}</section> : <p>No assessment attached.</p>}<ReportAssessmentHistory entry={entry} />{entry.sources.isError ? <ReportRegionFailure label={`Evidence ${entry.evidence.id} cited sources`} retry={() => void entry.sources.refetch()} /> : entry.sources.isPending ? <p>Loading cited sources…</p> : entry.sources.data.length > 0 ? <div><span>Sources:</span><ul>{entry.sources.data.map(source => <li key={source.id}>{source.title} ({source.availability_status}){source.canonical_url && <> · <a href={source.canonical_url} target="_blank" rel="noreferrer">{source.canonical_url}</a></>}</li>)}</ul></div> : null}</article>) : <p>No submitted lab evidence.</p>}</div></details>
    <ReportProgressDisclosure progress={learning.progress} display={ownerSettings.settings.data?.progress_display ?? null} settings={ownerSettings.settings} />
  </main>
}

type ReportEntry = ReturnType<typeof useGoalEvidenceReport>['entries'][number]
function ReportAssessmentHistory({ entry }: { entry: ReportEntry }) {
  const history = entry.assessmentHistory
  if (history.isError) return <ReportRegionFailure label={`Evidence ${entry.evidence.id} assessment history`} retry={() => void history.refetch()} />
  if (history.isPending) return <p>Loading assessment history…</p>
  if (!history.data.length) return <p>No assessment history available.</p>
  return <details className="sb-report-assessment-history"><summary>Assessment history ({history.data.length}) <ChevronDown /></summary><div>{history.data.map((revision, index) => <article key={revision.id}><span>{revision.created_at} · {revision.state}{index === 0 ? ' · current' : ''}</span><strong>{revision.feedback}</strong><p>{revision.predecessor_assessment_id ? `Predecessor: ${revision.predecessor_assessment_id}` : 'Original assessment'}</p><h4>Rubric</h4>{revision.dimensions.length ? <ul>{revision.dimensions.map(dimension => <li key={`${revision.id}-${dimension.dimension_id}`}><strong>{dimension.dimension_id} · {dimension.outcome}</strong><p>{dimension.rationale}</p></li>)}</ul> : <p>No rubric dimensions recorded.</p>}<h4>Disputes and re-evaluation</h4>{revision.disputes.length ? <ul>{revision.disputes.map(dispute => <li key={dispute.id}><strong>{dispute.status}</strong> · {dispute.reason}{dispute.reevaluation ? ` · Re-evaluation ${dispute.reevaluation.status}` : ''}</li>)}</ul> : <p>No disputes recorded.</p>}</article>)}</div></details>
}

type ReportProgressQuery = ReturnType<typeof useGoalEvidenceReport>['progress']
type ReportSettingsQuery = ReturnType<typeof useOwnerSettings>['settings']
function ReportProgressDisclosure({ progress, display, settings }: { progress: ReportProgressQuery; display: 'simple' | 'detailed' | null; settings: ReportSettingsQuery }) {
  return <details className="sb-report-detail" data-progress-display={display ?? 'loading'}><summary>Learning progress and evidence links <ChevronDown /></summary><div className="sb-evidence-history">{settings.isError ? <ReportRegionFailure label="Progress display preference" retry={() => void settings.refetch()} /> : display === null ? <p>Loading progress display preference…</p> : progress.isError ? <ReportRegionFailure label="Learning progress" retry={() => void progress.refetch()} /> : progress.data ? (['coverage', 'proficiency', 'retention', 'readiness'] as const).map(key => <article key={key}><strong>{key} · {progress.data![key].classification}</strong>{display === 'detailed' && <><p>{progress.data![key].definition}</p><p>Uncertainty: {progress.data![key].uncertainty}</p><p>Evidence: {progress.data![key].supporting_evidence_refs.join(', ') || 'None'}</p></>}</article>) : <p>Loading learning progress…</p>}</div></details>
}

function ReportRegionFailure({ label, retry }: { label: string; retry: () => void }) {
  return <section className="sb-neutral" role="alert"><div><p>{label} could not be loaded. The rest of the report remains available.</p><Button tone="secondary" onClick={retry}>Retry {label.toLowerCase()}</Button></div></section>
}

export function CorePageView({ page, navigate, mode, selection }: { page: CorePage; navigate: Navigate; mode?: InterviewMode; selection?: InterviewSelection }) {
  let content: ReactNode
  switch (page) {
    case 'home': content = <Home navigate={navigate} />; break
    case 'onboarding': content = <Onboarding navigate={navigate} />; break
    case 'learn-roadmap': content = <Roadmap navigate={navigate} />; break
    case 'topic-studio': content = <Topic navigate={navigate} />; break
    case 'interview-hub': content = <InterviewHub navigate={navigate} {...(mode ? { mode } : {})} {...(selection ? { selection } : {})} />; break
    case 'practice': content = <Practice navigate={navigate} {...(selection ? { selection } : {})} />; break
    case 'mock': content = <Mock navigate={navigate} {...(selection ? { selection } : {})} />; break
    case 'reports': content = <Reports navigate={navigate} {...(selection ? { selection } : {})} />; break
  }
  return <div className={`sb-core sb-page-${page}`}>{content}</div>
}

export default CorePageView
