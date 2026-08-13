# IDK-006 — Provider CLI support decision

Status: approved

Decision version: `1.1`

Approval date: 2026-08-13

Approver role: engineering owner, acting through the implementation request that directed approval and recording of IDK-006

This decision approves a local-only CLI integration. It does not approve SaaS infrastructure, remote support, telemetry, deployment machinery, automatic provider fallback, API-key forwarding, or background source retrieval.

## Supported providers and versions

| Provider | Supported CLI versions | Pinned model behavior | Adapter version | Output contract |
| --- | --- | --- | --- | --- |
| Codex CLI | Any installed release identified by the canonical `codex-cli VERSION` output and the required command-surface probe | Always `gpt-5.6-terra` with reasoning effort `high` | `codex-cli-adapter-v1` | `codex-jsonl-agent-message-v1` |
| Claude Code | Any installed release identified by the canonical `VERSION (Claude Code)` output and the required command-surface probe | Always the fixed model ID `claude-sonnet-4-6`; moving aliases and account defaults are prohibited | `claude-code-adapter-v1` | `claude-stream-json-structured-output-v1` |

There is no numeric lower bound, upper bound, major-version pin, or prerelease exclusion. The locally available CLI is used when the resolved executable identifies itself with the provider's bounded canonical version shape, exposes every required command flag, and passes the safe authentication probe. Numeric version comparison is deliberately absent; the executable identity and command-surface probes are the mechanical compatibility boundary. Unidentified output and missing required flags fail closed because they do not establish that the configured executable can run the approved direct argv.

## Approved direct argv

Every item below is an argv element. No item is interpreted by a shell, and subprocess execution uses `shell=False`. `<executable>` is the already-resolved absolute regular executable, `<schema-file>` is an owner-only file under the per-request restricted temporary directory, `<schema-json>` is the canonical JSON Schema generated from the operation's pinned Pydantic contract, and `<work-dir>` is that restricted directory. Learner prompt and context are never argv elements.

Codex uses the same transport for topic generation/regeneration, evidence/Practice/Mock-final evaluation, Mock next-turn generation, and tutor turns:

```text
<executable>
--ask-for-approval
never
exec
--ephemeral
--ignore-user-config
--ignore-rules
--model
gpt-5.6-terra
--config
model_reasoning_effort="high"
--sandbox
read-only
--json
--output-schema
<schema-file>
--cd
<work-dir>
--skip-git-repo-check
--color
never
-
```

Claude Code uses the same transport for those operations, with the operation-specific schema replacing `<schema-json>`:

```text
<executable>
-p
--input-format
text
--output-format
stream-json
--verbose
--json-schema
<schema-json>
--model
claude-sonnet-4-6
--tools
""
--strict-mcp-config
--no-session-persistence
--permission-mode
dontAsk
--safe-mode
```

The canonical request envelope containing purpose, context, and output-schema version is written to stdin. Source retrieval does not use either provider command: it remains a separate explicit URL retrieval job under the separate `source-network-v1` disclosure.

## Discovery and configuration

Executable discovery is configuration-led, not `PATH`-led. The approved defaults are `/opt/homebrew/bin/codex` and `/opt/homebrew/bin/claude`; an override must be an absolute path. Discovery resolves symlinks once, rejects missing/broken/non-regular/non-executable/group-writable/world-writable targets, and invokes the resolved target. A later `PATH` substitution cannot change the selected executable.

Version discovery invokes only:

- Codex: `<resolved-codex> --version`, accepting exactly `codex-cli MAJOR.MINOR.PATCH`.
- Claude Code: `<resolved-claude> --version`, accepting exactly `MAJOR.MINOR.PATCH (Claude Code)`.

Required-flag discovery invokes the corresponding local `--help` surfaces and checks only fixed flag names. Raw help/version/authentication stdout and stderr are discarded after private parsing and never enter an API response, structured log, diagnostic row, or audit record.

Authentication/configuration discovery never reads or parses a credential file:

- Codex: `<resolved-codex> login status`; exit zero means configured, every other outcome means authentication/configuration unavailable. Output is not parsed.
- Claude Code: `<resolved-claude> auth status --json`; configured requires exit zero and a bounded JSON object whose `loggedIn` member is exactly `true`. All other shapes/outcomes are unavailable. No identity, email, organization, subscription, authentication method, or credential value is retained.

The same fixed authentication probe runs immediately before each paid/model invocation. Authentication revoked after a capability refresh is therefore classified as `authentication-unavailable` before learner context is delivered. The resolved executable's device, inode, modification time, size, and mode are pinned with the cached adapter; replacement requires an explicit capability refresh and otherwise fails as a version/command-surface mismatch.

Installation is not authentication. A prior successful job is never configuration evidence. Capability discovery runs at application startup, is cached for HTTP reads, and is repeated only through the explicit capability refresh control. Adapter lookup uses that same cache. Refresh replaces the complete per-provider snapshot atomically.

The learner-visible states are fixed:

| State | Meaning | Recovery guidance |
| --- | --- | --- |
| `executable-missing` | The configured absolute CLI executable is absent or unsafe | Install the supported CLI or correct its absolute path, then refresh |
| `unsupported-version` | The executable cannot be identified as the expected CLI or lacks required command flags | Install a CLI build exposing the required command surface, then refresh |
| `authentication-unavailable` | The supported CLI's safe status probe did not confirm local configuration | Complete that CLI's own local sign-in, then refresh |
| `configured` | Executable, version, required flags, and authentication/configuration probe all passed | The provider may be selected |

No raw subprocess error, path, identity, or authentication detail is learner-visible.

## Environment policy

Only existing values for these exact keys may cross the subprocess boundary:

| Provider | Allowlist |
| --- | --- |
| Codex | `HOME`, `PATH`, `TMPDIR`, `LANG`, `LC_ALL`, `CODEX_HOME`, `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`, `SSL_CERT_FILE`, `SSL_CERT_DIR`, `CODEX_CA_CERTIFICATE` |
| Claude Code | `HOME`, `PATH`, `TMPDIR`, `LANG`, `LC_ALL`, `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`, `SSL_CERT_FILE`, `SSL_CERT_DIR`, `NODE_EXTRA_CA_CERTS` |

Proxy URLs containing a username or password are rejected rather than forwarded. Values are never logged or returned. API keys, access/session tokens, cookies, authorization headers, AWS/cloud credentials, database/connection secrets, arbitrary parent environment entries, shell startup variables, editor variables, unrelated application settings, usernames as standalone values, and any environment key not listed above are prohibited. In particular, `OPENAI_API_KEY`, `CODEX_API_KEY`, `CODEX_ACCESS_TOKEN`, `ANTHROPIC_API_KEY`, and `ANTHROPIC_AUTH_TOKEN` are not approved. Authentication uses only the CLI's own local credential store as reached by the CLI itself.

## Timeouts, cancellation, and output

The approved timers are:

- first valid stdout JSON event: 20 seconds;
- inactivity after a valid stdout JSON event: 180 seconds;
- absolute process lifetime: 1,200 seconds.

Stderr, arbitrary bytes, and incomplete/malformed lines are not heartbeat evidence. Timer outcomes remain distinct: `no-first-output`, `inactivity-timeout`, and `absolute-timeout`. Cancellation and every timeout send `SIGTERM` to the recorded process group, wait the bounded termination grace already owned by the shared process implementation, then send `SIGKILL` to the same group if it still exists. PID, PGID, process-start identity, and restricted temp path are persisted before request bytes are written. Startup reconciliation verifies process identity before signalling and never kills a reused PID.

Provider stdout is capped at 2 MiB and stderr at 64 KiB; discovery-probe streams are capped at 64 KiB each. Crossing a ceiling terminates the full process group and returns only the fixed `output-limit` classification. Failed/provider-error streams are discarded. Only schema-invalid output enters the governed quarantine store and its IDK-010 deletion lifecycle.

Codex output is a JSONL event stream and succeeds only with one completed turn and one final completed `agent_message` whose text is strict JSON. Claude output is a stream-JSON event sequence and succeeds only with one non-error result event containing `structured_output`. Duplicate JSON object members at any depth, malformed/truncated events, extra domain fields, wrong schema/contract versions, adversarial nested types, missing/duplicate terminal events, and any payload rejected by the operation-specific strict schema are quarantined. Provider error events and nonzero exit are safe process failures, not domain results.

Only the schema-validated mapping crosses the provider port. Invalid raw output is stored only in the approved owner-local quarantine store, referenced by hash, excluded from ordinary logs/search/results/domain publication, and deleted under IDK-010 policy 1.0. A missing command surface disables that provider until the installed CLI exposes the approved argv contract or the adapter contract is deliberately revised; numeric CLI version changes alone never disable it.

## Evidence and approval basis

The engineering owner reviewed current official primary documentation and performed read-only local command inspection. No credential file was read, no raw authentication result was exposed, and no model/network invocation was made.

- OpenAI Codex CLI command reference, accessed 2026-08-13: <https://learn.chatgpt.com/docs/developer-commands?surface=cli>. It documents `codex exec`, stdin prompt `-`, `--json`, `--output-schema`, `--ephemeral`, `--ignore-user-config`, `--ignore-rules`, `--model`, `--sandbox`, and `codex login status`.
- OpenAI Codex non-interactive reference, accessed 2026-08-13: <https://learn.chatgpt.com/docs/non-interactive-mode>.
- Anthropic Claude Code CLI reference, accessed 2026-08-13: <https://code.claude.com/docs/en/cli-usage>. Anthropic headless reference: <https://code.claude.com/docs/en/headless>. Authentication reference: <https://code.claude.com/docs/en/authentication>.
- Anthropic model configuration and model IDs, accessed 2026-08-13: <https://code.claude.com/docs/en/model-config> and <https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions>. These support the fixed `claude-sonnet-4-6` provenance ID.
- The approved Codex `gpt-5.6-terra` / `high` policy comes from the existing product authority in PRD AI-02 and D7, not from an unperformed live availability probe. Discovery proves the CLI supports explicit `--model` and `--config`; actual account/model availability remains a safely classified invocation outcome.
- Local isolated inspection on 2026-08-13: `/opt/homebrew/bin/codex --version` reported `codex-cli 0.147.0`; `/opt/homebrew/bin/claude --version` reported `2.1.220 (Claude Code)`. Codex root and `exec --help`, Claude root and `auth status --help`, and both fixed status commands demonstrated every approved flag/status surface. Status results were reduced to the fixed `configured` classification without emitting raw output.
- Deterministic tests exercise accepted and malformed CLI identity shapes, required command flags, exact argv, minimized environment, safe status reduction, cache refresh, event envelopes, timers, cancellation, schema quarantine, and publication isolation. Those tests, not a paid live invocation, are the authoritative automated compatibility evidence.

The timeout values are an application safety policy, not a claim about provider latency or an external service-level objective. A model change, environment addition, or argv/output-contract change requires a new decision version and contract fixtures before it can report configured. Installing a different CLI version does not require a decision update when the same identification, command-surface, authentication, and output-contract checks pass.

The engineering owner explicitly approved the 20-second first-valid-output, 180-second inactivity, and 1,200-second absolute timeout policy on 2026-08-13 after reviewing the completed implementation and validation evidence.

Decision version 1.1 supersedes the numeric ranges in version 1.0. On 2026-08-13, the engineering owner directed the runtime to use whatever locally installed CLI version is available; numeric version pinning and range rejection were therefore removed while executable identification and capability probes remain fail closed.
