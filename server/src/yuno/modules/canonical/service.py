from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import asdict

from yuno.modules.canonical.domain import (
    ContentRevision,
    MergeChangeType,
    MergeEntityType,
    MergeItem,
    MergeResolution,
    Topic,
    TopicRelation,
)
from yuno.shared.domain.hashing import hash_payload
from yuno.shared.domain.ids import new_id


def build_merge_items(
    proposal_id: str,
    *,
    base_topics: Sequence[Topic],
    target_topics: Sequence[Topic],
    base_relations: Sequence[TopicRelation],
    target_relations: Sequence[TopicRelation],
    base_content: Iterable[ContentRevision],
    target_content: Iterable[ContentRevision],
    overlay_topic_ids: set[str],
    local_state_topic_ids: set[str],
) -> tuple[MergeItem, ...]:
    items: list[MergeItem] = []
    base = {topic.stable_id: topic for topic in base_topics}
    target = {topic.stable_id: topic for topic in target_topics}
    for topic_id in sorted(set(base) | set(target)):
        before, after = base.get(topic_id), target.get(topic_id)
        if before is None:
            change, title = MergeChangeType.ADDED, after.title
        elif after is None:
            change, title = MergeChangeType.DELETED, before.title
        elif _topic_payload(before) != _topic_payload(after):
            change, title = MergeChangeType.MODIFIED, after.title
        else:
            continue
        deleted_local = (
            change is MergeChangeType.DELETED and topic_id in local_state_topic_ids
        )
        conflict = deleted_local or topic_id in overlay_topic_ids
        conflict_type = (
            "local-state-on-deleted-topic"
            if deleted_local
            else "overlay-conflict"
            if conflict
            else None
        )
        recommended = (
            MergeResolution.OVERLAY_WINS
            if conflict
            else MergeResolution.ACCEPT_CANONICAL
        )
        explanation = (
            "Your local choice stays in control; accepting the update records it against the new curriculum version."
            if conflict
            else "Use the published curriculum change."
        )
        items.append(
            MergeItem(
                new_id(),
                proposal_id,
                MergeEntityType.TOPIC,
                change,
                topic_id,
                title,
                f"Topic {change.value}: {title}",
                "This deleted topic will remain as an archived local topic."
                if deleted_local
                else "This changes the goal roadmap and generated-content cache key.",
                conflict_type,
                True,
                recommended,
                None,
                explanation,
                {"before": _topic_payload(before), "after": _topic_payload(after)},
            )
        )

    def relation_key(r: TopicRelation):
        return (r.from_stable_id, r.to_stable_id, r.relation_type.value)

    br, tr = (
        {relation_key(r): r for r in base_relations},
        {relation_key(r): r for r in target_relations},
    )
    for key in sorted(set(br) | set(tr)):
        before, after = br.get(key), tr.get(key)
        change = (
            MergeChangeType.ADDED
            if before is None
            else MergeChangeType.DELETED
            if after is None
            else MergeChangeType.MODIFIED
            if before.rationale != after.rationale
            else None
        )
        if change is None:
            continue
        items.append(
            MergeItem(
                new_id(),
                proposal_id,
                MergeEntityType.RELATION,
                change,
                key[1],
                f"{key[0]} → {key[1]}",
                f"Relationship {change.value}",
                "This may change roadmap ordering.",
                None,
                True,
                MergeResolution.ACCEPT_CANONICAL,
                None,
                "Use the published relationship change.",
                {
                    "key": key,
                    "before": {
                        "from_topic_id": before.from_stable_id,
                        "to_topic_id": before.to_stable_id,
                        "relation_type": before.relation_type.value,
                        "rationale": before.rationale,
                    }
                    if before
                    else None,
                    "after": {
                        "from_topic_id": after.from_stable_id,
                        "to_topic_id": after.to_stable_id,
                        "relation_type": after.relation_type.value,
                        "rationale": after.rationale,
                    }
                    if after
                    else None,
                },
            )
        )

    def content_key(c: ContentRevision):
        return (c.topic_stable_id, c.layer, c.kind)

    bc, tc = (
        {content_key(c): c for c in base_content},
        {content_key(c): c for c in target_content},
    )
    for key in sorted(set(bc) | set(tc)):
        before, after = bc.get(key), tc.get(key)
        change = (
            MergeChangeType.ADDED
            if before is None
            else MergeChangeType.DELETED
            if after is None
            else MergeChangeType.MODIFIED
            if before.markdown_hash != after.markdown_hash
            else None
        )
        if change is None:
            continue
        items.append(
            MergeItem(
                new_id(),
                proposal_id,
                MergeEntityType.CONTENT,
                change,
                key[0],
                f"{key[0]} · {key[1]}",
                f"Content {change.value}",
                "Existing generated content will surface as stale until regenerated.",
                None,
                True,
                MergeResolution.ACCEPT_CANONICAL,
                None,
                "Use the published content change.",
                {
                    "topic_id": key[0],
                    "layer": key[1],
                    "kind": key[2],
                    "before": {
                        "markdown_ref": before.markdown_ref,
                        "markdown_hash": before.markdown_hash,
                    }
                    if before
                    else None,
                    "after": {
                        "markdown_ref": after.markdown_ref,
                        "markdown_hash": after.markdown_hash,
                    }
                    if after
                    else None,
                },
            )
        )
    return tuple(items)


def diff_hash(items: Sequence[MergeItem]) -> str:
    return hash_payload(
        [
            {
                k: v
                for k, v in asdict(item).items()
                if k not in {"id", "proposal_id", "selected", "chosen_resolution"}
            }
            for item in items
        ]
    )


def _topic_payload(topic: Topic | None):
    if topic is None:
        return None
    return {
        "stable_id": topic.stable_id,
        "title": topic.title,
        "subject": topic.subject,
        "scope_tags": list(topic.scope_tags),
        "level_tag": topic.level_tag,
        "target_capability": topic.target_capability,
        "recommended_layer": topic.recommended_layer,
        "checkpoint_start": topic.checkpoint_start,
        "checkpoint_end": topic.checkpoint_end,
    }
