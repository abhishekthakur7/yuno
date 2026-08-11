import { ALL_LESSONS, COURSE, CURRENT_LESSON_ID } from './model'

describe('learning journey fixture', () => {
  it('keeps the approved eleven-lesson technical journey', () => {
    expect(COURSE.modules).toHaveLength(4)
    expect(ALL_LESSONS).toHaveLength(11)
    expect(ALL_LESSONS.some((lesson) => lesson.id === CURRENT_LESSON_ID)).toBe(true)
  })

  it('contains long technical titles for responsive curriculum validation', () => {
    expect(Math.max(...ALL_LESSONS.map((lesson) => lesson.title.length))).toBeGreaterThan(80)
  })
})
