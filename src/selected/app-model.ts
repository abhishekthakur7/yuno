export const APP_PAGE_IDS = [
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
] as const

export type AppPageId = (typeof APP_PAGE_IDS)[number]
export type AppPage = 'home' | AppPageId

export const APP_PAGE_LABELS: Readonly<Record<AppPageId, string>> = {
  onboarding: 'Onboarding',
  'learn-roadmap': 'Learn roadmap',
  'topic-studio': 'Topic studio',
  'interview-hub': 'Interview prep',
  practice: 'Practice',
  mock: 'Mock interview',
  reports: 'Reports',
  evidence: 'Evidence',
  imports: 'Imports',
  'canonical-updates': 'Canonical updates',
  search: 'Search',
  jobs: 'Jobs',
  settings: 'Settings',
}

export function isAppPageId(value: string): value is AppPageId {
  return APP_PAGE_IDS.includes(value as AppPageId)
}

export function appHref(page: AppPage): string {
  return page === 'home' ? '/' : `/app/${page}`
}

export const INTERVIEW_MODES = ['refresher', 'questions'] as const
export type InterviewMode = (typeof INTERVIEW_MODES)[number]

export function isInterviewMode(value: unknown): value is InterviewMode {
  return typeof value === 'string' && (INTERVIEW_MODES as readonly string[]).includes(value)
}
