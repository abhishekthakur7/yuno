import { createContext, useContext, useEffect, useMemo, useReducer, type Dispatch, type ReactNode } from 'react'
import {
  ALL_LESSONS,
  CURRICULUM_MODULES,
  CURRENT_LESSON_ID,
  MOCK_CURRENT_QUESTION,
  MOCK_FIXTURE_DRAFT,
  MOCK_PRIOR_TURNS,
  PRACTICE_QUESTIONS,
  STARTER_CODE,
  type Depth,
  type KnowledgeState,
} from './model'

export interface RoadmapChoice {
  id: string
  depth: Depth
  learnerState: KnowledgeState
  skipped: boolean
}

export interface RunCheck {
  label: string
  passed: boolean
  detail: string
}

export interface RunResult {
  status: 'passed' | 'needs-work'
  checks: readonly RunCheck[]
}

export interface EvidenceRecord {
  id: string
  artifact: string
  kind: 'static-review'
  conclusion: string
  limitation: string
}

export interface PracticeAttempt {
  id: string
  questionId: string
  answer: string
  facts: readonly string[]
  tradeoffs: readonly string[]
}

export interface MockTurn {
  id: string
  question: string
  answer: string
}

export interface LearningState {
  version: 1
  onboarding: {
    path: 'Learn' | 'Interview Prep'
    target: 'Mid-level' | 'Senior' | 'Staff'
    goalName: string
    approved: boolean
  }
  currentLessonId: string
  roadmapOrder: readonly string[]
  roadmap: Readonly<Record<string, RoadmapChoice>>
  codeDraft: string
  codeNotes: string
  runResult: RunResult | null
  evidence: readonly EvidenceRecord[]
  practice: {
    questionIndex: number
    draft: string
    hintRequested: boolean
    mode: 'answering' | 'feedback'
    attempts: readonly PracticeAttempt[]
  }
  mock: {
    status: 'active' | 'paused' | 'completed'
    draft: string
    priorTurns: readonly MockTurn[]
    completedTurns: readonly MockTurn[]
    reportKind: 'fixture-evaluation' | 'transcript-only' | null
  }
}

type OnboardingField = 'path' | 'target' | 'goalName'

export type LearningAction =
  | { type: 'SET_ONBOARDING'; field: OnboardingField; value: string }
  | { type: 'APPROVE_ROADMAP' }
  | { type: 'SELECT_LESSON'; lessonId: string }
  | { type: 'SET_DEPTH'; lessonId: string; depth: Depth }
  | { type: 'SET_LEARNER_STATE'; lessonId: string; learnerState: KnowledgeState }
  | { type: 'TOGGLE_SKIP'; lessonId: string }
  | { type: 'MOVE_LESSON'; lessonId: string; direction: -1 | 1 }
  | { type: 'SET_CODE'; value: string }
  | { type: 'SET_NOTES'; value: string }
  | { type: 'RUN_CHECKS' }
  | { type: 'RESET_CODE' }
  | { type: 'SUBMIT_CODE' }
  | { type: 'SET_PRACTICE_DRAFT'; value: string }
  | { type: 'REQUEST_HINT' }
  | { type: 'SUBMIT_PRACTICE' }
  | { type: 'START_REPAIR' }
  | { type: 'CONTINUE_PRACTICE' }
  | { type: 'SET_MOCK_DRAFT'; value: string }
  | { type: 'SAFE_EXIT_MOCK' }
  | { type: 'RESUME_MOCK' }
  | { type: 'COMPLETE_MOCK' }
  | { type: 'RESET_LEARNING_STATE' }

function createRoadmap(): Readonly<Record<string, RoadmapChoice>> {
  return Object.fromEntries(ALL_LESSONS.map((lesson) => [lesson.id, {
    id: lesson.id,
    depth: lesson.recommendedDepth,
    learnerState: lesson.state,
    skipped: false,
  }]))
}

export function createInitialState(): LearningState {
  return {
    version: 1,
    onboarding: {
      path: 'Learn',
      target: 'Senior',
      goalName: '',
      approved: false,
    },
    currentLessonId: CURRENT_LESSON_ID,
    roadmapOrder: ALL_LESSONS.map((lesson) => lesson.id),
    roadmap: createRoadmap(),
    codeDraft: STARTER_CODE,
    codeNotes: 'Assumption: the ledger and reservation write share one database boundary.',
    runResult: null,
    evidence: [],
    practice: {
      questionIndex: 0,
      draft: '',
      hintRequested: false,
      mode: 'answering',
      attempts: [],
    },
    mock: {
      status: 'active',
      draft: '',
      priorTurns: MOCK_PRIOR_TURNS.map((turn) => ({ ...turn })),
      completedTurns: [],
      reportKind: null,
    },
  }
}

function replaceRoadmapChoice(state: LearningState, lessonId: string, next: Partial<RoadmapChoice>): LearningState {
  const current = state.roadmap[lessonId]
  if (!current) return state
  const updated = { ...current, ...next }
  if (Object.entries(next).every(([key, value]) => current[key as keyof RoadmapChoice] === value)) return state
  return {
    ...state,
    onboarding: { ...state.onboarding, approved: false },
    roadmap: { ...state.roadmap, [lessonId]: updated },
  }
}

export function activeRoadmapLessonIds(state: LearningState): readonly string[] {
  return state.roadmapOrder.filter((lessonId) => state.roadmap[lessonId] && !state.roadmap[lessonId]?.skipped)
}

function adjacentActiveLessonId(state: LearningState, lessonId: string): string | null {
  const index = state.roadmapOrder.indexOf(lessonId)
  if (index < 0) return activeRoadmapLessonIds(state)[0] ?? null
  for (let offset = 1; offset < state.roadmapOrder.length; offset += 1) {
    const next = state.roadmapOrder[index + offset]
    if (next && state.roadmap[next] && !state.roadmap[next]?.skipped) return next
    const previous = state.roadmapOrder[index - offset]
    if (previous && state.roadmap[previous] && !state.roadmap[previous]?.skipped) return previous
  }
  return null
}

export function evaluateCode(code: string): RunResult {
  const checks: RunCheck[] = [
    {
      label: 'Carries a stable request key',
      passed: /requestId|idempotencyKey/.test(code),
      detail: 'The duplicate decision needs a durable key that survives redelivery.',
    },
    {
      label: 'Removes check-then-write as the race arbiter',
      passed: /putIfAbsent|insertIfAbsent|unique|compareAndSet/.test(code),
      detail: 'A prior read may optimize, but an atomic operation must decide concurrent duplicates.',
    },
    {
      label: 'Returns the winning durable decision',
      passed: /orElse|existing|winner|saved/.test(code),
      detail: 'The losing consumer should reuse the already recorded outcome.',
    },
  ]
  return { status: checks.every((check) => check.passed) ? 'passed' : 'needs-work', checks }
}

function practiceFeedback(answer: string): Pick<PracticeAttempt, 'facts' | 'tradeoffs'> {
  const namesDurableGuard = /idempoten|unique|dedup|atomic/i.test(answer)
  return {
    facts: namesDurableGuard
      ? ['The answer names a durable duplicate guard for the commit-before-acknowledgement window.', 'SQS standard delivery can repeat, so acknowledgement alone is not the correctness boundary.']
      : ['The failure window is identified, but the answer does not yet name a durable duplicate guard.', 'Acknowledgement can be lost after the business commit, allowing the same message to return.'],
    tradeoffs: [
      'A unique key plus atomic write is direct, but its retention horizon and contention behavior must be explicit.',
      'An outbox helps publish downstream work atomically; by itself it does not deduplicate the incoming command.',
    ],
  }
}

export function learningReducer(state: LearningState, action: LearningAction): LearningState {
  switch (action.type) {
    case 'SET_ONBOARDING': {
      if (action.field === 'path' && (action.value === 'Learn' || action.value === 'Interview Prep')) return { ...state, onboarding: { ...state.onboarding, path: action.value, approved: false } }
      if (action.field === 'target' && (action.value === 'Mid-level' || action.value === 'Senior' || action.value === 'Staff')) return { ...state, onboarding: { ...state.onboarding, target: action.value, approved: false } }
      if (action.field === 'goalName') return { ...state, onboarding: { ...state.onboarding, goalName: action.value, approved: false } }
      return state
    }
    case 'APPROVE_ROADMAP':
      return { ...state, onboarding: { ...state.onboarding, approved: true } }
    case 'SELECT_LESSON': {
      const choice = state.roadmap[action.lessonId]
      if (!choice) return state
      if (!choice.skipped) return { ...state, currentLessonId: action.lessonId }
      return {
        ...state,
        currentLessonId: action.lessonId,
        onboarding: { ...state.onboarding, approved: false },
        roadmap: { ...state.roadmap, [action.lessonId]: { ...choice, skipped: false } },
      }
    }
    case 'SET_DEPTH':
      return replaceRoadmapChoice(state, action.lessonId, { depth: action.depth })
    case 'SET_LEARNER_STATE':
      return replaceRoadmapChoice(state, action.lessonId, { learnerState: action.learnerState })
    case 'TOGGLE_SKIP': {
      const current = state.roadmap[action.lessonId]
      if (!current) return state
      const next = replaceRoadmapChoice(state, action.lessonId, { skipped: !current.skipped })
      if (current.skipped || action.lessonId !== state.currentLessonId) return next
      return { ...next, currentLessonId: adjacentActiveLessonId(next, action.lessonId) ?? state.currentLessonId }
    }
    case 'MOVE_LESSON': {
      const order = [...state.roadmapOrder]
      const index = order.indexOf(action.lessonId)
      const target = index + action.direction
      if (index < 0 || target < 0 || target >= order.length) return state
      const swap = order[target]
      if (!swap) return state
      const sourceModule = CURRICULUM_MODULES.find((module) => module.lessons.some((lesson) => lesson.id === action.lessonId))
      const targetModule = CURRICULUM_MODULES.find((module) => module.lessons.some((lesson) => lesson.id === swap))
      if (!sourceModule || sourceModule.id !== targetModule?.id) return state
      order[target] = action.lessonId
      order[index] = swap
      return { ...state, onboarding: { ...state.onboarding, approved: false }, roadmapOrder: order }
    }
    case 'SET_CODE':
      return { ...state, codeDraft: action.value, runResult: null }
    case 'SET_NOTES':
      return { ...state, codeNotes: action.value }
    case 'RUN_CHECKS':
      return { ...state, runResult: evaluateCode(state.codeDraft) }
    case 'RESET_CODE':
      return { ...state, codeDraft: STARTER_CODE, runResult: null }
    case 'SUBMIT_CODE': {
      if (!state.codeDraft.trim()) return state
      const result = evaluateCode(state.codeDraft)
      const evidence: EvidenceRecord = {
        id: `evidence-${state.evidence.length + 1}`,
        artifact: state.codeDraft,
        kind: 'static-review',
        conclusion: result.status === 'passed'
          ? 'Static fixture checks find an explicit atomic duplicate boundary.'
          : 'Static fixture checks still find an unresolved duplicate race.',
        limitation: 'Static browser review only; no Java or AWS runtime behavior was executed.',
      }
      return { ...state, runResult: result, evidence: [...state.evidence, evidence] }
    }
    case 'SET_PRACTICE_DRAFT':
      return { ...state, practice: { ...state.practice, draft: action.value } }
    case 'REQUEST_HINT':
      return { ...state, practice: { ...state.practice, hintRequested: true } }
    case 'SUBMIT_PRACTICE': {
      const answer = state.practice.draft.trim()
      const question = PRACTICE_QUESTIONS[state.practice.questionIndex]
      if (!answer || !question) return state
      const feedback = practiceFeedback(answer)
      const attempt: PracticeAttempt = {
        id: `attempt-${state.practice.attempts.length + 1}`,
        questionId: question.id,
        answer,
        ...feedback,
      }
      return { ...state, practice: { ...state.practice, mode: 'feedback', attempts: [...state.practice.attempts, attempt] } }
    }
    case 'START_REPAIR': {
      const latest = state.practice.attempts.at(-1)
      return { ...state, practice: { ...state.practice, mode: 'answering', draft: latest?.answer ?? '', hintRequested: false } }
    }
    case 'CONTINUE_PRACTICE':
      return { ...state, practice: { ...state.practice, questionIndex: Math.min(state.practice.questionIndex + 1, PRACTICE_QUESTIONS.length - 1), draft: '', hintRequested: false, mode: 'answering' } }
    case 'SET_MOCK_DRAFT':
      return state.mock.status === 'completed' ? state : { ...state, mock: { ...state.mock, draft: action.value } }
    case 'SAFE_EXIT_MOCK':
      return { ...state, mock: { ...state.mock, status: 'paused' } }
    case 'RESUME_MOCK':
      return state.mock.status === 'completed' ? state : { ...state, mock: { ...state.mock, status: 'active' } }
    case 'COMPLETE_MOCK': {
      if (state.mock.status === 'completed' || !state.mock.draft.trim()) return state
      const completedTurn: MockTurn = { id: 'mock-turn-3', question: MOCK_CURRENT_QUESTION, answer: state.mock.draft }
      const reportKind = state.mock.draft === MOCK_FIXTURE_DRAFT ? 'fixture-evaluation' : 'transcript-only'
      return { ...state, mock: { ...state.mock, status: 'completed', completedTurns: [...state.mock.priorTurns, completedTurn], reportKind } }
    }
    case 'RESET_LEARNING_STATE':
      return createInitialState()
  }
}

interface LearningContextValue {
  state: LearningState
  dispatch: Dispatch<LearningAction>
}

const LearningContext = createContext<LearningContextValue | null>(null)

export const LEARNING_STORAGE_KEY = 'yuno.learning.state.v1'
export function learningStorageKey(scope: string): string {
  return `${LEARNING_STORAGE_KEY}.${encodeURIComponent(scope)}`
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

function hydrateLearningState(value: unknown, initial = createInitialState()): LearningState | null {
  if (!isRecord(value) || value.version !== 1) return null

  const onboarding = isRecord(value.onboarding) ? value.onboarding : {}
  const practice = isRecord(value.practice) ? value.practice : {}
  const mock = isRecord(value.mock) ? value.mock : {}
  const roadmap = isRecord(value.roadmap) ? value.roadmap : {}
  const hydratedRoadmap = { ...initial.roadmap }
  for (const [lessonId, rawChoice] of Object.entries(roadmap)) {
    const fallback = initial.roadmap[lessonId]
    if (!fallback || !isRecord(rawChoice)) continue
    hydratedRoadmap[lessonId] = {
      id: fallback.id,
      depth: rawChoice.depth === 'Essential' || rawChoice.depth === 'Implementation' || rawChoice.depth === 'Production' || rawChoice.depth === 'Interview'
        ? rawChoice.depth
        : fallback.depth,
      learnerState: rawChoice.learnerState === 'likely known' || rawChoice.learnerState === 'partial' || rawChoice.learnerState === 'unverified' || rawChoice.learnerState === 'new'
        ? rawChoice.learnerState
        : fallback.learnerState,
      skipped: typeof rawChoice.skipped === 'boolean' ? rawChoice.skipped : fallback.skipped,
    }
  }

  const attempts = Array.isArray(practice.attempts)
    ? practice.attempts.filter((item): item is PracticeAttempt => isRecord(item)
      && typeof item.id === 'string'
      && typeof item.questionId === 'string'
      && typeof item.answer === 'string'
      && isStringArray(item.facts)
      && isStringArray(item.tradeoffs))
    : initial.practice.attempts
  const isMockTurn = (item: unknown): item is MockTurn => isRecord(item)
    && typeof item.id === 'string'
    && typeof item.question === 'string'
    && typeof item.answer === 'string'
  const hydrateTurns = (value: unknown, fallback: readonly MockTurn[]): readonly MockTurn[] => Array.isArray(value)
    && value.every(isMockTurn)
    ? value
    : fallback
  const evidence = Array.isArray(value.evidence)
    ? value.evidence.filter((item): item is EvidenceRecord => isRecord(item)
      && typeof item.id === 'string'
      && typeof item.artifact === 'string'
      && item.kind === 'static-review'
      && typeof item.conclusion === 'string'
      && typeof item.limitation === 'string')
    : initial.evidence
  const rawRunResult = value.runResult
  const runResult = rawRunResult === null
    ? null
    : isRecord(rawRunResult)
      && (rawRunResult.status === 'passed' || rawRunResult.status === 'needs-work')
      && Array.isArray(rawRunResult.checks)
      && rawRunResult.checks.every((check) => isRecord(check)
        && typeof check.label === 'string'
        && typeof check.passed === 'boolean'
        && typeof check.detail === 'string')
        ? rawRunResult as unknown as RunResult
        : initial.runResult
  const persistedOrder = isStringArray(value.roadmapOrder)
    ? value.roadmapOrder.filter((id, index, order) => Boolean(hydratedRoadmap[id]) && order.indexOf(id) === index)
    : []
  const roadmapOrder = [...persistedOrder, ...initial.roadmapOrder.filter((id) => !persistedOrder.includes(id))]

  return {
    version: 1,
    onboarding: {
      path: onboarding.path === 'Learn' || onboarding.path === 'Interview Prep' ? onboarding.path : initial.onboarding.path,
      target: onboarding.target === 'Mid-level' || onboarding.target === 'Senior' || onboarding.target === 'Staff' ? onboarding.target : initial.onboarding.target,
      goalName: typeof onboarding.goalName === 'string' ? onboarding.goalName : initial.onboarding.goalName,
      approved: typeof onboarding.approved === 'boolean' ? onboarding.approved : initial.onboarding.approved,
    },
    currentLessonId: typeof value.currentLessonId === 'string' && hydratedRoadmap[value.currentLessonId] ? value.currentLessonId : initial.currentLessonId,
    roadmapOrder,
    roadmap: hydratedRoadmap,
    codeDraft: typeof value.codeDraft === 'string' ? value.codeDraft : initial.codeDraft,
    codeNotes: typeof value.codeNotes === 'string' ? value.codeNotes : initial.codeNotes,
    runResult,
    evidence,
    practice: {
      questionIndex: typeof practice.questionIndex === 'number' && Number.isInteger(practice.questionIndex) && practice.questionIndex >= 0 && practice.questionIndex < PRACTICE_QUESTIONS.length ? practice.questionIndex : initial.practice.questionIndex,
      draft: typeof practice.draft === 'string' ? practice.draft : initial.practice.draft,
      hintRequested: typeof practice.hintRequested === 'boolean' ? practice.hintRequested : initial.practice.hintRequested,
      mode: practice.mode === 'answering' || practice.mode === 'feedback' ? practice.mode : initial.practice.mode,
      attempts,
    },
    mock: {
      status: mock.status === 'active' || mock.status === 'paused' || mock.status === 'completed' ? mock.status : initial.mock.status,
      draft: typeof mock.draft === 'string' ? mock.draft : initial.mock.draft,
      priorTurns: hydrateTurns(mock.priorTurns, initial.mock.priorTurns),
      completedTurns: hydrateTurns(mock.completedTurns, initial.mock.completedTurns),
      reportKind: mock.reportKind === 'fixture-evaluation' || mock.reportKind === 'transcript-only' || mock.reportKind === null ? mock.reportKind : initial.mock.reportKind,
    },
  }
}

function loadState(storageKey: string): LearningState {
  const initial = createInitialState()
  const keepCurrentLessonActive = (loaded: LearningState): LearningState => {
    if (!loaded.roadmap[loaded.currentLessonId]?.skipped) return loaded
    return {
      ...loaded,
      currentLessonId: adjacentActiveLessonId(loaded, loaded.currentLessonId) ?? loaded.currentLessonId,
    }
  }
  const parse = (raw: string | null): unknown => {
    if (!raw) return null
    try { return JSON.parse(raw) as unknown } catch { return null }
  }
  const current = hydrateLearningState(parse(window.localStorage.getItem(storageKey)), initial)
  if (current) return keepCurrentLessonActive(current)

  return initial
}

function LearningStateStore({ children, storageKey }: { children: ReactNode; storageKey: string }) {
  const [state, dispatch] = useReducer(learningReducer, storageKey, loadState)
  useEffect(() => {
    window.localStorage.setItem(storageKey, JSON.stringify(state))
  }, [state, storageKey])
  const value = useMemo(() => ({ state, dispatch }), [state])
  return <LearningContext.Provider value={value}>{children}</LearningContext.Provider>
}

export function LearningStateProvider({ children, scope = 'setup' }: { children: ReactNode; scope?: string }) {
  const storageKey = learningStorageKey(scope)
  return <LearningStateStore key={storageKey} storageKey={storageKey}>{children}</LearningStateStore>
}

export function useLearningState(): LearningContextValue {
  const value = useContext(LearningContext)
  if (!value) throw new Error('useLearningState must be used inside LearningStateProvider')
  return value
}

export function currentPracticeQuestion(state: LearningState) {
  return PRACTICE_QUESTIONS[state.practice.questionIndex] ?? PRACTICE_QUESTIONS[0]
}

export function currentRoadmapChoice(state: LearningState): RoadmapChoice {
  return state.roadmap[CURRENT_LESSON_ID] ?? {
    id: CURRENT_LESSON_ID,
    depth: 'Implementation',
    learnerState: 'partial',
    skipped: false,
  }
}
