"""Framework-free roadmap domain and the pure D2 projector."""

from __future__ import annotations

import heapq
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum

from yuno.shared.domain.errors import ConflictError, DomainValidationError
from yuno.shared.domain.hashing import hash_payload


class OverlayEntryType(StrEnum):
    ORDER_CONSTRAINT = "order_constraint"
    SKIP = "skip"
    DEPTH = "depth"
    BRIDGE = "bridge"
    RECOMMENDATION = "recommendation"
    MERGE_RESOLUTION = "merge_resolution"
    ARCHIVED_LOCAL_TOPIC = "archived_local_topic"


class OverlayProposalType(StrEnum):
    RECOMMENDATION = "recommendation"
    EMPHASIS = "emphasis"
    EXAMPLE = "example"
    EXERCISE = "exercise"
    ORDERING = "ordering"
    BRIDGE = "bridge"


class OverlayProposalState(StrEnum):
    AWAITING_DECISION = "awaiting-learner-decision"
    ACCEPTED = "accepted"
    POSTPONED = "postponed"
    DISMISSED = "dismissed"
    REJECTED_STALE = "rejected-stale"


class OverlayDecisionType(StrEnum):
    ACCEPT = "accept"
    ADD = "add"
    POSTPONE = "postpone"
    DISMISS = "dismiss"


class LearningClassification(StrEnum):
    LIKELY_KNOWN = "likely-known"
    PARTIAL = "partial"
    UNVERIFIED = "unverified"
    NEW = "new"


class CorrectionType(StrEnum):
    CORRECTION = "correction"
    CONFIRMATION = "confirmation"
    GAP = "gap"
    TRANSFER_CONFIRMATION = "transfer-confirmation"


@dataclass(frozen=True)
class RoadmapTopic:
    stable_id: str
    title: str
    subject: str
    scope_tags: tuple[str, ...]
    level_tag: str
    target_capability: str
    recommended_depth: str


@dataclass(frozen=True)
class RoadmapRelation:
    before_topic_id: str
    after_topic_id: str


@dataclass(frozen=True)
class PersonalOverlay:
    id: str
    owner_id: str
    goal_id: str
    base_graph_version_id: str
    state: str
    row_version: int
    created_at: str


@dataclass(frozen=True)
class OverlayEntry:
    id: str
    owner_id: str
    goal_id: str
    overlay_id: str
    graph_version_id: str
    topic_stable_id: str | None
    entry_type: OverlayEntryType
    value: dict[str, object]
    reason: str | None
    source: str
    approved_at: str
    supersedes_entry_id: str | None = None
    content_hash: str = ""


@dataclass(frozen=True)
class OverlayProposal:
    id: str
    owner_id: str
    goal_id: str
    generated_against_graph_version_id: str
    topic_stable_id: str | None
    proposal_type: OverlayProposalType
    payload: dict[str, object]
    content_hash: str
    state: OverlayProposalState
    state_reason: str | None
    created_at: str
    decided_at: str | None = None


@dataclass(frozen=True)
class OverlayProposalDecision:
    id: str
    owner_id: str
    goal_id: str
    proposal_id: str
    decision: OverlayDecisionType
    reason: str | None
    decided_at: str


@dataclass(frozen=True)
class LearningState:
    id: str
    owner_id: str
    goal_id: str
    topic_stable_id: str
    graph_version_id: str
    classification: LearningClassification
    origin: str
    recommended_depth: str
    explanation: str
    derivation_version: str
    input_hash: str
    derived_at: str


@dataclass(frozen=True)
class LearnerCorrection:
    id: str
    owner_id: str
    goal_id: str
    topic_stable_id: str
    correction_type: CorrectionType
    value: str
    reason: str | None
    created_at: str
    supersedes_correction_id: str | None = None


@dataclass(frozen=True)
class RoadmapIdempotencyRecord:
    id: str
    owner_id: str
    goal_id: str
    operation: str
    idempotency_key: str
    request_hash: str
    response_json: str
    created_at: str


@dataclass(frozen=True)
class ProjectedTopic:
    stable_id: str
    title: str
    subject: str
    scope_tags: tuple[str, ...]
    level_tag: str
    target_capability: str
    recommended_depth: str
    depth_override: str | None
    is_skipped: bool
    classification: LearningClassification
    explanation: str
    has_transferred_evidence: bool
    is_archived_local: bool = False
    pending_proposals: tuple[dict[str, object], ...] = ()
    conflicts: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class RoadmapProjection:
    graph_version_id: str
    projection_version: str
    topics: tuple[ProjectedTopic, ...]


class InvalidOrderConstraintError(ConflictError):
    code = "invalid_order_constraint"


class ProposalStaleError(ConflictError):
    code = "proposal_stale"


def validate_proposal_payload(
    proposal_type: OverlayProposalType,
    topic_stable_id: str | None,
    payload: Mapping[str, object],
) -> None:
    if proposal_type is OverlayProposalType.BRIDGE:
        if topic_stable_id is None:
            raise DomainValidationError("A bridge proposal must identify a topic.")
        for field in ("why", "relationship"):
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                raise DomainValidationError(
                    f"A bridge proposal requires a non-empty '{field}'."
                )
        placement = payload.get("proposed_placement")
        if (
            placement is None
            or (isinstance(placement, str) and not placement.strip())
            or (isinstance(placement, Mapping) and not placement)
            or not isinstance(placement, (str, Mapping))
        ):
            raise DomainValidationError(
                "A bridge proposal requires a non-empty 'proposed_placement'."
            )
    if proposal_type is OverlayProposalType.ORDERING:
        for field in ("before_topic_id", "after_topic_id"):
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                raise DomainValidationError(
                    f"An ordering proposal requires a non-empty '{field}'."
                )


def project_roadmap(
    *,
    graph_version_id: str,
    topics: Iterable[RoadmapTopic],
    prerequisite_relations: Iterable[RoadmapRelation],
    overlay_entries: Iterable[OverlayEntry] = (),
    learning_states: Iterable[LearningState] = (),
    corrections: Iterable[LearnerCorrection] = (),
    transferred_evidence_topic_ids: Iterable[str] = (),
    pending_proposals: Iterable[Mapping[str, object]] = (),
    conflicts: Iterable[Mapping[str, object]] = (),
) -> RoadmapProjection:
    """Return a deterministic projection without mutating any input or store."""
    topic_items = tuple(topics)
    relation_items = tuple(prerequisite_relations)
    entry_items = tuple(overlay_entries)
    state_items = tuple(learning_states)
    correction_items = tuple(corrections)
    proposal_items = tuple(dict(item) for item in pending_proposals)
    conflict_items = tuple(dict(item) for item in conflicts)
    # Only entries expressed against the current graph participate. A merge
    # carries retained choices forward explicitly, so old-version overlays
    # cannot silently leak into the new projection.
    entry_items = tuple(
        entry for entry in entry_items if entry.graph_version_id == graph_version_id
    )
    canonical_topic_ids = {topic.stable_id for topic in topic_items}
    archived = [
        entry
        for entry in entry_items
        if entry.entry_type is OverlayEntryType.ARCHIVED_LOCAL_TOPIC
        and entry.topic_stable_id not in canonical_topic_ids
    ]
    archived_topic_ids = {entry.topic_stable_id for entry in archived}
    retained_topic_values = {
        entry.topic_stable_id: entry.value.get("before")
        for entry in entry_items
        if entry.entry_type is OverlayEntryType.MERGE_RESOLUTION
        and entry.value.get("retained") is True
        and entry.value.get("entity_type") == "topic"
        and isinstance(entry.value.get("before"), Mapping)
    }
    topic_items = tuple(
        RoadmapTopic(
            stable_id=topic.stable_id,
            title=str(retained_topic_values[topic.stable_id].get("title", topic.title)),
            subject=str(
                retained_topic_values[topic.stable_id].get("subject", topic.subject)
            ),
            scope_tags=tuple(
                retained_topic_values[topic.stable_id].get(
                    "scope_tags", topic.scope_tags
                )
            ),
            level_tag=str(
                retained_topic_values[topic.stable_id].get("level_tag", topic.level_tag)
            ),
            target_capability=str(
                retained_topic_values[topic.stable_id].get(
                    "target_capability", topic.target_capability
                )
            ),
            recommended_depth=str(
                retained_topic_values[topic.stable_id].get(
                    "recommended_layer", topic.recommended_depth
                )
            ),
        )
        if topic.stable_id in retained_topic_values
        else topic
        for topic in topic_items
    )
    topic_items = topic_items + tuple(
        RoadmapTopic(
            stable_id=entry.topic_stable_id or "",
            title=str(entry.value.get("title", "Archived local topic")),
            subject=str(entry.value.get("subject", "archived")),
            scope_tags=tuple(str(v) for v in entry.value.get("scope_tags", [])),
            level_tag=str(entry.value.get("level_tag", "archived")),
            target_capability=str(entry.value.get("target_capability", "understand")),
            recommended_depth=str(entry.value.get("recommended_layer", "Essential")),
        )
        for entry in archived
        if entry.topic_stable_id
    )
    topic_by_id = {topic.stable_id: topic for topic in topic_items}
    if len(topic_by_id) == 0:
        return RoadmapProjection(
            graph_version_id, hash_payload({"graph": graph_version_id}), ()
        )

    canonical_edges = {
        (edge.before_topic_id, edge.after_topic_id)
        for edge in relation_items
        if edge.before_topic_id in topic_by_id and edge.after_topic_id in topic_by_id
    }
    ordered_entries = sorted(entry_items, key=lambda item: (item.approved_at, item.id))
    superseded_entry_ids = {
        item.supersedes_entry_id
        for item in ordered_entries
        if item.supersedes_entry_id is not None
    }
    entries = [item for item in ordered_entries if item.id not in superseded_entry_ids]
    order_edges: set[tuple[str, str]] = set()
    latest_skip: dict[str, bool] = {}
    latest_depth: dict[str, str | None] = {}
    for entry in entries:
        if entry.entry_type is OverlayEntryType.ORDER_CONSTRAINT:
            before = str(entry.value.get("before_topic_id", ""))
            after = str(entry.value.get("after_topic_id", ""))
            if before in topic_by_id and after in topic_by_id:
                order_edges.add((before, after))
        elif (
            entry.topic_stable_id in topic_by_id
            and entry.entry_type is OverlayEntryType.SKIP
        ):
            latest_skip[entry.topic_stable_id] = bool(entry.value.get("skipped"))
        elif (
            entry.topic_stable_id in topic_by_id
            and entry.entry_type is OverlayEntryType.DEPTH
        ):
            value = entry.value.get("depth")
            latest_depth[entry.topic_stable_id] = (
                str(value) if value is not None else None
            )

    edges = canonical_edges | order_edges
    ordered_ids = _lexical_topological_sort(topic_by_id, edges)
    state_by_topic = {state.topic_stable_id: state for state in state_items}
    correction_by_topic = {
        item.topic_stable_id: item
        for item in sorted(
            correction_items, key=lambda item: (item.created_at, item.id)
        )
    }
    evidence_topics = frozenset(transferred_evidence_topic_ids)
    proposals_by_topic = _annotations_by_topic(proposal_items)
    conflicts_by_topic = _annotations_by_topic(conflict_items)

    projected: list[ProjectedTopic] = []
    for stable_id in ordered_ids:
        topic = topic_by_id[stable_id]
        state = state_by_topic.get(stable_id)
        correction = correction_by_topic.get(stable_id)
        classification = (
            state.classification if state else LearningClassification.UNVERIFIED
        )
        explanation = (
            state.explanation
            if state
            else "No diagnostic evidence has been recorded yet."
        )
        if correction is not None:
            try:
                classification = LearningClassification(correction.value)
            except ValueError as exc:
                raise DomainValidationError(
                    f"Correction for '{stable_id}' has invalid classification '{correction.value}'."
                ) from exc
            explanation = correction.reason or "Explicit learner correction."
        projected.append(
            ProjectedTopic(
                stable_id=stable_id,
                title=topic.title,
                subject=topic.subject,
                scope_tags=topic.scope_tags,
                level_tag=topic.level_tag,
                target_capability=topic.target_capability,
                recommended_depth=topic.recommended_depth,
                depth_override=latest_depth.get(stable_id),
                is_skipped=latest_skip.get(stable_id, False),
                classification=classification,
                explanation=explanation,
                has_transferred_evidence=stable_id in evidence_topics,
                is_archived_local=stable_id in archived_topic_ids,
                pending_proposals=tuple(proposals_by_topic.get(stable_id, ())),
                conflicts=tuple(conflicts_by_topic.get(stable_id, ())),
            )
        )

    projection_inputs = {
        "graph_version_id": graph_version_id,
        "topics": [asdict(topic_by_id[key]) for key in sorted(topic_by_id)],
        "canonical_edges": sorted(canonical_edges),
        "overlay_entries": [asdict(item) for item in entries],
        "learning_states": [
            asdict(item) for item in sorted(state_items, key=lambda x: x.id)
        ],
        "corrections": [
            asdict(item) for item in sorted(correction_items, key=lambda x: x.id)
        ],
        "transferred_evidence_topic_ids": sorted(evidence_topics),
        "pending_proposals": sorted(proposal_items, key=hash_payload),
        "conflicts": sorted(conflict_items, key=hash_payload),
    }
    return RoadmapProjection(
        graph_version_id=graph_version_id,
        projection_version=hash_payload(projection_inputs),
        topics=tuple(projected),
    )


def validate_order_constraint(
    topics: Iterable[RoadmapTopic],
    canonical_relations: Iterable[RoadmapRelation],
    existing_order_relations: Iterable[RoadmapRelation],
    candidate: RoadmapRelation,
) -> None:
    topic_ids = {topic.stable_id for topic in topics}
    if (
        candidate.before_topic_id not in topic_ids
        or candidate.after_topic_id not in topic_ids
    ):
        raise DomainValidationError(
            "Both order-constraint topics must exist in the pinned graph."
        )
    if candidate.before_topic_id == candidate.after_topic_id:
        raise InvalidOrderConstraintError("A topic cannot be ordered before itself.")
    canonical = {
        (edge.before_topic_id, edge.after_topic_id) for edge in canonical_relations
    }
    if _reachable(candidate.after_topic_id, candidate.before_topic_id, canonical):
        raise InvalidOrderConstraintError(
            f"'{candidate.after_topic_id}' is an unmodified prerequisite of "
            f"'{candidate.before_topic_id}'; that prerequisite cannot be reversed."
        )
    edges = (
        canonical
        | {
            (edge.before_topic_id, edge.after_topic_id)
            for edge in existing_order_relations
        }
        | {(candidate.before_topic_id, candidate.after_topic_id)}
    )
    try:
        _lexical_topological_sort(topic_ids, edges)
    except InvalidOrderConstraintError as exc:
        raise InvalidOrderConstraintError(
            "This order constraint would create a cycle in the roadmap."
        ) from exc


def _lexical_topological_sort(
    topic_ids: Iterable[str], edges: set[tuple[str, str]]
) -> list[str]:
    topic_id_set = frozenset(topic_ids)
    outgoing = {topic_id: set() for topic_id in topic_id_set}
    indegree = {topic_id: 0 for topic_id in topic_id_set}
    for before, after in edges:
        if (
            before not in topic_id_set
            or after not in topic_id_set
            or after in outgoing[before]
        ):
            continue
        outgoing[before].add(after)
        indegree[after] += 1
    available = [topic_id for topic_id, count in indegree.items() if count == 0]
    heapq.heapify(available)
    ordered: list[str] = []
    while available:
        current = heapq.heappop(available)
        ordered.append(current)
        for dependent in sorted(outgoing[current]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                heapq.heappush(available, dependent)
    if len(ordered) != len(topic_id_set):
        raise InvalidOrderConstraintError(
            "The roadmap ordering constraints contain a cycle."
        )
    return ordered


def _reachable(start: str, target: str, edges: set[tuple[str, str]]) -> bool:
    outgoing: dict[str, set[str]] = {}
    for before, after in edges:
        outgoing.setdefault(before, set()).add(after)
    pending = [start]
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current not in visited:
            visited.add(current)
            pending.extend(outgoing.get(current, ()))
    return False


def _annotations_by_topic(
    items: Iterable[Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {}
    for item in items:
        topic_id = item.get("topic_stable_id")
        if isinstance(topic_id, str):
            result.setdefault(topic_id, []).append(dict(item))
    return result
