import { useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  copyInterviewBundle,
  createInterviewBundle,
  deleteInterviewBundle,
  interviewBundlesQueryOptions,
  interviewQuestionsQueryOptions,
  patchInterviewBundle,
  refreshersQueryOptions,
  practiceRunQueryOptions,
  createPracticeRun,
  requestPracticeHint,
  submitPracticeAnswer,
  retryPracticeEvaluation,
  cancelPracticeEvaluation,
  completeMockRun,
  createMockRun,
  mockRunQueryOptions,
  mockReportQueryOptions,
  pauseMockRun,
  resumeMockRun,
  retryMockRun,
  submitMockAnswer,
  type InterviewBundle,
  type InterviewBundleCopy,
  type InterviewBundleCreate,
  type InterviewBundlePatch,
  type PracticeRunCreate,
  type MockRun,
  type MockRunCreate,
} from './api/interview'
import { jobQueryOptions } from './api/jobs'
import { useJobEvents } from './job-events'

export function useInterview(goalId: string | null) {
  const queryClient = useQueryClient()
  const bundles = useQuery(interviewBundlesQueryOptions())
  const refreshers = useQuery(refreshersQueryOptions(goalId))
  const questions = useQuery(interviewQuestionsQueryOptions(goalId))
  const refreshBundles = () => queryClient.invalidateQueries({ queryKey: ['interview-bundles'] })
  const refreshQuestions = () => queryClient.invalidateQueries({ queryKey: ['goals', goalId, 'questions'] })
  const acceptBundle = (bundle: InterviewBundle) => {
    queryClient.setQueryData<InterviewBundle[]>(['interview-bundles'], current => {
      const existing = current ?? []
      return existing.some(item => item.id === bundle.id)
        ? existing.map(item => item.id === bundle.id ? bundle : item)
        : [...existing, bundle]
    })
    void refreshQuestions()
  }
  const create = useMutation({
    mutationFn: (body: InterviewBundleCreate) => createInterviewBundle(body),
    onSuccess: acceptBundle,
  })
  const update = useMutation({
    mutationFn: ({ bundle, patch }: { bundle: InterviewBundle; patch: InterviewBundlePatch }) => patchInterviewBundle(bundle, patch),
    onSuccess: acceptBundle,
  })
  const copy = useMutation({
    mutationFn: ({ bundleId, body }: { bundleId: string; body: InterviewBundleCopy }) => copyInterviewBundle(bundleId, body),
    onSuccess: acceptBundle,
  })
  const remove = useMutation({
    mutationFn: deleteInterviewBundle,
    onSuccess: (_result, bundle) => {
      queryClient.setQueryData<InterviewBundle[]>(['interview-bundles'], current => current?.filter(item => item.id !== bundle.id) ?? [])
      void refreshQuestions()
    },
  })
  return { bundles, refreshers, questions, create, update, copy, remove, refreshBundles }
}

export function useMockRun(runId: string | null, onRun: (runId: string) => void) {
  const queryClient = useQueryClient()
  const run = useQuery(mockRunQueryOptions(runId))
  const accept = (value: MockRun) => {
    onRun(value.id)
    queryClient.setQueryData(['interview-runs', value.id], value)
  }
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['interview-runs', runId] })
  const create = useMutation({ mutationFn: (body: MockRunCreate) => createMockRun(body), onSuccess: accept })
  const pause = useMutation({ mutationFn: (draft: string) => pauseMockRun(runId!, draft), onSuccess: accept })
  const resume = useMutation({ mutationFn: () => resumeMockRun(runId!), onSuccess: accept })
  const answerKey = useRef(crypto.randomUUID())
  const retryKey = useRef(crypto.randomUUID())
  const answer = useMutation({ mutationFn: (value: string) => submitMockAnswer(runId!, value, answerKey.current), onSuccess: () => void refresh() })
  const complete = useMutation({ mutationFn: ({ draft, idempotencyKey }: { draft: string; idempotencyKey: string }) => completeMockRun(runId!, draft, idempotencyKey), onSuccess: () => void refresh() })
  const retry = useMutation({ mutationFn: () => retryMockRun(runId!, retryKey.current), onSuccess: () => void refresh() })
  const completeJobId = complete.data && 'job_id' in complete.data ? complete.data.job_id : null
  const activeJobId = retry.data?.job_id ?? completeJobId ?? answer.data?.job_id ?? run.data?.active_job_id ?? null
  useJobEvents([activeJobId])
  const activeJob = useQuery(jobQueryOptions(activeJobId))
  useEffect(() => {
    if (!activeJob.data || !['succeeded', 'failed', 'cancelled'].includes(activeJob.data.status)) return
    if (answer.data?.job_id === activeJob.data.job_id) answerKey.current = crypto.randomUUID()
    if (retry.data?.job_id === activeJob.data.job_id) retryKey.current = crypto.randomUUID()
    void queryClient.invalidateQueries({ queryKey: ['interview-runs', runId] })
  }, [activeJob.data, answer.data, queryClient, retry.data, runId])
  return { run, create, pause, resume, answer, complete, retry, activeJob }
}

export function useMockReport(runId: string | null, enabled = true) {
  return useQuery(mockReportQueryOptions(runId, enabled))
}

export function usePracticeRun(runId: string | null, onRun: (runId: string) => void) {
  const queryClient = useQueryClient()
  const run = useQuery(practiceRunQueryOptions(runId))
  const accept = (value: Awaited<ReturnType<typeof createPracticeRun>>) => {
    onRun(value.id)
    queryClient.setQueryData(['interview-runs', value.id], value)
  }
  const create = useMutation({ mutationFn: (body: PracticeRunCreate) => createPracticeRun(body), onSuccess: accept })
  const hint = useMutation({ mutationFn: () => requestPracticeHint(runId!), onSuccess: accept })
  const submitKey = useRef(crypto.randomUUID())
  const retryKey = useRef(crypto.randomUUID())
  const submit = useMutation({ mutationFn: (answer: string) => submitPracticeAnswer(runId!, answer, submitKey.current), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['interview-runs', runId] }) })
  const retry = useMutation({ mutationFn: () => retryPracticeEvaluation(runId!, retryKey.current), onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['interview-runs', runId] }) })
  const activeJobId = retry.data?.job_id ?? submit.data?.job_id ?? run.data?.active_job_id ?? null
  useJobEvents([activeJobId])
  const activeJob = useQuery(jobQueryOptions(activeJobId))
  useEffect(() => {
    if (!activeJob.data || !['succeeded', 'failed', 'cancelled'].includes(activeJob.data.status)) return
    if (submit.data?.job_id === activeJob.data.job_id) submitKey.current = crypto.randomUUID()
    if (retry.data?.job_id === activeJob.data.job_id) retryKey.current = crypto.randomUUID()
    void queryClient.invalidateQueries({ queryKey: ['interview-runs', runId] })
  }, [activeJob.data, queryClient, retry.data, runId, submit.data])
  const cancel = useMutation({ mutationFn: () => cancelPracticeEvaluation(runId!), onSuccess: accept })
  return { run, create, hint, submit, retry, cancel, activeJob }
}
