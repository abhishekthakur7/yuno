import { queryOptions } from '@tanstack/react-query'

import { client } from './client'
import { ApiError } from './queries'
import type { components } from './schema'

export type OwnerSettings = components['schemas']['OwnerSettingsResponse']
export type ProgressDisplay = OwnerSettings['progress_display']
export type OwnerSettingsPatch = components['schemas']['OwnerSettingsPatchRequest']

function failure(error: components['schemas']['ErrorResponse'] | undefined, status: number, message: string): never {
  throw new ApiError(error?.message ?? message, status)
}

export function settingsQueryOptions() {
  return queryOptions({
    queryKey: ['settings'],
    queryFn: async () => {
      const { data, error, response } = await client.GET('/api/v1/settings')
      if (error || !data) failure(error, response.status, 'Settings could not be loaded.')
      return data
    },
  })
}

export async function patchSettings(settings: OwnerSettings, body: OwnerSettingsPatch): Promise<OwnerSettings> {
  const { data, error, response } = await client.PATCH('/api/v1/settings', {
    params: { header: { 'If-Match': String(settings.row_version) } },
    body,
  })
  if (error || !data) failure(error, response.status, 'Settings could not be saved.')
  return data
}
