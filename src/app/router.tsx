import { QueryClientProvider } from '@tanstack/react-query'
import { Outlet, RouterProvider, createRootRoute, createRoute, createRouter, notFound } from '@tanstack/react-router'
import LearningApp from '../selected/LearningApp'
import { isAppPageId, isInterviewMode, type InterviewMode, type InterviewSelection } from '../selected/app-model'
import { LearningStateProvider } from '../shared/state'
import { queryClient } from './query-client'
import { useProfileGoals } from '../shared/use-profile-goals'
import './root.css'

function MissingRoute() {
  return <main className="root-not-found"><div><h1>That learning view does not exist</h1><p>Return to your saved learning workspace.</p><a href="/">Open My learning</a></div></main>
}

const rootRoute = createRootRoute({ component: Outlet, notFoundComponent: MissingRoute })

function GoalScopedLearningState({ children }: { children: React.ReactNode }) {
  const { currentGoal } = useProfileGoals()
  return <LearningStateProvider scope={currentGoal?.id ?? 'setup'}>{children}</LearningStateProvider>
}

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: () => <GoalScopedLearningState><LearningApp page="home" /></GoalScopedLearningState>,
})

const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/$pageId',
  validateSearch: (search: Record<string, unknown>): { mode?: InterviewMode; bundleId?: string; bundleItemId?: string } => {
    const mode = isInterviewMode(search['mode']) ? search['mode'] : undefined
    const bundleId = typeof search['bundleId'] === 'string' && search['bundleId'].trim() ? search['bundleId'] : undefined
    const bundleItemId = typeof search['bundleItemId'] === 'string' && search['bundleItemId'].trim() ? search['bundleItemId'] : undefined
    return { ...(mode ? { mode } : {}), ...(bundleId && bundleItemId ? { bundleId, bundleItemId } : {}) }
  },
  beforeLoad: ({ params }) => { if (!isAppPageId(params.pageId)) throw notFound() },
  component: () => {
    const { pageId } = appRoute.useParams()
    // TanStack Router keeps unrecognised search params in location search rather than
    // stripping them, so re-narrow here: an unknown `?mode=` must still reach us as undefined.
    const search = appRoute.useSearch()
    const rawMode: unknown = search.mode
    const mode = isInterviewMode(rawMode) ? rawMode : undefined
    const selection: InterviewSelection | undefined = search.bundleId && search.bundleItemId
      ? { bundleId: search.bundleId, bundleItemId: search.bundleItemId }
      : undefined
    if (!isAppPageId(pageId)) return <MissingRoute />
    return <GoalScopedLearningState><LearningApp page={pageId} {...(mode ? { mode } : {})} {...(selection ? { selection } : {})} /></GoalScopedLearningState>
  },
})

const routeTree = rootRoute.addChildren([indexRoute, appRoute])
export const router = createRouter({ routeTree, defaultPreload: false, defaultNotFoundComponent: MissingRoute })

declare module '@tanstack/react-router' {
  interface Register { router: typeof router }
}

export function AppRouter() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
