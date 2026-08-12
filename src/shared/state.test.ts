import { createInitialState, learningReducer } from './state'

describe('shared learner behavior', () => {
  it('keeps only the editable draft in browser state', () => {
    let state = createInitialState()
    state = learningReducer(state, { type: 'SET_CODE', value: 'revised artifact' })
    expect(state.codeDraft).toBe('revised artifact')
    expect(state).not.toHaveProperty('runResult')
    expect(state).not.toHaveProperty('evidence')
  })

  it('does not retain interview state in the browser reducer', () => {
    expect(createInitialState()).not.toHaveProperty('mock')
  })

})
