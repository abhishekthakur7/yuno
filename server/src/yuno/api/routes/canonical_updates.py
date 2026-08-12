from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends

from yuno.api.contracts import (
    CanonicalMergeItemResponse,
    CanonicalMergeProposalResponse,
    CanonicalUpdateAcceptRequest,
    CanonicalUpdateAcceptResponse,
    CanonicalUpdateDecisionRequest,
    CanonicalUpdateDecisionResponse,
    CanonicalUpdateResponse,
    CanonicalUpdateVersionResponse,
)
from yuno.api.dependencies import (
    get_job_dispatcher,
    get_owner_id,
    get_unit_of_work,
    idempotency_key,
)
from yuno.modules.audit.domain import AuditEvent
from yuno.modules.canonical.domain import (
    CanonicalMergeFollowup,
    CanonicalMergeProposal,
    MergeProposalStatus,
    MergeResolution,
)
from yuno.modules.canonical.service import build_merge_items, diff_hash
from yuno.modules.roadmap.domain import (
    OverlayEntry,
    OverlayEntryType,
    RoadmapIdempotencyRecord,
)
from yuno.shared.application.jobs import JobDispatcher, JobRequest
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import (
    ConflictError,
    IdempotencyConflictError,
    NotFoundError,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id

router = APIRouter(tags=["canonical"])


class ProposalStale(ConflictError):
    code = "proposal_stale"


@router.get("/goals/{goal_id}/canonical-update", response_model=CanonicalUpdateResponse)
def get_update(
    goal_id: str,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[object, Depends(get_unit_of_work)],
):
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    goal = uow.profiles_goals.get_goal(owner_id, goal_id)
    if goal is None:
        raise NotFoundError("Goal workspace not found.")
    base = uow.canonical.get_published_version(goal.graph_version_id)
    versions = uow.canonical.list_published_versions()
    if base is None:
        raise NotFoundError("The goal's approved canonical graph is unavailable.")
    if not versions or versions[0].id == base.id:
        return CanonicalUpdateResponse(
            state="empty",
            goal_id=goal_id,
            base_version=_version(base),
            target_version=None,
            proposal=None,
        )
    target = versions[0]
    proposal = uow.canonical_merges.get_current_merge_proposal(
        owner_id, goal_id, base.id, target.id
    )
    if proposal is None:
        proposal_id = new_id()
        base_topics, target_topics = (
            uow.canonical.get_published_topics(base.id),
            uow.canonical.get_published_topics(target.id),
        )
        entries = uow.roadmap.list_overlay_entries(owner_id, goal_id)
        local = {
            e.topic_stable_id for e in uow.evidence.list_evidence(owner_id, goal_id)
        } | {e.topic_stable_id for e in entries}
        items = build_merge_items(
            proposal_id,
            base_topics=base_topics,
            target_topics=target_topics,
            base_relations=uow.canonical.get_published_relations(base.id),
            target_relations=uow.canonical.get_published_relations(target.id),
            base_content=_content(uow, base.id, base_topics),
            target_content=_content(uow, target.id, target_topics),
            overlay_topic_ids={e.topic_stable_id for e in entries if e.topic_stable_id},
            local_state_topic_ids={x for x in local if x},
        )
        proposal = CanonicalMergeProposal(
            proposal_id,
            owner_id,
            goal_id,
            base.id,
            target.id,
            goal.row_version,
            diff_hash(items),
            _local_state_hash(entries, uow.evidence.list_evidence(owner_id, goal_id)),
            MergeProposalStatus.AWAITING,
            now_text(SystemClock()),
        )
        uow.canonical_merges.add_merge_proposal(proposal, items)
        uow.commit()
    items = uow.canonical_merges.list_merge_items(owner_id, proposal.id)
    state = (
        proposal.status.value
        if proposal.status is not MergeProposalStatus.AWAITING
        else "conflict-needs-resolution"
        if any(i.conflict_type for i in items)
        else "proposed"
    )
    return CanonicalUpdateResponse(
        state=state,
        goal_id=goal_id,
        base_version=_version(base),
        target_version=_version(target),
        proposal=_proposal(proposal, items),
    )


@router.post(
    "/canonical-update-proposals/{proposal_id}/decision",
    response_model=CanonicalUpdateDecisionResponse,
)
def decide(
    proposal_id: str,
    body: CanonicalUpdateDecisionRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[object, Depends(get_unit_of_work)],
    _key: Annotated[str, Depends(idempotency_key)],
):
    proposal = uow.canonical_merges.get_merge_proposal(owner_id, proposal_id)
    if proposal is None:
        raise NotFoundError("Canonical update proposal not found.")
    request = body.model_dump(mode="json")
    operation = f"canonical-update-decision:{proposal_id}"
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    if replay := _replay(
        uow, owner_id, operation, _key, request, CanonicalUpdateDecisionResponse
    ):
        return replay
    now = now_text(SystemClock())
    persisted_status = {"postpone": "postponed", "dismiss": "dismissed"}[body.decision]
    if not uow.canonical_merges.close_merge_proposal(
        owner_id, proposal_id, "awaiting", persisted_status, now
    ):
        raise ConflictError("The proposal is no longer awaiting a decision.")
    uow.audit.append(
        AuditEvent(
            new_id(),
            owner_id,
            proposal.goal_id,
            "learner",
            "canonical_merge_proposal",
            proposal_id,
            body.decision,
            hash_payload(proposal),
            hash_payload({"status": body.decision}),
            body.reason,
            None,
            None,
            now,
        )
    )
    response = CanonicalUpdateDecisionResponse(
        proposal_id=proposal_id, status=persisted_status, decided_at=now
    )
    _store(uow, owner_id, proposal.goal_id, operation, _key, request, response, now)
    uow.commit()
    return response


@router.post(
    "/canonical-update-proposals/{proposal_id}/accept",
    response_model=CanonicalUpdateAcceptResponse,
)
def accept(
    proposal_id: str,
    body: CanonicalUpdateAcceptRequest,
    owner_id: Annotated[str, Depends(get_owner_id)],
    uow: Annotated[object, Depends(get_unit_of_work)],
    dispatcher: Annotated[JobDispatcher, Depends(get_job_dispatcher)],
    key: Annotated[str, Depends(idempotency_key)],
):
    proposal = uow.canonical_merges.get_merge_proposal(owner_id, proposal_id)
    if proposal is None:
        raise NotFoundError("Canonical update proposal not found.")
    request = body.model_dump(mode="json")
    operation = f"canonical-update-accept:{proposal_id}"
    uow.profiles_goals.lock_idempotency_commands(owner_id)
    if replay := _replay(
        uow, owner_id, operation, key, request, CanonicalUpdateAcceptResponse
    ):
        return replay
    goal = uow.profiles_goals.get_goal(owner_id, proposal.goal_id)
    latest = uow.canonical.list_published_versions()
    if (
        proposal.status is not MergeProposalStatus.AWAITING
        or goal is None
        or goal.graph_version_id != proposal.base_version_id
        or goal.row_version != proposal.goal_row_version
        or not latest
        or latest[0].id != proposal.target_version_id
    ):
        raise ProposalStale(
            "The canonical update proposal is stale; fetch the current base-to-latest diff."
        )
    base_topics = uow.canonical.get_published_topics(proposal.base_version_id)
    target_topics = uow.canonical.get_published_topics(proposal.target_version_id)
    current_entries = uow.roadmap.list_overlay_entries(owner_id, proposal.goal_id)
    local_topics = {
        evidence.topic_stable_id
        for evidence in uow.evidence.list_evidence(owner_id, proposal.goal_id)
    } | {entry.topic_stable_id for entry in current_entries}
    current_items = build_merge_items(
        proposal.id,
        base_topics=base_topics,
        target_topics=target_topics,
        base_relations=uow.canonical.get_published_relations(proposal.base_version_id),
        target_relations=uow.canonical.get_published_relations(
            proposal.target_version_id
        ),
        base_content=_content(uow, proposal.base_version_id, base_topics),
        target_content=_content(uow, proposal.target_version_id, target_topics),
        overlay_topic_ids={
            entry.topic_stable_id for entry in current_entries if entry.topic_stable_id
        },
        local_state_topic_ids={topic_id for topic_id in local_topics if topic_id},
    )
    if diff_hash(current_items) != proposal.diff_hash:
        raise ProposalStale(
            "Learner state changed; fetch the recomputed canonical update."
        )
    if (
        _local_state_hash(
            current_entries, uow.evidence.list_evidence(owner_id, proposal.goal_id)
        )
        != proposal.local_state_hash
    ):
        raise ProposalStale(
            "Learner state changed; fetch the recomputed canonical update."
        )
    persisted = {
        i.id: i
        for i in uow.canonical_merges.list_merge_items(owner_id, proposal_id)
    }
    submitted = {i.item_id: i for i in body.items}
    if len(submitted) != len(body.items) or set(submitted) != set(persisted):
        raise ConflictError("Every merge item must be submitted exactly once.")
    unresolved = [
        i.id
        for i in persisted.values()
        if i.conflict_type and submitted[i.id].resolution is None
    ]
    if unresolved:
        raise ConflictError("Unresolved conflicts: " + ", ".join(unresolved))
    invalid = [
        item_id
        for item_id, item in persisted.items()
        if (
            not submitted[item_id].selected
            and submitted[item_id].resolution != "retain-local"
        )
        or (
            submitted[item_id].selected
            and item.conflict_type == "local-state-on-deleted-topic"
            and submitted[item_id].resolution != "overlay-wins"
        )
        or (
            submitted[item_id].selected
            and item.conflict_type == "overlay-conflict"
            and submitted[item_id].resolution
            not in ("overlay-wins", "accept-canonical")
        )
        or (
            submitted[item_id].selected
            and not item.conflict_type
            and submitted[item_id].resolution not in (None, "accept-canonical")
        )
    ]
    if invalid:
        raise ConflictError(
            "Invalid selection/resolution combinations: " + ", ".join(invalid)
        )
    now = now_text(SystemClock())
    overlay = uow.roadmap.get_or_create_overlay(
        owner_id, proposal.goal_id, proposal.base_version_id
    )
    if (
        uow.roadmap.advance_overlay_base(
            owner_id, proposal.goal_id, overlay.row_version, proposal.target_version_id
        )
        is None
    ):
        raise ProposalStale(
            "The learner overlay changed while accepting this proposal."
        )
    canonical_wins_topics = {
        item.topic_id
        for item_id, item in persisted.items()
        if item.conflict_type == "overlay-conflict"
        and submitted[item_id].selected
        and submitted[item_id].resolution == "accept-canonical"
    }
    superseded_ids = {
        entry.supersedes_entry_id
        for entry in current_entries
        if entry.supersedes_entry_id is not None
    }
    active_entries = [entry for entry in current_entries if entry.id not in superseded_ids]
    for prior in active_entries:
        if prior.topic_stable_id in canonical_wins_topics:
            continue
        uow.roadmap.append_overlay_entry(
            OverlayEntry(
                new_id(),
                owner_id,
                proposal.goal_id,
                overlay.id,
                proposal.target_version_id,
                prior.topic_stable_id,
                prior.entry_type,
                prior.value,
                prior.reason,
                "canonical_merge",
                now,
                prior.id,
                hash_payload(
                    {
                        "carried_from": prior.id,
                        "target": proposal.target_version_id,
                        "value": prior.value,
                    }
                ),
            )
        )
    for item_id, item in persisted.items():
        choice = submitted[item_id]
        resolution = choice.resolution or MergeResolution.ACCEPT_CANONICAL.value
        uow.canonical_merges.update_merge_item(
            owner_id,
            proposal_id,
            item_id,
            selected=choice.selected,
            resolution=resolution,
        )
        if item.conflict_type or not choice.selected:
            entry_type = (
                OverlayEntryType.ARCHIVED_LOCAL_TOPIC
                if item.conflict_type == "local-state-on-deleted-topic"
                else OverlayEntryType.MERGE_RESOLUTION
            )
            before = item.payload.get("before") or {}
            value = {
                "merge_item_id": item.id,
                "selected": choice.selected,
                "resolution": resolution,
                "retained": not choice.selected,
                "entity_type": item.entity_type.value,
                "change_type": item.change_type.value,
                "before": before,
                **(
                    before
                    if entry_type is OverlayEntryType.ARCHIVED_LOCAL_TOPIC
                    else {}
                ),
            }
            uow.roadmap.append_overlay_entry(
                OverlayEntry(
                    new_id(),
                    owner_id,
                    proposal.goal_id,
                    overlay.id,
                    proposal.target_version_id,
                    item.topic_id,
                    entry_type,
                    value,
                    "Canonical merge learner decision",
                    "canonical_merge",
                    now,
                    None,
                    hash_payload(
                        {"proposal": proposal.id, "item": item.id, "value": value}
                    ),
                )
            )
    moved = uow.profiles_goals.update_goal(
        owner_id,
        proposal.goal_id,
        proposal.goal_row_version,
        {"graph_version_id": proposal.target_version_id},
    )
    if moved is None:
        raise ProposalStale("The goal changed while accepting this proposal.")
    if not uow.canonical_merges.close_merge_proposal(
        owner_id, proposal_id, "awaiting", "accepted", now
    ):
        raise ProposalStale("The proposal changed while it was being accepted.")
    imports = uow.imports.list_imports(owner_id, proposal.goal_id)
    for record in imports:
        payload = {"import_id": record.id, "operation": "reprocess_import"}
        uow.canonical_merges.add_merge_followup(
            CanonicalMergeFollowup(
                new_id(),
                owner_id,
                proposal.goal_id,
                proposal_id,
                "reprocess_import",
                payload,
                "pending-dispatch",
                None,
                now,
            )
        )
    for kind, status, payload in (
        (
            "roadmap",
            "completed-derived",
            {"projection": "roadmap", "strategy": "recompute-on-read"},
        ),
        (
            "generated_content",
            "completed-derived",
            {
                "projection": "generated_content",
                "strategy": "exact-version-key-mismatch",
            },
        ),
        (
            "search",
            "pending-dispatch",
            {"projection": "search", "strategy": "rebuild-after-installation"},
        ),
    ):
        uow.canonical_merges.add_merge_followup(
            CanonicalMergeFollowup(
                new_id(),
                owner_id,
                proposal.goal_id,
                proposal_id,
                kind,
                payload,
                status,
                None,
                now,
            )
        )
    uow.audit.append(
        AuditEvent(
            new_id(),
            owner_id,
            proposal.goal_id,
            "learner",
            "canonical_merge_proposal",
            proposal_id,
            "accepted",
            hash_payload({"pin": proposal.base_version_id}),
            hash_payload({"pin": proposal.target_version_id}),
            "Explicit canonical update acceptance",
            None,
            None,
            now,
        )
    )
    response = CanonicalUpdateAcceptResponse(
        proposal_id=proposal_id,
        status="accepted",
        goal_id=proposal.goal_id,
        base_version_id=proposal.base_version_id,
        target_version_id=proposal.target_version_id,
        goal_graph_version_id=proposal.target_version_id,
        accepted_at=now,
        invalidation_state="pending-dispatch",
        reprocess_job=None,
    )
    _store(uow, owner_id, proposal.goal_id, operation, key, request, response, now)
    uow.commit()
    for followup in uow.canonical_merges.list_merge_followups(owner_id, proposal_id):
        if followup.kind != "reprocess_import":
            continue
        try:
            ref = dispatcher.enqueue(
                JobRequest(
                    kind="reprocess_import",
                    owner_id=owner_id,
                    goal_id=proposal.goal_id,
                    payload=followup.payload,
                    dedupe_key=str(followup.payload["import_id"]),
                    idempotency_key=f"canonical-merge:{proposal_id}:{followup.id}",
                    request_ref=f"ImportRecord:{followup.payload['import_id']}",
                )
            )
            uow.canonical_merges.mark_followup_dispatched(
                owner_id, followup.id, ref.job_id
            )
            uow.commit()
        except Exception:  # noqa: BLE001 - merge committed; intent remains pending
            break
    # Return the durable acceptance fact stored before best-effort dispatch.
    # This makes response-loss replay byte-stable; job state is authoritative
    # through the Jobs API and the durable follow-up intent.
    return response


def _content(uow, version_id, topics):
    return tuple(
        r
        for t in topics
        for r in uow.canonical.get_published_content_revisions(version_id, t.stable_id)
    )


def _version(v):
    return CanonicalUpdateVersionResponse(id=v.id, version_label=v.version_label)


def _proposal(p, items):
    return CanonicalMergeProposalResponse(
        id=p.id,
        status=p.status.value,
        diff_hash=p.diff_hash,
        items=[
            CanonicalMergeItemResponse(
                id=i.id,
                entity_type=i.entity_type.value,
                change_type=i.change_type.value,
                topic_id=i.topic_id,
                title=i.title,
                summary=i.summary,
                impact=i.impact,
                conflict_type=i.conflict_type,
                selected=i.selected,
                recommended_resolution=i.recommended_resolution.value,
                chosen_resolution=i.chosen_resolution.value
                if i.chosen_resolution
                else None,
                resolution_explanation=i.resolution_explanation,
            )
            for i in items
        ],
    )


def _replay(uow, owner_id, operation, key, request, response_type):
    prior = uow.roadmap.get_idempotency(owner_id, operation, key)
    if prior is None:
        return None
    if prior.request_hash != hash_payload(request):
        raise IdempotencyConflictError(
            "Idempotency key was reused with a different canonical-update request."
        )
    return response_type.model_validate_json(prior.response_json)


def _store(uow, owner_id, goal_id, operation, key, request, response, now):
    uow.roadmap.add_idempotency(
        RoadmapIdempotencyRecord(
            new_id(),
            owner_id,
            goal_id,
            operation,
            key,
            hash_payload(request),
            json.dumps(response.model_dump(mode="json"), sort_keys=True),
            now,
        )
    )


def _local_state_hash(entries, evidence):
    return hash_payload(
        {
            "overlays": [
                {
                    "id": item.id,
                    "content_hash": item.content_hash,
                    "supersedes": item.supersedes_entry_id,
                }
                for item in entries
            ],
            "evidence": [
                {"id": item.id, "topic_id": item.topic_stable_id} for item in evidence
            ],
        }
    )
