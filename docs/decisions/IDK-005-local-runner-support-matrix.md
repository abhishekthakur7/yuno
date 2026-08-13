# IDK-005 — Local runner support matrix

Status: approved

Decision version: `1.0`

Policy identifier: `runner-toolchain-v1`

Approval date: 2026-08-13

Approver role: engineering owner, acting through the implementation request that directed approval and recording of IDK-005

This decision approves the compatibility policy for the local runner. It does not activate execution. IDK-007 separately owns whether execution may be enabled and the complete limits/cleanup posture; IDK-008 separately owns database-exercise posture. After IDK-406 implements the exact probes, a Java item may report toolchain compatibility as `supported`; top-level `enabled` stays false and no learner process may start until the exact platform/JDK tuple has approved activation evidence and IDK-007's gate passes.

## 1. Approved matrix

The MVP matrix is deliberately narrow. A combination not listed here is unsupported; upstream availability alone does not widen the matrix.

| Surface | Approved value | Required evidence before top-level enablement | Everything else |
| --- | --- | --- | --- |
| Host operating system | Ubuntu 24.04 LTS host or conventional VM guest, exact `/etc/os-release` values `ID=ubuntu` and `VERSION_ID=24.04`; configured execution-environment attestation `host-or-vm` | End-to-end compile/test and limit/cancel/cleanup smoke evidence for the exact platform/JDK tuple | Unsupported |
| Host architecture | `x86_64`/`amd64` or `aarch64`/`arm64`, normalized to `x86_64` or `arm64` | Evidence is per normalized architecture and full JDK identity; one tuple's evidence does not activate another | Unsupported |
| Java | Complete, stable JDK feature release `21.x`; `java` and `javac` from one configured JDK home, exact full version/implementor and architecture | Paired identity/sentinel must pass for compatibility; exact-tuple test-driver/limit/cancel/cleanup smoke and approval are required for enablement | JRE-only, Java 8/11/17, 22+, prerelease/EA, mixed homes, mixed versions/implementors, and mixed architectures are incompatible |
| Java build mode | `direct-jdk-v1`: application-constructed `javac` and `java` argv only | Exact-argv tests and exact-tuple smoke | Maven, Gradle, Ant, wrappers, dependency resolution/download, and learner-selected compiler/launcher flags are unsupported |
| Learner Python execution | None in MVP | Not applicable | Unsupported and absent from advertised capabilities |
| Relational execution | Absent in MVP | IDK-008 decision v1.0 | No capability item, setting, credential, endpoint, or operation |
| Go execution | None in MVP | A later separately approved matrix/version | Absent from the capability contract |

Ubuntu containers, WSL, and other Linux-compatibility layers are not approved platform rows. Configuration must explicitly attest `runner_execution_environment=host-or-vm`; absent or another value is incompatible. WSL is positively detected by `WSL_INTEROP`, `WSL_DISTRO_NAME`, or case-insensitive `microsoft` in `/proc/sys/kernel/osrelease`. A container is positively detected by `/.dockerenv`, `/run/.containerenv`, or the bounded markers `docker`, `containerd`, `kubepods`, or `lxc` in `/proc/1/cgroup`. Any match overrides the attestation and fails closed. The runner does not claim it can prove the absence of a deliberately concealed layer; an incorrect administrator attestation is configuration outside the approved posture.

macOS is not an MVP execution platform. The current adapter cannot enforce its address-space memory ceiling on Darwin, so detecting a JDK there must not produce `supported`. Native Windows is unsupported because the current process policy depends on POSIX-only resource limits, process groups, and wait semantics. Static review remains available on every unsupported runner platform.

The application's own Python runtime is not a learner-code capability. Its version belongs to application packaging and CI, not to `GET /runner/capabilities`; this decision does not authorize executing learner Python with the server interpreter.

## 2. Direct Java compile/test contract

`direct-jdk-v1` accepts only UTF-8 `.java` sources declared by logical path and content hash. Each logical path is a relative POSIX path whose components match `[A-Za-z0-9._]+`, with no empty, `.`, `..`, leading-hyphen, or symlink component. Learner paths under the reserved `_yuno/` test-driver namespace are rejected. Sources may use the Java 21 standard library. External classpaths, network or dependency fetches, annotation processors, agents, native libraries, GUI processes, preview features, `module-info.java`, other JVM languages, and user-controlled JVM/compiler flags are prohibited.

The application materializes every validated learner path under the per-run workspace, refuses every existing/symlink path component, and creates each file exclusively with no-follow semantics. The normalized path-to-hash mapping is one-to-one: duplicate normalized paths, duplicate materialization targets, or any target outside the workspace are rejected before confirmation. It creates empty application-owned classes and source-path directories and supplies a fresh environment containing only `LANG=C.UTF-8`, `LC_ALL=C.UTF-8`, and `TZ=UTC`. `PATH`, `CLASSPATH`, `JDK_JAVAC_OPTIONS`, `JDK_JAVA_OPTIONS`, `JAVA_TOOL_OPTIONS`, `_JAVA_OPTIONS`, and every other parent variable are excluded. The application then constructs the compile argv using sorted validated source paths:

```text
<configured-jdk-home>/bin/javac
--release
21
-proc:none
-encoding
UTF-8
--class-path
<classes-directory>
--source-path
<empty-source-path-directory>
-d
<classes-directory>
<sorted-validated-learner-java-sources...>
[<server-owned-driver-source-for-test-only>]
```

A `compile` operation stops after that phase. A `test` operation additionally requires an approved scenario manifest to provide an application-owned Java test-driver source under `_yuno/` and its explicit fully qualified main class. The driver identity is an ASCII dotted Java identifier validated independently from learner text. The driver source and hash appear in the confirmation alongside learner sources and are appended as the final source argument to the same fixed compile argv; learner inputs can never occupy or replace the reserved driver path. The application, not learner text, constructs the launch argv:

```text
<configured-jdk-home>/bin/java
-cp
<classes-directory>
<approved-test-driver-fqcn>
```

The driver uses only the standard library and exits zero only when every assertion passes; nonzero is a test failure. Its stdout/stderr is untrusted, bounded test output and is never parsed as authoritative domain data. The first alphabetically sorted learner source is never inferred as an entry point. A main-method launch without an approved test driver is a run/demo operation, not a test, and is outside the MVP contract.

Compile, test, and static-review results remain distinct. Passing this runner proves only that the declared sources compiled and the approved local driver completed under the configured process controls. It is not a sandbox, hostile-code isolation, production behavior, AWS behavior, dependency/build reproducibility, or a hiring/readiness claim.

### 2.1 Server-owned test-driver manifest

`runner-test-driver-manifest-v1` is an immutable server-owned registry. Each row contains exactly:

- stable `driver_id` and integer `driver_version`;
- approved `scenario_id` and `scenario_revision`;
- `language=java`, `operation=test`, and `build_mode=direct-jdk-v1`;
- reserved logical path under `_yuno/`, source-content reference, and SHA-256;
- validated fully qualified main class;
- `status=approved`, approval-basis reference, reviewer role, and approval date.

`(scenario_id, scenario_revision, operation)` and `(driver_id, driver_version)` are unique. A `test` confirmation requires exactly one approved row; `compile` requires none. IDK-405 owns the reviewed scenario-to-driver content binding for each test-enabled hands-on scenario. IDK-406 owns the immutable table/loader and enforcement.

`POST /runner/confirmations` replaces caller-selected language/capability and the ambiguous `artifact_id` with `goal_id`, `hands_on_work_id`, `scenario_revision`, optional `artifact_revision_id`, `operation`, declared learner inputs/hashes, and the acknowledgement version. The server verifies ownership and the work/scenario binding; when an artifact revision is supplied, its immutable content must exactly match the declared inputs. For an exploratory editor draft, the artifact reference is null and the confirmation rows are the immutable input snapshot; no `hands_on_artifacts` or evidence row is created. The server fixes Java/build mode, injects the matching driver, and records its identity/hash. The caller cannot submit or choose a driver. The confirmation response names the capability snapshot and, for `test`, the driver ID/version/path/hash/FQCN so the learner can inspect exactly what will execute.

## 3. Configuration and discovery

Discovery is configuration-led and never `PATH`-led. Configuration supplies one absolute JDK home. The runner derives only `<home>/bin/java` and `<home>/bin/javac`, resolves each target, and rejects a missing, broken, non-regular, non-executable, group-writable, or world-writable target. It parses the bounded JDK-home `release` file and requires `JAVA_VERSION`, `IMPLEMENTOR`, and `OS_ARCH` plus a module set containing `jdk.compiler`. It never substitutes another PATH executable or silently combines installations.

Platform discovery reads a bounded `/etc/os-release`, requires the exact approved Ubuntu identifiers, normalizes the machine architecture, and checks known WSL/container markers before probing Java. Missing, malformed, or contradictory platform identity fails closed without executing a toolchain.

The bounded Java probe performs all of the following. It is a trusted, application-owned, fixed-input compatibility probe: it uses no learner/scenario input and may run while IDK-007 controls are unavailable, so its result affects only the item-level toolchain state. It cannot make top-level enablement true. IDK-007 separately requires a final sentinel inside the complete broker/cgroup/namespace boundary before learner compilation; a failure to construct that boundary is a controls failure, not `sentinel-failed` JDK incompatibility.

1. Invoke configured `javac --version` and `java -XshowSettings:properties -version` as direct argv with a five-second timeout, bounded output, and the same fresh fixed environment from §2. Every JDK process, including identity probes and the sentinel, excludes all parent/Java option-injection variables.
2. Require both commands to exit zero and parse the same complete stable JDK `21.x` version, with no `-ea`, `-internal`, preview, or other prerelease identity.
3. Require `java.home` to resolve to the configured JDK home; require exact full-version agreement among `java`, `javac`, and `release`; require the `release` implementor/architecture to agree with the runtime and platform; and hash both executable identities into the snapshot.
4. Compile and launch an application-owned, fixed Java 21 sentinel with `direct-jdk-v1`; success requires exit zero and the exact bounded sentinel result.
5. Record only normalized safe metadata and a diagnostic code. Raw paths and raw probe stdout/stderr never enter an API response, learner-visible error, ordinary structured log, or evidence record.

Capability GETs may use a cache no older than 60 seconds. Its key is policy version, normalized platform/attestation, configuration revision plus canonical configured-home fingerprint, and nullable safe identities for both `java` and `javac`; absent configuration/targets use explicit sentinels. Any relevant settings change atomically invalidates the cache. Confirmation always performs a fresh probe. Enqueue verifies the same snapshot, and the worker verifies the executable device/inode/size/mtime/mode plus the sentinel immediately before learner-code execution. A changed or unverifiable installation fails without running learner code; no prior successful probe is permanent availability evidence.

## 4. Capability states and enablement

Each Java capability item uses exactly `supported`, `missing`, or `incompatible`:

| State | Meaning |
| --- | --- |
| `supported` | The configured full JDK 21 passes every current probe on the exact approved platform row and the requested operation is `direct-jdk-v1`; this is compatibility only, not execution enablement |
| `missing` | The host is an approved platform row but the JDK home, `java`, or `javac` configuration/target is absent |
| `incompatible` | The host is outside the matrix; a target is unsafe; an identity is malformed; version/home/architecture differs; the sentinel fails/times out; or the requested build mode is not approved |

Precedence is platform incompatibility, then missing required configuration/targets, then detected incompatibility, then `supported`. The API retains a separate top-level `enabled` value. It is true only when IDK-007's posture is enabled, every limit is configured, and an approved `runner_activation_evidence` row exactly matches policy, OS/version/architecture, build mode, JDK implementor/full version, and both executable identity hashes. A compatible new stable `21.x` patch or implementor can report `supported`, but remains disabled until its own evidence row is approved. Confirmation and enqueue require both `enabled=true` and the requested capability currently `supported`.

When the Java item is `supported` but that exact evidence row is absent, top-level `enabled=false`, `disabled_code=activation-evidence-missing`, and the exact message is: “Java 21 is compatible, but local execution is not activated for this exact platform and JDK build. Static review remains available; no run was started.” IDK-007 owns other top-level disabled codes/messages and their precedence; none changes the item compatibility state.

Python is not returned as a capability item in MVP. A Python request is rejected before confirmation with `python-execution-unsupported`. IDK-008 decision v1.0 makes relational/database execution absent: it is never returned as a capability item, and retired relational runner signatures receive ordinary Java-only `422` closed-schema validation before route/UoW with zero side effects.

The fixed item diagnostic/state mapping is total:

| Diagnostic code | State or request disposition |
| --- | --- |
| `jdk-home-missing`, `java-missing`, `javac-missing` | `missing` |
| `unsupported-platform`, `platform-unverifiable`, `unsafe-executable`, `probe-timeout`, `probe-failed`, `malformed-identity`, `version-mismatch`, `home-mismatch`, `architecture-mismatch`, `sentinel-failed`, `build-mode-unsupported` | `incompatible` |
| successful exact probe | `supported`, diagnostic code null |
| `python-execution-unsupported` | request rejection before confirmation; Python is not a capability item |

Condition mapping is exact: wrong OS/version/architecture or a positive WSL/container marker yields `unsupported-platform`; missing, malformed, unreadable, or contradictory OS identity and missing/malformed host-or-VM attestation yield `platform-unverifiable`. Tool conditions map directly to the correspondingly named code above; probe nonzero, timeout, and malformed output remain distinct.

No diagnostic substitutes raw OS/tool output, filesystem paths, environment values, or learner source.

## 5. Exact learner messages

The API/UI selects one fixed message from the diagnostic code; braces contain only normalized safe display values. Unsupported OS display is reduced to `linux`, `macOS`, `windows`, or `unknown`; version is digits and dots or `unknown`; architecture is `x86_64`, `arm64`, or `unknown`; and safe Java version is digits and dots or `unknown`.

| Code | Message |
| --- | --- |
| `unsupported-platform` | “Local execution is unavailable on {os} {version} ({arch}). Runner policy 1.0 supports Ubuntu 24.04 LTS on x86_64 or arm64 only. Static review remains available; no run was started.” |
| `platform-unverifiable` | “Local execution is unavailable because this host platform could not be verified. Static review remains available; no run was started.” |
| `jdk-home-missing` | “Java Run is unavailable because a JDK home is not configured. Configure one complete JDK 21 installation, then refresh capabilities. No run was started.” |
| `java-missing` | “Java Run is unavailable because `java` is missing from the configured JDK 21 home. Configure a complete JDK, then refresh capabilities. No run was started.” |
| `javac-missing` | “Java Run is unavailable because `javac` is missing from the configured JDK 21 home. Configure a complete JDK, then refresh capabilities. No run was started.” |
| `unsafe-executable` | “Java Run is unavailable because the configured JDK installation did not pass local executable safety checks. Correct the installation, then refresh capabilities. No run was started.” |
| `probe-timeout`, `probe-failed`, `malformed-identity`, `sentinel-failed` | “Java Run is unavailable because the configured JDK could not be verified ({reason}). Check the installation, then refresh capabilities. No run was started.” |
| `version-mismatch` | “Java Run supports a stable full JDK 21 only. The configured JDK reports {safe-version}. Configure JDK 21, then refresh capabilities. No run was started.” |
| `home-mismatch` | “Java Run is unavailable because `java` and `javac` do not resolve to the same configured JDK home. Configure one complete JDK 21 installation. No run was started.” |
| `architecture-mismatch` | “Java Run is unavailable because the configured JDK architecture does not match the supported host architecture. Configure a matching JDK 21 installation. No run was started.” |
| `build-mode-unsupported` | “This exercise requires an unsupported build mode. Runner policy 1.0 uses `javac` and `java` directly; Maven, Gradle, Ant, project wrappers, and external dependencies are not run. Static review remains available.” |
| `python-execution-unsupported` | “Python execution is not available in runner policy 1.0. Static review remains available; no run was started.” |

The `{reason}` values are exact: `probe-timeout` → “the probe timed out”; `probe-failed` → “the probe failed”; `malformed-identity` → “the tool identity was malformed”; `sentinel-failed` → “the compile/run sentinel failed”.

When compatible and enabled, the disclosure is exactly: “Java 21 compile/test is available on Ubuntu 24.04 ({arch}) using direct JDK tools. It runs only declared sources and an approved test driver in a controlled local process. It is not a security sandbox and does not prove production or AWS behavior.”

IDK-007 owns the exact disabled-by-policy and resource-limit recovery messages. Those messages must not imply that a compatible toolchain makes execution enabled.

## 6. Records and change control

IDK-406 replaces the current ad-hoc capability result with three immutable record types:

- `runner_capability_snapshots`: policy/build mode; state and diagnostic; normalized platform/attestation; nullable JDK feature/full version/implementor/architecture and nullable `java`/`javac` identity hashes; probe/expiry timestamps; and nullable environment/limits policy versions. Full tool identity and both hashes are required exactly for `supported`; relevant partial identity may be retained for `incompatible`; tool fields are absent for `missing` and failures before tool discovery. Environment/limits versions are both required and exact-evidence-matching when top-level enabled.
- `runner_activation_evidence`: the exact policy, platform, architecture, build mode, JDK implementor/full version, both executable hashes, environment/limits policy versions, compile/test/limit/cancel/cleanup evidence references, approver role, and approval time. The exact tuple is unique and rows are immutable.
- `runner_test_driver_manifests`: the versioned server-owned driver contract in §2.1.

`runner_confirmations` and `runner_records` each require FKs to the exact capability snapshot and activation-evidence row; a test confirmation/run additionally requires the test-driver-manifest FK. A confirmation cannot be created without a currently enabled exact tuple. Existing result rows retain these immutable references.

`GET /runner/capabilities` returns top-level `enabled`, fixed safe `disabled_code`/`disabled_message`, policy/environment/limits versions, and capability items containing `policy_version`, `build_mode`, `state`, `diagnostic_code`, fixed `message`, normalized `{os, version, arch}`, and safe `{feature_version, full_version, implementor, arch}` toolchain metadata. It removes free-form `detail`; it returns no path, raw probe output, executable hash, or evidence locator.

Every capability snapshot records, subject to the state-dependent nullability above:

- `runner-toolchain-v1`;
- normalized OS ID/version/architecture and attestation to the extent safely discovered;
- nullable Java feature/full version, normalized implementor, and reported architecture, required exactly for `supported`;
- build mode `direct-jdk-v1`;
- probe time and fixed diagnostic code;
- nullable safe executable identity hashes, both required exactly for `supported`, never raw configured paths;
- nullable environment-policy and limits-policy versions separately owned by IDK-007, both required exactly when top-level enabled.

Top-level enablement resolves `activation_evidence_ref`, absent while disabled and required exactly when enabled. The confirmation and runner record reference the exact capability snapshot and activation evidence. A later policy version may recompute availability, but an existing result retains its original toolchain, scenario, inputs, test-driver, environment, limits, and activation-evidence references.

Version 1.0 is immutable. Adding/removing an OS, architecture, Java feature, learner language, build tool, wrapper, dependency mechanism, container/VM posture, or invocation shape requires a new approved policy version and complete fixtures plus activation evidence for every new row. Stable JDK 21 patch and implementor changes intentionally remain compatible within this row when the full paired identity and sentinel pass, but they never activate automatically: each exact implementor/full-version/architecture/executable-hash tuple requires new smoke evidence and approval. Supersession removes the obsolete execution path; it does not add a compatibility fallback.

## 7. Activation ownership and evidence

Approval of this document resolves the IDK-005 policy question only. IDK-406 owns these required implementation changes before compatibility may report `supported`, and the evidence requirements before top-level `enabled` may become true:

1. Replace the current threaded `subprocess` `preexec_fn` boundary with a dedicated, application-owned Linux launcher/helper that establishes the complete approved IDK-007 cgroup/namespace/mount/filter/resource boundary before `exec`. The helper opens the configured target with `O_NOFOLLOW`, validates the open descriptor against the capability snapshot, and uses descriptor-bound execution (`fexecve` or an equivalent kernel-bound primitive); path re-resolution between verification and execution is prohibited.
2. Implement exact OS/architecture/WSL/container detection and the absolute configured-JDK-home probe above.
3. Probe and pin both `java` and `javac`, execute the sentinel, and revalidate before confirmation, enqueue, and worker execution.
4. Replace first-source main-class inference with the approved scenario-owned test driver and explicit fully qualified entry point; remove the obsolete inference path.
5. Remove false Python and configured-string relational `supported` reports. Python and relational/database execution both stay absent under the approved policies.
6. Persist the matrix/build-mode/safe-platform/tool identity and evidence references, and render only the fixed messages above.
7. Test every state, diagnostic, and exact message; unsafe/missing/replaced fake executables; version/home/architecture mismatch; cache expiry; pre-enqueue and worker races; exact compile/test argv; unsupported Maven/Gradle/wrapper/Python requests; and the no-learner-execution failure path.
8. Record end-to-end compile/test, timeout/limit, cancellation, child-process cleanup, and temp cleanup evidence on Ubuntu 24.04 for each exact architecture/JDK identity tuple before activating it. Compatible tuples without their own evidence remain top-level disabled.

IDK-007 decision v1.0 additionally fixes every limit and the overall enablement posture. IDK-008 decision v1.0 fixes database execution as absent. Until IDK-406 implements these policies and the evidence above passes, Run remains absent/disabled and Submit/static review remains fully usable.

## 8. Evidence and approval basis

The engineering owner reviewed the current implementation and official primary documentation on 2026-08-13.

- Oracle's Java roadmap identifies Java 21 as an LTS release: <https://www.oracle.com/java/technologies/java-se-support-roadmap.html>.
- Oracle documents JDK 21 installation for Linux and both x64 and AArch64 packages: <https://docs.oracle.com/en/java/javase/21/install/installation-jdk-linux-platforms.html>.
- Ubuntu documents 24.04 LTS standard security maintenance through May 2029: <https://documentation.ubuntu.com/release-notes/24.04/>.
- Python documents `resource`, `os.wait4`, and `os.killpg` as Unix-only interfaces: <https://docs.python.org/3/library/resource.html> and <https://docs.python.org/3/library/os.html>.
- Python documents that `subprocess` `preexec_fn` is POSIX-only and unsafe in threaded applications because it may deadlock before `exec`: <https://docs.python.org/3/library/subprocess.html>.
- Oracle documents `javac` class/source paths and `JDK_JAVAC_OPTIONS`, and documents Java option-injection environment variables; the approved runner therefore sets its paths explicitly and forwards none of them: <https://docs.oracle.com/en/java/javase/21/docs/specs/man/javac.html> and <https://docs.oracle.com/en/java/javase/21/troubleshoot/environment-variables-and-system-properties.html>.
- Maven's official release history and Gradle's official installation guidance establish that those are separate build-tool surfaces; neither is invoked by the approved direct-JDK contract: <https://maven.apache.org/docs/history.html> and <https://docs.gradle.org/current/userguide/installation.html>.

Read-only local inspection found a macOS 27 arm64 host, OpenJDK 17 command-line tools, Maven using a different JDK, no Gradle, and CPython 3.13. Those observations are not support evidence for any approved row. They demonstrate why PATH presence, a compiler-only probe, or an ambient build-tool installation cannot establish the approved paired identity. No learner code or runner process was executed for this decision.
