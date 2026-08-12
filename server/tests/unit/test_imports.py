"""D10 parser, dedupe, graph-bound mapping, and hash projection tests."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from yuno.modules.imports.domain import (
    ImportStatus,
    ImportType,
    MappingState,
    parse_source,
)
from yuno.modules.imports.service import (
    correct_statement,
    create_import,
    dismiss_statement,
    map_statement,
    mark_import_parsing,
    parse_import,
    reprocess_import,
    verify_statement,
)
from yuno.shared.domain.errors import DomainValidationError


class FakeImports:
    def __init__(self) -> None:
        self.records = {}
        self.statements = {}
        self.mappings = []
        self.topic_hashes = {}
        self.decisions = []

    def add_import(self, record):
        self.records[record.id] = record
        return record

    def get_import(self, owner_id, import_id):
        row = self.records.get(import_id)
        return row if row and row.owner_id == owner_id else None

    def update_import(self, owner_id, import_id, expected_version, changes):
        row = self.get_import(owner_id, import_id)
        if row is None or row.row_version != expected_version:
            return None
        row = replace(row, **changes, row_version=expected_version + 1)
        self.records[import_id] = row
        return row

    def add_statement(self, statement):
        self.statements[statement.id] = statement
        return statement

    def get_statement(self, owner_id, statement_id):
        row = self.statements.get(statement_id)
        return row if row and row.owner_id == owner_id else None

    def get_statement_for_occurrence(
        self, owner_id, import_id, sequence, parser_version
    ):
        return next(
            (
                row
                for row in self.statements.values()
                if row.owner_id == owner_id
                and row.import_id == import_id
                and row.sequence == sequence
                and row.parser_version == parser_version
            ),
            None,
        )

    def get_unmapped_canonical_by_hash(self, owner_id, parser_version, normalized_hash):
        return next(
            (
                row
                for row in self.statements.values()
                if row.owner_id == owner_id
                and row.parser_version == parser_version
                and row.normalized_hash == normalized_hash
                and row.mapping_state is MappingState.UNMAPPED
            ),
            None,
        )

    def list_statements(self, owner_id, import_id):
        return tuple(
            sorted(
                (
                    row
                    for row in self.statements.values()
                    if row.owner_id == owner_id and row.import_id == import_id
                ),
                key=lambda row: row.sequence,
            )
        )

    def update_statement(self, owner_id, statement_id, expected_version, changes):
        row = self.get_statement(owner_id, statement_id)
        if row is None or row.row_version != expected_version:
            return None
        row = replace(row, **changes, row_version=expected_version + 1)
        self.statements[statement_id] = row
        return row

    def append_statement_decision(self, decision):
        self.decisions.append(decision)
        return decision

    def get_active_mapping(self, owner_id, statement_id):
        return next(
            (
                row
                for row in self.mappings
                if row.owner_id == owner_id
                and row.statement_id == statement_id
                and row.revoked_at is None
            ),
            None,
        )

    def append_mapping(self, mapping):
        self.mappings.append(mapping)
        return mapping

    def revoke_mapping(self, owner_id, mapping_id, revoked_at):
        for index, mapping in enumerate(self.mappings):
            if (
                mapping.owner_id == owner_id
                and mapping.id == mapping_id
                and mapping.revoked_at is None
            ):
                revoked = replace(mapping, revoked_at=revoked_at)
                self.mappings[index] = revoked
                return revoked
        return None

    def list_approved_mappings(
        self, owner_id, goal_id, graph_version_id, topic_stable_id
    ):
        return tuple(
            (mapping, self.statements[mapping.statement_id])
            for mapping in self.mappings
            if mapping.owner_id == owner_id
            and mapping.goal_id == goal_id
            and mapping.graph_version_id == graph_version_id
            and mapping.topic_stable_id == topic_stable_id
            and mapping.revoked_at is None
        )

    def get_topic_hash(self, owner_id, goal_id, graph_version_id, topic_stable_id):
        return self.topic_hashes.get(
            (owner_id, goal_id, graph_version_id, topic_stable_id)
        )

    def upsert_topic_hash(self, topic_hash):
        self.topic_hashes[
            (
                topic_hash.owner_id,
                topic_hash.goal_id,
                topic_hash.graph_version_id,
                topic_hash.topic_stable_id,
            )
        ] = topic_hash
        return topic_hash


class FakeAudit:
    def __init__(self):
        self.events = []

    def append(self, event):
        self.events.append(event)
        return event


class FakeUow:
    def __init__(self):
        self.imports = FakeImports()
        self.audit = FakeAudit()
        self.profiles_goals = SimpleNamespace(
            get_goal=lambda owner, goal: (
                SimpleNamespace(graph_version_id="graph-v1", status="active")
                if owner == "owner" and goal == "goal"
                else None
            )
        )
        self.canonical = SimpleNamespace(
            get_published_topics=lambda version: (
                (SimpleNamespace(stable_id="topic-in"),)
                if version == "graph-v1"
                else ()
            )
        )


def _parsed(uow: FakeUow, text: str):
    record = create_import(
        uow, "owner", goal_id="goal", import_type=ImportType.MARKDOWN, source_text=text
    )
    mark_import_parsing(uow, "owner", record.id)
    return record, parse_import(uow, "owner", record.id)


def test_parser_is_deterministic_and_preserves_order():
    source = b"# Heading\n- SQS may redeliver.\n\n2. ACK after commit."
    first = parse_source(source)
    assert first == parse_source(source)
    assert [row.sequence for row in first] == [1, 2, 3]
    assert [row.normalized_text for row in first] == [
        "heading",
        "sqs may redeliver.",
        "ack after commit.",
    ]


def test_duplicate_occurrences_remain_inspectable_but_only_one_is_unmapped():
    uow = FakeUow()
    _record, result = _parsed(uow, "- Same claim\nSame   CLAIM")
    assert len(result.statements) == 2
    assert result.statements[0].mapping_state is MappingState.UNMAPPED
    assert result.statements[1].mapping_state is MappingState.DUPLICATE
    assert result.statements[1].duplicate_of_statement_id == result.statements[0].id
    assert result.duplicate_candidates == (result.statements[1].id,)


def test_mapping_rejects_out_of_graph_and_approved_mapping_changes_hash():
    uow = FakeUow()
    _record, result = _parsed(uow, "A personal note")
    statement = result.statements[0]
    with pytest.raises(DomainValidationError):
        map_statement(
            uow,
            "owner",
            statement.id,
            goal_id="goal",
            topic_stable_id="topic-out",
            expected_version=statement.row_version,
        )
    assert uow.imports.mappings == []
    assert uow.imports.topic_hashes == {}

    mapping, projection = map_statement(
        uow,
        "owner",
        statement.id,
        goal_id="goal",
        topic_stable_id="topic-in",
        expected_version=statement.row_version,
    )
    assert mapping.topic_stable_id == "topic-in"
    assert projection.imports_hash
    assert (
        uow.imports.records[result.statements[0].import_id].status
        is ImportStatus.APPLIED
    )


def test_correction_dedupes_unmapped_collision_without_persistence_error():
    uow = FakeUow()
    _record, result = _parsed(uow, "First claim\nSecond claim")
    corrected = correct_statement(
        uow,
        "owner",
        result.statements[1].id,
        corrected_text="  FIRST   CLAIM ",
        expected_version=1,
    )
    assert corrected.mapping_state is MappingState.DUPLICATE
    assert corrected.duplicate_of_statement_id == result.statements[0].id
    assert (
        uow.imports.records[corrected.import_id].status is ImportStatus.LEARNER_REVIEW
    )


def test_mapped_correction_refreshes_topic_hash_and_reprocess_keeps_review():
    uow = FakeUow()
    record, result = _parsed(uow, "Original personal note")
    statement = result.statements[0]
    _mapping, before = map_statement(
        uow,
        "owner",
        statement.id,
        goal_id="goal",
        topic_stable_id="topic-in",
        expected_version=1,
    )
    mapped = uow.imports.get_statement("owner", statement.id)
    corrected = correct_statement(
        uow,
        "owner",
        statement.id,
        corrected_text="Corrected personal note",
        expected_version=mapped.row_version,
    )
    after = uow.imports.get_topic_hash("owner", "goal", "graph-v1", "topic-in")
    assert after.imports_hash != before.imports_hash
    verified = verify_statement(
        uow,
        "owner",
        statement.id,
        expected_version=corrected.row_version,
    )

    reprocessed = reprocess_import(uow, "owner", record.id)
    preserved = next(row for row in reprocessed.statements if row.id == statement.id)
    assert preserved.corrected_text == "Corrected personal note"
    assert preserved.trust_state == verified.trust_state


def test_duplicate_corrected_unique_becomes_unmapped_and_mapped_dismiss_revokes_hash():
    uow = FakeUow()
    _record, result = _parsed(uow, "Same claim\nSame claim")
    duplicate = correct_statement(
        uow,
        "owner",
        result.statements[1].id,
        corrected_text="Now unique",
        expected_version=1,
    )
    assert duplicate.mapping_state is MappingState.UNMAPPED
    assert duplicate.duplicate_of_statement_id is None

    original = result.statements[0]
    _mapping, before = map_statement(
        uow,
        "owner",
        original.id,
        goal_id="goal",
        topic_stable_id="topic-in",
        expected_version=1,
    )
    mapped = uow.imports.get_statement("owner", original.id)
    dismissed = dismiss_statement(
        uow,
        "owner",
        original.id,
        expected_version=mapped.row_version,
    )
    after = uow.imports.get_topic_hash("owner", "goal", "graph-v1", "topic-in")
    assert dismissed.mapping_state is MappingState.UNMAPPED
    assert uow.imports.get_active_mapping("owner", original.id) is None
    assert after.imports_hash != before.imports_hash
