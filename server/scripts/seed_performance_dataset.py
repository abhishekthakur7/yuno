#!/usr/bin/env python3
"""IDK-504: build the one representative local dataset the perf harness measures.

Spec §8.6 requires every measurement to carry "dataset shape" context, and
IDK-504 (unlike IDK-501, which snapshots governed tables across an Alembic
upgrade) needs exactly one deterministic, sizeable dataset a Playwright run
and a server-side script can both point at. Per IDK-504's implementation
note, this reuses the IDK-501 fixtures/helpers' *pattern* rather than
maintaining a second synthetic dataset shape: every write below goes
through the same real services/unit-of-work calls
`server/tests/integration/test_alembic_representative_upgrades.py`'s
helpers use (`_provision_owner`, `_publish_fixture`, `_create_fixture_goal`,
`_seed_generated_artifact`, `_apply_depth_override`, `_apply_skip_decision`,
`_seed_completed_mock_transcript`'s evidence+assessment half,
`_seed_active_job`, `_seed_stale_search_projection`) -- never
`Base.metadata.create_all`, never a hand-written INSERT for governed
domain data. Nothing here is imported from that test module (or any test
module): each helper is reproduced from the real service/route functions
directly, since a seeder script is not a pytest fixture and cannot import
from `server/tests`.

Determinism: every id this script itself assigns (topics, relations,
content revisions, the goals, evidence, imports, artifacts, jobs, sources,
rubric) is a fixed literal string, not `new_id()`. Nothing here calls a
random-number generator. Two runs against two fresh databases produce
byte-identical counts in the printed dataset-shape JSON (verified by
running the seeder twice against two temp databases). Row-level ids
assigned deep inside a called service function via `new_id()`
(ULID, time+randomness-based) are the one exception this script cannot
remove without reimplementing that service's domain logic, which IDK-504
explicitly says not to do; the dataset *shape* -- the counts a report's
context object records -- stays identical regardless.

Preconditions: the target database must already be at the Alembic head
(the harness runs `alembic upgrade head` first; `publish_canonical_graph`
itself refuses to publish otherwise via `require_single_head`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from yuno.api.contracts import (
    DepthOverrideRequest,
    LearnerCorrectionRequest,
    SkipDecisionRequest,
)
from yuno.api.routes.roadmap import post_correction, post_depth, post_skip
from yuno.modules.canonical.domain import (
    CanonicalGraphManifest,
    ContentRevision,
    RelationType,
    Topic,
    TopicRelation,
)
from yuno.modules.canonical.publisher import publish_canonical_graph
from yuno.modules.canonical.validation import compute_manifest_hash
from yuno.modules.evidence_evaluation.domain import (
    AssessmentState,
    DimensionOutcome,
    EvaluationDimensionResult,
    EvaluationRequest,
    EvaluationResult,
    Rubric,
    RubricDimension,
    RubricStatus,
)
from yuno.modules.evidence_evaluation.service import create_evidence, perform_assessment
from yuno.modules.identity.service import ensure_local_owner
from yuno.modules.imports.domain import ImportType
from yuno.modules.imports.service import (
    create_import,
    mark_import_parsing,
    parse_import,
)
from yuno.modules.jobs_events.repository import JobRepository
from yuno.modules.learning_content.domain import (
    GENERATION_SCHEMA_VERSION,
    GeneratedClaim,
    GenerateResult,
    TopicLayer,
)
from yuno.modules.learning_content.service import reserve_generation, run_generation
from yuno.modules.notebook_review.domain import NotebookEntryKind
from yuno.modules.notebook_review.service import create_notebook_entry
from yuno.modules.profiles_goals.domain import GoalPath, TargetCapability, TargetLevel
from yuno.modules.profiles_goals.service import create_goal, ensure_profile
from yuno.modules.provenance.domain import Source, SourceAvailability
from yuno.modules.roadmap.domain import CorrectionType, LearningClassification
from yuno.modules.settings_data.service import ensure_owner_settings
from yuno.shared.application.jobs import JobLane, JobRequest
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.infrastructure.database import (
    create_engine_for,
    create_session_factory,
)
from yuno.unit_of_work import create_unit_of_work_factory

DEFAULT_DATABASE_URL = "sqlite+pysqlite:///./perf.db"

# ---------------------------------------------------------------------------
# Deterministic canonical graph: 6 subjects x 10 topics = 60 topics.
#
# java -> spring_boot -> aws -> system_design -> rdb is one linear
# cross-subject prerequisite chain (each subject's first topic depends on
# the previous subject's last topic); within a subject the 10 topics form
# their own linear prerequisite chain. dsa is a separate 10-topic
# prerequisite chain, and CUR-02 requires every dsa topic to carry a
# scenario relation -- each dsa topic N points a `scenario` relation at
# system_design topic N. All of this is one direction (subject order,
# then dsa -> system_design), so the combined prerequisite+scenario graph
# validation.py checks is acyclic by construction.
# ---------------------------------------------------------------------------

_SUBJECT_CHAIN = ("java", "spring_boot", "aws", "system_design", "rdb")
_TOPICS_PER_SUBJECT = 10
_DSA_TOPIC_COUNT = 10

_LAYER_BY_POSITION = (
    TopicLayer.ESSENTIAL.value,
    TopicLayer.IMPLEMENTATION.value,
    TopicLayer.ALTERNATIVES.value,
)


def _topic_stable_id(subject: str, index: int) -> str:
    return f"perf-topic-{subject}-{index:02d}"


def _build_manifest() -> tuple[CanonicalGraphManifest, dict[str, str]]:
    topics: list[Topic] = []
    relations: list[TopicRelation] = []
    content_revisions: list[ContentRevision] = []
    topic_identity_slugs: dict[str, str] = {}

    checkpoint = 0
    previous_subject_last_id: str | None = None
    for subject in _SUBJECT_CHAIN:
        previous_in_subject: str | None = None
        for index in range(1, _TOPICS_PER_SUBJECT + 1):
            stable_id = _topic_stable_id(subject, index)
            topic_identity_slugs[stable_id] = stable_id
            topics.append(
                Topic(
                    graph_version_id="",
                    stable_id=stable_id,
                    title=f"[PERF] {subject} topic {index:02d}",
                    subject=subject,
                    scope_tags=(f"perf-{subject}",),
                    level_tag="perf-level-1" if index <= 5 else "perf-level-2",
                    target_capability="implement",
                    recommended_layer=_LAYER_BY_POSITION[
                        index % len(_LAYER_BY_POSITION)
                    ],
                    checkpoint_start=checkpoint,
                    checkpoint_end=checkpoint + 1,
                )
            )
            checkpoint += 1
            if previous_in_subject is not None:
                relations.append(
                    TopicRelation(
                        id=f"perf-relation-{previous_in_subject}-{stable_id}",
                        graph_version_id="",
                        from_stable_id=previous_in_subject,
                        to_stable_id=stable_id,
                        relation_type=RelationType.PREREQUISITE,
                        rationale="Representative perf dataset: in-subject ordering.",
                    )
                )
            elif previous_subject_last_id is not None:
                relations.append(
                    TopicRelation(
                        id=f"perf-relation-{previous_subject_last_id}-{stable_id}",
                        graph_version_id="",
                        from_stable_id=previous_subject_last_id,
                        to_stable_id=stable_id,
                        relation_type=RelationType.PREREQUISITE,
                        rationale="Representative perf dataset: cross-subject ordering.",
                    )
                )
            previous_in_subject = stable_id
        previous_subject_last_id = previous_in_subject

    content_revisions.append(
        ContentRevision(
            id=f"perf-content-{_topic_stable_id('java', 1)}-essential",
            graph_version_id="",
            topic_stable_id=_topic_stable_id("java", 1),
            layer=TopicLayer.ESSENTIAL.value,
            kind="perf-kind-explanation",
            status="published",
            markdown_ref="fixture://perf/java-01/essential.md",
            markdown_hash="perf-markdown-hash-java-01-essential",
            prompt_template_version=None,
            creator_owner_id="",
            supersedes_revision_id=None,
            created_at="",
        )
    )

    previous_dsa: str | None = None
    for index in range(1, _DSA_TOPIC_COUNT + 1):
        stable_id = _topic_stable_id("dsa", index)
        topic_identity_slugs[stable_id] = stable_id
        topics.append(
            Topic(
                graph_version_id="",
                stable_id=stable_id,
                title=f"[PERF] dsa topic {index:02d}",
                subject="dsa",
                scope_tags=("perf-dsa",),
                level_tag="perf-level-1",
                target_capability="understand",
                recommended_layer=TopicLayer.ESSENTIAL.value,
                checkpoint_start=checkpoint,
                checkpoint_end=checkpoint + 1,
            )
        )
        checkpoint += 1
        if previous_dsa is not None:
            relations.append(
                TopicRelation(
                    id=f"perf-relation-{previous_dsa}-{stable_id}",
                    graph_version_id="",
                    from_stable_id=previous_dsa,
                    to_stable_id=stable_id,
                    relation_type=RelationType.PREREQUISITE,
                    rationale="Representative perf dataset: dsa ordering.",
                )
            )
        scenario_target = _topic_stable_id("system_design", index)
        relations.append(
            TopicRelation(
                id=f"perf-relation-scenario-{stable_id}-{scenario_target}",
                graph_version_id="",
                from_stable_id=stable_id,
                to_stable_id=scenario_target,
                relation_type=RelationType.SCENARIO,
                rationale="CUR-02: dsa topic bound to a scenario-carrying topic.",
            )
        )
        previous_dsa = stable_id

    manifest_without_hash = CanonicalGraphManifest(
        version_label="perf-canonical-v1",
        manifest_version="1",
        manifest_hash="",
        topics=tuple(topics),
        relations=tuple(relations),
        content_revisions=tuple(content_revisions),
    )
    manifest = CanonicalGraphManifest(
        version_label=manifest_without_hash.version_label,
        manifest_version=manifest_without_hash.manifest_version,
        manifest_hash=compute_manifest_hash(manifest_without_hash),
        topics=manifest_without_hash.topics,
        relations=manifest_without_hash.relations,
        content_revisions=manifest_without_hash.content_revisions,
    )
    return manifest, topic_identity_slugs


# ---------------------------------------------------------------------------
# Learner-data seeding, driven through the real application services.
# ---------------------------------------------------------------------------


def _provision_owner(uow_factory) -> str:
    """The same provisioning `create_app`'s ASGI lifespan runs (spec §4.2
    D1: the local owner is granted both `learner` and
    `designated_editorial_approver` by `ensure_local_owner` itself).
    """
    with uow_factory() as uow:
        owner = ensure_local_owner(uow, "Performance dataset owner")
        ensure_profile(uow, owner.id)
        ensure_owner_settings(uow, owner.id)
        uow.commit()
    return owner.id


def _build_basis_ref(manifest: CanonicalGraphManifest) -> str:
    """IDK-002 section 4's `basis_ref` contract, enforced by
    `validate_basis_ref` (`canonical/validation.py`) since migration
    `4747447ccaa3`'s `basis_ref_valid` JSON CHECK. This dataset's initial
    publish has no real editorial review behind it (same synthetic-fixture
    caveat `tests/fixtures/canonical/data/v1_approved.json`'s own
    `basis_ref.notes` states), so every `*_reviewed`/`*_total` pair is set
    to the manifest's own real topic counts (satisfying section 4's
    exhaustive-review equality check) rather than to an arbitrary number.
    """
    topic_count = len(manifest.topics)
    payload = {
        "basis_ref_version": "editorial-approval-basis-v1",
        "policy_identifier": "editorial-approval-criteria-v1",
        "reviewed_manifest_hash": manifest.manifest_hash,
        "checklist_completed_at": "2026-08-01T00:00:00.000000Z",
        "review_kind": "initial",
        "diff_against_version_label": None,
        "curriculum_boundary_review": {
            "result": "pass",
            "topics_reviewed": topic_count,
            "topics_total": topic_count,
        },
        "dsa_scenario_review": {
            "result": "pass",
            "dsa_topics_reviewed": _DSA_TOPIC_COUNT,
            "dsa_topics_total": _DSA_TOPIC_COUNT,
        },
        "dag_identity_review": {
            "result": "pass",
            "reused_stable_ids_confirmed": 0,
            "reused_stable_ids_total": 0,
        },
        "source_citation_review": {
            "structural_result": "pass",
            "live_check_result": "pass",
            "structural_claims_reviewed": 0,
            "structural_claims_total": 0,
            "live_check_sample_size": 0,
            "live_check_population_size": 0,
        },
        "layer_reversal_review": {
            "result": "pass",
            "topics_reviewed": topic_count,
            "topics_total": topic_count,
        },
        "half_seed_immutability_check": {"result": "pass"},
        "diff_review": None,
        "approver_is_sole_content_author": True,
        "notes": (
            "IDK-504 performance-dataset seed basis_ref -- synthetic, not a "
            "real editorial review; reviewed_manifest_hash only matches this "
            "script's own generated manifest."
        ),
    }
    return json.dumps(payload)


def _publish_graph(uow_factory, engine, owner_id: str):
    manifest, topic_identity_slugs = _build_manifest()
    return publish_canonical_graph(
        engine=engine,
        uow_factory=uow_factory,
        manifest=manifest,
        actor_owner_id=owner_id,
        basis_ref=_build_basis_ref(manifest),
        topic_identity_slugs=topic_identity_slugs,
    )


def _create_goal(uow_factory, owner_id: str, graph_version_id: str, name: str):
    with uow_factory() as uow:
        goal = create_goal(
            uow,
            owner_id,
            name=name,
            path=GoalPath.LEARN,
            subject="java",
            role=None,
            target_level=TargetLevel.SENIOR,
            target_capability=TargetCapability.IMPLEMENT,
            graph_version_id=graph_version_id,
            approved_graph_exists=True,
        )
        uow.commit()
    return goal


def _apply_depth_override(
    uow_factory, owner_id: str, goal_id: str, topic_stable_id: str, depth: str, key: str
) -> None:
    with uow_factory() as uow:
        post_depth(
            goal_id,
            DepthOverrideRequest(
                topic_stable_id=topic_stable_id,
                depth=depth,
                reason="Representative perf dataset.",
            ),
            owner_id,
            uow,
            key,
        )


def _apply_skip_decision(
    uow_factory,
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
                reason="Representative perf dataset.",
            ),
            owner_id,
            uow,
            key,
        )


def _apply_correction(
    uow_factory, owner_id: str, goal_id: str, topic_stable_id: str, key: str
) -> None:
    with uow_factory() as uow:
        post_correction(
            goal_id,
            LearnerCorrectionRequest(
                topic_stable_id=topic_stable_id,
                classification=LearningClassification.LIKELY_KNOWN,
                correction_type=CorrectionType.CORRECTION,
                reason="Representative perf dataset.",
            ),
            owner_id,
            uow,
            key,
        )


def _source(uow_factory, owner_id: str, source_id: str, suffix: str) -> str:
    with uow_factory() as uow:
        source = Source(
            id=source_id,
            owner_id=owner_id,
            origin="fixture",
            source_type="documentation",
            title=f"Perf dataset source {suffix}",
            publisher="Perf dataset publisher",
            canonical_url=f"https://example.invalid/perf/{suffix}",
            license_status="approved-open-license",
            availability_status=SourceAvailability.AVAILABLE,
            withdrawal_reason=None,
            superseded_by_source_id=None,
            created_at="2026-08-01T00:00:00.000000Z",
            updated_at="2026-08-01T00:00:00.000000Z",
        )
        uow.provenance.add_source(source)
        uow.commit()
    return source.id


class _PerfGenerationAdapter:
    """A structural `GenerationAdapter`: returns a fixed body deterministically,
    mirroring `test_generated_content_api.py`'s `FakeGenerationAdapter` (a
    test double implementing a port, not domain logic) without importing
    from a test module.
    """

    def __init__(self, body: str, source_id: str) -> None:
        self._body = body
        self._source_id = source_id

    def generate(self, request):
        return GenerateResult(
            body=self._body,
            provider="perf-dataset-provider",
            model="perf-dataset-model-v1",
            contract_version="perf-dataset-provider-contract-v1",
            schema_version=GENERATION_SCHEMA_VERSION,
            generated_at="2026-08-01T00:00:00.000000Z",
            claims=(
                GeneratedClaim(
                    claim_text="A representative perf dataset claim.",
                    claim_type="fact",
                    sensitive=False,
                    citations=(),
                ),
            ),
            warnings=(),
        )


def _seed_generated_artifact(
    uow_factory,
    owner_id: str,
    goal_id: str,
    topic_stable_id: str,
    *,
    suffix: str,
    source_id: str,
):
    with uow_factory() as uow:
        _ref, attempt, _dispatch = reserve_generation(
            uow,
            owner_id,
            goal_id,
            topic_stable_id,
            TopicLayer.ESSENTIAL,
            f"perf-generate-{suffix}",
        )
        uow.commit()
    adapter = _PerfGenerationAdapter(
        f"Representative perf dataset body for {suffix}.", source_id
    )
    return run_generation(uow_factory, adapter, owner_id, attempt.id)


def _seed_rubric(uow_factory, owner_id: str) -> Rubric:
    with uow_factory() as uow:
        rubric = Rubric(
            "perf-rubric-v1",
            owner_id,
            "perf-dataset-fixture-v0",
            "implement",
            "perf-role",
            "senior",
            "fixture-v0",
            RubricStatus.FIXTURE,
            "fixture-v0-non-production",
            "2026-08-01T00:00:00.000000Z",
        )
        uow.evidence.add_rubric(
            rubric,
            (
                RubricDimension(
                    "perf-rubric-dimension-reasoning",
                    rubric.id,
                    "reasoning",
                    "Reasoning",
                    "Perf dataset controlled dimension.",
                    1,
                    "Accept only the controlled perf-dataset shape as exact.",
                ),
            ),
        )
        uow.commit()
    return rubric


class _PerfEvaluationAdapter:
    def evaluate(self, request) -> EvaluationResult:
        return EvaluationResult(
            state=AssessmentState.FEEDBACK_READY,
            dimensions=(
                EvaluationDimensionResult(
                    "reasoning",
                    DimensionOutcome.PASS,
                    "Meets the representative perf dataset bar.",
                    (request.evidence_id,),
                ),
            ),
            facts=("A representative perf dataset fact.",),
            trade_offs=(),
            citations=(),
            ambiguities=(),
            feedback="Representative perf dataset feedback.",
            cross_question_candidate=None,
            revision_invitation=None,
            warnings=(),
            limitation_labels=("fixture-v0-non-production",),
        )


def _seed_evidence_with_assessment(
    uow_factory,
    owner_id: str,
    goal_id: str,
    topic_stable_id: str,
    rubric: Rubric,
    *,
    suffix: str,
):
    with uow_factory() as uow:
        evidence = create_evidence(
            uow,
            owner_id,
            goal_id,
            topic_stable_id=topic_stable_id,
            evidence_type="perf-fixture",
            capability="implement",
            summary=f"Representative perf dataset evidence {suffix}",
            origin="perf-dataset",
            content=f"Representative perf dataset evidence content {suffix}.",
            content_version="perf-v1",
        )
        uow.commit()
    with uow_factory() as uow:
        request = EvaluationRequest(
            evidence.id,
            "perf-dataset-task",
            rubric.id,
            rubric.version,
            (),
            "implement",
            (),
            (),
            rubric.role,
            rubric.level,
            "interactive",
        )
        perform_assessment(uow, _PerfEvaluationAdapter(), owner_id, request)
        uow.commit()
    return evidence


def _seed_notebook_entry(
    uow_factory, owner_id: str, goal_id: str, topic_stable_id: str, *, suffix: str
):
    with uow_factory() as uow:
        entry = create_notebook_entry(
            uow,
            owner_id,
            goal_id,
            entry_kind=NotebookEntryKind.USER,
            markdown=f"Representative perf dataset notebook entry {suffix}.",
            topic_stable_id=topic_stable_id,
        )
        uow.commit()
    return entry


def _seed_import(uow_factory, owner_id: str, goal_id: str, *, suffix: str):
    with uow_factory() as uow:
        record = create_import(
            uow,
            owner_id,
            goal_id=goal_id,
            import_type=ImportType.PLAIN_TEXT,
            source_text=(
                "Representative perf dataset import statement one.\n"
                f"Representative perf dataset import statement two ({suffix}).\n"
            ),
        )
        uow.commit()
        import_id = record.id
    with uow_factory() as uow:
        mark_import_parsing(uow, owner_id, import_id)
        uow.commit()
    with uow_factory() as uow:
        parse_import(uow, owner_id, import_id)
        uow.commit()
    return import_id


def _seed_terminal_job(
    session_factory, owner_id: str, *, kind: str, dedupe_key: str, succeed: bool
) -> str:
    with session_factory() as session:
        repo = JobRepository(session, SystemClock())
        job = repo.enqueue(
            JobRequest(kind, owner_id, {}, dedupe_key=dedupe_key), JobLane.INTERACTIVE
        )
        session.commit()
        claimed = repo.claim(
            JobLane.INTERACTIVE, "perf-dataset-worker", now_text(SystemClock())
        )
        session.commit()
        assert claimed is not None and claimed.id == job.id
        if succeed:
            repo.finish_success(
                claimed,
                f"perf-dataset-result:{job.id}",
                f"perf-dataset-result-hash:{job.id}",
            )
        else:
            repo.finish_failure(
                claimed, "Representative perf dataset failure.", retryable=False
            )
        session.commit()
        return job.id


def _seed_active_job(session_factory, owner_id: str) -> str:
    with session_factory() as session:
        repo = JobRepository(session, SystemClock())
        job = repo.enqueue(
            JobRequest(
                "rebuild_index", owner_id, {}, dedupe_key="perf-dataset-active-job"
            ),
            JobLane.BACKGROUND,
        )
        session.commit()
        return job.id


def _rebuild_search(uow_factory, owner_id: str) -> None:
    with uow_factory() as uow:
        uow.search.rebuild(owner_id, "perf-dataset-rebuild")
        uow.commit()


def _search_document_count(engine, owner_id: str) -> int:
    from sqlalchemy import text

    with engine.connect() as connection:
        return int(
            connection.execute(
                text(
                    "SELECT count(*) FROM search_documents WHERE owner_id = :owner_id"
                ),
                {"owner_id": owner_id},
            ).scalar_one()
        )


def seed(database_url: str) -> dict:
    engine = create_engine_for(database_url)
    try:
        session_factory = create_session_factory(engine)
        uow_factory = create_unit_of_work_factory(session_factory)

        owner_id = _provision_owner(uow_factory)
        version = _publish_graph(uow_factory, engine, owner_id)

        goal_one = _create_goal(
            uow_factory, owner_id, version.id, "Representative perf goal one"
        )
        goal_two = _create_goal(
            uow_factory, owner_id, version.id, "Representative perf goal two"
        )

        # Roadmap overlays/corrections/depth overrides/skip decisions.
        _apply_depth_override(
            uow_factory,
            owner_id,
            goal_one.id,
            _topic_stable_id("java", 2),
            "Implementation",
            "perf-depth-1",
        )
        _apply_depth_override(
            uow_factory,
            owner_id,
            goal_one.id,
            _topic_stable_id("aws", 1),
            "Alternatives",
            "perf-depth-2",
        )
        _apply_skip_decision(
            uow_factory,
            owner_id,
            goal_one.id,
            _topic_stable_id("rdb", 5),
            True,
            "perf-skip-1",
        )
        _apply_correction(
            uow_factory,
            owner_id,
            goal_two.id,
            _topic_stable_id("spring_boot", 3),
            "perf-correction-1",
        )

        # Provenance sources and generated artifacts with provenance.
        source_one = _source(uow_factory, owner_id, "perf-source-one", "one")
        source_two = _source(uow_factory, owner_id, "perf-source-two", "two")
        artifact_topics = [
            (_topic_stable_id("java", 1), "goal-one-java-01", goal_one.id, source_one),
            (_topic_stable_id("aws", 1), "goal-one-aws-01", goal_one.id, source_one),
            (
                _topic_stable_id("spring_boot", 1),
                "goal-two-spring-01",
                goal_two.id,
                source_two,
            ),
        ]
        generated_artifact_count = 0
        for topic_stable_id, suffix, goal_id, source_id in artifact_topics:
            _seed_generated_artifact(
                uow_factory,
                owner_id,
                goal_id,
                topic_stable_id,
                suffix=suffix,
                source_id=source_id,
            )
            generated_artifact_count += 1

        # Evidence records with assessments.
        rubric = _seed_rubric(uow_factory, owner_id)
        evidence_topics = [
            (_topic_stable_id("java", 3), "goal-one-java-03", goal_one.id),
            (_topic_stable_id("java", 4), "goal-one-java-04", goal_one.id),
            (_topic_stable_id("aws", 2), "goal-one-aws-02", goal_one.id),
            (_topic_stable_id("system_design", 1), "goal-two-sd-01", goal_two.id),
            (_topic_stable_id("rdb", 1), "goal-two-rdb-01", goal_two.id),
        ]
        evidence_count = 0
        for topic_stable_id, suffix, goal_id in evidence_topics:
            _seed_evidence_with_assessment(
                uow_factory, owner_id, goal_id, topic_stable_id, rubric, suffix=suffix
            )
            evidence_count += 1

        # Notebook entries.
        notebook_topics = [
            (_topic_stable_id("java", 1), "goal-one-note-1", goal_one.id),
            (_topic_stable_id("aws", 1), "goal-one-note-2", goal_one.id),
            (_topic_stable_id("spring_boot", 2), "goal-two-note-1", goal_two.id),
            (_topic_stable_id("system_design", 2), "goal-two-note-2", goal_two.id),
        ]
        notebook_count = 0
        for topic_stable_id, suffix, goal_id in notebook_topics:
            _seed_notebook_entry(
                uow_factory, owner_id, goal_id, topic_stable_id, suffix=suffix
            )
            notebook_count += 1

        # Imports.
        import_count = 0
        for goal_id, suffix in ((goal_one.id, "one"), (goal_two.id, "two")):
            _seed_import(uow_factory, owner_id, goal_id, suffix=suffix)
            import_count += 1

        # Jobs: two terminal (one succeeded, one failed), one active.
        _seed_terminal_job(
            session_factory,
            owner_id,
            kind="rebuild_index",
            dedupe_key="perf-dataset-succeeded-job",
            succeed=True,
        )
        _seed_terminal_job(
            session_factory,
            owner_id,
            kind="rebuild_index",
            dedupe_key="perf-dataset-failed-job",
            succeed=False,
        )
        _seed_active_job(session_factory, owner_id)
        job_count = 3

        # Populated search projection: rebuild after every other write above
        # so goals/evidence/notebook/generated-artifact rows are indexed.
        _rebuild_search(uow_factory, owner_id)
        search_document_count = _search_document_count(engine, owner_id)

        return {
            "graph_version_label": version.version_label,
            "graph_version_id": version.id,
            "goal_count": 2,
            "evidence_count": evidence_count,
            "notebook_count": notebook_count,
            "import_count": import_count,
            "generated_artifact_count": generated_artifact_count,
            "job_count": job_count,
            "search_document_count": search_document_count,
        }
    finally:
        engine.dispose()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed the deterministic representative dataset the IDK-504 perf harness measures."
    )
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    parser.add_argument("--json-out", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    manifest, _ = _build_manifest()
    shape = seed(args.database_url)
    shape["canonical_topic_count"] = len(manifest.topics)
    shape["relation_count"] = len(manifest.relations)

    payload = json.dumps(shape, indent=2, sort_keys=True)
    print(payload)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(payload + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
