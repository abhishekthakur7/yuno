import { queryOptions } from '@tanstack/react-query'

import { client } from './client'
import { ApiError } from './queries'
import type { components } from './schema'

type Disclosure = components['schemas']['DisclosureResponse']

function failure(error: components['schemas']['ErrorResponse'] | undefined, status: number, fallback: string): never {
  throw new ApiError(error?.message ?? fallback, status)
}

export function disclosuresQueryOptions() {
  return queryOptions({
    queryKey: ['disclosures'],
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/disclosures')
      if (error || !data) failure(error, response.status, 'Network disclosures could not be loaded.')
      return data
    },
  })
}

export function providerCapabilitiesQueryOptions() {
  return queryOptions({
    queryKey: ['provider-capabilities'],
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/provider-capabilities')
      if (error || !data) failure(error, response.status, 'Provider capabilities could not be loaded.')
      return data
    },
  })
}

export async function acceptDisclosure(disclosure: Disclosure): Promise<Disclosure> {
  const { data, error, response } = await client.POST('/api/v1/disclosures/{category}/accept', {
    params: { path: { category: disclosure.category } },
    body: { disclosure_version: disclosure.disclosure_version },
  })
  if (error || !data) failure(error, response.status, 'The network disclosure could not be accepted.')
  return data
}

export async function revokeDisclosure(disclosure: Disclosure): Promise<Disclosure> {
  const { data, error, response } = await client.POST('/api/v1/disclosures/{category}/revoke', {
    params: { path: { category: disclosure.category }, query: { disclosure_version: disclosure.disclosure_version } },
  })
  if (error || !data) failure(error, response.status, 'The network disclosure could not be revoked.')
  return data
}
