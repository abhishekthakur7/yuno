import { createContext, useContext, useEffect, useMemo, useReducer, type Dispatch, type ReactNode } from 'react'
import {
  MOCK_CURRENT_QUESTION,
  MOCK_FIXTURE_DRAFT,
  MOCK_PRIOR_TURNS,
  PRACTICE_QUESTIONS,
  STARTER_CODE,
} from './model'

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

export type LearningAction =
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

export function createInitialState(): LearningState {
  return {
    version: 1,
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

function hydratePersistedDrafts(value: unknown, initial = createInitialState()): LearningState | null {
  if (!isRecord(value) || value.version !== 1) return null

  const practice = isRecord(value.practice) ? value.practice : {}
  const mock = isRecord(value.mock) ? value.mock : {}

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
  return {
    ...initial,
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
  const parse = (raw: string | null): unknown => {
    if (!raw) return null
    try { return JSON.parse(raw) as unknown } catch { return null }
  }
  const current = hydratePersistedDrafts(parse(window.localStorage.getItem(storageKey)), initial)
  if (current) return current

  return initial
}

export function persistedLearningDrafts(state: LearningState) {
  return {
    version: state.version,
    codeDraft: state.codeDraft,
    codeNotes: state.codeNotes,
    runResult: state.runResult,
    evidence: state.evidence,
    practice: state.practice,
    mock: state.mock,
  }
}

function LearningStateStore({ children, storageKey }: { children: ReactNode; storageKey: string }) {
  const [state, dispatch] = useReducer(learningReducer, storageKey, loadState)
  useEffect(() => {
    window.localStorage.setItem(storageKey, JSON.stringify(persistedLearningDrafts(state)))
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
