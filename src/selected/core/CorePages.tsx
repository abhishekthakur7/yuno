import { forwardRef, useMemo, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from 'react'
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
  MOCK_CURRENT_QUESTION, PRACTICE_QUESTIONS, SIMULATION_LIMITATION, TOPIC_BRIEF,
  type Depth, type KnowledgeState, type Lesson,
} from '../../shared/model'
import { activeRoadmapLessonIds, currentPracticeQuestion, learningStorageKey, useLearningState } from '../../shared/state'
import { ApiError, canonicalVersionsQueryOptions } from '../../shared/api/queries'
import { goalDestination, resumePage, useProfileGoals } from '../../shared/use-profile-goals'
import type { GoalCreate, GoalWorkspace } from '../../shared/api/profile-goals'
import type { InterviewMode } from '../app-model'
import './core.css'

export type CorePage = 'home' | 'onboarding' | 'learn-roadmap' | 'topic-studio' | 'interview-hub' | 'practice' | 'mock' | 'reports'

type Navigate = (page: CorePage | string, mode?: InterviewMode) => void
type PageProps = { navigate: Navigate }
const DEPTHS: readonly Depth[] = ['Essential', 'Implementation', 'Production', 'Interview']
const STATES: readonly KnowledgeState[] = ['likely known', 'partial', 'unverified', 'new']
const LESSONS = ALL_LESSONS as readonly Lesson[]

const LESSON_CONTEXT: Readonly<Record<string, { heading: string; explanation: string; evidence: string }>> = {
  'delivery-contract': { heading: 'Start with the delivery contract', explanation: 'Standard queue delivery may repeat. Separate what the queue promises from what your handler must make safe before choosing a framework pattern.', evidence: 'State the delivery guarantee, the acknowledgement boundary, and one consequence for the consumer.' },
  'commit-window': { heading: 'Trace the commit window before fixing it', explanation: 'A business write can commit before acknowledgement succeeds. Walk the crash and redelivery sequence so the duplicate risk is concrete.', evidence: 'Produce a failure timeline that identifies the last durable fact at each step.' },
  'idempotency-retry': { heading: 'Close the race, not just the retry', explanation: 'A read followed by a write is not the arbiter when two consumers observe the same absence. Put the decision in a unique constraint or atomic operation and return the durable winner.', evidence: TOPIC_BRIEF.evidence },
  'atomic-write': { heading: 'Make one durable decision', explanation: 'The business outcome and duplicate marker need a boundary that cannot expose one without the other. Name the transaction or atomic primitive that provides it.', evidence: 'Explain the atomic boundary and what the losing concurrent request receives.' },
  'delayed-duplicates': { heading: 'Keep correctness beyond the immediate retry', explanation: 'Delayed and out-of-order deliveries make retention and ordering assumptions visible. Treat both as bounded design inputs, not hidden guarantees.', evidence: 'Defend a duplicate-retention horizon and the behavior after it expires.' },
  'visibility-timeout': { heading: 'Tune timeouts from observed work', explanation: 'Visibility must cover expected processing while renewals and retries stay bounded. A long timeout reduces churn but lengthens recovery from a lost worker.', evidence: 'Choose a timeout and retry budget from an explicit processing-latency assumption.' },
  'dead-letter': { heading: 'Quarantine without bypassing correctness', explanation: 'A dead-letter queue isolates poison work; replay still crosses the same duplicate boundary as first delivery.', evidence: 'Outline diagnose, correct, and replay steps that retain the original request key.' },
  observability: { heading: 'Instrument the decision boundary', explanation: 'Retry count alone cannot distinguish healthy recovery from duplicate amplification. Observe duplicate wins, handler latency, acknowledgement failures, and terminal quarantine.', evidence: 'Propose signals that can separate redelivery, contention, and poison-message failure.' },
  'failure-injection': { heading: 'Break one boundary at a time', explanation: 'Bounded failure injection makes recovery inspectable when the crash point and expected durable state are declared before the run.', evidence: 'Define one injected failure, the expected durable state, and the recovery observation.' },
  'tradeoff-review': { heading: 'Defend the availability cost', explanation: 'A duplicate-safe boundary changes the write-path availability budget. Compare fail-closed, fail-open, and deferred-reconciliation consequences under stated assumptions.', evidence: 'Defend one choice while naming the strongest alternative and its cost.' },
  'transfer-check': { heading: 'Transfer the pattern to a new trust boundary', explanation: 'A client-supplied key changes collision, abuse, and retention assumptions even when the atomic write pattern stays familiar.', evidence: 'Adapt the boundary for an untrusted key and identify the new validation requirement.' },
}

function lessonById(id: string): Lesson {
  return LESSONS.find((lesson) => lesson.id === id) ?? LESSONS.find((lesson) => lesson.id === CURRENT_LESSON_ID)!
}

function moduleForLesson(id: string) {
  return CURRICULUM_MODULES.find((module) => module.lessons.some((lesson) => lesson.id === id)) ?? CURRICULUM_MODULES[0]!
}

function orderedModuleLessons(module: (typeof CURRICULUM_MODULES)[number], order: readonly string[]): readonly Lesson[] {
  const position = new Map(order.map((id, index) => [id, index]))
  return [...module.lessons].sort((a, b) => (position.get(a.id) ?? 0) - (position.get(b.id) ?? 0))
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
  const { dispatch } = useLearningState()
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
    if (LESSONS.some((lesson) => lesson.id === currentGoal.resume_position)) {
      dispatch({ type: 'SELECT_LESSON', lessonId: currentGoal.resume_position })
    }
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
  const { state, dispatch } = useLearningState()
  const workspace = useProfileGoals()
  const canonicalVersions = useQuery(canonicalVersionsQueryOptions())
  const [preview, setPreview] = useState(false)
  const [subjectOrRole, setSubjectOrRole] = useState('')
  const [targetCapability, setTargetCapability] = useState<GoalCreate['target_capability']>('implement')
  const idempotencyKey = useRef(crypto.randomUUID())
  const graphVersion = canonicalVersions.data?.[0]
  const createWorkspace = () => {
    if (!graphVersion) return
    workspace.create.mutate({ input: {
      name: state.onboarding.goalName.trim(),
      path: state.onboarding.path === 'Learn' ? 'learn' : 'interview_prep',
      target_level: state.onboarding.target,
      target_capability: targetCapability,
      graph_version_id: graphVersion.id,
      ...(state.onboarding.path === 'Learn' ? { subject: subjectOrRole.trim() || null } : { role: subjectOrRole.trim() || null }),
    }, idempotencyKey: idempotencyKey.current }, { onSuccess: async (goal) => {
      window.localStorage.setItem(learningStorageKey(goal.id), JSON.stringify(state))
      const refreshedProfile = await workspace.profile.refetch()
      if (refreshedProfile.data?.current_goal_id === goal.id) await workspace.goals.refetch()
      else await workspace.switchGoal.mutateAsync(goal)
      navigate(goalDestination(goal))
    } })
  }
  return <main className="sb-page sb-onboarding">
    {!preview ? <section className="sb-card">
      <PageIntro eyebrow="Goal setup · 1 of 2" title="Shape your classroom"><span>For experienced backend engineers. Set the target; every inferred state remains editable.</span></PageIntro>
      <div className="sb-form-grid">
        <fieldset><legend>Primary path</legend><div className="sb-segments">{(['Learn', 'Interview Prep'] as const).map(value => <button type="button" key={value} className={state.onboarding.path === value ? 'is-selected' : ''} aria-pressed={state.onboarding.path === value} onClick={() => dispatch({ type: 'SET_ONBOARDING', field: 'path', value })}>{value === 'Learn' ? <BookOpen size={18} /> : <MessageSquareText size={18} />}{value}</button>)}</div></fieldset>
        <label>Target level<select value={state.onboarding.target} onChange={e => dispatch({ type: 'SET_ONBOARDING', field: 'target', value: e.target.value })}><option>Mid-level</option><option>Senior</option><option>Staff</option></select><small>Yuno’s MVP curriculum is for experienced backend engineers and does not include a beginner track.</small></label>
        <label>{state.onboarding.path === 'Learn' ? 'Subject' : 'Role'}<input value={subjectOrRole} onChange={(event) => setSubjectOrRole(event.target.value)} /></label>
        <label>Target capability<select value={targetCapability} onChange={(event) => setTargetCapability(event.target.value as GoalCreate['target_capability'])}><option value="know">Know</option><option value="understand">Understand</option><option value="choose">Choose</option><option value="implement">Implement</option><option value="diagnose">Diagnose</option><option value="defend">Defend</option></select></label>
        <label className="sb-wide">Goal name<input value={state.onboarding.goalName} onChange={e => dispatch({ type: 'SET_ONBOARDING', field: 'goalName', value: e.target.value })} /></label>
        <fieldset className="sb-wide"><legend>Starting evidence</legend><label className="sb-radio"><input type="radio" name="sb-diagnostic" checked={state.onboarding.diagnostic === 'take'} onChange={() => dispatch({ type: 'SET_ONBOARDING', field: 'diagnostic', value: 'take' })} /><span><strong>Take a short diagnostic</strong><small>Estimate what should be verified; this does not mark completion.</small></span></label><label className="sb-radio"><input type="radio" name="sb-diagnostic" checked={state.onboarding.diagnostic === 'skip'} onChange={() => dispatch({ type: 'SET_ONBOARDING', field: 'diagnostic', value: 'skip' })} /><span><strong>Skip for now</strong><small>Begin with conservative self-reported states.</small></span></label></fieldset>
        <label className="sb-wide">Optional notes or questions<textarea value={state.onboarding.sourceMaterial} onChange={e => dispatch({ type: 'SET_ONBOARDING_SOURCE', value: e.target.value })} placeholder={state.onboarding.path === 'Learn' ? 'Paste plain text or Markdown notes for later review.' : 'Paste questions you want to review later.'} /><small>Saved in this browser as untrusted source material. It is not parsed, imported, or treated as truth; Imports offers the explicit review handoff.</small></label>
      </div><footer className="sb-card-footer"><Button tone="quiet" onClick={() => navigate('home')}><ArrowLeft size={16} /> Cancel</Button><Button onClick={() => setPreview(true)} disabled={!state.onboarding.goalName.trim() || !subjectOrRole.trim()}>Preview full roadmap <ArrowRight size={16} /></Button></footer>
    </section> : <section className="sb-card">
      <PageIntro eyebrow="Goal setup · 2 of 2" title="Create a goal from this roadmap" action={<Button tone="quiet" onClick={() => setPreview(false)}><Settings2 size={16} /> Edit setup</Button>}>
        {state.onboarding.path} · {state.onboarding.target} · inferred states are not completion.
      </PageIntro>
      <div className="sb-preview">{CURRICULUM_MODULES.map((module, i) => {
        const moduleLessons = orderedModuleLessons(module, state.roadmapOrder)
        return <section key={module.id}><header><span>{String(i + 1).padStart(2, '0')}</span><div><h2>{module.title}</h2><small>{module.duration}</small></div></header><ol>{moduleLessons.map((lesson, lessonIndex) => {
          const choice = state.roadmap[lesson.id]
          return <li key={lesson.id} className={choice?.skipped ? 'is-skipped' : ''}><span>{lesson.title}</span><div className="sb-preview-controls"><label><span>Knowledge</span><select value={choice?.learnerState} onChange={e => dispatch({ type: 'SET_LEARNER_STATE', lessonId: lesson.id, learnerState: e.target.value as KnowledgeState })}>{STATES.map(value => <option key={value}>{value}</option>)}</select></label><label><span>Depth</span><select value={choice?.depth} onChange={e => dispatch({ type: 'SET_DEPTH', lessonId: lesson.id, depth: e.target.value as Depth })}>{DEPTHS.map(value => <option key={value}>{value}</option>)}</select></label><Button tone="quiet" onClick={() => dispatch({ type: 'TOGGLE_SKIP', lessonId: lesson.id })}>{choice?.skipped ? 'Restore' : 'Skip'}</Button><div className="sb-order"><button disabled={lessonIndex === 0} onClick={() => dispatch({ type: 'MOVE_LESSON', lessonId: lesson.id, direction: -1 })} aria-label={`Move ${lesson.title} earlier`}><ArrowUp size={16} /></button><button disabled={lessonIndex === moduleLessons.length - 1} onClick={() => dispatch({ type: 'MOVE_LESSON', lessonId: lesson.id, direction: 1 })} aria-label={`Move ${lesson.title} later`}><ArrowDown size={16} /></button></div></div></li>
        })}</ol></section>
      })}</div>
      <footer className="sb-card-footer sb-approval"><span><ShieldCheck size={18} /> {workspace.create.isError ? 'Goal creation failed.' : canonicalVersions.isError ? 'Approved curriculum could not be loaded.' : canonicalVersions.isPending ? 'Loading approved curriculum…' : graphVersion ? 'Ready to create this goal.' : 'No approved curriculum is available.'}</span><span>{canonicalVersions.isError && <Button tone="secondary" onClick={() => void canonicalVersions.refetch()}>Retry</Button>}<Button disabled={!graphVersion || workspace.create.isPending} onClick={createWorkspace}><Check size={17} /> {workspace.create.isPending ? 'Creating goal…' : 'Create goal from roadmap'}</Button></span></footer>
    </section>}
  </main>
}

function Roadmap({ navigate }: PageProps) {
  const { state, dispatch } = useLearningState()
  const workspace = useProfileGoals()
  const [open, setOpen] = useState<ReadonlySet<string>>(() => new Set([CURRENT_LESSON_ID]))
  const byId = useMemo(() => new Map(LESSONS.map(lesson => [lesson.id, lesson])), [])
  const ordered = state.roadmapOrder.map(id => byId.get(id)).filter((x): x is Lesson => Boolean(x))
  const toggle = (id: string) => setOpen(current => { const next = new Set(current); next.has(id) ? next.delete(id) : next.add(id); return next })
  const openLesson = (lessonId: string) => {
    if (!workspace.currentGoal) return
    workspace.recordNavigation.mutate({ goal: workspace.currentGoal, position: lessonId, destination: '/app/topic-studio' }, { onSuccess: () => { dispatch({ type: 'SELECT_LESSON', lessonId }); navigate('topic-studio') } })
  }
  return <main className="sb-page sb-roadmap"><PageIntro eyebrow={state.onboarding.approved ? 'Approved personal overlay' : 'Unapproved roadmap preview'} title="Your editable roadmap" action={<Button onClick={() => navigate(state.onboarding.approved ? 'topic-studio' : 'onboarding')}>{state.onboarding.approved ? 'Jump to current' : 'Return to approval'} <ArrowRight size={16} /></Button>}>
    Jump, skip, reorder, or correct any inferred state. Changes are learner-owned and never claim mastery.
  </PageIntro>
  <div className="sb-roadmap-summary"><span><span className="sb-dot is-qualified" /> Historical: 4 with qualified evidence</span><span><span className="sb-dot is-current" /> Current checkpoint</span><span>{state.onboarding.approved ? 'Roadmap approved' : 'Preview state'}</span></div>
  <section className="sb-roadmap-list" aria-label="Editable roadmap">{ordered.map((lesson, index) => {
    const choice = state.roadmap[lesson.id]
    const module = CURRICULUM_MODULES.find(item => item.lessons.some(candidate => candidate.id === lesson.id))!
    const previousLesson = ordered[index - 1]
    const first = !previousLesson || moduleForLesson(previousLesson.id).id !== module.id
    const moduleLessons = orderedModuleLessons(module, state.roadmapOrder)
    const moduleIndex = moduleLessons.findIndex((item) => item.id === lesson.id)
    return <div key={lesson.id}>{first && <header className="sb-module-head"><span>Section {CURRICULUM_MODULES.indexOf(module) + 1}</span><strong>{module.title}</strong><small>{module.duration}</small></header>}
      <article className={`sb-roadmap-row ${lesson.id === state.currentLessonId ? 'is-current' : ''} ${choice?.skipped ? 'is-skipped' : ''}`}>
        <button className="sb-lesson-link" disabled={!workspace.currentGoal || workspace.recordNavigation.isPending} onClick={() => openLesson(lesson.id)} aria-label={`${String(index + 1).padStart(2, '0')} ${lesson.title}${choice?.skipped ? ' · skipped; opening restores it to the roadmap sequence' : ''}`}><span>{String(index + 1).padStart(2, '0')}</span><span><strong>{lesson.title}</strong><small>{lesson.kind} · {lesson.duration} · capability: {lesson.capability}{choice?.skipped ? ' · Skipped · open to restore' : ''}</small></span></button>
        <button className="sb-customize" aria-expanded={open.has(lesson.id)} aria-controls={`sb-controls-${lesson.id}`} onClick={() => toggle(lesson.id)}><Settings2 size={16} /> Customize</button>
        <div id={`sb-controls-${lesson.id}`} className={`sb-roadmap-controls ${open.has(lesson.id) ? 'is-open' : ''}`}><label>Depth<select value={choice?.depth} onChange={e => dispatch({ type: 'SET_DEPTH', lessonId: lesson.id, depth: e.target.value as Depth })}>{DEPTHS.map(x => <option key={x}>{x}</option>)}</select></label><label>Knowledge<select value={choice?.learnerState} onChange={e => dispatch({ type: 'SET_LEARNER_STATE', lessonId: lesson.id, learnerState: e.target.value as KnowledgeState })}>{STATES.map(x => <option key={x}>{x}</option>)}</select></label><Button tone="quiet" onClick={() => dispatch({ type: 'TOGGLE_SKIP', lessonId: lesson.id })}>{choice?.skipped ? 'Restore' : 'Skip'}</Button><div className="sb-order"><button disabled={moduleIndex === 0} onClick={() => dispatch({ type: 'MOVE_LESSON', lessonId: lesson.id, direction: -1 })} aria-label={`Move ${lesson.title} earlier`}><ArrowUp size={16} /></button><button disabled={moduleIndex === moduleLessons.length - 1} onClick={() => dispatch({ type: 'MOVE_LESSON', lessonId: lesson.id, direction: 1 })} aria-label={`Move ${lesson.title} later`}><ArrowDown size={16} /></button></div></div>
      </article></div>
  })}</section>
  </main>
}

function Curriculum({ navigate, close }: PageProps & { close?: () => void }) {
  const { state, dispatch } = useLearningState()
  const workspace = useProfileGoals()
  const openLesson = (lessonId: string) => {
    if (!workspace.currentGoal) return
    workspace.recordNavigation.mutate({ goal: workspace.currentGoal, position: lessonId, destination: '/app/topic-studio' }, { onSuccess: () => { dispatch({ type: 'SELECT_LESSON', lessonId }); navigate('topic-studio'); close?.() } })
  }
  return <div className="sb-curriculum"><header><div><span className="sb-kicker">Roadmap</span><strong>4 sections · 11 lessons</strong></div><Button tone="quiet" onClick={() => navigate('learn-roadmap')}>Edit plan</Button></header>{CURRICULUM_MODULES.map((module, i) => <details key={module.id} open><summary><span>{String(i + 1).padStart(2, '0')} · {module.title}</span><ChevronDown size={16} /></summary>{orderedModuleLessons(module, state.roadmapOrder).map((lesson) => { const skipped = state.roadmap[lesson.id]?.skipped; return <button key={lesson.id} disabled={!workspace.currentGoal || workspace.recordNavigation.isPending} className={`${lesson.id === state.currentLessonId ? 'is-current' : ''} ${skipped ? 'is-skipped' : ''}`} aria-current={lesson.id === state.currentLessonId ? 'step' : undefined} aria-label={`${lesson.title}${skipped ? ' · skipped; opening restores it to the roadmap sequence' : ''}`} onClick={() => openLesson(lesson.id)}><span className="sb-mini-check"><Circle size={10} /></span><span><strong>{lesson.title}</strong><small>{lesson.duration} · {state.roadmap[lesson.id]?.learnerState}{skipped ? ' · Skipped · open to restore' : ''}</small></span></button> })}</details>)}</div>
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

function Topic({ navigate }: PageProps) {
  const { state, dispatch } = useLearningState()
  const workspace = useProfileGoals()
  const lesson = lessonById(state.currentLessonId)
  const module = moduleForLesson(lesson.id)
  const activeIds = activeRoadmapLessonIds(state)
  const currentIndex = activeIds.indexOf(lesson.id)
  const previousLesson = currentIndex > 0 ? lessonById(activeIds[currentIndex - 1]!) : null
  const nextId = activeIds[currentIndex + 1]
  const nextLesson = nextId ? lessonById(nextId) : null
  const context = LESSON_CONTEXT[lesson.id] ?? LESSON_CONTEXT[CURRENT_LESSON_ID]!
  const selectLesson = (id: string) => {
    if (!workspace.currentGoal) return
    workspace.recordNavigation.mutate({ goal: workspace.currentGoal, position: id, destination: '/app/topic-studio' }, { onSuccess: () => { dispatch({ type: 'SELECT_LESSON', lessonId: id }); window.scrollTo({ top: 0 }) } })
  }
  return <Classroom navigate={navigate}><article className="sb-topic">
    <PageIntro eyebrow={`Section ${CURRICULUM_MODULES.indexOf(module) + 1} · checkpoint ${currentIndex + 1} of ${activeIds.length}`} title={lesson.title} action={<div className="sb-topic-actions"><Button onClick={() => document.getElementById('sb-lesson-artifact')?.scrollIntoView({ block: 'start' })}>{lesson.id === CURRENT_LESSON_ID ? 'Open implementation lab' : 'Open checkpoint'} <ArrowDown size={16} /></Button><Button tone="quiet" onClick={() => document.getElementById('sb-lesson-tools')?.scrollIntoView({ block: 'start' })}>Lesson tools <NotebookPen size={16} /></Button></div>}><span>{state.roadmap[lesson.id]?.depth} · {lesson.duration} · target capability: {lesson.capability}</span></PageIntro>
    <section className="sb-reading"><span>{String(currentIndex + 1).padStart(2, '0')}</span><div><h2>{context.heading}</h2>{lesson.id === CURRENT_LESSON_ID && <p>{TOPIC_BRIEF.problem}</p>}<p>{context.explanation}</p><aside><strong>Evidence target</strong><p>{context.evidence}</p></aside></div></section>
    {lesson.id === CURRENT_LESSON_ID ? <section className="sb-code" id="sb-lesson-artifact"><header><span><Code2 size={17} /> ReservationService.java</span><Button tone="quiet" onClick={() => dispatch({ type: 'RESET_CODE' })}><RotateCcw size={15} /> Reset</Button></header><label className="sb-sr-only" htmlFor="sb-code">Java code</label><textarea id="sb-code" value={state.codeDraft} onChange={e => dispatch({ type: 'SET_CODE', value: e.target.value })} spellCheck={false} />
      <footer><p>{SIMULATION_LIMITATION}</p><div><Button tone="secondary" onClick={() => dispatch({ type: 'RUN_CHECKS' })}><Play size={16} /> Run static checks</Button><Button onClick={() => dispatch({ type: 'SUBMIT_CODE' })}><ShieldCheck size={16} /> Submit evidence</Button></div></footer>
      <div className="sb-output" aria-live="polite"><header><strong>Static check output</strong><span>{state.runResult?.status ?? 'Not run'}</span></header>{state.runResult ? state.runResult.checks.map(check => <div key={check.label}><span className={check.passed ? 'is-pass' : 'is-fail'}>{check.passed ? <Check size={14} /> : <X size={14} />}</span><p><strong>{check.label}</strong><small>{check.detail}</small></p></div>) : <p>No process will run. These deterministic browser checks inspect text patterns only.</p>}</div>
    </section> : <section className="sb-checkpoint-note" id="sb-lesson-artifact"><FileText size={22} /><div><strong>Reading checkpoint</strong><p>This lesson has no runnable artifact in the selected local fixture. Continue through the sequenced curriculum or use the roadmap to change its depth and inferred state.</p></div></section>}
  </article><TopicTools /><ClassroomProgress navigate={navigate} previous={previousLesson?.title ?? 'Course roadmap'} previousTarget={previousLesson ? undefined : 'learn-roadmap'} onPrevious={previousLesson ? () => selectLesson(previousLesson.id) : undefined} next={nextLesson?.title ?? 'Guided practice'} nextTarget={nextLesson ? undefined : 'practice'} onNext={nextLesson ? () => selectLesson(nextLesson.id) : undefined} /></Classroom>
}

function TopicTools() {
  const { state, dispatch } = useLearningState()
  return <Tabs.Root id="sb-lesson-tools" defaultValue="notes" className="sb-tools"><Tabs.List aria-label="Secondary lesson tools"><Tabs.Trigger value="notes"><NotebookPen size={16} /> Notes</Tabs.Trigger><Tabs.Trigger value="resources"><BookOpen size={16} /> Resources</Tabs.Trigger><Tabs.Trigger value="help"><HelpCircle size={16} /> Help</Tabs.Trigger></Tabs.List><Tabs.Content value="notes"><label htmlFor="sb-notes">Goal notebook · user entry</label><textarea id="sb-notes" value={state.codeNotes} onChange={e => dispatch({ type: 'SET_NOTES', value: e.target.value })} /></Tabs.Content><Tabs.Content value="resources"><a href={TOPIC_BRIEF.sourceUrl} target="_blank" rel="noreferrer"><FileText size={18} /><span><strong>{TOPIC_BRIEF.source}</strong><small>Official source · opens a new tab</small></span><ArrowRight size={16} /></a></Tabs.Content><Tabs.Content value="help"><div className="sb-empty"><MessageSquareText /><strong>Topic help is unavailable in this static presentation</strong><span>No provider or network request is configured.</span></div></Tabs.Content></Tabs.Root>
}

function InterviewHub({ navigate, mode }: PageProps & { mode?: InterviewMode }) {
  const { state, dispatch } = useLearningState()
  const choices = [
    { title: 'Refresher', text: 'Review the message delivery contract and evidence gaps.', meta: 'Focused reading', Icon: BookOpen, target: 'topic-studio', lessonId: 'delivery-contract', hubMode: 'refresher' as InterviewMode },
    { title: 'Question bank', text: 'Choose a scenario without completing the Learn path.', meta: '2 fixture questions', Icon: HelpCircle, target: 'practice', hubMode: 'questions' as InterviewMode },
    { title: 'Guided practice', text: 'Request a hint, submit, inspect feedback, and repair.', meta: 'Hints on request', Icon: Code2, target: 'practice' },
    { title: 'Mock interview', text: state.mock.status === 'paused' ? 'Resume the exact locally saved draft.' : 'Answer without hints, rubrics, or evaluation until completion.', meta: state.mock.status === 'paused' ? 'Paused' : 'Neutral while active', Icon: MessageSquareText, target: 'mock' },
  ]
  const activeChoice = mode ? choices.find((choice) => choice.hubMode === mode) : undefined
  const openChoice = (choice: (typeof choices)[number], asMode?: InterviewMode) => {
    if (choice.lessonId) dispatch({ type: 'SELECT_LESSON', lessonId: choice.lessonId })
    if (asMode) { navigate('interview-hub', asMode); return }
    if (choice.title === 'Mock interview' && state.mock.status === 'paused') dispatch({ type: 'RESUME_MOCK' })
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
  const { state, dispatch } = useLearningState()
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
    <section className="sb-report-next" aria-labelledby="sb-report-next-title"><div><span className="sb-eyebrow">{nextAction.eyebrow}</span><h2 id="sb-report-next-title">{nextAction.title}</h2><p>{nextAction.detail}</p></div><Button onClick={() => { if ('lessonId' in nextAction) dispatch({ type: 'SELECT_LESSON', lessonId: nextAction.lessonId }); navigate(nextAction.target) }}>{nextAction.label} <ArrowRight size={16} /></Button></section>
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
