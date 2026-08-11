import { QueryClient } from '@tanstack/react-query'

// retry: 1 (not the default 3) so a genuinely-down backend surfaces its
// `failure` view state quickly instead of retrying for several seconds.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
})
