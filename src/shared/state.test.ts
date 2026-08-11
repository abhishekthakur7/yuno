import { MOCK_FIXTURE_DRAFT, REFERENCE_CODE } from './model'
import { activeRoadmapLessonIds, createInitialState, learningReducer } from './state'

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

  it('requires an explicit onboarding approval and preserves roadmap choices', () => {
    let state = createInitialState()
    expect(state.onboarding.approved).toBe(false)
    state = learningReducer(state, { type: 'SET_DEPTH', lessonId: 'idempotency-retry', depth: 'Production' })
    state = learningReducer(state, { type: 'MOVE_LESSON', lessonId: 'idempotency-retry', direction: 1 })
    state = learningReducer(state, { type: 'APPROVE_ROADMAP' })
    expect(state.onboarding.approved).toBe(true)
    expect(state.roadmap['idempotency-retry']?.depth).toBe('Production')
    expect(state.roadmapOrder.indexOf('idempotency-retry')).toBeGreaterThan(2)
  })

  it('tracks the learner-selected lesson and keeps reordering within a section', () => {
    let state = createInitialState()
    state = learningReducer(state, { type: 'SELECT_LESSON', lessonId: 'observability' })
    expect(state.currentLessonId).toBe('observability')

    const before = state.roadmapOrder
    state = learningReducer(state, { type: 'MOVE_LESSON', lessonId: 'commit-window', direction: 1 })
    expect(state.roadmapOrder).toBe(before)
  })

  it('requires reapproval after onboarding inputs change', () => {
    let state = learningReducer(createInitialState(), { type: 'APPROVE_ROADMAP' })
    state = learningReducer(state, { type: 'SET_ONBOARDING', field: 'target', value: 'Staff' })
    expect(state.onboarding.approved).toBe(false)
  })

  it.each([
    { type: 'SET_DEPTH', lessonId: 'idempotency-retry', depth: 'Production' } as const,
    { type: 'SET_LEARNER_STATE', lessonId: 'idempotency-retry', learnerState: 'new' } as const,
    { type: 'TOGGLE_SKIP', lessonId: 'idempotency-retry' } as const,
    { type: 'MOVE_LESSON', lessonId: 'idempotency-retry', direction: 1 } as const,
  ])('requires reapproval after roadmap mutation $type', (action) => {
    const approved = learningReducer(createInitialState(), { type: 'APPROVE_ROADMAP' })
    expect(learningReducer(approved, action).onboarding.approved).toBe(false)
  })

  it('uses reordered non-skipped lessons for progression and moves current off a skipped lesson', () => {
    let state = createInitialState()
    state = learningReducer(state, { type: 'MOVE_LESSON', lessonId: 'idempotency-retry', direction: 1 })
    expect(activeRoadmapLessonIds(state).slice(2, 5)).toEqual(['atomic-write', 'idempotency-retry', 'delayed-duplicates'])

    state = learningReducer(state, { type: 'TOGGLE_SKIP', lessonId: 'idempotency-retry' })
    expect(state.currentLessonId).toBe('delayed-duplicates')
    expect(activeRoadmapLessonIds(state)).not.toContain('idempotency-retry')

    state = learningReducer(state, { type: 'SELECT_LESSON', lessonId: 'idempotency-retry' })
    expect(state.currentLessonId).toBe('idempotency-retry')
    expect(state.roadmap['idempotency-retry']?.skipped).toBe(false)
  })

  it('preserves onboarding source material without treating it as imported truth', () => {
    let state = createInitialState()
    state = learningReducer(state, { type: 'SET_ONBOARDING_SOURCE', value: '# Questions\n- What is the retry horizon?' })
    state = learningReducer(state, { type: 'APPROVE_ROADMAP' })
    expect(state.onboarding.sourceMaterial).toBe('# Questions\n- What is the retry horizon?')
    expect(state.evidence).toHaveLength(0)
  })
})
