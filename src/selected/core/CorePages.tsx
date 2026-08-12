import { forwardRef, useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import * as AlertDialog from '@radix-ui/react-alert-dialog'
import * as Dialog from '@radix-ui/react-dialog'
import * as Tabs from '@radix-ui/react-tabs'
import {
  Archive, ArrowDown, ArrowLeft, ArrowRight, ArrowUp, BookOpen, Check, ChevronDown, Circle,
  Clock3, Code2, FileText, HelpCircle, History, Lightbulb, ListTree, MessageSquareText,
  LockKeyhole, NotebookPen, Pause, Play, RefreshCcw, RotateCcw, Settings2, ShieldCheck, X,
} from 'lucide-react'
import {
  ALL_LESSONS, CURRICULUM_MODULES, CURRENT_LESSON_ID, FIXTURE_REPORT,
  MOCK_CURRENT_QUESTION, PRACTICE_QUESTIONS, SIMULATION_LIMITATION,
  type Depth, type Lesson,
} from '../../shared/model'
import { currentPracticeQuestion, useLearningState } from '../../shared/state'
import { ApiError, canonicalVersionsQueryOptions } from '../../shared/api/queries'
import { goalDestination, resumePage, useProfileGoals } from '../../shared/use-profile-goals'
import type { GoalCreate, GoalWorkspace } from '../../shared/api/profile-goals'
import { useDiagnostic, type DiagnosticConfidence, type DiagnosticPreviewEdit, type DiagnosticSetup } from '../../shared/use-diagnostic'
import { useRoadmap } from '../../shared/use-roadmap'
import {
  TOPIC_LAYERS,
  type TopicCheckpoint,
  type TopicLayerContent,
  type TopicLayerName,
} from '../../shared/api/learning-content'
import { useTopicContent } from '../../shared/use-topic-content'
import type { LearnerCorrection, OverlayProposal, OverlayProposalDecision } from '../../shared/api/roadmap'
import type { InterviewMode } from '../app-model'
import './core.css'

export type CorePage = 'home' | 'onboarding' | 'learn-roadmap' | 'topic-studio' | 'interview-hub' | 'practice' | 'mock' | 'reports'

type Navigate = (page: CorePage | string, mode?: InterviewMode) => void
type PageProps = { navigate: Navigate }
const DEPTHS: readonly Depth[] = ['Essential', 'Implementation', 'Production', 'Interview']
const LESSONS = ALL_LESSONS as readonly Lesson[]

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
  const resumeTitle = currentGoal?.resume_position ? LESSONS.find((lesson) => lesson.id === currentGoal.resume_position)?.title ?? currentGoal.resume_position : null
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
  const [targetLevel, setTargetLevel] = useState<GoalCreate['target_level']>('Senior')
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
    if (!graphVersion) return
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
        <label>Target level<select value={targetLevel} onChange={e => setTargetLevel(e.target.value as typeof targetLevel)}><option>Mid-level</option><option>Senior</option><option>Staff</option></select><small>Yuno’s MVP curriculum is for experienced backend engineers and does not include a beginner track.</small></label>
        <label>{path === 'Learn' ? 'Subject' : 'Role'}<input value={subjectOrRole} onChange={(event) => setSubjectOrRole(event.target.value)} /></label>
        <label>Target capability<select value={targetCapability} onChange={(event) => setTargetCapability(event.target.value as GoalCreate['target_capability'])}><option value="know">Know</option><option value="understand">Understand</option><option value="choose">Choose</option><option value="implement">Implement</option><option value="diagnose">Diagnose</option><option value="defend">Defend</option></select></label>
        <label className="sb-wide">Goal name<input value={goalName} onChange={e => setGoalName(e.target.value)} /></label>
        <fieldset className="sb-wide"><legend>Starting evidence · optional</legend><label className="sb-radio"><input type="radio" name="sb-diagnostic" checked={diagnosticChoice === 'take'} onChange={() => setDiagnosticChoice('take')} /><span><strong>Take a short diagnostic</strong><small>Questions adapt to your saved responses and confidence. This does not mark completion.</small></span></label><label className="sb-radio"><input type="radio" name="sb-diagnostic" checked={diagnosticChoice === 'skip'} onChange={() => setDiagnosticChoice('skip')} /><span><strong>Skip diagnostic</strong><small>Go directly to a conservative roadmap preview without a later forced retake.</small></span></label></fieldset>
        <label className="sb-wide">Optional {path === 'Learn' ? 'notes' : 'questions'} · untrusted seed<textarea value={seed} onChange={e => setSeed(e.target.value)} placeholder={path === 'Learn' ? 'Paste plain text or Markdown notes for later review.' : 'Paste questions you want to review later.'} /><small>Captured verbatim on the local server and visibly marked untrusted until you review it later in Imports. It is never treated as truth or evidence.</small><Button type="button" tone="quiet" onClick={() => setSeed('')}>Skip {path === 'Learn' ? 'notes' : 'questions'}</Button></label>
      </div>{diagnosticError && <div className="sb-action-error" role="alert"><span>Setup was not saved. You can retry without re-entering answers.</span></div>}<footer className="sb-card-footer"><Button tone="quiet" onClick={() => navigate('home')}><ArrowLeft size={16} /> Cancel</Button><Button onClick={() => void beginDiagnostic()} disabled={working || !graphVersion || !goalName.trim() || !subjectOrRole.trim()}>{working ? 'Saving setup…' : diagnosticChoice === 'take' ? 'Start diagnostic' : 'Skip to roadmap preview'} <ArrowRight size={16} /></Button></footer>
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

function TopicLayerPanel({
  layerName,
  layer,
  checkpointNumber,
  isPending,
  isError,
  onRetry,
  anchorId,
}: {
  layerName: TopicLayerName
  layer: TopicLayerContent | undefined
  checkpointNumber: number
  isPending: boolean
  isError: boolean
  onRetry: () => void
  anchorId: string | undefined
}) {
  if (isPending) {
    return <section className="sb-layer-state" aria-live="polite"><RefreshCcw /><h2>Loading {layerName}</h2><p>Loading approved topic content.</p></section>
  }
  if (isError) {
    return <section className="sb-layer-state" data-layer-state="unavailable" aria-live="polite"><LockKeyhole /><h2>Topic content unavailable</h2><p>Notes and Help are still available.</p><Button onClick={onRetry}>Retry</Button></section>
  }
  if (layer?.state === 'ready') {
    return <section className="sb-reading" id={anchorId}>
      <span>{String(checkpointNumber).padStart(2, '0')}</span>
      <div>
        <h2>{layer.layer}</h2>
        <div className="sb-layer-copy">{layer.markdown}</div>
        {layer.checkpoint && <CheckpointContract checkpoint={layer.checkpoint} />}
      </div>
    </section>
  }

  const state = layer?.state ?? 'empty'
  const stale = state === 'stale'
  return <section className="sb-layer-state" data-layer-state={state} aria-live="polite">
    <FileText />
    <h2>{stale ? `${layerName} is out of date` : `No ${layerName} content yet`}</h2>
    <p>{stale ? 'This layer needs to be regenerated before you use it.' : 'No content has been approved for this layer.'}</p>
  </section>
}

function Topic({ navigate }: PageProps) {
  const { state, dispatch } = useLearningState()
  const workspace = useProfileGoals()
  const goal = workspace.currentGoal
  const roadmap = useRoadmap(goal?.id ?? null)
  const [selectedLayer, setSelectedLayer] = useState<TopicLayerName>('Essential')
  const roadmapTopics = (roadmap.roadmap.data?.topics ?? []).filter(topic => !topic.is_skipped)
  const roadmapIds = roadmapTopics.map(topic => topic.stable_id)
  const currentLessonId = goal?.resume_position && roadmapIds.includes(goal.resume_position) ? goal.resume_position : (roadmapIds[0] ?? CURRENT_LESSON_ID)
  const topicContent = useTopicContent(goal?.id ?? null, currentLessonId)
  const projectedTopic = roadmapTopics.find(topic => topic.stable_id === currentLessonId)
  const fixtureLesson = LESSONS.find(lesson => lesson.id === currentLessonId)
  const activeIds = roadmapIds.length ? roadmapIds : [CURRENT_LESSON_ID]
  const currentIndex = Math.max(0, activeIds.indexOf(currentLessonId))
  const previousId = currentIndex > 0 ? activeIds[currentIndex - 1] : null
  const nextId = activeIds[currentIndex + 1]
  const selectLesson = (id: string) => {
    if (!workspace.currentGoal) return
    workspace.recordNavigation.mutate({ goal: workspace.currentGoal, position: id, destination: '/app/topic-studio' }, { onSuccess: () => { window.scrollTo({ top: 0 }) } })
  }
  const activeLayer = topicContent.data?.layers.find(layer => layer.layer === selectedLayer)
  const sourcesLayer = topicContent.data?.layers.find(layer => layer.layer === 'Sources')
  const sourcesMarkdown = sourcesLayer?.state === 'ready' ? sourcesLayer.markdown : null
  const title = projectedTopic?.title ?? fixtureLesson?.title ?? currentLessonId
  const previousTitle = roadmapTopics.find(topic => topic.stable_id === previousId)?.title ?? previousId ?? 'Course roadmap'
  const nextTitle = roadmapTopics.find(topic => topic.stable_id === nextId)?.title ?? nextId ?? 'Guided practice'
  return <Classroom navigate={navigate}><article className="sb-topic">
    <PageIntro eyebrow={`Topic Studio · checkpoint ${currentIndex + 1} of ${activeIds.length}`} title={title} action={<div className="sb-topic-actions"><Button onClick={() => document.getElementById('sb-lesson-artifact')?.scrollIntoView({ block: 'start' })}>{currentLessonId === CURRENT_LESSON_ID ? 'Open implementation lab' : 'Open checkpoint'} <ArrowDown size={16} /></Button><Button tone="quiet" onClick={() => document.getElementById('sb-lesson-tools')?.scrollIntoView({ block: 'start' })}>Lesson tools <NotebookPen size={16} /></Button></div>}><span>{projectedTopic?.depth_override ?? projectedTopic?.recommended_depth ?? 'Essential'} · target capability: {projectedTopic?.target_capability ?? 'unverified'}</span></PageIntro>
    <TopicLayerTabs selected={selectedLayer} onSelect={setSelectedLayer} />
    <TopicLayerPanel layerName={selectedLayer} layer={activeLayer} checkpointNumber={currentIndex + 1} isPending={topicContent.isPending} isError={topicContent.isError} onRetry={() => { void topicContent.refetch() }} anchorId={currentLessonId === CURRENT_LESSON_ID ? undefined : 'sb-lesson-artifact'} />
    {currentLessonId === CURRENT_LESSON_ID ? <section className="sb-code" id="sb-lesson-artifact"><header><span><Code2 size={17} /> ReservationService.java</span><Button tone="quiet" onClick={() => dispatch({ type: 'RESET_CODE' })}><RotateCcw size={15} /> Reset</Button></header><label className="sb-sr-only" htmlFor="sb-code">Java code</label><textarea id="sb-code" value={state.codeDraft} onChange={e => dispatch({ type: 'SET_CODE', value: e.target.value })} spellCheck={false} />
      <footer><p>{SIMULATION_LIMITATION}</p><div><Button tone="secondary" onClick={() => dispatch({ type: 'RUN_CHECKS' })}><Play size={16} /> Run static checks</Button><Button onClick={() => dispatch({ type: 'SUBMIT_CODE' })}><ShieldCheck size={16} /> Submit evidence</Button></div></footer>
      <div className="sb-output" aria-live="polite"><header><strong>Static check output</strong><span>{state.runResult?.status ?? 'Not run'}</span></header>{state.runResult ? state.runResult.checks.map(check => <div key={check.label}><span className={check.passed ? 'is-pass' : 'is-fail'}>{check.passed ? <Check size={14} /> : <X size={14} />}</span><p><strong>{check.label}</strong><small>{check.detail}</small></p></div>) : <p>No process will run. These deterministic browser checks inspect text patterns only.</p>}</div>
    </section> : null}
  </article><TopicTools conversationScope={topicContent.data?.conversation_scope ?? null} sourcesMarkdown={sourcesMarkdown} /><ClassroomProgress navigate={navigate} previous={previousTitle} previousTarget={previousId ? undefined : 'learn-roadmap'} onPrevious={previousId ? () => selectLesson(previousId) : undefined} next={nextTitle} nextTarget={nextId ? undefined : 'practice'} onNext={nextId ? () => selectLesson(nextId) : undefined} /></Classroom>
}

function TopicTools({ conversationScope, sourcesMarkdown }: { conversationScope: string | null; sourcesMarkdown: string | null }) {
  const { state, dispatch } = useLearningState()
  return <Tabs.Root id="sb-lesson-tools" defaultValue="notes" className="sb-tools">
    <Tabs.List aria-label="Secondary lesson tools"><Tabs.Trigger value="notes"><NotebookPen size={16} /> Notes</Tabs.Trigger><Tabs.Trigger value="resources"><BookOpen size={16} /> Resources</Tabs.Trigger><Tabs.Trigger value="help"><HelpCircle size={16} /> Help</Tabs.Trigger></Tabs.List>
    <Tabs.Content value="notes"><label htmlFor="sb-notes">Goal notebook</label><textarea id="sb-notes" value={state.codeNotes} onChange={e => dispatch({ type: 'SET_NOTES', value: e.target.value })} /></Tabs.Content>
    <Tabs.Content value="resources">{sourcesMarkdown
      ? <div className="sb-tool-content"><FileText size={18} /><div><strong>Approved sources</strong><p>{sourcesMarkdown}</p></div></div>
      : <div className="sb-empty"><FileText /><strong>No approved sources yet</strong><span>Check the Sources layer after content is published.</span></div>}
    </Tabs.Content>
    <Tabs.Content value="help"><div className="sb-empty" data-conversation-scope={conversationScope ?? undefined}><MessageSquareText /><strong>{conversationScope ? 'Conversation attached to this topic' : 'Topic conversation unavailable'}</strong><span>{conversationScope ? 'Messages stay with this topic. Chat is not connected yet.' : 'Retry the topic content request to restore it.'}</span></div></Tabs.Content>
  </Tabs.Root>
}

function InterviewHub({ navigate, mode }: PageProps & { mode?: InterviewMode }) {
  const { state, dispatch } = useLearningState()
  const workspace = useProfileGoals()
  const choices = [
    { title: 'Refresher', text: 'Review the message delivery contract and evidence gaps.', meta: 'Focused reading', Icon: BookOpen, target: 'topic-studio', lessonId: 'delivery-contract', hubMode: 'refresher' as InterviewMode },
    { title: 'Question bank', text: 'Choose a scenario without completing the Learn path.', meta: '2 fixture questions', Icon: HelpCircle, target: 'practice', hubMode: 'questions' as InterviewMode },
    { title: 'Guided practice', text: 'Request a hint, submit, inspect feedback, and repair.', meta: 'Hints on request', Icon: Code2, target: 'practice' },
    { title: 'Mock interview', text: state.mock.status === 'paused' ? 'Resume the exact locally saved draft.' : 'Answer without hints, rubrics, or evaluation until completion.', meta: state.mock.status === 'paused' ? 'Paused' : 'Neutral while active', Icon: MessageSquareText, target: 'mock' },
  ]
  const activeChoice = mode ? choices.find((choice) => choice.hubMode === mode) : undefined
  const openChoice = (choice: (typeof choices)[number], asMode?: InterviewMode) => {
    if (asMode) { navigate('interview-hub', asMode); return }
    if (choice.title === 'Mock interview' && state.mock.status === 'paused') dispatch({ type: 'RESUME_MOCK' })
    if (choice.lessonId && workspace.currentGoal) {
      workspace.recordNavigation.mutate({ goal: workspace.currentGoal, position: choice.lessonId, destination: '/app/topic-studio' }, { onSuccess: () => navigate(choice.target) })
      return
    }
    navigate(choice.target)
  }
  return <main className="sb-page sb-interview"><PageIntro eyebrow="Interview prep · Senior backend" title="Choose the mode you need"><span>Generic product-company context; no company-specific or hiring-readiness claim.</span></PageIntro>
    {activeChoice && <section className="sb-mode-detail" data-testid="interview-mode-detail" data-mode={mode}>
      <span>{activeChoice.meta}</span>
      <activeChoice.Icon />
      <h2>{activeChoice.title}</h2>
      <p>{activeChoice.text}</p>
      <div>
        <Button onClick={() => openChoice(activeChoice)}>Open {activeChoice.title} <ArrowRight size={16} /></Button>
        <Button tone="quiet" onClick={() => navigate('interview-hub')}><ArrowLeft size={16} /> Back to Interview prep</Button>
      </div>
    </section>}
    <section className="sb-mode-list">{choices.map((choice, i) => <article key={choice.title} aria-current={choice.hubMode && choice.hubMode === mode ? 'true' : undefined}><span>0{i + 1}</span><choice.Icon /><div><h2>{choice.title}</h2><p>{choice.text}</p><small>{choice.meta}</small></div><button aria-label={`Open ${choice.title}`} onClick={() => openChoice(choice, choice.hubMode)}><ArrowRight /></button></article>)}</section><aside className="sb-neutral"><ShieldCheck /><div><strong>Mock stays evaluation-free while active</strong><p>Only one question and the response field are shown. Consolidated evidence appears after an explicit terminal completion.</p></div></aside></main>
}

function Practice({ navigate }: PageProps) {
  const { state, dispatch } = useLearningState()
  const question = currentPracticeQuestion(state)
  const latest = state.practice.attempts.at(-1)
  const history = (state.practice.mode === 'feedback' ? state.practice.attempts.slice(0, -1) : [...state.practice.attempts]).reverse()
  return <Classroom navigate={navigate}><article className="sb-practice"><PageIntro eyebrow={`Guided practice · ${state.practice.questionIndex + 1} of ${PRACTICE_QUESTIONS.length}`} title="Reason through the failure boundary"><span>Your draft and append-only attempts use shared browser state.</span></PageIntro><section className="sb-question"><span>Scenario</span><h2>{question.prompt}</h2></section>{state.practice.mode === 'answering' ? <section className="sb-answer"><label htmlFor="sb-answer">Your response</label><textarea id="sb-answer" value={state.practice.draft} onChange={e => dispatch({ type: 'SET_PRACTICE_DRAFT', value: e.target.value })} placeholder="Name the failure window, protection, and cost…" /><div><Button tone="quiet" onClick={() => dispatch({ type: 'REQUEST_HINT' })} disabled={state.practice.hintRequested}><Lightbulb size={16} /> {state.practice.hintRequested ? 'Hint requested' : 'Request hint'}</Button><Button disabled={!state.practice.draft.trim()} onClick={() => dispatch({ type: 'SUBMIT_PRACTICE' })}>Submit response</Button></div>{state.practice.hintRequested && <aside className="sb-hint"><Lightbulb /><div><strong>Requested hint</strong><p>{question.hint}</p></div></aside>}</section> : latest && <section className="sb-feedback"><span className="sb-kicker">Post-submission review</span><h2>Keep factual corrections separate from defensible choices.</h2><div className="sb-feedback-grid"><section><h3><Check size={17} /> Facts and corrections</h3>{latest.facts.map(x => <p key={x}>{x}</p>)}</section><section><h3><Settings2 size={17} /> Trade-offs to defend</h3>{latest.tradeoffs.map(x => <p key={x}>{x}</p>)}</section></div><details><summary>Your submitted response <ChevronDown /></summary><p>{latest.answer}</p></details><footer><Button tone="secondary" onClick={() => dispatch({ type: 'START_REPAIR' })}><RefreshCcw size={16} /> Repair answer</Button><Button onClick={() => dispatch({ type: 'CONTINUE_PRACTICE' })}>Continue <ArrowRight size={16} /></Button></footer></section>}{history.length > 0 && <details className="sb-history"><summary>Earlier attempts ({history.length}) <ChevronDown /></summary>{history.map(item => <article key={item.id}><strong>{item.id}</strong><p>{item.answer}</p></article>)}</details>}</article><ClassroomProgress navigate={navigate} previous="Topic studio" previousTarget="topic-studio" next="Interview prep" nextTarget="interview-hub" /></Classroom>
}

function Mock({ navigate }: PageProps) {
  const { state, dispatch } = useLearningState()
  const [exitOpen, setExitOpen] = useState(false)
  const [completeOpen, setCompleteOpen] = useState(false)
  const exitRef = useRef<HTMLButtonElement>(null)
  const completeRef = useRef<HTMLButtonElement>(null)
  if (state.mock.status === 'completed') return <main className="sb-mock-complete"><div><Check /></div><span className="sb-eyebrow">Interview complete</span><h1>The active session has ended.</h1><p>Your transcript is fixed. The available report gate is determined by the exact response fixture.</p><Button onClick={() => navigate('reports')}>Open report <ArrowRight size={16} /></Button></main>
  return <main className="sb-mock"><header><div><span /> Mock in progress</div><strong>Question 3 · final question</strong><button ref={exitRef} onClick={() => setExitOpen(true)}><Pause size={16} /> Save &amp; exit</button></header><section><div className="sb-interviewer"><span>03</span><div><strong>Interviewer</strong><small>Current bounded follow-up</small></div></div><h1>{MOCK_CURRENT_QUESTION}</h1><label htmlFor="sb-mock-answer">Your response</label><textarea id="sb-mock-answer" value={state.mock.draft} onChange={e => dispatch({ type: 'SET_MOCK_DRAFT', value: e.target.value })} placeholder="Answer with your decision and reasoning…" autoFocus /><footer><span>Draft retained in this browser. No hints or evaluation are available during the run.</span><Button ref={completeRef} disabled={!state.mock.draft.trim()} onClick={() => setCompleteOpen(true)}>Complete interview</Button></footer></section>
    <Confirm open={exitOpen} onOpenChange={setExitOpen} title="Pause this mock?" description="Your exact response draft will be retained in shared browser state. Resume it from Interview prep." trigger={exitRef} cancel="Keep answering" action="Save & exit" onAction={() => { dispatch({ type: 'SAFE_EXIT_MOCK' }); navigate('interview-hub') }} />
    <Confirm open={completeOpen} onOpenChange={setCompleteOpen} title="Complete the interview?" description="This terminal action ends the active session. The transcript cannot accept more answers afterward." trigger={completeRef} cancel="Return to answer" action="Complete & view report" onAction={() => { dispatch({ type: 'COMPLETE_MOCK' }); navigate('reports') }} />
  </main>
}

function Confirm({ open, onOpenChange, title, description, trigger, cancel, action, onAction }: { open: boolean; onOpenChange: (x: boolean) => void; title: string; description: string; trigger: React.RefObject<HTMLButtonElement | null>; cancel: string; action: string; onAction: () => void }) {
  return <AlertDialog.Root open={open} onOpenChange={onOpenChange}><AlertDialog.Portal><AlertDialog.Overlay className="sb-overlay" /><AlertDialog.Content className="sb-alert" onCloseAutoFocus={e => { e.preventDefault(); trigger.current?.focus() }}><AlertDialog.Title>{title}</AlertDialog.Title><AlertDialog.Description>{description}</AlertDialog.Description><div><AlertDialog.Cancel asChild><Button tone="secondary">{cancel}</Button></AlertDialog.Cancel><AlertDialog.Action asChild><Button onClick={onAction}>{action}</Button></AlertDialog.Action></div></AlertDialog.Content></AlertDialog.Portal></AlertDialog.Root>
}

function Reports({ navigate }: PageProps) {
  const { state } = useLearningState()
  const fixture = state.mock.reportKind === 'fixture-evaluation'
  const transcriptOnly = state.mock.reportKind === 'transcript-only'
  const turns = state.mock.completedTurns.length ? state.mock.completedTurns : state.mock.priorTurns
  const nextAction = !state.mock.reportKind
    ? { eyebrow: state.mock.status === 'paused' ? 'Saved draft' : 'Active mock', title: state.mock.status === 'paused' ? 'Resume your exact saved response' : 'Finish the active mock when your response is ready', detail: `${state.mock.draft.trim() ? 'A response draft is saved.' : 'The response is still empty.'} Terminal completion is required before any report gate is set.`, label: state.mock.status === 'paused' ? 'Resume mock' : 'Return to mock', target: 'mock' as CorePage }
    : state.evidence.length === 0
      ? { eyebrow: 'Next action', title: 'Submit your first lab evidence', detail: 'This report currently contains no submitted lab evidence. Return to the implementation lab to run or submit the current draft.', label: 'Open topic studio', target: 'topic-studio' as CorePage, lessonId: CURRENT_LESSON_ID }
      : state.practice.attempts.length === 0
        ? { eyebrow: 'Next action', title: 'Test the decision in guided practice', detail: `You have ${state.evidence.length} submitted lab evidence ${state.evidence.length === 1 ? 'entry' : 'entries'} and no guided-practice attempts yet.`, label: 'Start guided practice', target: 'practice' as CorePage }
        : { eyebrow: 'Next action', title: 'Continue from your saved practice state', detail: `${state.practice.attempts.length} append-only practice ${state.practice.attempts.length === 1 ? 'attempt is' : 'attempts are'} saved on scenario ${state.practice.questionIndex + 1} of ${PRACTICE_QUESTIONS.length}.`, label: 'Open guided practice', target: 'practice' as CorePage }
  return <main className="sb-page sb-reports"><PageIntro eyebrow="Evidence report · mock interview" title={fixture ? FIXTURE_REPORT.conclusion : transcriptOnly ? 'Transcript preserved; evaluation withheld.' : 'No terminal mock report is available.'} action={<Button tone="quiet" onClick={() => navigate('interview-hub')}><ArrowLeft size={16} /> Interview prep</Button>}><span>{fixture ? 'Exact deterministic fixture match. This is not a provider evaluation or hiring prediction.' : transcriptOnly ? 'Your answer differs from the exact fixture, so this browser presentation makes no evaluative claim.' : 'Complete the active mock to create a transcript.'}</span></PageIntro>
    <section className="sb-report-next" aria-labelledby="sb-report-next-title"><div><span className="sb-eyebrow">{nextAction.eyebrow}</span><h2 id="sb-report-next-title">{nextAction.title}</h2><p>{nextAction.detail}</p></div><Button onClick={() => navigate(nextAction.target)}>{nextAction.label} <ArrowRight size={16} /></Button></section>
    <section className="sb-report-gate"><span>Report gate</span><strong>{fixture ? 'Exact-fixture evaluation' : transcriptOnly ? 'Transcript only' : 'Unavailable'}</strong><p>{fixture ? 'Eligible only because every response matches the bundled deterministic fixture.' : transcriptOnly ? 'No score, rubric outcome, factual judgment, or readiness result is produced.' : 'Prior turns are displayed for context, not as a completed interview.'}</p></section>
    {fixture && <section className="sb-report-grid"><article><h2>Facts in transcript</h2>{FIXTURE_REPORT.facts.map(x => <p key={x}><Check size={16} /> {x}</p>)}</article><article><h2>Trade-offs named</h2>{FIXTURE_REPORT.tradeoffs.map(x => <p key={x}><Settings2 size={16} /> {x}</p>)}</article></section>}
    <details className="sb-report-detail" open><summary>Transcript and provenance <ChevronDown /></summary><div><section><h2>Interview transcript</h2>{turns.map(turn => <article key={turn.id}><span>Interviewer</span><p>{turn.question}</p><span>You</span><p>{turn.answer}</p></article>)}</section><aside><h2>Provenance</h2><dl><dt>Kind</dt><dd>{state.mock.reportKind ?? 'Unavailable'}</dd><dt>Turns</dt><dd>{turns.length}</dd><dt>Method</dt><dd>{fixture ? 'Exact string match to bundled fixture' : 'Transcript preservation only'}</dd></dl>{fixture && <><h3>Assumptions</h3><ul>{FIXTURE_REPORT.assumptions.map(x => <li key={x}>{x}</li>)}</ul></>}</aside></div></details>
    <details className="sb-report-detail"><summary>Submitted lab evidence ({state.evidence.length}) <ChevronDown /></summary><div className="sb-evidence-history">{state.evidence.length ? state.evidence.map(item => <article key={item.id}><strong>{item.conclusion}</strong><p>{item.limitation}</p></article>) : <p>No submitted lab evidence.</p>}</div></details>
  </main>
}

export function CorePageView({ page, navigate, mode }: { page: CorePage; navigate: Navigate; mode?: InterviewMode }) {
  let content: ReactNode
  switch (page) {
    case 'home': content = <Home navigate={navigate} />; break
    case 'onboarding': content = <Onboarding navigate={navigate} />; break
    case 'learn-roadmap': content = <Roadmap navigate={navigate} />; break
    case 'topic-studio': content = <Topic navigate={navigate} />; break
    case 'interview-hub': content = <InterviewHub navigate={navigate} {...(mode ? { mode } : {})} />; break
    case 'practice': content = <Practice navigate={navigate} />; break
    case 'mock': content = <Mock navigate={navigate} />; break
    case 'reports': content = <Reports navigate={navigate} />; break
  }
  return <div className={`sb-core sb-page-${page}`}>{content}</div>
}

export default CorePageView
