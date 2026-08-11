import { Outlet, RouterProvider, createRootRoute, createRoute, createRouter, notFound } from '@tanstack/react-router'
import LearningApp from '../selected/LearningApp'
import { isAppPageId } from '../selected/app-model'
import { LearningStateProvider } from '../shared/state'
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
  beforeLoad: ({ params }) => { if (!isAppPageId(params.pageId)) throw notFound() },
  component: () => {
    const { pageId } = appRoute.useParams()
    if (!isAppPageId(pageId)) return <MissingRoute />
    return <LearningStateProvider><LearningApp page={pageId} /></LearningStateProvider>
  },
})

const routeTree = rootRoute.addChildren([indexRoute, appRoute])
export const router = createRouter({ routeTree, defaultPreload: false, defaultNotFoundComponent: MissingRoute })

declare module '@tanstack/react-router' {
  interface Register { router: typeof router }
}

export function AppRouter() {
  return <RouterProvider router={router} />
}
