import * as AlertDialog from '@radix-ui/react-alert-dialog'
import { Check, Code2, Play, RefreshCcw, RotateCcw, X } from 'lucide-react'
import { useState } from 'react'

import type { HandsOnStaticReview } from '../../shared/api/hands-on'
import type { Assessment } from '../../shared/api/evidence'
import { inlineContentRef, sha256, type RunnerInput, type RunnerOutputChunk } from '../../shared/api/runner'
import { useHandsOn } from '../../shared/use-hands-on'
import { useRunner } from '../../shared/use-runner'
import { useLearningState } from '../../shared/state'

export function HandsOnLab({ goalId, topicId }: { goalId: string | null; topicId: string }) {
  const { state, dispatch } = useLearningState()
  const handsOn = useHandsOn(goalId, topicId)
  const [crossQuestionResponse, setCrossQuestionResponse] = useState('')
  const [runId, setRunId] = useState<string | null>(null)
  const [confirmationOpen, setConfirmationOpen] = useState(false)
  const [pendingInput, setPendingInput] = useState<RunnerInput | null>(null)
  const runner = useRunner(runId)
  const workspace = handsOn.workspace.data
  const latestArtifact = workspace?.artifacts.at(-1)
  const latestReview = latestArtifact
    ? [...(workspace?.reviews ?? [])].reverse().find(review => review.artifact_id === latestArtifact.id)
    : undefined
  const answeredQuestionIds = new Set(workspace?.artifacts.flatMap(artifact => artifact.response_to_question_id ? [artifact.response_to_question_id] : []) ?? [])
  const crossQuestion = latestReview
    ? [...(workspace?.cross_questions ?? [])].reverse().find(question => question.artifact_id === latestReview.artifact_id && !answeredQuestionIds.has(question.id))
    : undefined
  const reviewJobState = handsOn.reviewJob.data?.status
  const runnerCapabilities = runner.capabilities.data
  const javaCapability = runnerCapabilities?.capabilities?.find(item => item.language === 'java')
  const runnerEnabled = Boolean(runnerCapabilities?.enabled && javaCapability?.state === 'supported')
  const optionalCapabilities = runnerCapabilities?.capabilities?.filter(item => (item.language === 'python' || item.language === 'relational') && item.state === 'supported') ?? []
  const run = runner.run.data

  const requestRun = async () => {
    runner.confirmation.reset()
    runner.create.reset()
    const content = state.codeDraft
    const input = { logical_path: 'Main.java', declared_type: 'java-source', content_ref: inlineContentRef(content), content_hash: await sha256(content) }
    setPendingInput(input)
    setConfirmationOpen(true)
  }

  const confirmRun = async () => {
    if (!goalId || !pendingInput) return
    try {
      const confirmation = runner.confirmation.data ?? await runner.confirmation.mutateAsync({ goal_id: goalId, language: 'java', capability: javaCapability!.capability, operation: 'test', acknowledgement_version: 'runner-not-a-sandbox-v1', inputs: [pendingInput] })
      const created = await runner.create.mutateAsync({ confirmation_id: confirmation.id })
      setRunId(created.job_id)
      setConfirmationOpen(false)
    } catch {
      // Mutation state renders the recoverable error without closing confirmation.
    }
  }

  const submit = () => {
    if (!state.codeDraft.trim()) return
    handsOn.submit.mutate({
      artifact: state.codeDraft,
      ...(crossQuestion && crossQuestionResponse.trim()
        ? { cross_question_response: { question_id: crossQuestion.id, response: crossQuestionResponse.trim() } }
        : {}),
    }, { onSuccess: () => setCrossQuestionResponse('') })
  }

  if (!goalId) return null
  if (handsOn.workspace.isPending) {
    return <section className="sb-hands-on-state" aria-live="polite"><RefreshCcw className="sb-spin" /><strong>Loading hands-on scenario…</strong></section>
  }
  if (handsOn.workspace.isError || !workspace) {
    return <section className="sb-hands-on-state" role="alert"><strong>Hands-on scenario unavailable</strong><span>The topic content remains usable. No artifact or evidence was created.</span><button className="sb-button sb-button--secondary" onClick={() => void handsOn.workspace.refetch()}>Retry</button></section>
  }

  return <section className="sb-hands-on" id="sb-lesson-artifact" aria-labelledby="sb-hands-on-title">
    <header className="sb-scenario">
      <span className="sb-kicker">Hands-on scenario · {workspace.scenario.status} pending approved IDK-009 content</span>
      <h2 id="sb-hands-on-title">{workspace.scenario.title}</h2>
      <p>{workspace.scenario.prompt}</p>
      <dl><div><dt>Role</dt><dd>{workspace.scenario.role}</dd></div><div><dt>Level</dt><dd>{workspace.scenario.level}</dd></div></dl>
      <div className="sb-scenario-constraints"><strong>Production constraints</strong><ul>{workspace.scenario.constraints.map(constraint => <li key={constraint}>{constraint}</li>)}</ul></div>
    </header>

    <section className="sb-code">
      <header><span><Code2 size={17} /> Submitted artifact · Main.java · Java</span><button className="sb-button sb-button--quiet" onClick={() => dispatch({ type: 'RESET_CODE' })}><RotateCcw size={15} /> Reset draft</button></header>
      <label className="sb-sr-only" htmlFor="sb-code">Java artifact</label>
      <textarea id="sb-code" value={state.codeDraft} onChange={event => dispatch({ type: 'SET_CODE', value: event.target.value })} spellCheck={false} />
      <footer><p>Run executes a confirmed draft separately and never creates a revision or evidence. Submit stores a new immutable revision, creates its evidence candidate, and queues static review.</p><div><button className="sb-button sb-button--secondary" disabled={!runnerEnabled || !state.codeDraft.trim()} onClick={() => void requestRun()}><Play size={16} /> Run</button><button className="sb-button sb-button--primary" disabled={!state.codeDraft.trim() || handsOn.submit.isPending || Boolean(crossQuestion && !crossQuestionResponse.trim())} onClick={submit}>{handsOn.submit.isPending ? 'Submitting…' : latestArtifact ? 'Submit revision' : 'Submit artifact'}</button></div></footer>
      {!runner.capabilities.isPending && !runnerEnabled && <p className="sb-runner-disabled" role="status">Run unavailable: {runnerCapabilities?.disabled_reason ?? javaCapability?.detail ?? 'the controlled runner posture is not approved and enabled.'} Submit remains available for static review.</p>}
      {handsOn.submit.isError && <p className="sb-hands-on-error" role="alert">Submit failed. Your draft is unchanged and no new revision is shown. Try again.</p>}
      {handsOn.submit.isSuccess && <p className="sb-hands-on-notice" role="status">Submission accepted. Static review is queued; refreshing the linked revision chain…</p>}
    </section>

    <section className="sb-result-region sb-static-region" data-result-region="static-analysis" aria-labelledby="sb-static-analysis-title">
      <header><div><span className="sb-kicker">Evaluation method</span><h3 id="sb-static-analysis-title">Static analysis</h3></div><span>{latestReview ? 'feedback-ready' : reviewJobState === 'failed' ? 'failed-recoverable' : latestArtifact || reviewJobState ? reviewJobState ?? 'queued' : 'Not submitted'}</span></header>
      <p className="sb-result-definition"><strong>Code was inspected, not executed.</strong> Compilation and tests are reported separately below.</p>
      {latestReview ? <StaticReviewResult review={latestReview} assessment={handsOn.assessments.get(latestReview.assessment_id)} /> : reviewJobState === 'failed' ? <p role="alert">Static review failed recoverably. The submitted immutable revision and evidence candidate remain linked. <a href="/app/jobs">Open Jobs to retry this review.</a></p> : <p>{latestArtifact || reviewJobState ? 'Static review is queued. The submitted revision is already preserved.' : 'Submit the artifact to request rubric-based static review.'}</p>}
      {crossQuestion && <section className="sb-cross-question" aria-labelledby="sb-cross-question-title"><span className="sb-kicker">Adaptive cross-question · targets {crossQuestion.target_gap}</span><h4 id="sb-cross-question-title">{crossQuestion.question}</h4><label htmlFor="sb-cross-question-response">Response required with your revision</label><textarea id="sb-cross-question-response" value={crossQuestionResponse} onChange={event => setCrossQuestionResponse(event.target.value)} /></section>}
    </section>

    <section className="sb-result-region sb-runtime-region" data-result-region="runtime" aria-labelledby="sb-runtime-title">
      <header><div><span className="sb-kicker">Execution results</span><h3 id="sb-runtime-title">Runtime</h3></div><span>{run?.state ?? (confirmationOpen ? 'pending-confirmation' : 'Not run')}</span></header>
      <p className="sb-result-definition"><strong>Controlled subprocess execution only.</strong> This is not a sandbox or hostile-code isolation, and it is not proof of production or AWS behavior. Runtime execution is separate and cannot create hands-on evidence.</p>
      {optionalCapabilities.length > 0 && <p className="sb-runner-capabilities">Also configured: {optionalCapabilities.map(item => item.language === 'relational' ? 'relational connector' : 'Python').join(', ')}</p>}
      {(runner.confirmation.isError || runner.create.isError || runner.run.isError || runner.cancel.isError) && <p className="sb-hands-on-error" role="alert">The runner request failed. No static-review submission was affected.</p>}
      {run && <div className="sb-runner-actions"><span>Run {run.id} · {run.cleanup_state ?? 'cleanup pending'}</span>{['queued', 'preparing', 'running', 'cancel-requested'].includes(run.state) && <button className="sb-button sb-button--secondary" disabled={runner.cancel.isPending || run.state === 'cancel-requested'} onClick={() => runner.cancel.mutate()}>{runner.cancel.isPending || run.state === 'cancel-requested' ? 'Cancel requested…' : 'Cancel run'}</button>}{['failed', 'timed-out-or-limited', 'cancelled', 'cleanup-failed'].includes(run.state) && <button className="sb-button sb-button--secondary" onClick={() => void requestRun()}>Confirm fresh retry</button>}</div>}
      {run?.cleanup_state === 'cleanup-failed' && <p className="sb-hands-on-error" role="alert">Cleanup failed. A process or temporary file may require manual recovery. {run.cleanup_diagnostic}</p>}
      <div className="sb-runtime-panels"><RuntimePhase title="Compilation" titleId="sb-compilation-title" phase={run?.compile_phase} chunks={run?.output_chunks.filter(chunk => chunk.phase === 'compile') ?? []} /><RuntimePhase title="Test execution" titleId="sb-tests-title" phase={run?.test_phase} chunks={run?.output_chunks.filter(chunk => chunk.phase === 'test') ?? []} /></div>
    </section>

    <RunnerConfirmationDialog open={confirmationOpen} onOpenChange={setConfirmationOpen} input={pendingInput} pending={runner.confirmation.isPending || runner.create.isPending} onConfirm={() => void confirmRun()} />

    <section className="sb-revision-chain" aria-labelledby="sb-revision-chain-title"><header><div><span className="sb-kicker">Linked lifecycle</span><h3 id="sb-revision-chain-title">Immutable revision chain</h3></div><span>{workspace.work_id ? `Work ${workspace.work_id}` : 'Starts on Submit'}</span></header>{workspace.artifacts.length ? <ol>{workspace.artifacts.map(artifact => { const review = [...workspace.reviews].reverse().find(item => item.artifact_id === artifact.id); const question = [...workspace.cross_questions].reverse().find(item => item.artifact_id === artifact.id); return <li key={artifact.id}><strong>Revision {artifact.revision_number}</strong><span>Evidence {artifact.evidence_id}</span><span>Static review: {review ? 'feedback-ready' : 'queued'}</span>{question && <span>Cross-question: {answeredQuestionIds.has(question.id) ? 'answered' : 'awaiting response'}</span>}</li> })}</ol> : <p>No submitted revisions yet.</p>}</section>
  </section>
}

function RunnerConfirmationDialog({ open, onOpenChange, input, pending, onConfirm }: { open: boolean; onOpenChange: (open: boolean) => void; input: RunnerInput | null; pending: boolean; onConfirm: () => void }) {
  return <AlertDialog.Root open={open} onOpenChange={onOpenChange}><AlertDialog.Portal><AlertDialog.Overlay className="sb-overlay" /><AlertDialog.Content className="sb-alert sb-runner-confirmation"><AlertDialog.Title>Confirm controlled Java run</AlertDialog.Title><AlertDialog.Description>Only the declared input below will be copied into a temporary workspace and executed as a controlled subprocess.</AlertDialog.Description>{input && <dl><div><dt>Logical path</dt><dd>{input.logical_path}</dd></div><div><dt>Declared type</dt><dd>{input.declared_type}</dd></div><div><dt>SHA-256 hash</dt><dd><code>{input.content_hash}</code></dd></div></dl>}<p><strong>Limitation:</strong> Controlled subprocess execution only. This is not a sandbox or hostile-code isolation, and it is not proof of production or AWS behavior.</p><div><AlertDialog.Cancel asChild><button className="sb-button sb-button--secondary">Cancel</button></AlertDialog.Cancel><button className="sb-button sb-button--primary" disabled={pending || !input} onClick={onConfirm}>{pending ? 'Starting…' : 'Confirm and run'}</button></div></AlertDialog.Content></AlertDialog.Portal></AlertDialog.Root>
}

function RuntimePhase({ title, titleId, phase, chunks }: { title: string; titleId: string; phase: { state: string } | null | undefined; chunks: RunnerOutputChunk[] }) {
  const ordered = [...chunks].sort((left, right) => (left.ordinal ?? left.sequence) - (right.ordinal ?? right.sequence))
  return <section aria-labelledby={titleId}><h4 id={titleId}>{title}</h4><strong>{phase?.state ?? 'Not run'}</strong>{ordered.length > 0 && <ol className="sb-runner-output">{ordered.map(chunk => <li key={`${chunk.stream}-${chunk.sequence}`}><span>{chunk.sequence} · {chunk.stream}{chunk.truncated ? ' · truncated' : ''}</span><pre>{chunk.content}</pre></li>)}</ol>}</section>
}

function StaticReviewResult({ review, assessment }: { review: HandsOnStaticReview; assessment: Assessment | undefined }) {
  return <><aside className="sb-static-limitation"><strong>Static-review limitation</strong><p>{review.limitation}</p></aside><p className="sb-rubric-version">Rubric {review.rubric_id} · version {review.rubric_version} · {review.rubric_status}</p>{review.feedback && <p>{review.feedback}</p>}{assessment ? <ul className="sb-rubric-results">{assessment.dimensions.map(dimension => <li key={dimension.dimension_id}><span className={dimension.outcome === 'pass' ? 'is-pass' : 'is-fail'}>{dimension.outcome === 'pass' ? <Check size={14} /> : <X size={14} />}</span><div><strong>{dimension.dimension_id} · {dimension.outcome}</strong><p>{dimension.rationale}</p></div></li>)}</ul> : <p role="status">Loading rubric dimensions…</p>}</>
}
