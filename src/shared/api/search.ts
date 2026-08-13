import { queryOptions } from '@tanstack/react-query'

import { client } from './client'
import { ApiError } from './queries'
import type { components } from './schema'

export type SearchEntityType = 'canonical-topic' | 'canonical-content' | 'generated-artifact' | 'notebook-entry' | 'evidence'

function failure(error: components['schemas']['ErrorResponse'] | undefined, status: number, fallback: string): never {
  throw new ApiError(error?.message ?? fallback, status)
}

export function searchQueryOptions(query: string, goalId: string | null, types: SearchEntityType[] = []) {
  return queryOptions({
    queryKey: ['search', goalId, query, types],
    enabled: Boolean(goalId && query),
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/search', {
        params: { query: { q: query, goal_id: goalId!, types: types.length ? types.join(',') : null } },
      })
      if (error || !data) failure(error, response.status, 'Search results could not be loaded.')
      return data
    },
  })
}

export function searchIndexStatusQueryOptions() {
  return queryOptions({
    queryKey: ['search-index', 'status'],
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/search-index/status')
      if (error || !data) failure(error, response.status, 'Search index status could not be loaded.')
      return data
    },
    refetchInterval: (query) => query.state.data?.status === 'rebuilding' ? 2_000 : false,
  })
}

export async function rebuildSearchIndex(): Promise<components['schemas']['JobRefResponse']> {
  const { data, error, response } = await client.POST('/api/v1/search-index/rebuild', {
    params: { header: { 'Idempotency-Key': crypto.randomUUID() } },
  })
  if (error || !data) failure(error, response.status, 'The search index rebuild could not be started.')
  return data
}
