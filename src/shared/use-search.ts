import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  rebuildSearchIndex,
  searchIndexStatusQueryOptions,
  searchQueryOptions,
  type SearchEntityType,
} from './api/search'

export function useSearch(goalId: string | null, query: string, types: SearchEntityType[] = []) {
  const queryClient = useQueryClient()
  const results = useQuery(searchQueryOptions(query, goalId, types))
  const status = useQuery(searchIndexStatusQueryOptions())
  const rebuild = useMutation({
    mutationFn: rebuildSearchIndex,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['search-index', 'status'] })
      await queryClient.invalidateQueries({ queryKey: ['search', goalId] })
    },
  })

  return { results, status, rebuild }
}
