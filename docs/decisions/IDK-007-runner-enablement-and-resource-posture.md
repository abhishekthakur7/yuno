# IDK-007 — Runner enablement and resource posture

Status: approved

Decision version: `1.0`

Policy identifiers: `runner-environment-v1`, `runner-limits-v1`, `runner-risk-ack-v1`, `runner-run-confirmation-v1`, `yuno-runner-broker-v1`, `runner-broker-service-v1`, `runner-runtime-view-v1`, `runner-workspace-fs-v1`, `runner-syscall-filter-v1`

Approval date: 2026-08-13

Approver role: engineering/security owner, acting through the implementation request that directed approval and recording of IDK-007

This decision approves the local-runner enablement, limit, termination, and cleanup policy. It does not activate execution. IDK-005 remains the toolchain authority, IDK-008 remains the database-exercise authority, IDK-010 remains the retention/data-lifecycle authority, and IDK-406 must implement and prove this policy on every exact activation tuple before learner code may run.

## 1. Enablement posture

The runner is disabled by default and becomes available only after the local owner explicitly enables it in Settings. A first attempted Run never enables execution automatically.

Persist `desired_enabled` separately from derived `effective_enabled`:

- `desired_enabled` defaults to false and can become true only through the version-checked Settings acknowledgement in §2.
- `effective_enabled` is derived and true only when `desired_enabled=true`, the current risk acknowledgement is valid, IDK-005 reports compatible Java, exact activation evidence exists, every cgroup/launcher/network/workspace control passes, reconciliation is complete, and no safety suspension exists.
- Any policy, toolchain tuple, activation-evidence, launcher, network-filter, or execution-environment change revokes the acknowledgement, sets `desired_enabled=false`, and requires explicit re-enable. There is no automatic compatibility fallback or re-enable.
- Turning Settings Off atomically commits `desired_enabled=false`, rejects new confirmations/enqueues, cancels queued runner jobs, and requests termination of preparing/running runs. The request returns after cancellation is durable; Jobs continues to expose termination and cleanup progress.
- Submit/static review never depends on runner enablement and remains usable in every disabled, unsupported, limited, cancelled, reconciling, or cleanup-failed state.

There is at most one live runner job per installation in `preparing`, `running`, `cancel-requested`, or `cleanup-pending`. At most three additional runner jobs may be queued. A fourth queued request returns `429 runner-capacity` without consuming its confirmation. The same still-valid confirmation may be retried until its original five-minute expiry. These runner admission values are owned by this decision and are independent of any generic job cap or later lifecycle policy.

## 2. Settings risk acknowledgement

Settings uses this exact dialog:

Title: **Enable local Java execution?**

Body: **Yuno will compile and run the displayed Java sources and Yuno test driver as local processes under a dedicated restricted runner identity. Time, CPU, memory, task, output, filesystem, network, and cleanup controls reduce risk, but this is not a security sandbox or hostile-code isolation. A defect in the operating system, Java runtime, or privileged runner broker could still expose host resources. Yuno does not inject AWS credentials. A passing run proves only this local compile/test—not production, security, AWS behavior, hiring, or readiness. You can disable Run at any time; disabling stops new runs and cancels active runs.**

Required unchecked checkbox: **I understand these limits and want to enable local execution on this computer.**

Primary action: **Enable local execution**

Secondary action: **Keep disabled**

The command requires `accepted=true` and the exact `runner-risk-ack-v1`. It persists the acknowledgement version, toolchain/environment/limits policy versions, activation-evidence reference, acknowledgement time, and enablement revision. It has no wall-clock expiry, but any referenced-version/evidence change or manual disable revokes it. Closing/cancelling the dialog changes nothing.

## 3. Per-run confirmation

Settings opt-in is not consent for an individual process. Every compile/test requires a fresh `runner-run-confirmation-v1` confirmation showing:

- operation and scenario revision;
- every learner logical path and SHA-256;
- for test, the server-owned driver ID/version/path/hash/FQCN;
- exact application-constructed compile and test argv;
- toolchain, capability-snapshot, activation-evidence, environment, limits, and enablement revisions;
- every numeric limit in §4; and
- the full limitation statement from §2.

Required unchecked checkbox: **I reviewed these files and want Yuno to run this compile/test on my computer.**

Primary action: **Run locally**

A confirmation is immutable, single-use, and expires 300 seconds after creation. Input/hash, artifact/work/scenario/driver, argv, capability/evidence, environment, limits, risk-acknowledgement, or enablement-revision change makes it stale. Confirmation, enqueue, and worker preparation each recheck all gates. Retrying a failed, limited, or cancelled run always requires a new confirmation.

## 4. Exact aggregate limits

All limits cover one confirmed run across compile plus optional test. The test phase receives only the remaining wall, CPU, output, file-system, and task budgets. No learner or scenario may raise them.

| Resource | Approved value | Enforcement and measurement |
| --- | --- | --- |
| Preparation before learner exec | 10 seconds | Monotonic deadline from worker claim through verified workspace/cgroup/filter/launcher setup; expiry starts no learner process |
| Wall execution threshold | 30 seconds | A dedicated broker watchdog uses a monotonic timer and freezes/kills the cgroup on the first observation at or above 30 seconds; phase transition counts. This is a termination threshold, not a real-time maximum: record actual observation and final duration. Cancellation/cleanup timing is separate |
| Aggregate CPU threshold | 20 CPU-seconds | A dedicated broker watchdog samples the run-cgroup `cpu.stat usage_usec` with a 10-ms target cadence and freezes/kills on the first observation at or above 20 seconds. Record threshold, observed usage, final usage, cadence gaps, and overshoot; no maximum scheduler-latency/overshoot claim is made. `cpu.max=200000 100000` caps throughput at two logical CPUs |
| Process-tree memory | 1 GiB | cgroup v2 `memory.max=1073741824`, `memory.swap.max=0`, `memory.oom.group=1`; `memory.events`/`memory.peak` record outcome |
| Processes/threads | 128 tasks | cgroup v2 `pids.max=128`; JVM threads count. A broker watcher terminates on any `pids.events max` increment; the hard controller denial remains authoritative even if observation is delayed |
| Learner inputs | 100 files; 10 MiB aggregate decoded bytes | Checked before confirmation and rechecked before materialization; server driver excluded from learner count but included in workspace |
| Server test driver | 256 KiB maximum | Checked at manifest load/confirmation/materialization |
| Stdout | 1 MiB | First excess terminates the tree; only in-budget content plus one in-budget marker retained |
| Stderr | 1 MiB | Same |
| Combined captured output | 2 MiB | Aggregate across compile/test and both streams; first excess terminates |
| Single workspace regular file | 16 MiB | `RLIMIT_FSIZE` hard-denies growth; it is defense-in-depth and a handled `EFBIG` is not falsely reported as a supervisor-observed terminal limit |
| Open file descriptors | 256 | `RLIMIT_NOFILE` hard-denies additional opens; it is defense-in-depth and a handled `EMFILE` is not falsely reported as a supervisor-observed terminal limit |
| Core dump | 0 bytes | `RLIMIT_CORE=0` |
| Workspace | 256 MiB; 10,000 filesystem entries | Dedicated broker-owned `runner-workspace-fs-v1` per-run filesystem over private tmpfs backing. Its byte/entry accounting authoritatively records a monotonic denial event before returning `ENOSPC`; all sources, driver, classes, directories, links, and outputs count. Any denial event freezes/kills and classifies the run even if learner code handles the syscall error |
| Live runner concurrency | 1 | Installation-wide atomic lease until cleanup is terminal |
| Queued runner jobs | 3 | Atomic admission check; fourth returns `429 runner-capacity` |
| TERM grace | 2 seconds | Monotonic after SIGTERM before forced tree kill |
| Empty-tree verification | 2 seconds | Require cgroup `populated=0`; otherwise cleanup fails/suspends |

This decision independently owns execution enforcement and runner admission. Its authoritative workspace-denial event makes the 256 MiB/10,000-entry cancellation/classification behavior consistent with the separately recorded IDK-010 lifecycle policy; IDK-010 owns retention, expiry, and disposal after cleanup, while this decision owns how the live run is bounded and stopped.

## 5. Kernel/resource boundary

Every learner run uses one delegated parent cgroup v2 subtree spanning its workspace-filesystem server, final sentinel, compile, and test. The parent owns the aggregate CPU, memory, pids, freeze, kill, and populated-empty controls; `workspace` and `payload` child cgroups exist only for attribution and may not carry looser limits. Activation requires writable `cpu`, `memory`, and `pids` controllers. The filesystem server and launcher join the parent before serving/materializing learner-controlled operations or executing the worker's final in-run sentinel. Cumulative parent counters start before either child becomes active and are never reset between phases. IDK-005's capability-discovery sentinel is a distinct trusted, fixed-input probe: it runs with the stripped environment and bounded probe timeout but does not require IDK-007 controls, affects only item compatibility, and never makes top-level enablement true. The worker repeats the sentinel inside the full run boundary; a control/setup failure is `runner-controls-unavailable`, not JDK incompatibility.

`memory.max`, `memory.swap.max`, `pids.max`, `cpu.stat`, and `cgroup.kill` are authoritative for the complete process tree. `RLIMIT_NPROC`, `RLIMIT_AS`, `RLIMIT_CPU`, and direct-child `wait4` are not accepted: per-process CPU limits race and do not represent the aggregate run. Per-process `RLIMIT_FSIZE`, `RLIMIT_NOFILE`, and `RLIMIT_CORE=0` remain defense-in-depth and never substitute for cgroup accounting.

The privilege boundary is one administrator-installed, root-owned and non-app-writable `yuno-runner-broker-v1` daemon. Its root-owned service unit is bound to an immutable `runner-broker-service-v1` manifest: delegated cgroup v2 subtree; `KillMode=control-group`; one-second service-manager watchdog with `WatchdogSignal=SIGKILL`; bounded stop timeout followed by control-group kill; no automatic restart; and all per-run leaves nested beneath the broker service cgroup. The independent service manager therefore kills the broker, launchers, and every run descendant if the broker exits, is SIGKILLed, or stops heartbeating. Its Unix `SOCK_SEQPACKET` endpoint is owned by the app service identity, mode `0600`, and accepts a length-bounded versioned binary request containing only an existing prepared run ID plus sealed input/runtime-manifest file descriptors. It never accepts a path, PID, cgroup name, mount option, executable argv, UID/GID, limit, or syscall list from the caller. The broker resolves all policy from the immutable database snapshot and its root-owned configuration, verifies the request against it, and refuses mismatch. The app cannot replace the binary/configuration; activation evidence binds their hashes and service-unit/delegation identity.

Loss of the sole authenticated app control connection makes the broker freeze/kill every active run leaf, persist or return the fixed safe recovery classification if possible, and exit nonzero; the service manager remains the independent kill backstop. The app treats connection loss, broker/service exit, watchdog action, or missing heartbeat as `runner-controls-unavailable`, durably safety-suspends enablement and writes a cleanup intent before any broker restart. The service has `Restart=no`; only startup/offline reconciliation may start it again after all old leaves are proven empty. Static review stays available.

The broker creates private user, PID, mount, and network namespaces and the delegated parent/child cgroup tree before any compiler or learner-influenced process. Its fresh root is built from `runner-runtime-view-v1`: an immutable manifest of every mounted object with logical destination, type, mode, owner, size and SHA-256; internal symlinks have canonical in-root targets, and absolute/escaping symlinks, mount crossings, devices, sockets, and unmanifested objects are rejected. It exposes the complete verified JDK/native dependency closure read-only, namespace-local `/proc`, exactly `/dev/null`, `/dev/zero`, `/dev/random`, and `/dev/urandom`, and `runner-workspace-fs-v1` as the sole writable filesystem (including private `/tmp`). It then `pivot_root`s, detaches the old root, closes every old-root descriptor, and verifies the mount table. The workspace filesystem is served by a broker child in the same aggregate parent run cgroup (under its `workspace` child), stores content on private tmpfs, presents ownership/mode `yuno-runner:0700` and `nodev,nosuid,noexec`, forbids devices/sockets/hard links and escaping symlinks, and counts every logical entry and allocated byte including sources/driver/classes. Its CPU, memory, and task use therefore consumes the same 20-second/1-GiB/128-task aggregate; parent `cgroup.kill` terminates it with the payload. It serializes allocation-changing operations per run; before an operation would exceed 256 MiB or 10,000 entries, it increments a monotonic in-memory denial counter, notifies the broker supervisor, and only then returns `ENOSPC`. The supervisor freezes/kills the parent on the counter/eventfd before accepting terminal success. If the filesystem server/event channel fails, the independent service hierarchy kills the parent and records `runner-controls-unavailable`; it never becomes an ordinary passing result. No host home, host `/tmp`, runtime socket directory, or arbitrary host path is present. One active-run lease and immediate safety suspension prevent another run from sharing residual capacity after cleanup failure.

For each run the privileged broker forks a dedicated launcher child; the long-lived broker remains outside the run cgroup/namespaces and never parses learner content. After namespace/mount/cgroup setup and before JDK exec, that launcher child clears supplementary groups, sets real/effective/saved GID and UID to the dedicated unprivileged runner identity, clears effective/permitted/inheritable/ambient capabilities and locks the capability bounding/securebits state against regain, sets non-dumpable, sets `no_new_privs`, and verifies the resulting UID/GID/group/capability state from namespace-local `/proc`. Every broker/request/control descriptor is `CLOEXEC` and closed; learner processes inherit only stdin `/dev/null` and bounded stdout/stderr pipes. No control channel survives exec.

The dedicated descriptor-bound Linux launcher additionally:

- performs and verifies the privilege/capability drop above before exec;
- closes every inherited descriptor except stdin/stdout/stderr, with stdin fixed to `/dev/null`;
- uses IDK-005's fixed environment (`LANG`, `LC_ALL`, `TZ` only);
- attaches to the prepared cgroup before exec;
- installs the deny-by-default `runner-syscall-filter-v1` manifest for the detected architecture. The manifest is an immutable sorted syscall-number/action table stored with its SHA-256 in activation evidence; its contract has default `KILL_PROCESS`, explicit `ALLOW` entries only for the reviewed JDK compile/test closure, and fixed `ERRNO(EPERM)` entries for `socket`, `socketpair`, `io_uring_setup`, `pidfd_getfd`, `ptrace`, `process_vm_readv`, `process_vm_writev`, `unshare`, `setns`, `mount`, `umount2`, `pivot_root`, `move_mount`, `open_tree`, `fsopen`, `fsmount`, `fspick`, `mount_setattr`, `bpf`, and `userfaultfd`. Any table/action change is a new policy version, not merely new evidence; and
- descriptor-binds the already verified JDK executable per IDK-005.

Failure to verify the root-owned broker/service/delegation, runtime-view/workspace-filesystem manifests, privilege drop, cgroup, namespaces/mount view, authoritative workspace denial channel, `no_new_privs`, descriptor closure, or syscall filter makes `effective_enabled=false`. These controls reduce exposure but are not called a security sandbox or hostile-code isolation: a kernel, broker, filter, mount, or JDK defect can still expose host resources, and activation evidence is not proof against hostile code.

This environment policy applies only to IDK-005 `direct-jdk-v1` Java compile/test. IDK-008 decision v1.0 makes database execution absent; it grants no learner Java network access and introduces no connector. Any future executable database connector requires a new approved immutable environment/credential/operation policy and activation evidence and cannot reuse this run cgroup with weaker controls.

## 6. Limit outcomes

The first terminating cause wins atomically, except an ensuing cleanup failure additionally sets safety suspension. Fixed terminal limit codes are:

- `runner-preparation-time-limit`
- `runner-wall-time-limit`
- `runner-cpu-time-limit`
- `runner-memory-limit`
- `runner-task-limit`
- `runner-input-files-limit`
- `runner-input-bytes-limit`
- `runner-driver-bytes-limit`
- `runner-stdout-limit`
- `runner-stderr-limit`
- `runner-workspace-bytes-limit`
- `runner-workspace-entries-limit`

Input/driver and preparation limits reject or fail before learner execution. Supervisor-observed wall, CPU, memory, task, output, or authoritative workspace-denial breaches freeze then kill the cgroup without the cancellation grace, preserve only bounded partial output, return `timed-out-or-limited`, and never count as a passing test/evidence. Kernel counter/event changes distinguish memory and task breaches; the broker-owned workspace counter distinguishes byte versus entry denial. A missed broker/service-manager/filesystem heartbeat or unverifiable mechanism is `runner-controls-unavailable`, makes the result non-passing, and safety-suspends enablement; scheduler delay is recorded rather than hidden as an exact bound.

The exact runtime template is: **The run stopped at the {label} limit ({value}). Partial output may be shown. This result is limited and does not count as a passing runtime test; static review remains available.**

Pre-execution copy is literal rather than using the runtime template:

| Code | Exact learner message |
| --- | --- |
| `runner-input-files-limit` | “This run cannot be confirmed because it declares more than 100 learner files. Reduce the declared files and try again; no process was started.” |
| `runner-input-bytes-limit` | “This run cannot be confirmed because its learner inputs exceed 10 MiB decoded. Reduce the declared inputs and try again; no process was started.” |
| `runner-driver-bytes-limit` | “This scenario cannot run locally because its approved test driver exceeds 256 KiB. Static review remains available; no process was started.” |
| `runner-preparation-time-limit` | “The queued run could not start within the 10-second preparation limit. Confirm a fresh run after the runner becomes available; no learner process was started.” |

Code-to-label/value mapping is fixed:

| Code | Label | Value |
| --- | --- | --- |
| `runner-wall-time-limit` | wall-time | 30 seconds |
| `runner-cpu-time-limit` | aggregate CPU | 20 CPU-seconds |
| `runner-memory-limit` | process-tree memory | 1 GiB with no swap |
| `runner-task-limit` | process/thread task | 128 tasks |
| `runner-stdout-limit` | captured stdout | 1 MiB |
| `runner-stderr-limit` | captured stderr | 1 MiB |
| `runner-workspace-bytes-limit` | workspace bytes | 256 MiB |
| `runner-workspace-entries-limit` | workspace entries | 10,000 entries |

The 2 MiB combined-output ceiling is the sum invariant implied by the two one-MiB stream ceilings and has no separate terminal code. Capture assigns one ordered sequence across both streams; if the same capture event would cross multiple limits, stdout precedes stderr. Each stream reserves the UTF-8 byte length of the exact marker **[Yuno: output limit reached; remaining bytes omitted]** inside its one-MiB ceiling, so retained learner bytes plus the marker never exceed the ceiling.

File-size and descriptor values are hard-denial constraints rather than claimed terminal classifications. A handled `EFBIG` or `EMFILE` may continue and finish under ordinary compile/test semantics; an unhandled failure is an ordinary non-passing compile/test result. Workspace denials are authoritatively mediated and therefore always terminate/classify. The 10,000-entry ceiling is stricter than a 10,000-regular-file maximum because internal sources, driver, classes, and directories also count.

## 7. Disabled states and exact messages

Top-level disabled precedence is evaluated before offering an enable action:

1. `runner-safety-suspended`
2. `runner-reconciling`
3. `runner-policy-incomplete`
4. `runner-controls-unavailable`
5. IDK-005 missing/incompatible item state
6. IDK-005 `activation-evidence-missing`
7. `runner-acknowledgement-required`, only when a prior enabled/acknowledged revision was revoked
8. `runner-owner-disabled`, for first use or a voluntary Settings disable

| Code | Exact learner message |
| --- | --- |
| `runner-safety-suspended` | “Local execution is suspended after an unresolved process or workspace cleanup failure. Static review remains available; resolve the displayed local recovery item before enabling Run again.” |
| `runner-reconciling` | “Local execution is temporarily off while Yuno reconciles prior runner processes and workspaces. Static review remains available.” |
| `runner-policy-incomplete` | “Local execution remains off because the approved runner policy is not completely configured. Static review remains available; no run was started.” |
| `runner-controls-unavailable` | “Local execution remains off because the approved Linux process, resource, network, or workspace controls could not be verified. Static review remains available; no run was started.” |
| `runner-owner-disabled` | “Local execution is off. Static review remains available. Review the local-process risks in Settings to enable Run.” |
| `runner-acknowledgement-required` | “Local execution remains off because the runner policy or validated execution tuple changed. Review and accept the current risks in Settings; no run was started.” |
| `runner-capacity` | “Local execution already has one active and three queued runs. Wait or cancel a queued run, then retry this same confirmation before it expires; no additional run was queued.” |
| `runner-confirmation-expired` | “This run confirmation expired after 5 minutes. Review the current inputs and confirm a fresh run; no run was started.” |
| `runner-confirmation-consumed` | “This run confirmation was already used. Confirm a fresh run with the current inputs; no run was started.” |
| `runner-confirmation-stale` | “The files, test driver, toolchain, or runner policy changed. Review the current run details and confirm again; no run was started.” |
| `runner-cancel-requested` | “Cancellation was requested. Yuno is stopping the run; process termination and temporary-file cleanup are not yet verified.” |
| `runner-cleanup-pending` | “The run has stopped. Yuno is verifying that its process tree is empty and removing temporary files.” |
| `runner-cleanup-complete` | “The run is finished, its process tree is empty, and temporary-file cleanup was verified.” |
| `runner-cancelled` | “The run was cancelled. Check the recorded cleanup status; partial output may be shown.” |
| `runner-cleanup-failed` | “The run stopped, but Yuno could not verify that every process and temporary file was removed. Local execution is now suspended. Static review remains available; use the displayed recovery item.” |
| `runner-recovery-automatic` | “Local execution is suspended while Yuno retries verified cleanup. Do not use Run. Static review remains available; no manual command is shown or executed by the web interface.” |
| `runner-manual-recovery-required` | “Local execution remains suspended because cleanup could not be verified. Do not use Run. Static review remains available. A local operator must inspect and reconcile the recorded recovery item with Yuno’s offline runner-admin command before a reviewed reset.” |

Raw cgroup/proc paths, PIDs, host paths, kernel text, exception text, environment, and learner content never substitute for these messages.

## 8. Termination, cleanup, and reconciliation

Every terminal path uses the verified cgroup, with a graceful branch only for operator/user actions:

1. Durably record the trigger and `cancel-requested`/limit state before signalling.
2. For learner cancellation, Settings disable, graceful shutdown, or reconciliation, repeatedly enumerate the verified run cgroup, open/verify pidfds for every current member, and send SIGTERM through those pidfds. Repeat until empty or the two-second grace expires; this includes descendants that changed process group or session and closes membership races during the grace period. A resource-limit or watchdog-control failure instead freezes and kills immediately; it receives no CPU/wall-consuming grace.
3. At the end of a graceful two-second window, or immediately for a limit/control failure, write `1` to the verified cgroup's `cgroup.kill`; pidfd SIGKILL is a fallback only for still-observed members.
4. Reap and wait at most two seconds for the parent run cgroup and both child cgroups to report `cgroup.events populated=0`.
5. Only after empty-tree proof, remove the workspace without following links, at offsets 0 ms, 250 ms, and 1,000 ms, then remove the cgroup.
6. `cleanup-complete` requires both workspace absence and empty/removed cgroup. Leader exit alone is insufficient.

Any identity mismatch is never signalled. An unverifiable descendant/cgroup, invalid cleanup reference, failed empty-tree proof, or third workspace/cgroup removal failure writes a durable cleanup intent, records `cleanup-failed`, atomically revokes desired/effective enablement, cancels other runner work, and enters persistent safety suspension. Recovery is not an HTTP learner action. IDK-406 provides an offline `yuno.runner_admin` command with `inspect`, `reconcile`, and `reset` operations keyed only by an existing intent ID; it accepts no caller-supplied path/cgroup/PID. It acquires the runner-admin lease, refuses while the app/worker owns that lease, exposes only fixed safe classifications, and permits `reset` only after `reconcile` proves the cgroup absent/empty and the workspace absent and records the local operator, review basis, policy version, and time. The normal web UI cannot dismiss the suspension or invent/execute a destructive command.

Startup reconciliation completes before runner capabilities can be enabled. It inspects every nonterminal record and cleanup intent, applies the same identity-safe termination/removal protocol, and leaves the rest of Yuno/static review available. Shutdown first stops runner admission/claims, cancels queued runs, terminates/drains the active cgroup, persists cleanup, and only then stops the worker/database.

Unresolved cleanup retries at startup and every 60 seconds. This decision independently sets one hour after the first failed cleanup as an escalation boundary, not a planned wait: safety suspension starts immediately, retries continue, and at one hour the fixed recovery item becomes `manual-recovery-required`. The durable intent is never silently discarded and no workspace is removed until its cgroup is proven empty. Any future lifecycle policy controls retention only after resolution and cannot shorten active recovery.

## 9. Immutable records and state transitions

IDK-406 adds:

- `runner_enablements`: desired/effective state, risk acknowledgement, all bound policy/evidence versions, revision, enabled/disabled/revoked/suspended timestamps, and fixed reason;
- `runner_limit_snapshots`: immutable exact numeric values and enforcement versions referenced by confirmations/runs/evidence;
- `runner_safety_suspensions`: trigger runner/cleanup intent, fixed classification, created time, reviewed reset basis/role/time;
- `runner_cleanup_intents`: immutable run/cgroup/workspace safe identities; state; attempt count/last/next/escalated times; process-empty, workspace-absence, and cgroup-removal outcomes; safe diagnostic; suspension reference; and reviewed-reset reference. It is API-private and replaces any attempt to store compound runner cleanup in file-only cleanup intents;
- per-run cgroup identity, controller/delegation/filter/launcher/workspace-quota identity hashes, CPU/memory/task counters/events, termination trigger/timestamps, empty-tree proof, and cleanup attempts/outcome.

Enable/disable/revoke/suspend/reset uses optimistic revision checks and one transaction for state plus audit event. Confirmation and run rows reference the exact enablement revision, risk acknowledgement, limit snapshot, capability snapshot, activation evidence, driver, and input snapshot. Raw host paths are never public/audit data; any necessary private operational reference is protected and its post-resolution retention remains IDK-010's separate lifecycle decision.

Version 1.0 is immutable. Any numeric limit, enforcement mechanism, filter, launcher, acknowledgement meaning, or enablement/cleanup semantics change requires a new approved version, new activation evidence, acknowledgement revocation, and explicit re-enable. Obsolete execution paths are removed rather than retained as fallbacks.

## 10. Activation evidence and implementation ownership

IDK-406 owns implementation and must record, for every exact IDK-005 tuple, the launcher/filter/controller/namespace/mount/workspace-quota identities, `runner-environment-v1`, `runner-limits-v1`, and engineering/security approval. Required automated/native evidence includes:

- exact boundary and one-over tests for hard controller/capture/input/workspace values, recorded wall/CPU observation and watchdog-liveness behavior without a false maximum-overshoot claim, hard-denial behavior for file/FD constraints, and every message;
- workspace-filesystem service, final sentinel, compile, and test sharing cumulative parent wall/CPU/memory/task budgets, with child counters used only for attribution;
- real cgroup memory OOM, CPU, and 128/+1 task pressure;
- broker-filesystem byte/entry boundary and one-over cases, including learner-handled `ENOSPC`, proving the monotonic denial counter/event terminates with the exact classification; filesystem daemon/event-channel failure is controls-unavailable; per-file/FD/core denial has no false terminal classification;
- root-owned broker request validation, runtime-view manifest identity, privilege/capability drop on both architectures, private user/PID/mount/network namespaces and sole-writable-workspace verification; `/proc/self/fd` proves only `/dev/null` stdin plus stdout/stderr survive; no host-home, host-`/tmp`, runtime socket, old-root descriptor, symlink/mount escape, or arbitrary writable path; deny-by-default syscall-filter bypass tests including socket/socketpair, io_uring, pidfd duplication, ptrace/process-vm, and namespace mutation, with ordinary Java compile/test still working;
- descendants that fork, `setsid`, ignore TERM, and flood output/files, followed by two-second escalation, cgroup empty proof, and cleanup;
- broker SIGKILL, crash, deadlock/missed service-manager heartbeat, and app-control-channel loss while CPU-saturating, forked, `setsid`, and silent descendants run; the independent service unit kills the complete hierarchy, the app persists suspension/cleanup intent, no automatic restart occurs, and static review remains available;
- cancel before spawn/during compile/between phases/during test, completion/cancel/limit races, Settings disable during a run, and shutdown drain;
- crash/startup reconciliation, identity mismatch, invalid cleanup reference, retry/escalation, persistent safety suspension, and reviewed reset;
- dispatcher lifecycle-hook ordering: runner reconciliation before runner admission on startup, and runner admission stop/cancel/drain/cleanup persistence before generic worker/database shutdown;
- Settings enable/disable/re-acknowledgement and accessible focus/keyboard behavior;
- five-minute confirmation expiry, single use, every stale-boundary input, and runner capacity; and
- full static-review usability and zero evidence/artifact append from every runner-only path.

Policy approval creates no activation evidence. IDK-008's decision gate is now approved, but until IDK-406 implementation/native evidence passes, Run remains absent/disabled.

## 11. Evidence and approval basis

The engineering/security owner reviewed the current implementation, PRD Appendix C, and official primary sources on 2026-08-13.

- Linux documents cgroup v2 whole-tree `cpu.stat`, `cpu.max`, `memory.max`, `memory.swap.max`, `memory.oom.group`, `pids.max`, `cgroup.events`, and `cgroup.kill`: <https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html>.
- Linux documents that `no_new_privs` is inherited across fork/clone and preserved across exec: <https://docs.kernel.org/userspace-api/no_new_privs.html>.
- Linux documents seccomp filters and explicitly warns that seccomp is not a sandbox by itself: <https://docs.kernel.org/userspace-api/seccomp_filter.html>.
- Python documents Unix resource-limit semantics used only for the approved defense-in-depth limits: <https://docs.python.org/3/library/resource.html>.

Current code's threaded `preexec_fn`, `RLIMIT_NPROC`/`RLIMIT_AS`, direct-child CPU accounting, process-group-only termination, inherited PATH environment, polling-only workspace ceiling, and one-shot removal do not meet this policy. IDK-406 must remove them; none remains as a compatibility path.
