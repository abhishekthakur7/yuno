import { QueryClientProvider } from '@tanstack/react-query'
import { Outlet, RouterProvider, createRootRoute, createRoute, createRouter, notFound } from '@tanstack/react-router'
import LearningApp from '../selected/LearningApp'
import { isAppPageId, isInterviewMode, type InterviewMode } from '../selected/app-model'
import { LearningStateProvider } from '../shared/state'
import { queryClient } from './query-client'
import './root.css'

function MissingRoute() {
  return <main className="root-not-found"><div><h1>That learning view does not exist</h1><p>Return to your saved learning workspace.</p><a href="/">Open My learning</a></div></main>
}

const rootRoute = createRootRoute({ component: Outlet, notFoundComponent: MissingRoute })

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: () => <LearningStateProvider><LearningApp page="home" /></LearningStateProvider>,
})

const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/$pageId',
  validateSearch: (search: Record<string, unknown>): { mode?: InterviewMode } => {
    return isInterviewMode(search['mode']) ? { mode: search['mode'] } : {}
  },
  beforeLoad: ({ params }) => { if (!isAppPageId(params.pageId)) throw notFound() },
  component: () => {
    const { pageId } = appRoute.useParams()
    // TanStack Router keeps unrecognised search params in location search rather than
    // stripping them, so re-narrow here: an unknown `?mode=` must still reach us as undefined.
    const rawMode: unknown = appRoute.useSearch().mode
    const mode = isInterviewMode(rawMode) ? rawMode : undefined
    if (!isAppPageId(pageId)) return <MissingRoute />
    return <LearningStateProvider><LearningApp page={pageId} {...(mode ? { mode } : {})} /></LearningStateProvider>
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
