import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  patchSettings,
  settingsQueryOptions,
  type OwnerSettings,
  type ProgressDisplay,
} from './api/settings'

const SETTINGS_KEY = ['settings'] as const

export function useOwnerSettings() {
  const queryClient = useQueryClient()
  const settings = useQuery(settingsQueryOptions())
  const saveProgressDisplay = useMutation({
    mutationFn: (progressDisplay: ProgressDisplay) => {
      const current = queryClient.getQueryData<OwnerSettings>(SETTINGS_KEY)
      if (!current) throw new Error('Settings must be loaded before they can be saved.')
      return patchSettings(current, { progress_display: progressDisplay })
    },
    onMutate: async (progressDisplay) => {
      await queryClient.cancelQueries({ queryKey: SETTINGS_KEY })
      const previous = queryClient.getQueryData<OwnerSettings>(SETTINGS_KEY)
      if (previous) queryClient.setQueryData<OwnerSettings>(SETTINGS_KEY, { ...previous, progress_display: progressDisplay })
      return { previous }
    },
    onError: (_error, _patch, context) => {
      if (context?.previous) queryClient.setQueryData(SETTINGS_KEY, context.previous)
    },
    onSuccess: (updated) => queryClient.setQueryData(SETTINGS_KEY, updated),
    onSettled: () => queryClient.invalidateQueries({ queryKey: SETTINGS_KEY }),
  })
  return { settings, saveProgressDisplay }
}
