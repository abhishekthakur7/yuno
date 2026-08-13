# IDK-004 — Role-level competency descriptions

This decision approves the learner-facing role-level copy used to choose practice scope. It resolves the copy policy only; it does not claim that consuming screens have activated the copy before the evidence in section 6 passes.

## 1. Status and contract

Approved as decision version 1.0 on 2026-08-13.

Owner and approver: product owner, acting through the project implementation request.

| Contract | Approved version |
| --- | --- |
| Role competency copy | `role-competency-copy-v1` |
| Persisted target levels | `Mid-level`, `Senior`, `Staff` |
| Persisted target capabilities | `know`, `understand`, `choose`, `implement`, `diagnose`, `defend` |

The three target-level values remain the existing wire and storage contract. This decision adds display metadata keyed by those values; it adds no alias, company field, beginner tier, migration, or compatibility path.

## 2. Exact learner-facing copy

Heading:

> Choose the scope you want to practice

Audience note:

> Yuno is for backend engineers who have already shipped software. It does not include an absolute-beginner track.

Title-variation helper:

> Titles vary across companies. Choose the description closest to the scope you want to practice—not necessarily your current title. You can change it later. This choice changes scenario breadth and evaluation expectations; it does not validate a title or predict hiring, promotion, or job performance.

| Stored value | Display label | Competency description |
| --- | --- | --- |
| `Mid-level` | Mid-level backend engineer | Work within a bounded service or data path, with attention to correctness, testability, direct failures, and local operational consequences. |
| `Senior` | Senior backend engineer | Work across an end-to-end multi-service and data flow, including partial failure, rollout, recovery, observability, and alternatives under constraints. |
| `Staff` | Staff-level backend engineer | Work across systems and teams, including decision boundaries, migration and rollback, second-order failure, capacity, cost, ownership, governance, and exceptions. |

Target-capability helper:

> Level sets the scope of practice. Capability sets what you want to demonstrate now. Choose one; you can edit it before confirming the goal and later in Settings.

The descriptions are targets for practice, not claims about the learner's current competence. They deliberately contain no years-of-experience band, people-management requirement, promotion criterion, compensation claim, employer ladder, or hiring prediction. `Mid-level` is not a beginner or entry-level track; `Staff` does not imply people management.

## 3. Capability-ladder interpretation

Every target level permits every capability. Level changes the breadth and evaluation bar; capability states the action the learner wants to demonstrate. A level never removes a capability, hides a roadmap topic, or creates evidence, completion, or LearningState.

| Capability | Meaning | Mid-level scope | Senior scope | Staff scope |
| --- | --- | --- | --- | --- |
| `know` | Recall accurate terminology and facts. | Bounded service or data path. | Multi-service or data flow. | Cross-system or platform context. |
| `understand` | Explain mechanisms and constraints. | Local runtime and data behavior. | Inter-service and operational behavior. | Systemic and organizational consequences. |
| `choose` | Select an approach under constraints. | Local implementation choice. | End-to-end design or rollout choice. | Decision boundaries, platform, or migration direction. |
| `implement` | Produce a testable artifact or precise implementation. | Direct service or data-path change. | Feasibility proof, invariant, or rollout-safe change. | Prototype, contract, migration guardrail, or reference implementation. |
| `diagnose` | Use evidence to find cause and recovery. | Direct failure. | Partial or distributed failure. | Systemic or second-order failure and ownership gaps. |
| `defend` | Justify and revise under challenge. | Local choice and consequence. | Architecture and trade-offs as constraints change. | Cross-team boundaries, economics, governance, exceptions, and reversal criteria. |

The target level and capability are independent, explicit selections. The UI composes the selected scope description with the chosen capability meaning; the level copy does not require a particular action. Staff does not mean “no implementation,” and Mid-level does not prohibit defense.

## 4. Ambiguity and history rules

- First-use setup has no preselected level. The learner makes and confirms an explicit selection before continuing. The product never infers or silently changes level from a current title, employer, years of experience, imported text, diagnostic answers, assessment results, or model output.
- “Not sure” is helper text, not a fourth stored level: choose Mid-level for bounded component work, Senior for end-to-end flows, or Staff for cross-system and multi-team decisions.
- An invalid or missing stored value fails closed to a required selection rather than silently becoming Senior or another level.
- Returning to an unconfirmed setup restores the learner's saved explicit choice. Existing goal and bundle editors show the stored value.
- Changing a target affects future scenario selection, evaluation expectations, context, and recommendations only. Existing evidence and assessments retain their recorded scenario, rubric, level, and capability; those stored records are never rewritten. Current explanatory role copy may follow a later approved copy version without changing that historical assessment meaning.
- Diagnostic or evidence may recommend depth or capability, but it cannot silently change either explicit target selection.

## 5. Alignment and application

These learner-facing descriptions are the counterpart to IDK-009 section 3's evaluator calibration:

- Mid-level: bounded implementation, direct diagnosis, and local consequences.
- Senior: multi-service flow, partial failure, rollout, recovery, observability, and trade-offs.
- Staff: cross-system and multi-team boundaries, migration, rollback, second-order failure, capacity, cost, ownership, governance, and exceptions.

Neither decision overrides the other. This copy changes no IDK-009 scenario ID, rubric, capability binding, or derived-state rule. A mismatch fails closed during IDK-405 and IDK-503 review.

One versioned copy registry supplies onboarding, goal Settings, Interview Prep role/level controls, and scenario role-context help. Compact controls may show only the exact display label, but the title-variation helper and selected description must be available adjacent to the selection and programmatically associated with it. Onboarding shows all three choices and the audience note; no beginner option appears.

## 6. Required activation evidence

Approval is not production activation. Before `role-competency-copy-v1` is treated as active:

- IDK-104 proves the exact heading, three stored values and labels, descriptions/helpers, no beginner option, no first-use preselection, accessible association, and no persistence before explicit confirmation. IDK-105 proves the explicit level/capability can be edited before goal confirmation and that the final choice persists across pause/reload.
- IDK-301 proves the shared copy is used for generic Interview Prep role/level controls, the heading follows the selected level, and no company-specific field or claim is introduced.
- IDK-405 proves all six approved IDK-009 hands-on scenario records map to the exact three level values and use this shared learner-facing calibration without replacing IDK-009's evaluator calibration.
- IDK-503 manually reviews the shipped copy and IDK-009 scenario metadata together, including ambiguous company-title examples and assistive-technology access to the selected description.

Until those checks pass, the stable tier names may remain visible, but invented or unapproved competency prose must not be presented as final copy.

## 7. Change control and approval record

A meaning change requires `role-competency-copy-v2` and a new product-owner approval. Existing goal and bundle records retain their stable enum values. Historical assessment meaning remains fixed by its recorded scenario, rubric, level, and capability metadata; activating new explanatory copy rewrites none of those records.

| Approver | Role | Date | Decision | Version | Evidence reference |
| --- | --- | --- | --- | --- | --- |
| Product owner | Product owner | 2026-08-13 | Approved without changes | 1.0 | Sections 2–6 and the project implementation request |

Decision values: `approved`, `changes requested`. This approval resolves IDK-004 and, together with approved IDK-009 decision version 1.0, removes IDK-405's remaining decision blocker. It does not mark IDK-405 implemented or production-active.
