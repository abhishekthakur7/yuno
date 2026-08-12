import { createContext, useContext, useMemo, useReducer, type Dispatch, type ReactNode } from 'react'
import { STARTER_CODE } from './model'

export interface RunCheck {
  label: string
  passed: boolean
  detail: string
}

export interface RunResult {
  status: 'passed' | 'needs-work'
  checks: readonly RunCheck[]
}

export interface LearningState {
  version: 1
  codeDraft: string
  runResult: RunResult | null
}

export type LearningAction =
  | { type: 'SET_CODE'; value: string }
  | { type: 'RUN_CHECKS' }
  | { type: 'RESET_CODE' }
  | { type: 'RESET_LEARNING_STATE' }

export function createInitialState(): LearningState {
  return {
    version: 1,
    codeDraft: STARTER_CODE,
    runResult: null,
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
    case 'RESET_LEARNING_STATE':
      return createInitialState()
  }
}

interface LearningContextValue {
  state: LearningState
  dispatch: Dispatch<LearningAction>
}

const LearningContext = createContext<LearningContextValue | null>(null)

function LearningStateStore({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(learningReducer, undefined, createInitialState)
  const value = useMemo(() => ({ state, dispatch }), [state])
  return <LearningContext.Provider value={value}>{children}</LearningContext.Provider>
}

export function LearningStateProvider({ children, scope = 'setup' }: { children: ReactNode; scope?: string }) {
  void scope
  return <LearningStateStore>{children}</LearningStateStore>
}

export function useLearningState(): LearningContextValue {
  const value = useContext(LearningContext)
  if (!value) throw new Error('useLearningState must be used inside LearningStateProvider')
  return value
}
