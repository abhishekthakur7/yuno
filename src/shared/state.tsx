import { createContext, useContext, useMemo, useReducer, type Dispatch, type ReactNode } from 'react'
import { STARTER_CODE } from './model'

export interface LearningState {
  version: 1
  codeDraft: string
}

export type LearningAction =
  | { type: 'SET_CODE'; value: string }
  | { type: 'RESET_CODE' }
  | { type: 'RESET_LEARNING_STATE' }

export function createInitialState(): LearningState {
  return {
    version: 1,
    codeDraft: STARTER_CODE,
  }
}

export function learningReducer(state: LearningState, action: LearningAction): LearningState {
  switch (action.type) {
    case 'SET_CODE':
      return { ...state, codeDraft: action.value }
    case 'RESET_CODE':
      return { ...state, codeDraft: STARTER_CODE }
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
