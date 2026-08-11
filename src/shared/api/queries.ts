import { queryOptions } from '@tanstack/react-query'

import { client } from './client'

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function healthQueryOptions() {
  return queryOptions({
    queryKey: ['health'],
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/health')
      if (error || !data) {
        throw new ApiError(error?.message ?? 'Failed to load health status', response.status)
      }
      return data
    },
  })
}

export function canonicalVersionsQueryOptions() {
  return queryOptions({
    queryKey: ['canonical', 'versions'],
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/canonical/versions')
      if (error || !data) throw new ApiError(error?.message ?? 'Failed to load canonical versions', response.status)
      return data
    },
  })
}
