import { useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { cancelRunnerRun, confirmRunnerInputs, createRunnerRun, getRunnerCapabilities, getRunnerRun } from './api/runner'

const terminalStates = new Set(['completed', 'failed', 'timed-out-or-limited', 'cancelled', 'cleanup-complete', 'cleanup-failed'])

export function useRunner(runId: string | null) {
  const queryClient = useQueryClient()
  const createKeys = useRef(new Map<string, string>())
  const cancelKeys = useRef(new Map<string, string>())
  const capabilities = useQuery({ queryKey: ['runner', 'capabilities'], queryFn: getRunnerCapabilities, staleTime: 15_000 })
  const confirmation = useMutation({ mutationFn: confirmRunnerInputs })
  const create = useMutation({
    mutationFn: (body: { confirmation_id: string }) => {
      const key = createKeys.current.get(body.confirmation_id) ?? crypto.randomUUID()
      createKeys.current.set(body.confirmation_id, key)
      return createRunnerRun(body, key)
    },
    onSuccess: (_data, body) => createKeys.current.delete(body.confirmation_id),
  })
  const run = useQuery({
    queryKey: ['runner-runs', runId], enabled: Boolean(runId), queryFn: () => getRunnerRun(runId!),
    refetchInterval: query => terminalStates.has(query.state.data?.state ?? '') ? false : 750,
  })
  const cancel = useMutation({
    mutationFn: () => {
      const key = cancelKeys.current.get(runId!) ?? crypto.randomUUID()
      cancelKeys.current.set(runId!, key)
      return cancelRunnerRun(runId!, key)
    },
    onSuccess: data => queryClient.setQueryData(['runner-runs', runId], data),
  })
  return { capabilities, confirmation, create, run, cancel }
}
