import type { ReactNode } from 'react'

import type { ViewState } from '../../shared/view-state'
import './route-view.css'

export interface RouteViewProps {
  state: ViewState
  label: string
  onRetry?: () => void
  children: ReactNode
}

const COPY: Record<Exclude<ViewState, 'ready'>, { heading: (label: string) => string; description: string }> = {
  loading: {
    heading: (label) => `Loading ${label}`,
    description: 'Fetching the latest data for this page.',
  },
  empty: {
    heading: (label) => `No ${label} yet`,
    description: 'There is nothing to show here right now.',
  },
  stale: {
    heading: (label) => `${label} may be out of date`,
    description: "We're refreshing this page's data in the background.",
  },
  locked: {
    heading: (label) => `${label} is locked`,
    description: 'This page is not available until an earlier step is complete.',
  },
  unavailable: {
    heading: (label) => `${label} is unavailable`,
    description: 'This page cannot be reached right now.',
  },
  failure: {
    heading: (label) => `Couldn't load ${label}`,
    description: 'Something went wrong while loading this page.',
  },
}

export default function RouteView(props: RouteViewProps) {
  const { state, label, onRetry, children } = props

  if (state === 'ready') {
    return <>{children}</>
  }

  const copy = COPY[state]
  const showRetry = Boolean(onRetry) && (state === 'failure' || state === 'unavailable')

  return (
    <main className="app-route-state" data-route-state={state} aria-live="polite">
      <h1>{copy.heading(label)}</h1>
      <p>{copy.description}</p>
      {showRetry ? (
        <button type="button" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </main>
  )
}
