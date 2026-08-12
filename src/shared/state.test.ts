import { MOCK_FIXTURE_DRAFT, REFERENCE_CODE } from './model'
import { createInitialState, learningReducer, persistedLearningDrafts } from './state'

describe('shared learner behavior', () => {
  it('keeps static fixture results separate from server-backed evidence', () => {
    let state = createInitialState()
    state = learningReducer(state, { type: 'SET_CODE', value: REFERENCE_CODE })
    state = learningReducer(state, { type: 'RUN_CHECKS' })
    expect(state.runResult?.status).toBe('passed')
    expect(state).not.toHaveProperty('evidence')
  })

  it('preserves the exact mock draft on safe exit and gates fixture evaluation', () => {
    let state = createInitialState()
    const exactDraft = 'My exact unfinished response.\nKeep spacing intact.'
    state = learningReducer(state, { type: 'SET_MOCK_DRAFT', value: exactDraft })
    state = learningReducer(state, { type: 'SAFE_EXIT_MOCK' })
    expect(state.mock.status).toBe('paused')
    expect(state.mock.draft).toBe(exactDraft)

    state = learningReducer(state, { type: 'RESUME_MOCK' })
    state = learningReducer(state, { type: 'COMPLETE_MOCK' })
    expect(state.mock.reportKind).toBe('transcript-only')

    state = createInitialState()
    expect(state.mock.draft).toBe('')
    state = learningReducer(state, { type: 'SET_MOCK_DRAFT', value: MOCK_FIXTURE_DRAFT })
    state = learningReducer(state, { type: 'COMPLETE_MOCK' })
    expect(state.mock.reportKind).toBe('fixture-evaluation')

    state = createInitialState()
    state = learningReducer(state, { type: 'SET_MOCK_DRAFT', value: `${MOCK_FIXTURE_DRAFT} ` })
    state = learningReducer(state, { type: 'COMPLETE_MOCK' })
    expect(state.mock.reportKind).toBe('transcript-only')
  })

  it('serializes only the bounded draft slices that remain browser-backed', () => {
    const persisted = persistedLearningDrafts(createInitialState())
    expect(Object.keys(persisted).sort()).toEqual([
      'codeDraft', 'mock', 'runResult', 'version',
    ])
    expect(persisted).not.toHaveProperty('onboarding')
    expect(persisted).not.toHaveProperty('roadmap')
    expect(persisted).not.toHaveProperty('roadmapOrder')
    expect(persisted).not.toHaveProperty('currentLessonId')
    expect(persisted).not.toHaveProperty('codeNotes')
  })

})
