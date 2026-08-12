import { createContext, useContext, useEffect, useMemo, useReducer, type Dispatch, type ReactNode } from 'react'
import {
  MOCK_CURRENT_QUESTION,
  MOCK_FIXTURE_DRAFT,
  MOCK_PRIOR_TURNS,
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

export interface MockTurn {
  id: string
  question: string
  answer: string
}

export interface LearningState {
  version: 1
  codeDraft: string
  runResult: RunResult | null
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
  | { type: 'RUN_CHECKS' }
  | { type: 'RESET_CODE' }
  | { type: 'SET_MOCK_DRAFT'; value: string }
  | { type: 'SAFE_EXIT_MOCK' }
  | { type: 'RESUME_MOCK' }
  | { type: 'COMPLETE_MOCK' }
  | { type: 'RESET_LEARNING_STATE' }

export function createInitialState(): LearningState {
  return {
    version: 1,
    codeDraft: STARTER_CODE,
    runResult: null,
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

export function learningReducer(state: LearningState, action: LearningAction): LearningState {
  switch (action.type) {
    case 'SET_CODE':
      return { ...state, codeDraft: action.value, runResult: null }
    case 'RUN_CHECKS':
      return { ...state, runResult: evaluateCode(state.codeDraft) }
    case 'RESET_CODE':
      return { ...state, codeDraft: STARTER_CODE, runResult: null }
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

function hydratePersistedDrafts(value: unknown, initial = createInitialState()): LearningState | null {
  if (!isRecord(value) || value.version !== 1) return null

  const mock = isRecord(value.mock) ? value.mock : {}
  const isMockTurn = (item: unknown): item is MockTurn => isRecord(item)
    && typeof item.id === 'string'
    && typeof item.question === 'string'
    && typeof item.answer === 'string'
  const hydrateTurns = (value: unknown, fallback: readonly MockTurn[]): readonly MockTurn[] => Array.isArray(value)
    && value.every(isMockTurn)
    ? value
    : fallback
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
    runResult,
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
    runResult: state.runResult,
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
