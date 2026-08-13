import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { ApiError } from './api/queries'
import {
  confirmGoalDelete,
  createDeletePreflight,
  createExport,
  deleteOperationQueryOptions,
  exportOperationQueryOptions,
  type DeleteImpact,
} from './api/data-operations'

export function useDataOperations(goalId: string | null) {
  const queryClient = useQueryClient()
  const [exportId, setExportId] = useState<string | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [staleDeleteImpact, setStaleDeleteImpact] = useState(false)
  const exportStatus = useQuery(exportOperationQueryOptions(exportId))
  const deleteStatus = useQuery(deleteOperationQueryOptions(deleteId))
  useEffect(() => {
    if (deleteStatus.data?.status !== 'complete') return
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: ['profile'] }),
      queryClient.invalidateQueries({ queryKey: ['goals'] }),
    ])
  }, [deleteStatus.data?.status, queryClient])
  const startExport = useMutation({
    mutationFn: () => createExport(goalId, crypto.randomUUID()),
    onSuccess: (job) => setExportId(job.job_id),
  })
  const preflight = useMutation({
    mutationFn: () => createDeletePreflight(goalId!, crypto.randomUUID()),
    onSuccess: () => setStaleDeleteImpact(false),
  })
  const confirmDelete = useMutation({
    mutationFn: (impact: DeleteImpact) => confirmGoalDelete(goalId!, impact, crypto.randomUUID()),
    onSuccess: (job) => { setDeleteId(job.job_id); setStaleDeleteImpact(false) },
    onError: (error) => { if (error instanceof ApiError && error.status === 409) setStaleDeleteImpact(true) },
  })
  const refreshPreflight = () => {
    preflight.reset()
    confirmDelete.reset()
    setStaleDeleteImpact(false)
    preflight.mutate()
  }
  return { startExport, exportStatus, preflight, confirmDelete, deleteStatus, staleDeleteImpact, refreshPreflight }
}
