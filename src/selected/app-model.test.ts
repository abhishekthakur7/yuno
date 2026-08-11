import { describe, expect, it } from 'vitest'
import { APP_PAGE_IDS, appHref, isAppPageId, isInterviewMode } from './app-model'

describe('selected application route contract', () => {
  it('keeps the exact 13 canonical page IDs', () => {
    expect(APP_PAGE_IDS).toEqual([
      'onboarding',
      'learn-roadmap',
      'topic-studio',
      'interview-hub',
      'practice',
      'mock',
      'reports',
      'evidence',
      'imports',
      'canonical-updates',
      'search',
      'jobs',
      'settings',
    ])
  })

  it('maps Home to root and canonical pages beneath /app', () => {
    expect(appHref('home')).toBe('/')
    expect(appHref('topic-studio')).toBe('/app/topic-studio')
    expect(isAppPageId('reports')).toBe(true)
    expect(isAppPageId('report')).toBe(false)
  })

  it('recognizes the interview hub mode query states', () => {
    expect(isInterviewMode('refresher')).toBe(true)
    expect(isInterviewMode('mock')).toBe(false)
  })
})
