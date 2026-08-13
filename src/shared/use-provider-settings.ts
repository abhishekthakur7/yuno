import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  acceptDisclosure,
  disclosuresQueryOptions,
  providerCapabilitiesQueryOptions,
  refreshProviderCapabilities,
  revokeDisclosure,
} from './api/provider-settings'

export function useProviderSettings() {
  const queryClient = useQueryClient()
  const disclosures = useQuery(disclosuresQueryOptions())
  const capabilities = useQuery(providerCapabilitiesQueryOptions())
  const refreshDisclosures = () => queryClient.invalidateQueries({ queryKey: ['disclosures'] })
  const accept = useMutation({ mutationFn: acceptDisclosure, onSuccess: refreshDisclosures })
  const revoke = useMutation({ mutationFn: revokeDisclosure, onSuccess: refreshDisclosures })
  const refreshCapabilities = useMutation({
    mutationFn: refreshProviderCapabilities,
    onSuccess: data => queryClient.setQueryData(['provider-capabilities'], data),
  })
  return { disclosures, capabilities, accept, revoke, refreshCapabilities }
}
