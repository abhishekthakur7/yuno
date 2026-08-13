import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  patchSettings,
  settingsQueryOptions,
  type OwnerSettings,
  type OwnerSettingsPatch,
  type ProgressDisplay,
} from './api/settings'

const SETTINGS_KEY = ['settings'] as const

export function useOwnerSettings() {
  const queryClient = useQueryClient()
  const settings = useQuery(settingsQueryOptions())
  const save = useMutation({
    mutationFn: (patch: OwnerSettingsPatch) => {
      const current = queryClient.getQueryData<OwnerSettings>(SETTINGS_KEY)
      if (!current) throw new Error('Settings must be loaded before they can be saved.')
      return patchSettings(current, patch)
    },
    onSuccess: (updated) => queryClient.setQueryData(SETTINGS_KEY, updated),
    onSettled: () => queryClient.invalidateQueries({ queryKey: SETTINGS_KEY }),
  })
  const saveProgressDisplay = useMutation({
    mutationFn: (progressDisplay: ProgressDisplay) => save.mutateAsync({ progress_display: progressDisplay }),
  })
  return { settings, save, saveProgressDisplay }
}
