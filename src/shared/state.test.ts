import { MOCK_FIXTURE_DRAFT, REFERENCE_CODE } from './model'
import { createInitialState, learningReducer, persistedLearningDrafts } from './state'

describe('shared learner behavior', () => {
  it('keeps exploratory Run separate from evidence-producing Submit', () => {
    let state = createInitialState()
    state = learningReducer(state, { type: 'SET_CODE', value: REFERENCE_CODE })
    state = learningReducer(state, { type: 'RUN_CHECKS' })
    expect(state.runResult?.status).toBe('passed')
    expect(state.evidence).toHaveLength(0)

    state = learningReducer(state, { type: 'SUBMIT_CODE' })
    expect(state.evidence).toHaveLength(1)
    expect(state.evidence[0]?.limitation).toContain('no Java or AWS runtime behavior')
  })

  it('reveals practice help only on request and feedback only after submit', () => {
    let state = createInitialState()
    expect(state.practice.hintRequested).toBe(false)
    expect(state.practice.attempts).toHaveLength(0)

    state = learningReducer(state, { type: 'REQUEST_HINT' })
    expect(state.practice.hintRequested).toBe(true)
    expect(state.practice.attempts).toHaveLength(0)

    state = learningReducer(state, { type: 'SET_PRACTICE_DRAFT', value: 'Use a unique idempotency key in the same atomic write.' })
    state = learningReducer(state, { type: 'SUBMIT_PRACTICE' })
    expect(state.practice.mode).toBe('feedback')
    expect(state.practice.attempts[0]?.facts).toHaveLength(2)
    expect(state.practice.attempts[0]?.tradeoffs).toHaveLength(2)

    state = learningReducer(state, { type: 'START_REPAIR' })
    state = learningReducer(state, { type: 'SET_PRACTICE_DRAFT', value: `${state.practice.draft} Bound its retention.` })
    state = learningReducer(state, { type: 'SUBMIT_PRACTICE' })
    expect(state.practice.attempts).toHaveLength(2)
    expect(state.practice.attempts[0]?.answer).not.toBe(state.practice.attempts[1]?.answer)
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
      'codeDraft', 'codeNotes', 'evidence', 'mock', 'practice', 'runResult', 'version',
    ])
    expect(persisted).not.toHaveProperty('onboarding')
    expect(persisted).not.toHaveProperty('roadmap')
    expect(persisted).not.toHaveProperty('roadmapOrder')
    expect(persisted).not.toHaveProperty('currentLessonId')
  })

})
