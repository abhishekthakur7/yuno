# IDK-406 — Runner execution deferral and accepted risk posture

Status: recorded

Decision date: 2026-08-14

Decider role: engineering/security owner, acting through the project implementation request

Scope: this records a scheduling and risk decision about IDK-406's implementation. It amends no approved decision. IDK-005 `runner-toolchain-v1` and IDK-007's nine policy identifiers remain approved, immutable, and unweakened — they are the bar this record declines to build to, not a bar this record lowers.

## 1. The decision

The privileged isolation layer IDK-007 requires will not be built. Specifically, no work is scheduled for the root broker (`yuno-runner-broker-v1`), the delegated cgroup v2 subtree (`runner-limits-v1`'s `memory.max`, `pids.max`, `cpu.stat`, `cgroup.kill`), the private user/PID/mount/network namespaces and `pivot_root` runtime view (`runner-runtime-view-v1`), the workspace filesystem service (`runner-workspace-fs-v1`), or the syscall filter (`runner-syscall-filter-v1`).

Consequently **local Java execution stays disabled**. `runner_enabled` remains `False` and every `runner_*` policy value in `server/src/yuno/config.py` remains `None`, so `policy_ready()` returns false, `require_policy()` raises, and `GET /runner/capabilities` reports `enabled: false`. No learner process can start.

## 2. Why this is recorded rather than left implicit

IDK-406's ticket previously described the execution machinery as "untouched". That was wrong in both directions, and the correction matters more than the wording.

What exists is a substantially complete execution service — `server/src/yuno/modules/runner/service.py` (786 lines: capability reporting, input validation, confirmation creation, environment stripping, bounded output capture, workspace-usage classification, `execute_runner_job`), a real `LocalRunnerProcessPort` (`runner/adapters.py:86`) wired at `api/app.py:966`, and 24 integration tests.

What that adapter uses for isolation is POSIX `resource.setrlimit` through `preexec_fn` (`runner/adapters.py:92-108`): `RLIMIT_CPU`, `RLIMIT_AS`, `RLIMIT_NPROC`, `RLIMIT_FSIZE`. IDK-007 §5 addresses these primitives by name and rejects them: "`RLIMIT_NPROC`, `RLIMIT_AS`, `RLIMIT_CPU`, and direct-child `wait4` are not accepted: per-process CPU limits race and do not represent the aggregate run." They are permitted only as defense-in-depth beside cgroup accounting, never as a substitute for it.

So the gap is not "unbuilt" — it is "built to a standard the approved policy explicitly refuses." Those two states look identical in a status column and are completely different when execution is switched on. This document exists so no future reader mistakes one for the other.

## 3. Accepted risk

The owner has accepted the following, explicitly, for any future state in which execution is enabled without the IDK-007 layer:

`resource.setrlimit` bounds how much a process may consume. It does not bound what a process may reach. Learner-supplied Java compiled and run under the current adapter can read any file the invoking user can read — including the home directory, SSH private keys, cloud credential files, and browser profile data — write anywhere that user can write, and open outbound network connections. There is no filesystem view restriction, no network namespace, and no syscall filtering. The "socket-denied" property IDK-007 and IDK-008 rely on is a property of the namespace layer that does not exist.

The owner's recorded position: this is a local-first, single-owner product running the owner's own exercises on the owner's own machine, and that exposure is acceptable to them. This is a considered acceptance, not an oversight, and it is recorded with that attribution rather than left as an unstated assumption in configuration.

That acceptance is personal to this deployment. It does not transfer to any multi-user, hosted, shared-machine, or distributed context — IDK-603's hosted/SaaS scope in particular cannot inherit it, and would need its own decision.

## 4. What is unaffected

- **Static review remains fully available** and is what ships today. IDK-405's hands-on lifecycle, artifact submission, and rubric review never execute anything and are unchanged.
- **IDK-008's no-connector posture** is unchanged: no database execution, no connector, regardless of this record.
- **IDK-005's support matrix** is unchanged. macOS remains a non-execution platform, JDK 21.x remains the only approved runtime, and this machine (Darwin arm64, JDK 17.0.15) satisfies neither.
- **The learner-facing disclosure** in IDK-007 §2 already states plainly that the runner "is not a security sandbox or hostile-code isolation". That wording was accurate when written and remains the wording to ship if execution is ever enabled; nothing here permits softening it.

## 5. What revisiting this requires

Enabling execution needs all of the following, and no subset is sufficient:

1. Either the IDK-007 isolation layer implemented on Linux with cgroup v2, namespaces, and the syscall filter, **or** a new approved IDK-007 decision version that records a different posture in its own terms — not configuration set behind a policy that forbids it.
2. An approved platform: Ubuntu 24.04 LTS with the exact `/etc/os-release` identifiers, on `x86_64` or `arm64`, per IDK-005. Note that the platform discovery IDK-005 §90 specifies is itself unimplemented — no `/etc/os-release` check and no `runner_execution_environment` attestation exist in `config.py` today, so the code would not currently refuse an unapproved platform on its own.
3. A complete stable JDK `21.x`, single home, matching implementor and architecture.
4. A `runner_activation_evidence` row for the exact platform/JDK tuple, per IDK-005 §112.

## 6. Consequences for other tickets

- **IDK-406** does not reach Complete. Its status records partial implementation with execution deferred, and it stops implying hardened isolation is forthcoming.
- **IDK-503** reviews the shipped absence of execution rather than a runner threat model, and confirms the PRD Appendix C rows are dispositioned against a disabled runner.
- **IDK-505** must report local Java execution as an MVP capability that is present in code but disabled and not shipped, so no release note, capability list, or learner-facing copy claims it. An unsupported-claim audit that omitted this would be exactly the fabrication IDK-505 exists to catch.
