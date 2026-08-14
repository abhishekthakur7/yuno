"""IDK-501: Alembic representative-upgrade coverage.

Three areas, each a distinct acceptance criterion of the ticket:

1. `test_every_revision_upgrades_forward_to_head` -- parametrized over
   every revision id in the installed chain (mechanically derived from
   `ScriptDirectory.walk_revisions()`, never hardcoded): a fresh database
   stamped at that revision upgrades cleanly to `head` and the resulting
   schema matches `Base.metadata` exactly (`alembic check`). `downgrade()`
   is never called anywhere in this file -- `c5b1e70a94d2`'s is a
   deliberate `NotImplementedError` (forward-only, see that module's
   docstring), so calling it would fail every parametrized case.

2. `test_representative_fixture_upgrades_to_head_with_zero_governed_data_loss`
   -- builds one database at `GOVERNED_DATA_LOSS_BASELINE` (currently
   `fb1c910aedc7`'s own parent; see that constant's docstring for why this
   is a distinct constant from `HEAD_MINUS_ONE` below and what its one
   deliberate schema-difference exception is), seeds spec §4.8's
   representative scenarios through the real services/repositories the
   product itself uses (never `Base.metadata.create_all`, never
   hand-written INSERTs for governed domain data), snapshots every
   governed table, upgrades to `head`, and asserts byte-for-byte
   preservation.

   Represented (all ten named in spec §4.8 / this ticket):
     1. two goals with cross-goal transferred evidence
        -- `tests/integration/test_evidence_transfer_delete.py::_seed`
        plus `evidence_evaluation.service.transfer_evidence`.
     2. a paused diagnostic session -- `diagnostics.service.create_diagnostic`
        / `append_diagnostic_answer` / `patch_diagnostic(PAUSE)` called
        directly (no canonical topic lookup is on this path -- see
        `diagnostics.domain.next_question`, which reasons only from the
        session's own prior answers).
     3. approved canonical graph v1 and v2 with a goal pinned mid-transition
        -- `_publish_fixture` below (same `uow.canonical.*` calls as
        `canonical.publisher.publish_canonical_graph`, minus its
        `require_single_head(engine)` step 1 -- see that helper's
        docstring for why) publishing `tests/fixtures/canonical`'s
        `v1_approved` then `v2_approved`, with a goal created via
        `profiles_goals.service.create_goal` pinned to v1 and never
        repinned.
     4. an overlay conflict plus an upstream-deleted topic carrying local
        state -- the same goal gets a depth override on
        `fixture-topic-alpha` (a topic v2 modifies) and a skip decision on
        `fixture-topic-gamma` (a topic v2 drops), applied *before* v2
        publishes, by calling `api.routes.roadmap.post_depth`/`post_skip`
        directly against a hand-built `UnitOfWork` -- those two functions
        are plain Python (FastAPI's `Depends(...)` markers only matter to
        the ASGI layer), exactly `test_canonical_merge_api.py::_setup`'s
        `local_state=True` branch minus its `client.post(...)` calls. This
        proves the *state* a merge proposal would need survives the
        upgrade; actually computing/accepting a merge proposal is a
        separate feature this ticket does not exercise.
     5. imports -- `imports.service.create_import` attached to the same
        goal, exactly `_setup(imported=True)`.
     6. a generated artifact with a provenance snapshot --
        `learning_content.service.reserve_generation` +
        `run_generation` called directly with
        `test_generated_content_api.py`'s `FakeGenerationAdapter`/`_source`.
        `run_generation` *is* the dispatcher's job-handler body; calling
        it synchronously runs the identical persistence logic without the
        dispatcher/provider-disclosure plumbing that only exists to
        schedule and gate work over HTTP (unreachable here -- see below).
     7. an active job -- `jobs_events.repository.JobRepository.enqueue`
        directly against a hand-built session, exactly the construction
        `test_durable_jobs.py` uses throughout.
     8. a job requiring startup recovery reconciliation --
        `JobRepository.enqueue` + `.add_attempt(...)` left `running` with
        a stale process identity and *not* reconciled, exactly
        `test_durable_jobs.py::test_startup_reconciles_active_states_and_sweeps_temp_path`'s
        setup (the reconciliation call itself is deliberately omitted:
        leaving the job un-reconciled is the point).
     9. a completed Mock transcript -- `interview.service.create_bundle`
        / `create_mock_run` / `validate_mock_completion` /
        `evidence_evaluation.service.create_evidence` /
        `reserve_mock_completion` seeded at the baseline like everything
        else, then (deliberately *after* `command.upgrade(config,
        "head")` -- see `GOVERNED_DATA_LOSS_BASELINE`)
        `api.routes.interview.run_mock_final_evaluation_job` called
        directly (again, the dispatcher's job-handler body) with a rubric
        seeded via `test_mock_report_api.py::_seed_rubric` and a fixture
        `EvaluationAdapter`. Still a real service call end to end, just
        one that happens post-upgrade rather than pre-upgrade for this
        one migration cycle.
    10. a deliberately stale FTS5 projection -- `uow.search.rebuild(...)`
        (the real projection build), then one more real write
        (`create_evidence`) *after* that rebuild with no further rebuild.
        `SearchRepository.state()` computes staleness by comparing the
        stored watermark to a fresh recomputation, so this is genuine
        staleness, not a hand-set status string.

   None omitted: every construction above goes through a real
   service/repository call; the only raw SQL in this module is in
   sections 3 and 4 below, exactly where the ticket says raw SQL is
   correct because no service can produce that data.

   This database cannot use the `client`/`TestClient` fixture: `create_app`'s
   ASGI lifespan calls `alembic_guard.require_single_head`, which refuses a
   database below head (that refusal is itself IDK-501/IDK-101's subject).
   The offline publisher (`canonical.publisher.publish_canonical_graph`)
   calls the same guard for the same reason, which is why `_publish_fixture`
   below re-implements its persistence steps instead of calling it.

3. `test_relational_placeholder_disposal_is_bounded_and_controls_survive`
   -- IDK-501's headline criterion. A database at `f06c40340400` gets a
   hand-inserted `language='relational'` runner/job placeholder subgraph
   (raw SQL: no service can create a `relational` row -- the value is
   retired) plus a control set that must all survive (an unrelated
   `language='java'` runner/job pair, an unrelated non-runner job, and
   real goal/evidence/artifact rows built through services). After
   upgrading to `head`: every placeholder-owned row is gone, every
   control row is byte-identical, no surviving `jobs`/`runner_records`
   row's logical reference points at a removed id, and the narrowed CHECK
   rejects a fresh `language='relational'` insert.

4. `test_language_python_row_stops_the_migration_with_a_diagnostic` -- the
   ticket's required negative case (also satisfies the "one genuinely
   broken revision" parametrization the implementation notes ask for): a
   `language='python'` row is not covered by the approved disposal, so the
   migration must raise rather than silently delete it, and must leave the
   database at its last committed revision (no partial state).
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from tests.fixtures.canonical import load_fixture
from tests.integration.test_evidence_transfer_delete import (
    _seed as _seed_evidence_transfer,
)
from tests.integration.test_generated_content_api import FakeGenerationAdapter
from tests.integration.test_mock_report_api import _seed_rubric
from yuno.api.contracts import DepthOverrideRequest, SkipDecisionRequest
from yuno.api.routes.interview import run_mock_final_evaluation_job
from yuno.api.routes.roadmap import post_depth, post_skip
from yuno.modules.canonical.domain import (
    CanonicalGraphVersion,
    CanonicalVersionStatus,
    EditorialApproval,
    TopicIdentity,
)
from yuno.modules.diagnostics.domain import (
    DiagnosticAction,
    DiagnosticConfidence,
    next_question,
)
from yuno.modules.diagnostics.service import (
    append_diagnostic_answer,
    create_diagnostic,
    patch_diagnostic,
)
from yuno.modules.evidence_evaluation.domain import (
    AssessmentState,
    DimensionOutcome,
    EvaluationDimensionResult,
    EvaluationResult,
    TransferClassification,
)
from yuno.modules.evidence_evaluation.service import create_evidence, transfer_evidence
from yuno.modules.identity.service import ensure_local_owner
from yuno.modules.imports.domain import ImportType
from yuno.modules.imports.service import create_import
from yuno.modules.interview.service import (
    create_bundle,
    create_mock_run,
    get_bundle,
    reserve_mock_completion,
    validate_mock_completion,
)
from yuno.modules.jobs_events.repository import JobRepository
from yuno.modules.learning_content.domain import TopicLayer
from yuno.modules.learning_content.service import reserve_generation, run_generation
from yuno.modules.profiles_goals.domain import GoalPath, TargetCapability, TargetLevel
from yuno.modules.profiles_goals.service import create_goal, ensure_profile
from yuno.modules.search.domain import SearchIndexStatus
from yuno.modules.settings_data.service import ensure_owner_settings
from yuno.shared.application.jobs import JobLane, JobRequest
from yuno.shared.application.unit_of_work import UnitOfWorkFactory
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.ids import new_id
from yuno.shared.infrastructure import alembic_guard
from yuno.shared.infrastructure.database import (
    create_engine_for,
    create_session_factory,
)
from yuno.unit_of_work import create_unit_of_work_factory

# The Java-only runner revision's (`c5b1e70a94d2`) own `down_revision`.
# Narrowing the two `language_valid` CHECK constraints (and the bounded
# relational-placeholder disposal that precedes it) is that revision's
# *entire* schema diff from here, which is what
# `test_relational_placeholder_disposal_is_bounded_and_controls_survive`
# and `test_language_python_row_stops_the_migration_with_a_diagnostic`
# below exercise: they need the pre-narrowing CHECK (permitting a hand-
# inserted `language='relational'` row) still in force at this baseline,
# so this stays pinned to the runner migration's own parent regardless of
# which revision is current `head`.
HEAD_MINUS_ONE = "f06c40340400"

# `fb1c910aedc7`'s (IDK-204) own `down_revision` -- `head`'s parent at the
# time this constant was introduced; two migrations (`4747447ccaa3`,
# `4cb74877e4ba`) have landed on top of `fb1c910aedc7` since, so this is
# now `head`'s great-grandparent, not its parent. It is deliberately *not*
# bumped forward to track `head`: doing so would shrink the span of
# migrations `test_representative_fixture_upgrades_to_head_with_zero_governed_data_loss`
# actually exercises. `4747447ccaa3`'s CHECK has its own dedicated
# coverage (`tests/integration/test_canonical_basis_ref_constraint.py`);
# `4cb74877e4ba`'s CHECKs have no dedicated test of their own as of this
# writing (only the raw-SQL seeding below, which targets a baseline
# *before* that migration and so never inserts a row the new CHECKs would
# reject) -- a gap, not something this file's baseline choice papers over.
# Used only by
# `test_representative_fixture_upgrades_to_head_with_zero_governed_data_loss`,
# which validates the zero-governed-data-loss property across this whole
# span. Every ORM model/service the representative fixture below uses
# works identically against a database at this revision as it does at
# `head`, with two deliberate exceptions:
#   1. `fb1c910aedc7` adds `assessment_dimension_results.is_critical`
#      (NOT NULL, no client-side default omission -- `service
#      .perform_assessment` always writes a real value), so a fresh
#      assessment cannot be created at this baseline through live
#      application code. Module docstring item 9's final evaluation step
#      is therefore seeded *after* `command.upgrade(config, "head")`
#      instead of before, and `assessments`/`assessment_dimension_results`
#      are proven writable-and-correctly-shaped post-upgrade rather than
#      preserved-byte-for-byte-across-upgrade (they hold zero rows before
#      that migration ever runs, so "preservation" would otherwise be a
#      vacuous empty-list check).
#   2. `4cb74877e4ba` adds `sources.withdrawal_reason`/
#      `sources.superseded_by_source_id`. `provenance.repository
#      .add_source` sets every field the *current* `Source` dataclass
#      carries (`SourceRow(**source.__dict__)`), including those two, so
#      it cannot run against this baseline's `sources` table, which lacks
#      both columns. `_seed_generated_artifact`'s backing `Source` row is
#      therefore seeded via raw SQL (`_insert_source_at_baseline`) instead
#      -- `sources`/`source_bodies` are not in `_GOVERNED_TABLES` (nothing
#      in this fixture set treats them as data whose preservation this
#      test proves), so this exception costs the test nothing it claims
#      to assert.
# Every other governed table is unaffected by either exception and keeps
# the byte-for-byte proof.
GOVERNED_DATA_LOSS_BASELINE = "c5b1e70a94d2"


# ---------------------------------------------------------------------------
# Shared low-level helpers
# ---------------------------------------------------------------------------


def _provision_owner(uow_factory: UnitOfWorkFactory, display_name: str) -> str:
    """The same provisioning `create_app`'s ASGI lifespan runs before
    accepting traffic (`api/app.py`): the singleton local owner, its
    `learner_profiles` row, and its `owner_settings` row. `create_goal`
    (used throughout this module) fails closed with `UnavailableError` if
    the profile is missing, which `ensure_local_owner` alone does not
    create -- this database has no lifespan to do it for us (see module
    docstring for why `client`/`create_app` are unusable here).
    """
    with uow_factory() as uow:
        owner = ensure_local_owner(uow, display_name)
        ensure_profile(uow, owner.id)
        ensure_owner_settings(uow, owner.id)
        uow.commit()
    return owner.id


def _config_at(url: str, revision: str):
    """A real `alembic.config.Config` pointed at `url`, already upgraded to
    `revision` -- the `alembic_guard.build_alembic_config()` +
    `set_main_option("sqlalchemy.url", ...)` pattern `test_alembic_head_guard.py`
    uses, so `command.upgrade(config, "head")` later targets this scratch
    database rather than whatever `YUNO_DATABASE_URL` happens to be.
    """
    config = alembic_guard.build_alembic_config()
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, revision)
    return config


def _engine_and_uow_factory(
    url: str,
) -> tuple[Engine, UnitOfWorkFactory, sessionmaker]:
    engine = create_engine_for(url)
    session_factory = create_session_factory(engine)
    return engine, create_unit_of_work_factory(session_factory), session_factory


def _dump_table(engine: Engine, table: str) -> list[dict]:
    """Every row of `table` as a plain dict, in a deterministic order.

    Sorting by the row's own JSON representation (rather than by a
    per-table primary-key column) means this works unmodified for every
    table regardless of its key shape (single id, composite, or an
    autoincrement `sequence` like `job_events`) -- exactly what a generic
    before/after equality check across ~30 differently-shaped tables needs.
    """
    with engine.connect() as connection:
        rows = [
            dict(row)
            for row in connection.execute(text(f"SELECT * FROM {table}"))
            .mappings()
            .all()
        ]
    return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, default=str))


def _row(engine: Engine, table: str, row_id: str, column: str = "id") -> dict:
    with engine.connect() as connection:
        return dict(
            connection.execute(
                text(f"SELECT * FROM {table} WHERE {column} = :value"),
                {"value": row_id},
            )
            .mappings()
            .one()
        )


def _count(engine: Engine, table: str, column: str, value: str) -> int:
    with engine.connect() as connection:
        return connection.execute(
            text(f"SELECT count(*) FROM {table} WHERE {column} = :value"),
            {"value": value},
        ).scalar_one()


def _publish_fixture(
    uow_factory: UnitOfWorkFactory, owner_id: str, fixture_name: str
) -> CanonicalGraphVersion:
    """Persist a `tests/fixtures/canonical` manifest as an approved version.

    Mirrors `canonical.publisher.publish_canonical_graph`'s steps 2-7
    exactly: same `uow.canonical.*` calls in the same order, same
    idempotent topic-identity-reuse check. It skips only step 1's
    `require_single_head(engine)` -- every caller in this module
    deliberately targets a below-`head` baseline (`HEAD_MINUS_ONE` or
    `GOVERNED_DATA_LOSS_BASELINE`), and the real publisher refusing
    exactly that is IDK-501/IDK-101's own subject, not something this
    helper should route around by construction.
    """
    fixture = load_fixture(fixture_name)
    assert fixture.approval is not None
    manifest = fixture.manifest
    with uow_factory() as uow:
        timestamp = now_text(SystemClock())
        previous = uow.canonical.list_published_versions()
        version = CanonicalGraphVersion(
            id=new_id(),
            version_label=manifest.version_label,
            manifest_version=manifest.manifest_version,
            manifest_hash=manifest.manifest_hash,
            status=CanonicalVersionStatus.PUBLISHED,
            creator_owner_id=owner_id,
            created_at=timestamp,
            published_at=timestamp,
            supersedes_version_id=previous[0].id if previous else None,
        )
        uow.canonical.create_version(version)
        for topic in manifest.topics:
            if not uow.canonical.topic_identity_exists(topic.stable_id):
                uow.canonical.create_topic_identity(
                    TopicIdentity(
                        stable_id=topic.stable_id,
                        stable_slug=fixture.topic_identity_slugs.get(
                            topic.stable_id, topic.stable_id
                        ),
                        created_at=timestamp,
                        retired_at=None,
                    )
                )
            uow.canonical.add_topic(replace(topic, graph_version_id=version.id))
        for relation in manifest.relations:
            uow.canonical.add_relation(replace(relation, graph_version_id=version.id))
        for revision in manifest.content_revisions:
            uow.canonical.add_content_revision(
                replace(
                    revision,
                    graph_version_id=version.id,
                    creator_owner_id=owner_id,
                    created_at=timestamp,
                )
            )
        uow.canonical.record_approval(
            EditorialApproval(
                id=new_id(),
                graph_version_id=version.id,
                approver_owner_id=owner_id,
                approver_role=fixture.approval.approver_role,
                basis_ref=fixture.approval.basis_ref,
                approved_at=timestamp,
            )
        )
        uow.commit()
    return version


def _create_fixture_goal(
    uow_factory: UnitOfWorkFactory, owner_id: str, graph_version_id: str, name: str
):
    with uow_factory() as uow:
        goal = create_goal(
            uow,
            owner_id,
            name=name,
            path=GoalPath.LEARN,
            subject="Java",
            role=None,
            target_level=TargetLevel.SENIOR,
            target_capability=TargetCapability.IMPLEMENT,
            graph_version_id=graph_version_id,
            approved_graph_exists=True,
        )
        uow.commit()
    return goal


def _insert_source_at_baseline(
    connection, *, id_: str, owner_id: str, suffix: str, timestamp: str
) -> None:
    """A `sources` row (+ its `source_bodies` row), via raw SQL -- the same
    convention `_insert_runner_confirmation` below uses, and for the same
    reason: the live path cannot run against this baseline by
    construction, not merely by inconvenience.

    `provenance.repository.add_source` does `SourceRow(**source.__dict__)`,
    which sets *every* field the current `Source` dataclass carries,
    including `withdrawal_reason`/`superseded_by_source_id` (added by
    `4cb74877e4ba`). Both `HEAD_MINUS_ONE` and `GOVERNED_DATA_LOSS_BASELINE`
    stamp a database strictly before that migration, so `sources` has
    neither column yet at those baselines -- the ORM insert would name a
    column the stamped schema doesn't have
    (`OperationalError: table sources has no column named
    withdrawal_reason`). This inserts only the columns both baselines'
    `sources`/`source_bodies` tables actually have.
    """
    connection.execute(
        text(
            "INSERT INTO sources "
            "(id,owner_id,origin,source_type,body_hash,license_status,availability_status,created_at,updated_at) "
            "VALUES (:id,:owner_id,'fixture','documentation','source-body-hash-fixture',"
            "'approved-open-license','available',:ts,:ts)"
        ),
        {"id": id_, "owner_id": owner_id, "ts": timestamp},
    )
    connection.execute(
        text(
            "INSERT INTO source_bodies (source_id,owner_id,title,publisher,canonical_url) "
            "VALUES (:id,:owner_id,:title,'Representative fixture publisher',:url)"
        ),
        {
            "id": id_,
            "owner_id": owner_id,
            "title": f"Representative fixture source {suffix}",
            "url": f"https://example.invalid/representative/{suffix}",
        },
    )


def _seed_generated_artifact(
    engine: Engine,
    uow_factory: UnitOfWorkFactory,
    owner_id: str,
    goal_id: str,
    topic_stable_id: str,
    *,
    suffix: str,
):
    """Reserve and run one generation attempt through the real service
    functions the HTTP route composes (`reserve_generation` then
    `run_generation`) -- see module docstring's item 6 for why the
    dispatcher/provider-disclosure layer around them is skipped rather
    than faked. The backing `Source` row is the one exception: seeded via
    `_insert_source_at_baseline` (raw SQL) rather than through
    `test_generated_content_api._source`/`add_source` -- see that helper's
    docstring for why the live ORM path cannot run at either baseline this
    module seeds.
    """
    source_id = f"representative-fixture-source-{suffix}"
    timestamp = now_text(SystemClock())
    with engine.begin() as connection:
        _insert_source_at_baseline(
            connection,
            id_=source_id,
            owner_id=owner_id,
            suffix=suffix,
            timestamp=timestamp,
        )
    with uow_factory() as uow:
        _ref, attempt, _dispatch = reserve_generation(
            uow,
            owner_id,
            goal_id,
            topic_stable_id,
            TopicLayer.ESSENTIAL,
            f"representative-generate-{suffix}",
        )
        uow.commit()
    adapter = FakeGenerationAdapter(
        f"Representative fixture body for {suffix}.", source_id
    )
    return run_generation(uow_factory, adapter, owner_id, attempt.id)


def _apply_depth_override(
    uow_factory: UnitOfWorkFactory,
    owner_id: str,
    goal_id: str,
    topic_stable_id: str,
    depth: str,
    key: str,
) -> None:
    with uow_factory() as uow:
        post_depth(
            goal_id,
            DepthOverrideRequest(
                topic_stable_id=topic_stable_id,
                depth=depth,
                reason="Representative fixture.",
            ),
            owner_id,
            uow,
            key,
        )


def _apply_skip_decision(
    uow_factory: UnitOfWorkFactory,
    owner_id: str,
    goal_id: str,
    topic_stable_id: str,
    skipped: bool,
    key: str,
) -> None:
    with uow_factory() as uow:
        post_skip(
            goal_id,
            SkipDecisionRequest(
                topic_stable_id=topic_stable_id,
                skipped=skipped,
                reason="Representative fixture.",
            ),
            owner_id,
            uow,
            key,
        )


class _FixtureEvaluationAdapter:
    """Minimal `EvaluationAdapter`: one passing dimension result matching
    `test_mock_report_api.py::_seed_rubric`'s single `"reasoning"`
    dimension, satisfying `evidence_evaluation.service._validate_evaluation_result`.
    """

    def evaluate(self, request) -> EvaluationResult:
        return EvaluationResult(
            state=AssessmentState.FEEDBACK_READY,
            dimensions=(
                EvaluationDimensionResult(
                    "reasoning",
                    DimensionOutcome.PASS,
                    "Meets the representative-upgrade fixture bar.",
                    (request.evidence_id,),
                ),
            ),
            facts=("A representative-upgrade fixture fact.",),
            trade_offs=(),
            citations=(),
            ambiguities=(),
            feedback="Representative-upgrade Mock fixture feedback.",
            cross_question_candidate=None,
            revision_invitation=None,
            warnings=(),
            limitation_labels=("fixture-v0-non-production",),
        )


def _seed_mock_transcript_ready_for_final_evaluation(
    uow_factory: UnitOfWorkFactory,
    owner_id: str,
    goal_id: str,
    topic_stable_id: str,
    *,
    suffix: str,
) -> str:
    """Everything module docstring item 9 needs *except* the final
    evaluation: bundle, run, reserved completion evidence. Split out from
    the final `run_mock_final_evaluation_job` call (see
    `_run_mock_final_evaluation` below) because that call is the one piece
    of this fixture set that writes `assessments`/`assessment_dimension_results`
    -- the two tables `fb1c910aedc7` (IDK-204) adds `is_critical` to, so a
    database at `GOVERNED_DATA_LOSS_BASELINE` (that migration's own parent)
    cannot accept that specific write yet. Every other governed table this
    module seeds predates that migration and is unaffected by it.
    """
    rubric = _seed_rubric(uow_factory)
    with uow_factory() as uow:
        bundle = create_bundle(
            uow,
            owner_id,
            {
                "goal_id": goal_id,
                "name": f"Representative Mock fixture {suffix}",
                "generic_role": "Synthetic role",
                "target_level": "Senior",
                "origin": "fixture-v0-non-production",
                "items": [
                    {
                        "subject": "technical",
                        "topic_stable_id": topic_stable_id,
                        "question": "Representative fixture Mock question?",
                        "position": 0,
                        "is_optional": False,
                        "included": True,
                    }
                ],
            },
        )
        run = create_mock_run(
            uow,
            owner_id,
            goal_id,
            bundle.id,
            bundle.items[0].id,
            rubric.id,
            rubric.version,
            "implement",
        )
        uow.commit()
        run_id = run.id

    draft = "A representative fixture Mock answer, fixed for terminal evaluation."
    with uow_factory() as uow:
        run = validate_mock_completion(uow, owner_id, run_id, draft)
        bundle = get_bundle(uow, owner_id, run.bundle_id)
        item = next(value for value in bundle.items if value.id == run.bundle_item_id)
        assert item.topic_stable_id is not None
        transcript = [
            {"kind": turn.kind.value, "body": turn.body} for turn in run.turns
        ] + [{"kind": "answer", "body": draft}]
        evidence = create_evidence(
            uow,
            owner_id,
            run.goal_id,
            topic_stable_id=item.topic_stable_id,
            evidence_type="mock-transcript",
            capability=run.requested_capability,
            summary="Completed Mock interview transcript",
            origin="mock-complete",
            content=json.dumps(transcript, ensure_ascii=False, separators=(",", ":")),
            content_version="mock-transcript-v1",
        )
        reserve_mock_completion(uow, owner_id, run_id, draft, new_id(), evidence.id)
        uow.commit()

    return run_id


def _run_mock_final_evaluation(
    uow_factory: UnitOfWorkFactory, owner_id: str, run_id: str
) -> None:
    """`run_mock_final_evaluation_job` is the dispatcher's job-handler body
    for `evaluate_mock_final`; calling it directly runs the identical
    `perform_assessment` + `complete_mock_evaluation` persistence the
    dispatcher would run asynchronously (module docstring item 9).
    """
    run_mock_final_evaluation_job(
        JobRequest("evaluate_mock_final", owner_id, {"run_id": run_id}),
        uow_factory,
        _FixtureEvaluationAdapter(),
    )


def _seed_active_job(session_factory: sessionmaker, owner_id: str) -> str:
    with session_factory() as session:
        repo = JobRepository(session, SystemClock())
        job = repo.enqueue(
            JobRequest(
                "rebuild_index", owner_id, {}, dedupe_key="representative-active-job"
            ),
            JobLane.BACKGROUND,
        )
        session.commit()
        return job.id


def _seed_job_requiring_startup_recovery(
    session_factory: sessionmaker, owner_id: str
) -> str:
    """A job stuck `running` with a stale attempt process identity --
    exactly `test_durable_jobs.py::test_startup_reconciles_active_states_and_sweeps_temp_path`'s
    setup, minus its later `dispatcher.reconcile_startup()` call: leaving
    it un-reconciled is the point -- this is the state a process killed
    mid-attempt leaves for the *next* startup to repair, and an Alembic
    upgrade over it must neither erase it nor silently "fix" it.
    """
    with session_factory() as session:
        repo = JobRepository(session, SystemClock())
        job = repo.enqueue(
            JobRequest("rebuild_index", owner_id, {}), JobLane.BACKGROUND
        )
        job.state = "running"
        job.attempt = 1
        job.started_at = now_text(SystemClock())
        repo.add_attempt(
            job, process_identity="999999:stale-worker", pid=999999, pgid=999999
        )
        session.commit()
        return job.id


def _seed_stale_search_projection(
    uow_factory: UnitOfWorkFactory, owner_id: str, goal_id: str
) -> None:
    with uow_factory() as uow:
        uow.search.rebuild(owner_id, "representative-fixture-rebuild")
        uow.commit()
    # One more real write after the rebuild, with no further rebuild -- see
    # module docstring item 10 for why this reproduces genuine staleness.
    with uow_factory() as uow:
        create_evidence(
            uow,
            owner_id,
            goal_id,
            topic_stable_id="queues",
            evidence_type="fixture",
            capability="implement",
            summary="Evidence added after the last search rebuild",
            origin="fixture",
            content="Deliberately post-rebuild evidence, to force staleness.",
            content_version="v1",
        )
        uow.commit()


def _search_status(uow_factory: UnitOfWorkFactory, owner_id: str) -> SearchIndexStatus:
    with uow_factory() as uow:
        return uow.search.state(owner_id).status


# ---------------------------------------------------------------------------
# (1) Every prior revision upgrades forward to head.
# ---------------------------------------------------------------------------


def _chain_revisions() -> list[str]:
    script = ScriptDirectory.from_config(alembic_guard.build_alembic_config())
    return [revision.revision for revision in script.walk_revisions()]


@pytest.mark.parametrize("revision", _chain_revisions())
def test_every_revision_upgrades_forward_to_head_with_matching_schema(
    revision: str, tmp_path: Path
) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'chain.db'}"
    config = alembic_guard.build_alembic_config()
    config.set_main_option("sqlalchemy.url", url)

    command.upgrade(config, revision)
    command.upgrade(config, "head")
    command.check(config)


# ---------------------------------------------------------------------------
# (2) The §4.8 representative fixture upgrades to head with zero governed
#     data loss.
# ---------------------------------------------------------------------------

# Every table this fixture writes into *before* the upgrade, dumped whole
# and compared before/after. Deliberately excludes
# `runner_confirmations`/`runner_records` and their satellite tables: this
# fixture seeds zero rows in them (that is
# `test_relational_placeholder_disposal_is_bounded_and_controls_survive`'s
# job below), so their equality here would be a trivial empty-list check.
# Also excludes `assessments`/`assessment_dimension_results`: see
# `GOVERNED_DATA_LOSS_BASELINE`'s docstring -- module docstring item 9's
# final evaluation writes those two only *after* the upgrade, so they are
# asserted separately (writable-and-correctly-shaped post-upgrade, not
# preserved-across-upgrade).
_GOVERNED_TABLES: tuple[str, ...] = (
    "goal_workspaces",
    "evidence",
    "evidence_payloads",
    "evidence_summary_bodies",
    "transferred_evidence_refs",
    "learning_states",
    "diagnostic_sessions",
    "diagnostic_answers",
    "canonical_graph_versions",
    "topics",
    "topic_relations",
    "editorial_approvals",
    "personal_overlays",
    "overlay_entries",
    "import_records",
    "import_statements",
    "generated_artifacts",
    "generated_artifact_bodies",
    "artifact_provenance_snapshots",
    "claims",
    "citations",
    "jobs",
    "job_bodies",
    "job_events",
    "job_attempts",
    "job_attempt_bodies",
    "interview_bundles",
    "interview_bundle_items",
    "interview_runs",
    "interview_turns",
    "audit_events",
    "search_index_state",
    "search_documents",
    "search_document_bodies",
)


def _build_representative_fixture(
    engine: Engine, uow_factory: UnitOfWorkFactory, session_factory: sessionmaker
) -> dict[str, object]:
    owner_id = _provision_owner(uow_factory, "Representative upgrade fixture owner")
    ids: dict[str, object] = {"owner_id": owner_id}

    # 1. Two goals with cross-goal transferred evidence.
    _seed_owner_id, source_goal_id, target_goal_id, evidence_id = (
        _seed_evidence_transfer(uow_factory)
    )
    assert _seed_owner_id == owner_id
    with uow_factory() as uow:
        transfer_ref = transfer_evidence(
            uow,
            owner_id,
            source_goal_id=source_goal_id,
            source_evidence_id=evidence_id,
            target_goal_id=target_goal_id,
            classification=TransferClassification.PARTIAL,
            rationale="Representative-upgrade fixture: partial cross-goal transfer.",
            recommended_depth="Implementation",
        )
        uow.commit()
    ids["evidence_transfer"] = {
        "source_goal_id": source_goal_id,
        "target_goal_id": target_goal_id,
        "evidence_id": evidence_id,
        "transfer_ref_id": transfer_ref.id,
    }

    # 3. Approved canonical graph v1 (goal 2's diagnostic references it too).
    v1 = _publish_fixture(uow_factory, owner_id, "v1_approved")

    # 2. A paused diagnostic session.
    with uow_factory() as uow:
        session = create_diagnostic(
            uow,
            owner_id,
            captured_graph_version_id=v1.id,
            setup_inputs={
                "path": "learn",
                "subject": "Distributed systems",
                "role": None,
                "target_level": "Senior",
                "target_capability": "diagnose",
                "weekly_time": "4 hours",
                "goal_name": "Representative fixture diagnostic",
            },
            approved_graph_exists=True,
        )
        uow.commit()
    first_question = next_question(session, ())
    assert first_question is not None
    with uow_factory() as uow:
        append_diagnostic_answer(
            uow,
            owner_id,
            session.id,
            question_ref=first_question.ref,
            answer="Representative fixture answer, deliberately uncertain.",
            confidence=DiagnosticConfidence.LOW,
        )
        uow.commit()
    with uow_factory() as uow:
        # One answer bumps `row_version` 1 -> 2 (`append_diagnostic_answer`
        # always re-saves the session), matching `test_diagnostics.py`'s
        # established `"If-Match": "2"` pause sequence.
        paused = patch_diagnostic(
            uow,
            owner_id,
            session.id,
            expected_version=2,
            action=DiagnosticAction.PAUSE,
            untrusted_seed_text=None,
            seed_was_supplied=False,
        )
        uow.commit()
    assert paused.state.value == "paused"
    ids["diagnostic_session_id"] = session.id

    # 3 (goal) + 4 (local state) + 5 (import): one goal pinned to v1, with
    # local overlay/skip state and an import, created *before* v2 exists --
    # "pinned mid-transition" once v2 publishes below and the goal stays put.
    merge_goal = _create_fixture_goal(
        uow_factory, owner_id, v1.id, "Representative canonical-merge fixture"
    )
    with uow_factory() as uow:
        import_record = create_import(
            uow,
            owner_id,
            goal_id=merge_goal.id,
            import_type=ImportType.PLAIN_TEXT,
            source_text="A representative-upgrade fixture import statement to reprocess.",
        )
        uow.commit()
    # See module docstring item 4: `fixture-topic-alpha` is modified by v2
    # (overlay conflict); `fixture-topic-gamma` is dropped by v2 (local
    # state on an upstream-deleted topic).
    _apply_depth_override(
        uow_factory,
        owner_id,
        merge_goal.id,
        "fixture-topic-alpha",
        "Internals",
        "representative-overlay-depth",
    )
    _apply_skip_decision(
        uow_factory,
        owner_id,
        merge_goal.id,
        "fixture-topic-gamma",
        True,
        "representative-overlay-skip",
    )
    v2 = _publish_fixture(uow_factory, owner_id, "v2_approved")
    assert merge_goal.graph_version_id == v1.id  # still pinned: "mid-transition"
    ids["canonical"] = {
        "v1_id": v1.id,
        "v2_id": v2.id,
        "merge_goal_id": merge_goal.id,
        "import_id": import_record.id,
    }

    # 6. A generated artifact with a provenance snapshot.
    artifact_goal = _create_fixture_goal(
        uow_factory, owner_id, v1.id, "Representative generated-content fixture"
    )
    artifact = _seed_generated_artifact(
        engine,
        uow_factory,
        owner_id,
        artifact_goal.id,
        "fixture-topic-alpha",
        suffix="representative",
    )
    ids["artifact_id"] = artifact.id

    # 7 + 8. An active job, and a job requiring startup recovery reconciliation.
    ids["jobs"] = {
        "active_job_id": _seed_active_job(session_factory, owner_id),
        "recovery_job_id": _seed_job_requiring_startup_recovery(
            session_factory, owner_id
        ),
    }

    # 9. A Mock transcript ready for its final evaluation (bundle, run,
    # reserved completion evidence). The final evaluation step -- the only
    # part of this fixture set that writes `assessments`/
    # `assessment_dimension_results` -- runs after the upgrade to `head`;
    # see `GOVERNED_DATA_LOSS_BASELINE`'s docstring for why.
    mock_goal = _create_fixture_goal(
        uow_factory, owner_id, v1.id, "Representative Mock fixture goal"
    )
    ids["mock_run_id"] = _seed_mock_transcript_ready_for_final_evaluation(
        uow_factory,
        owner_id,
        mock_goal.id,
        "fixture-topic-alpha",
        suffix="representative",
    )

    # 10. A deliberately stale FTS5 projection -- built last, over
    # everything above, so the rebuild has real content to project.
    _seed_stale_search_projection(uow_factory, owner_id, source_goal_id)

    return ids


def test_representative_fixture_upgrades_to_head_with_zero_governed_data_loss(
    tmp_path: Path,
) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'representative.db'}"
    config = _config_at(url, GOVERNED_DATA_LOSS_BASELINE)
    engine, uow_factory, session_factory = _engine_and_uow_factory(url)
    try:
        ids = _build_representative_fixture(engine, uow_factory, session_factory)

        before = {table: _dump_table(engine, table) for table in _GOVERNED_TABLES}
        # Nothing pre-existing to lose: module docstring item 9's final
        # evaluation (the only writer of these two tables) is deliberately
        # seeded after the upgrade -- see `GOVERNED_DATA_LOSS_BASELINE`.
        assert _dump_table(engine, "assessments") == []
        assert _dump_table(engine, "assessment_dimension_results") == []
        artifact_before = _row(engine, "generated_artifacts", ids["artifact_id"])
        with engine.connect() as connection:
            jobs_dedupe_before = dict(
                connection.execute(text("SELECT id, dedupe_key FROM jobs")).all()
            )
        search_status_before = _search_status(uow_factory, ids["owner_id"])
        assert search_status_before is SearchIndexStatus.STALE
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    command.check(config)  # the fixture database also reaches head's exact schema

    engine, uow_factory, _session_factory = _engine_and_uow_factory(url)
    try:
        after = {table: _dump_table(engine, table) for table in _GOVERNED_TABLES}
        for table in _GOVERNED_TABLES:
            assert after[table] == before[table], (
                f"{table!r} changed across the upgrade"
            )

        # Module docstring item 9's final evaluation: the migration under
        # test (`fb1c910aedc7`) leaves `assessments`/
        # `assessment_dimension_results` in a working, correctly-shaped
        # state for a fresh real-service write immediately after upgrading
        # -- the positive counterpart to the "zero data loss" proof above
        # for the two tables that migration actually changes.
        _run_mock_final_evaluation(uow_factory, ids["owner_id"], ids["mock_run_id"])
        assessments = _dump_table(engine, "assessments")
        dimension_results = _dump_table(engine, "assessment_dimension_results")
        assert len(assessments) == 1
        assert assessments[0]["state"] == "feedback-ready"
        assert len(dimension_results) == 1
        assert dimension_results[0]["outcome"] == "pass"
        assert dimension_results[0]["is_critical"] == 0

        # The D3 cache key (`uq_generated_artifacts_d3_exact_key`'s own
        # columns) and `body_hash` unchanged, named explicitly per the
        # ticket's minimum assertion list (already implied by the whole-row
        # `generated_artifacts` dump above, asserted again here by name).
        artifact_after = _row(engine, "generated_artifacts", ids["artifact_id"])
        d3_columns = (
            "graph_version_id",
            "topic_stable_id",
            "goal_id",
            "layer",
            "imports_hash",
            "prompt_template_version",
        )
        assert tuple(artifact_after[column] for column in d3_columns) == tuple(
            artifact_before[column] for column in d3_columns
        )
        assert artifact_after["body_hash"] == artifact_before["body_hash"] is not None

        with engine.connect() as connection:
            jobs_dedupe_after = dict(
                connection.execute(text("SELECT id, dedupe_key FROM jobs")).all()
            )
        assert jobs_dedupe_after == jobs_dedupe_before
        assert (
            jobs_dedupe_after[ids["jobs"]["active_job_id"]]
            == "representative-active-job"
        )

        # Approved `canonical_graph_versions` rows byte-identical, named
        # explicitly (already covered by the whole-table dump above too).
        v1_after = _row(engine, "canonical_graph_versions", ids["canonical"]["v1_id"])
        v2_after = _row(engine, "canonical_graph_versions", ids["canonical"]["v2_id"])
        assert v1_after in before["canonical_graph_versions"]
        assert v2_after in before["canonical_graph_versions"]

        search_status_after = _search_status(uow_factory, ids["owner_id"])
        assert search_status_after is SearchIndexStatus.STALE
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# (3) The bounded relational-placeholder disposal.
# ---------------------------------------------------------------------------

_RUNNER_CONFIRMATION_COLUMNS = (
    "id,owner_id,goal_id,artifact_id,language,capability,operation,inputs_hash,"
    "acknowledgement_version,idempotency_key,request_hash,reserved_run_id,"
    "environment_policy_version,limits_config_version,confirmed_at,expires_at,consumed_at"
)


def _insert_runner_confirmation(
    connection, *, id_: str, owner_id: str, language: str, timestamp: str
) -> None:
    connection.execute(
        text(
            f"INSERT INTO runner_confirmations ({_RUNNER_CONFIRMATION_COLUMNS}) VALUES "
            "(:id,:owner_id,NULL,NULL,:language,'query','compile','inputs-hash-fixture',"
            "'ack-v1',NULL,NULL,NULL,'env-v1','limits-v1',:ts,:ts,:ts)"
        ),
        {"id": id_, "owner_id": owner_id, "language": language, "ts": timestamp},
    )


def _insert_relational_placeholder_subgraph(
    connection, owner_id: str, timestamp: str
) -> dict[str, str]:
    """Everything IDK-406/408's disposal must remove, in one owner-scoped
    subgraph: a `language='relational'` confirmation and runner record,
    their exclusively owned inputs/bodies/output chunks, and a
    `kind='java_runner'` job whose `run_id`, `request_ref`
    (`'RunnerRun:<record id>'`), `result_ref` and `confirmation_ref` *all*
    target these placeholders -- so the migration's four independent
    match predicates (`id`, `run_id`, `result_ref`, `request_ref`,
    `confirmation_ref`) each get exercised, not just one of them.
    """
    ids = {
        "confirmation_id": "placeholder-confirmation-1",
        "confirmation_input_id": "placeholder-confirmation-input-1",
        "record_id": "placeholder-runner-record-1",
        "input_id": "placeholder-runner-input-1",
        "chunk_id": "placeholder-runner-chunk-1",
        "job_id": "placeholder-job-1",
        "attempt_id": "placeholder-job-attempt-1",
        "result_id": "placeholder-job-result-1",
    }
    request_ref = f"RunnerRun:{ids['record_id']}"

    _insert_runner_confirmation(
        connection,
        id_=ids["confirmation_id"],
        owner_id=owner_id,
        language="relational",
        timestamp=timestamp,
    )
    connection.execute(
        text(
            "INSERT INTO runner_confirmation_inputs "
            "(id,owner_id,confirmation_id,logical_path,declared_type,content_hash) "
            "VALUES (:id,:owner_id,:confirmation_id,'schema.sql','text/sql','confirmation-input-hash')"
        ),
        {
            "id": ids["confirmation_input_id"],
            "owner_id": owner_id,
            "confirmation_id": ids["confirmation_id"],
        },
    )
    connection.execute(
        text(
            "INSERT INTO runner_confirmation_input_bodies (input_id,owner_id,resolved_content) "
            "VALUES (:id,:owner_id,'SELECT 1;')"
        ),
        {"id": ids["confirmation_input_id"], "owner_id": owner_id},
    )

    connection.execute(
        text(
            "INSERT INTO runner_records "
            "(id,owner_id,goal_id,artifact_id,job_id,confirmation_id,language,capability,operation,"
            "toolchain,working_directory_policy,environment_policy_version,limits_config_version,"
            "state,argv_hash,outcome_hash,temp_path_hash,cleanup_state,cleanup_classification,"
            "limit_classification,created_at,updated_at) "
            "VALUES (:id,:owner_id,NULL,NULL,:job_id,:confirmation_id,'relational','query','compile',"
            "'relational-placeholder-v0','ephemeral','env-v1','limits-v1',"
            "'completed','argv-hash-fixture','outcome-hash-fixture',NULL,'cleanup-complete',NULL,"
            "NULL,:ts,:ts)"
        ),
        {
            "id": ids["record_id"],
            "owner_id": owner_id,
            "job_id": ids["job_id"],
            "confirmation_id": ids["confirmation_id"],
            "ts": timestamp,
        },
    )
    connection.execute(
        text(
            "INSERT INTO runner_record_bodies (runner_id,owner_id,argv_json,pid,pgid,temp_path,outcome_json) "
            "VALUES (:id,:owner_id,'[\"placeholder\"]',NULL,NULL,NULL,NULL)"
        ),
        {"id": ids["record_id"], "owner_id": owner_id},
    )
    connection.execute(
        text(
            "INSERT INTO runner_inputs (id,owner_id,runner_id,logical_path,declared_type,content_hash) "
            "VALUES (:id,:owner_id,:runner_id,'input.sql','text/sql','runner-input-hash')"
        ),
        {"id": ids["input_id"], "owner_id": owner_id, "runner_id": ids["record_id"]},
    )
    connection.execute(
        text(
            "INSERT INTO runner_input_bodies (input_id,owner_id,content_ref) "
            "VALUES (:id,:owner_id,'inline:SELECT 1;')"
        ),
        {"id": ids["input_id"], "owner_id": owner_id},
    )
    connection.execute(
        text(
            "INSERT INTO runner_output_chunks "
            "(id,owner_id,runner_id,phase,stream,sequence,ordinal,content_hash,truncated,created_at) "
            "VALUES (:id,:owner_id,:runner_id,'compile','stdout',1,1,'chunk-hash-fixture',0,:ts)"
        ),
        {
            "id": ids["chunk_id"],
            "owner_id": owner_id,
            "runner_id": ids["record_id"],
            "ts": timestamp,
        },
    )
    connection.execute(
        text(
            "INSERT INTO runner_output_chunk_bodies (chunk_id,owner_id,content_ref) "
            "VALUES (:id,:owner_id,'inline:placeholder output')"
        ),
        {"id": ids["chunk_id"], "owner_id": owner_id},
    )

    connection.execute(
        text(
            "INSERT INTO jobs "
            "(id,owner_id,goal_id,kind,schema_version,lane,state,retryable,dedupe_key,idempotency_key,"
            "payload_hash,request_ref,disclosure_ref,provider_name,confirmation_ref,correlation_id,"
            "request_id,run_id,substitution_ref,attempt,priority,result_ref,result_hash,worker_id,"
            "queued_at,started_at,terminal_at,updated_at) "
            "VALUES (:id,:owner_id,NULL,'java_runner','1','background','succeeded',0,NULL,NULL,"
            "'placeholder-payload-hash',:request_ref,NULL,NULL,:confirmation_id,:correlation_id,"
            ":request_id,:run_id,NULL,1,100,:result_ref,'placeholder-result-hash',NULL,"
            ":ts,:ts,:ts,:ts)"
        ),
        {
            "id": ids["job_id"],
            "owner_id": owner_id,
            "request_ref": request_ref,
            "confirmation_id": ids["confirmation_id"],
            "correlation_id": new_id(),
            "request_id": new_id(),
            "run_id": ids["record_id"],
            "result_ref": ids["record_id"],
            "ts": timestamp,
        },
    )
    connection.execute(
        text(
            "INSERT INTO job_bodies (job_id,owner_id,payload_json,diagnostic) VALUES (:id,:owner_id,'{}',NULL)"
        ),
        {"id": ids["job_id"], "owner_id": owner_id},
    )
    connection.execute(
        text(
            "INSERT INTO job_attempts "
            "(id,owner_id,job_id,attempt_number,substitution_ref,confirmation_ref,started_at,ended_at,outcome) "
            "VALUES (:id,:owner_id,:job_id,1,NULL,:confirmation_id,:ts,:ts,'succeeded')"
        ),
        {
            "id": ids["attempt_id"],
            "owner_id": owner_id,
            "job_id": ids["job_id"],
            "confirmation_id": ids["confirmation_id"],
            "ts": timestamp,
        },
    )
    connection.execute(
        text(
            "INSERT INTO job_attempt_bodies (attempt_id,owner_id,process_identity,pid,pgid,temp_path,diagnostic) "
            "VALUES (:id,:owner_id,'1234:placeholder',1234,1234,NULL,NULL)"
        ),
        {"id": ids["attempt_id"], "owner_id": owner_id},
    )
    connection.execute(
        text(
            "INSERT INTO job_events "
            "(owner_id,job_id,goal_id,run_id,type,state,progress,result_ref,retryable,correlation_id,"
            "request_id,created_at) "
            "VALUES (:owner_id,:job_id,NULL,:run_id,'state-changed','succeeded',NULL,:result_ref,0,"
            ":correlation_id,:request_id,:ts)"
        ),
        {
            "owner_id": owner_id,
            "job_id": ids["job_id"],
            "run_id": ids["record_id"],
            "result_ref": ids["record_id"],
            "correlation_id": new_id(),
            "request_id": new_id(),
            "ts": timestamp,
        },
    )
    connection.execute(
        text(
            "INSERT INTO job_results (id,owner_id,job_id,kind,schema_version,result_ref,result_hash,committed_at) "
            "VALUES (:id,:owner_id,:job_id,'java_runner','1',:result_ref,'placeholder-result-hash',:ts)"
        ),
        {
            "id": ids["result_id"],
            "owner_id": owner_id,
            "job_id": ids["job_id"],
            "result_ref": ids["record_id"],
            "ts": timestamp,
        },
    )
    connection.execute(
        text(
            "INSERT INTO job_result_bodies (result_id,owner_id,warnings_json,diagnostic_ref) "
            "VALUES (:id,:owner_id,'[]',NULL)"
        ),
        {"id": ids["result_id"], "owner_id": owner_id},
    )
    return ids


def _insert_java_control_subgraph(
    connection, owner_id: str, timestamp: str
) -> dict[str, str]:
    """An unrelated `language='java'` confirmation/record/job pair that
    must survive completely untouched -- the disposal's `WHERE
    language = 'relational'` predicate must not sweep up the language it
    is meant to keep.
    """
    ids = {
        "confirmation_id": "control-confirmation-java-1",
        "record_id": "control-runner-record-java-1",
        "job_id": "control-job-java-1",
    }
    _insert_runner_confirmation(
        connection,
        id_=ids["confirmation_id"],
        owner_id=owner_id,
        language="java",
        timestamp=timestamp,
    )
    connection.execute(
        text(
            "INSERT INTO runner_records "
            "(id,owner_id,goal_id,artifact_id,job_id,confirmation_id,language,capability,operation,"
            "toolchain,working_directory_policy,environment_policy_version,limits_config_version,"
            "state,argv_hash,outcome_hash,temp_path_hash,cleanup_state,cleanup_classification,"
            "limit_classification,created_at,updated_at) "
            "VALUES (:id,:owner_id,NULL,NULL,:job_id,:confirmation_id,'java','implement','test',"
            "'temurin-21','ephemeral','env-v1','limits-v1',"
            "'completed','argv-hash-control','outcome-hash-control',NULL,'cleanup-complete',NULL,"
            "NULL,:ts,:ts)"
        ),
        {
            "id": ids["record_id"],
            "owner_id": owner_id,
            "job_id": ids["job_id"],
            "confirmation_id": ids["confirmation_id"],
            "ts": timestamp,
        },
    )
    connection.execute(
        text(
            "INSERT INTO runner_record_bodies (runner_id,owner_id,argv_json,pid,pgid,temp_path,outcome_json) "
            'VALUES (:id,:owner_id,\'["javac","Main.java"]\',NULL,NULL,NULL,NULL)'
        ),
        {"id": ids["record_id"], "owner_id": owner_id},
    )
    connection.execute(
        text(
            "INSERT INTO jobs "
            "(id,owner_id,goal_id,kind,schema_version,lane,state,retryable,dedupe_key,idempotency_key,"
            "payload_hash,request_ref,disclosure_ref,provider_name,confirmation_ref,correlation_id,"
            "request_id,run_id,substitution_ref,attempt,priority,result_ref,result_hash,worker_id,"
            "queued_at,started_at,terminal_at,updated_at) "
            "VALUES (:id,:owner_id,NULL,'java_runner','1','background','succeeded',0,NULL,NULL,"
            "'control-java-payload-hash',:request_ref,NULL,NULL,:confirmation_id,:correlation_id,"
            ":request_id,:run_id,NULL,1,100,:result_ref,'control-java-result-hash',NULL,"
            ":ts,:ts,:ts,:ts)"
        ),
        {
            "id": ids["job_id"],
            "owner_id": owner_id,
            "request_ref": f"RunnerRun:{ids['record_id']}",
            "confirmation_id": ids["confirmation_id"],
            "correlation_id": new_id(),
            "request_id": new_id(),
            "run_id": ids["record_id"],
            "result_ref": ids["record_id"],
            "ts": timestamp,
        },
    )
    return ids


def _insert_control_parse_import_job(connection, owner_id: str, timestamp: str) -> str:
    """An unrelated non-runner job: no `run_id`/`request_ref`/
    `confirmation_ref` at all, proving the disposal's job predicate
    (`kind = 'java_runner' AND (...)`) never reaches a job of a different
    `kind`.
    """
    job_id = "control-job-parse-import-1"
    connection.execute(
        text(
            "INSERT INTO jobs "
            "(id,owner_id,goal_id,kind,schema_version,lane,state,retryable,dedupe_key,idempotency_key,"
            "payload_hash,request_ref,disclosure_ref,provider_name,confirmation_ref,correlation_id,"
            "request_id,run_id,substitution_ref,attempt,priority,result_ref,result_hash,worker_id,"
            "queued_at,started_at,terminal_at,updated_at) "
            "VALUES (:id,:owner_id,NULL,'parse_import','1','interactive','succeeded',0,NULL,NULL,"
            "'control-parse-import-payload-hash',NULL,NULL,NULL,NULL,:correlation_id,"
            ":request_id,NULL,NULL,1,100,NULL,NULL,NULL,"
            ":ts,:ts,:ts,:ts)"
        ),
        {
            "id": job_id,
            "owner_id": owner_id,
            "correlation_id": new_id(),
            "request_id": new_id(),
            "ts": timestamp,
        },
    )
    return job_id


def test_relational_placeholder_disposal_is_bounded_and_controls_survive(
    tmp_path: Path,
) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'placeholder-disposal.db'}"
    config = _config_at(url, HEAD_MINUS_ONE)
    engine, uow_factory, _session_factory = _engine_and_uow_factory(url)
    try:
        owner_id = _provision_owner(uow_factory, "Placeholder disposal fixture owner")
        v1 = _publish_fixture(uow_factory, owner_id, "v1_approved")
        control_goal = _create_fixture_goal(
            uow_factory, owner_id, v1.id, "Placeholder-disposal control goal"
        )
        with uow_factory() as uow:
            control_evidence = create_evidence(
                uow,
                owner_id,
                control_goal.id,
                topic_stable_id="fixture-topic-alpha",
                evidence_type="fixture",
                capability="implement",
                summary="Control evidence that must survive disposal",
                origin="fixture",
                content="Control evidence content.",
                content_version="v1",
            )
            uow.commit()
        control_artifact = _seed_generated_artifact(
            engine,
            uow_factory,
            owner_id,
            control_goal.id,
            "fixture-topic-alpha",
            suffix="disposal-control",
        )

        timestamp = now_text(SystemClock())
        with engine.begin() as connection:
            placeholder = _insert_relational_placeholder_subgraph(
                connection, owner_id, timestamp
            )
            control_java = _insert_java_control_subgraph(
                connection, owner_id, timestamp
            )
            control_parse_import_job_id = _insert_control_parse_import_job(
                connection, owner_id, timestamp
            )

        control_snapshot_before = {
            "goal": _row(engine, "goal_workspaces", control_goal.id),
            "evidence": _row(engine, "evidence", control_evidence.id),
            "artifact": _row(engine, "generated_artifacts", control_artifact.id),
            "java_confirmation": _row(
                engine, "runner_confirmations", control_java["confirmation_id"]
            ),
            "java_record": _row(engine, "runner_records", control_java["record_id"]),
            "java_job": _row(engine, "jobs", control_java["job_id"]),
            "parse_import_job": _row(engine, "jobs", control_parse_import_job_id),
        }
        removed_ids = {placeholder["confirmation_id"], placeholder["record_id"]}
        removed_request_ref = f"RunnerRun:{placeholder['record_id']}"
    finally:
        engine.dispose()

    command.upgrade(config, "head")

    engine = create_engine_for(url)
    try:
        # Every placeholder-owned row is gone.
        assert (
            _count(engine, "runner_confirmations", "id", placeholder["confirmation_id"])
            == 0
        )
        assert (
            _count(
                engine,
                "runner_confirmation_inputs",
                "id",
                placeholder["confirmation_input_id"],
            )
            == 0
        )
        assert (
            _count(
                engine,
                "runner_confirmation_input_bodies",
                "input_id",
                placeholder["confirmation_input_id"],
            )
            == 0
        )
        assert _count(engine, "runner_records", "id", placeholder["record_id"]) == 0
        assert (
            _count(
                engine, "runner_record_bodies", "runner_id", placeholder["record_id"]
            )
            == 0
        )
        assert _count(engine, "runner_inputs", "id", placeholder["input_id"]) == 0
        assert (
            _count(engine, "runner_input_bodies", "input_id", placeholder["input_id"])
            == 0
        )
        assert (
            _count(engine, "runner_output_chunks", "id", placeholder["chunk_id"]) == 0
        )
        assert (
            _count(
                engine,
                "runner_output_chunk_bodies",
                "chunk_id",
                placeholder["chunk_id"],
            )
            == 0
        )
        assert _count(engine, "jobs", "id", placeholder["job_id"]) == 0
        assert _count(engine, "job_bodies", "job_id", placeholder["job_id"]) == 0
        assert _count(engine, "job_attempts", "id", placeholder["attempt_id"]) == 0
        assert (
            _count(
                engine, "job_attempt_bodies", "attempt_id", placeholder["attempt_id"]
            )
            == 0
        )
        assert _count(engine, "job_events", "job_id", placeholder["job_id"]) == 0
        assert _count(engine, "job_results", "id", placeholder["result_id"]) == 0
        assert (
            _count(engine, "job_result_bodies", "result_id", placeholder["result_id"])
            == 0
        )

        # Every control row survives, byte-for-byte.
        assert (
            _row(engine, "goal_workspaces", control_goal.id)
            == control_snapshot_before["goal"]
        )
        assert (
            _row(engine, "evidence", control_evidence.id)
            == control_snapshot_before["evidence"]
        )
        assert (
            _row(engine, "generated_artifacts", control_artifact.id)
            == control_snapshot_before["artifact"]
        )
        assert (
            _row(engine, "runner_confirmations", control_java["confirmation_id"])
            == control_snapshot_before["java_confirmation"]
        )
        assert (
            _row(engine, "runner_records", control_java["record_id"])
            == control_snapshot_before["java_record"]
        )
        assert (
            _row(engine, "jobs", control_java["job_id"])
            == control_snapshot_before["java_job"]
        )
        assert (
            _row(engine, "jobs", control_parse_import_job_id)
            == control_snapshot_before["parse_import_job"]
        )

        # No surviving `jobs` row's logical reference points at a removed id.
        with engine.connect() as connection:
            surviving_jobs = (
                connection.execute(
                    text(
                        "SELECT id, run_id, request_ref, result_ref, confirmation_ref FROM jobs"
                    )
                )
                .mappings()
                .all()
            )
        assert surviving_jobs  # the two control jobs must still be there
        for job in surviving_jobs:
            assert job["run_id"] not in removed_ids
            assert job["result_ref"] not in removed_ids
            assert job["confirmation_ref"] not in removed_ids
            assert job["request_ref"] != removed_request_ref

        # No surviving `runner_records` row's logical reference points at a
        # removed id (only the control java record remains).
        with engine.connect() as connection:
            surviving_records = (
                connection.execute(
                    text("SELECT id, confirmation_id, job_id FROM runner_records")
                )
                .mappings()
                .all()
            )
        assert [record["id"] for record in surviving_records] == [
            control_java["record_id"]
        ]
        for record in surviving_records:
            assert record["confirmation_id"] not in removed_ids
            assert record["job_id"] not in removed_ids

        # The narrowed CHECK rejects a fresh `language='relational'` insert.
        with (
            pytest.raises(IntegrityError, match="language_valid"),
            engine.begin() as connection,
        ):
            _insert_runner_confirmation(
                connection,
                id_="post-upgrade-relational-attempt",
                owner_id=owner_id,
                language="relational",
                timestamp=timestamp,
            )
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# (4) A language='python' row stops the migration with a diagnostic.
# ---------------------------------------------------------------------------


def test_language_python_row_stops_the_migration_with_a_diagnostic(
    tmp_path: Path,
) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'python-guard.db'}"
    config = _config_at(url, HEAD_MINUS_ONE)
    engine, uow_factory, _session_factory = _engine_and_uow_factory(url)
    try:
        owner_id = _provision_owner(uow_factory, "Python guard fixture owner")
        timestamp = now_text(SystemClock())
        with engine.begin() as connection:
            _insert_runner_confirmation(
                connection,
                id_="python-placeholder-confirmation-1",
                owner_id=owner_id,
                language="python",
                timestamp=timestamp,
            )
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError) as excinfo:
        command.upgrade(config, "head")
    message = str(excinfo.value)
    assert "language='python'" in message
    assert "resolve them explicitly" in message.lower()
    assert "alembic upgrade head" in message.lower()

    # No partial state: the database is still stamped at the pre-upgrade
    # revision (the migration raised before its `_delete_in`/
    # `batch_alter_table` calls, and Alembic runs each revision inside its
    # own transaction), and the *old*, wider `language_valid` check is
    # still in force -- proving no DDL from this revision committed either.
    engine = create_engine_for(url)
    try:
        with engine.connect() as connection:
            stamped = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        assert stamped == HEAD_MINUS_ONE
        with engine.begin() as connection:
            _insert_runner_confirmation(
                connection,
                id_="still-old-check-relational",
                owner_id=owner_id,
                language="relational",
                timestamp=timestamp,
            )
    finally:
        engine.dispose()
