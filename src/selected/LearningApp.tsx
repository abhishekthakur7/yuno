import { useRef, useState, type ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { useNavigate } from '@tanstack/react-router'
import {
  ArrowLeft,
  BookOpen,
  BriefcaseBusiness,
  FileClock,
  FileSearch,
  History,
  Menu,
  RefreshCcw,
  Search,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Upload,
  X,
} from 'lucide-react'
import { useProfileGoals } from '../shared/use-profile-goals'
import { useRoadmap } from '../shared/use-roadmap'
import RouteView from './shell/RouteView'
import { useShellViewState } from './shell/useShellViewState'
import CorePageView, { type CorePage } from './core/CorePages'
import OperationalPageView, { type OperationalPage } from './operations/OperationalPages'
import { APP_PAGE_LABELS, isAppPageId, type AppPage, type InterviewMode } from './app-model'
import './app-shell.css'

const CORE_PAGES: readonly CorePage[] = ['home', 'onboarding', 'learn-roadmap', 'topic-studio', 'interview-hub', 'practice', 'mock', 'reports']

const utilityLinks: readonly { page: OperationalPage | 'reports'; label: string; description: string; icon: typeof Search }[] = [
  { page: 'reports', label: 'Reports', description: 'Conclusions and next actions', icon: FileSearch },
  { page: 'evidence', label: 'Evidence', description: 'Attempts, limits, and history', icon: ShieldCheck },
  { page: 'imports', label: 'Imports', description: 'Review untrusted notes and questions', icon: Upload },
  { page: 'canonical-updates', label: 'Canonical updates', description: 'Inspect opt-in curriculum changes', icon: RefreshCcw },
  { page: 'search', label: 'Search', description: 'Search this local learning set', icon: Search },
  { page: 'jobs', label: 'Jobs', description: 'Inspect local operation availability', icon: FileClock },
  { page: 'settings', label: 'Settings', description: 'Local profile, access, and data', icon: Settings },
]

function isCorePage(page: AppPage): page is CorePage {
  return CORE_PAGES.includes(page as CorePage)
}

function primaryGroup(page: AppPage): 'home' | 'learn' | 'interview' | 'tools' {
  if (page === 'home' || page === 'onboarding') return 'home'
  if (page === 'learn-roadmap' || page === 'topic-studio') return 'learn'
  if (page === 'interview-hub' || page === 'practice' || page === 'mock' || page === 'reports') return 'interview'
  return 'tools'
}

function navigateTo(navigate: ReturnType<typeof useNavigate>, target: AppPage): void {
  if (target === 'home') navigate({ to: '/' })
  else navigate({ to: '/app/$pageId', params: { pageId: target }, search: {} })
}

function GlobalHeader({ page }: { page: AppPage }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuTriggerRef = useRef<HTMLButtonElement>(null)
  const navigate = useNavigate()
  const group = primaryGroup(page)
  const go = (target: AppPage) => {
    setMenuOpen(false)
    navigateTo(navigate, target)
  }

  return (
    <>
      <header className="app-header">
        <button className="app-wordmark" onClick={() => go('home')} aria-label="Yuno home">
          <span className="app-mark" aria-hidden="true"><span /><span /><span /></span>
          <span>Yuno</span>
        </button>
        <nav className="app-primary-nav" aria-label="Primary navigation">
          <button className={group === 'home' ? 'is-active' : ''} aria-current={group === 'home' ? 'page' : undefined} onClick={() => go('home')}>My learning</button>
          <button className={group === 'learn' ? 'is-active' : ''} aria-current={group === 'learn' ? 'page' : undefined} onClick={() => go('learn-roadmap')}>Learn</button>
          <button className={group === 'interview' ? 'is-active' : ''} aria-current={group === 'interview' ? 'page' : undefined} onClick={() => go('interview-hub')}>Interview prep</button>
        </nav>
        <div className="app-header-actions">
          <button className="app-search-button" onClick={() => go('search')} aria-label="Search learning content"><Search size={18} /><span>Search</span></button>
          <button className={`app-menu-button ${group === 'tools' ? 'is-active' : ''}`} onClick={(event) => { menuTriggerRef.current = event.currentTarget; setMenuOpen(true) }} aria-haspopup="dialog"><SlidersHorizontal size={18} /><span>Tools</span></button>
          <span className="app-avatar" role="img" aria-label="Local learner">YU</span>
          <button className="app-mobile-menu" onClick={(event) => { menuTriggerRef.current = event.currentTarget; setMenuOpen(true) }} aria-label="Open navigation"><Menu size={21} /></button>
        </div>
      </header>
      <Dialog.Root open={menuOpen} onOpenChange={setMenuOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="app-menu-overlay" />
          <Dialog.Content className="app-nav-drawer" aria-describedby="app-menu-description" onCloseAutoFocus={(event) => { event.preventDefault(); menuTriggerRef.current?.focus() }}>
            <div className="app-drawer-head">
              <div><Dialog.Title>Workspace navigation</Dialog.Title><Dialog.Description id="app-menu-description">Learning stays primary; inspect operational tools deliberately.</Dialog.Description></div>
              <Dialog.Close className="app-icon-button" aria-label="Close navigation"><X size={20} /></Dialog.Close>
            </div>
            <nav className="app-drawer-nav" aria-label="Workspace destinations">
              <div className="app-drawer-group"><span>Learning</span>
                <button onClick={() => go('home')}><BookOpen size={18} /><span><strong>My learning</strong><small>Resume historical course state</small></span></button>
                <button onClick={() => go('learn-roadmap')}><History size={18} /><span><strong>Roadmap</strong><small>Inspect and control all lessons</small></span></button>
                <button onClick={() => go('interview-hub')}><BriefcaseBusiness size={18} /><span><strong>Interview prep</strong><small>Refresher, questions, practice, and mock</small></span></button>
                <button onClick={() => go('onboarding')}><SlidersHorizontal size={18} /><span><strong>Set up a goal</strong><small>Preview and approve a new roadmap</small></span></button>
              </div>
              <div className="app-drawer-group"><span>Inspect and operate</span>
                {utilityLinks.map((item) => <button key={item.page} className={page === item.page ? 'is-current' : ''} aria-current={page === item.page ? 'page' : undefined} onClick={() => go(item.page)}><item.icon size={18} /><span><strong>{item.label}</strong><small>{item.description}</small></span></button>)}
              </div>
            </nav>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  )
}

function CourseBand({ page }: { page: AppPage }) {
  const { currentGoal } = useProfileGoals()
  const roadmap = useRoadmap(currentGoal?.id ?? null)
  const navigate = useNavigate()
  const isInterview = page === 'interview-hub' || page === 'practice' || page === 'reports'
  const activeLessonIds = (roadmap.roadmap.data?.topics ?? []).filter(topic => !topic.is_skipped).map(topic => topic.stable_id)
  const position = currentGoal?.resume_position ? Math.max(0, activeLessonIds.indexOf(currentGoal.resume_position)) + 1 : 0
  return (
    <div className="app-course-band">
      <button className="app-course-back" onClick={() => navigateTo(navigate, isInterview ? 'interview-hub' : 'home')}><ArrowLeft size={16} /> {isInterview ? 'Interview prep' : 'My learning'}</button>
      <div className="app-course-name"><span>{isInterview ? 'Preparation workspace' : 'Current goal'}</span><strong>{currentGoal?.name ?? 'No current goal selected'}</strong></div>
      <div className="app-band-progress"><span>Position {position} of {activeLessonIds.length} active · evidence separate</span><div><span style={{ width: `${activeLessonIds.length ? (position / activeLessonIds.length) * 100 : 0}%` }} /></div></div>
    </div>
  )
}

function renderPage(page: AppPage, mode: InterviewMode | undefined, routerNavigate: ReturnType<typeof useNavigate>): ReactNode {
  const navigate = (target: string, targetMode?: InterviewMode) => {
    if (target === 'home') { routerNavigate({ to: '/' }); return }
    if (!isAppPageId(target)) return
    if (targetMode && target === 'interview-hub') routerNavigate({ to: '/app/$pageId', params: { pageId: target }, search: { mode: targetMode } })
    else routerNavigate({ to: '/app/$pageId', params: { pageId: target }, search: {} })
  }
  if (isCorePage(page)) return <CorePageView page={page} navigate={navigate} {...(mode ? { mode } : {})} />
  return <OperationalPageView page={page as OperationalPage} navigate={navigate} />
}

export default function LearningApp({ page, mode }: { page: AppPage; mode?: InterviewMode }) {
  const focusedMock = page === 'mock'
  const showCourseBand = page === 'learn-roadmap' || page === 'topic-studio' || page === 'interview-hub' || page === 'practice' || page === 'reports'
  const routerNavigate = useNavigate()
  const shell = useShellViewState()
  const label = page === 'home' ? 'My learning' : APP_PAGE_LABELS[page]
  return (
    <div className={`learning-app app-page-${page}`} data-app="yuno-learning" data-page={page} {...(mode ? { 'data-mode': mode } : {})}>
      {!focusedMock && <GlobalHeader page={page} />}
      {!focusedMock && showCourseBand && <CourseBand page={page} />}
      <RouteView state={shell.state} label={label} onRetry={shell.retry}>
        {renderPage(page, mode, routerNavigate)}
      </RouteView>
    </div>
  )
}
