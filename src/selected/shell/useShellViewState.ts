import { useQuery } from '@tanstack/react-query'

import { healthQueryOptions } from '../../shared/api/queries'
import type { ViewState } from '../../shared/view-state'

export interface ShellViewState {
  state: ViewState
  retry: () => void
}

// `/api/v1/health` returning 200 is IDK-101's confirmation the backend is available.
export function useShellViewState(): ShellViewState {
  const query = useQuery(healthQueryOptions())

  const state: ViewState = query.isError ? 'failure' : query.isPending ? 'loading' : 'ready'

  return {
    state,
    retry: () => {
      void query.refetch()
    },
  }
}
