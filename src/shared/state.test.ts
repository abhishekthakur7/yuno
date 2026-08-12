import { REFERENCE_CODE } from './model'
import { createInitialState, learningReducer } from './state'

describe('shared learner behavior', () => {
  it('keeps static fixture results separate from server-backed evidence', () => {
    let state = createInitialState()
    state = learningReducer(state, { type: 'SET_CODE', value: REFERENCE_CODE })
    state = learningReducer(state, { type: 'RUN_CHECKS' })
    expect(state.runResult?.status).toBe('passed')
    expect(state).not.toHaveProperty('evidence')
  })

  it('does not retain interview state in the browser reducer', () => {
    expect(createInitialState()).not.toHaveProperty('mock')
  })

})
