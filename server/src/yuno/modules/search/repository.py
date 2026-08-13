from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable

from sqlalchemy import text

from yuno.modules.search.domain import (
    SearchDocument,
    SearchIndexState,
    SearchIndexStatus,
    SearchResult,
)
from yuno.shared.domain.clock import SystemClock, utc_text
from yuno.shared.infrastructure.repository import SqlAlchemyRepository

PROJECTION_NAME = "default"
PROJECTION_VERSION = "search-v1"


class SearchRepository(SqlAlchemyRepository):
    """The only search read boundary; both paths enforce the same ACL predicate."""

    def source_watermark(self, owner_id: str) -> str:
        rows = self._session.execute(
            text("""
            SELECT source, entity_id, changed_at FROM (
              SELECT 'goal' source, id entity_id, updated_at changed_at FROM goal_workspaces WHERE owner_id = :owner_id
              UNION ALL SELECT 'generated', id, updated_at FROM generated_artifacts WHERE owner_id = :owner_id AND state = 'ready'
              UNION ALL SELECT 'notebook', id, updated_at FROM notebook_entries WHERE owner_id = :owner_id AND tombstoned_at IS NULL
              UNION ALL SELECT 'evidence', e.id, e.created_at FROM evidence e
                WHERE e.owner_id = :owner_id AND NOT EXISTS (SELECT 1 FROM evidence_tombstones t WHERE t.evidence_id=e.id AND t.owner_id=e.owner_id)
            ) ORDER BY source, entity_id
        """),
            {"owner_id": owner_id},
        ).all()
        payload = json.dumps([tuple(row) for row in rows], separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def state(self, owner_id: str) -> SearchIndexState:
        current = self.source_watermark(owner_id)
        row = (
            self._session.execute(
                text("""
            SELECT status, source_watermark, active_generation, rebuild_job_id,
                   failure_reference, updated_at
            FROM search_index_state
            WHERE owner_id=:owner_id AND projection_name=:projection_name
        """),
                {"owner_id": owner_id, "projection_name": PROJECTION_NAME},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return SearchIndexState(
                SearchIndexStatus.UNAVAILABLE, current, None, None, None, None
            )
        status = SearchIndexStatus(row["status"])
        if status is SearchIndexStatus.READY and row["source_watermark"] != current:
            status = SearchIndexStatus.STALE
        return SearchIndexState(
            status,
            row["source_watermark"],
            row["active_generation"],
            row["rebuild_job_id"],
            row["failure_reference"],
            row["updated_at"],
        )

    def search(
        self, owner_id: str, goal_id: str, query: str, types: tuple[str, ...]
    ) -> tuple[SearchResult, ...]:
        state = self.state(owner_id)
        use_index = state.active_generation is not None and state.status in (
            SearchIndexStatus.READY,
            SearchIndexStatus.REBUILDING,
            SearchIndexStatus.FAILED,
        )
        params: dict[str, object] = {
            "owner_id": owner_id,
            "goal_id": goal_id,
            "query": query,
            "generation": state.active_generation,
        }
        type_sql = ""
        if types:
            placeholders = []
            for index, entity_type in enumerate(types):
                key = f"type_{index}"
                params[key] = entity_type
                placeholders.append(f":{key}")
            type_sql = f" AND d.entity_type IN ({','.join(placeholders)})"
        if use_index:
            fts_query = _fts_query(query)
            if not fts_query:
                return ()
            params["query"] = fts_query
            # A raw FTS row is never returned: rowid is joined to the ACL source.
            statement = text(f"""
                SELECT d.entity_type, d.entity_id, d.goal_id, d.topic_stable_id,
                       b.title, b.body, b.tags
                FROM search_fts
                JOIN search_document_bodies b ON b.rowid = search_fts.rowid
                JOIN search_documents d ON d.id = b.document_id
                WHERE search_fts MATCH :query AND d.owner_id=:owner_id
                  AND d.goal_id=:goal_id AND d.generation=:generation {type_sql}
                ORDER BY bm25(search_fts), d.entity_type, d.entity_id
            """)
        else:
            statement = text(f"""
                SELECT d.entity_type, d.entity_id, d.goal_id, d.topic_stable_id,
                       b.title, b.body, b.tags
                FROM search_documents d
                JOIN search_document_bodies b ON b.document_id=d.id
                WHERE d.owner_id=:owner_id AND d.goal_id=:goal_id
                  AND d.generation=(
                    SELECT generation FROM search_documents
                    WHERE owner_id=:owner_id AND goal_id=:goal_id
                    ORDER BY updated_at DESC, generation DESC LIMIT 1
                  )
                  AND (lower(b.title) LIKE '%' || lower(:query) || '%'
                    OR lower(b.body) LIKE '%' || lower(:query) || '%'
                    OR lower(b.tags) LIKE '%' || lower(:query) || '%') {type_sql}
                ORDER BY d.entity_type, b.title COLLATE NOCASE, d.entity_id
            """)
        return tuple(
            SearchResult(**dict(row), degraded=not use_index)
            for row in self._session.execute(statement, params).mappings()
        )

    def mark_rebuilding(self, owner_id: str, job_id: str) -> None:
        now = utc_text(SystemClock().now())
        self._session.execute(
            text("""
            INSERT INTO search_index_state
              (id,owner_id,projection_name,active_generation,projection_version,status,source_watermark,rebuild_job_id,failure_reference,created_at,updated_at)
            SELECT :id,:owner_id,:projection_name,NULL,:projection_version,'rebuilding','',:job_id,NULL,:now,:now
            WHERE EXISTS (SELECT 1 FROM jobs WHERE id=:job_id AND owner_id=:owner_id AND state IN ('queued','running'))
            ON CONFLICT(owner_id,projection_name) DO UPDATE SET
              status='rebuilding', rebuild_job_id=excluded.rebuild_job_id,
              failure_reference=NULL, updated_at=excluded.updated_at
            WHERE EXISTS (SELECT 1 FROM jobs WHERE id=:job_id AND owner_id=:owner_id AND state IN ('queued','running'))
        """),
            {
                "id": _digest(owner_id, PROJECTION_NAME),
                "owner_id": owner_id,
                "projection_name": PROJECTION_NAME,
                "projection_version": PROJECTION_VERSION,
                "job_id": job_id,
                "now": now,
            },
        )

    def mark_failed(self, owner_id: str, job_id: str, diagnostic: str) -> None:
        now = utc_text(SystemClock().now())
        self._session.execute(
            text("""
                INSERT INTO search_index_state
                  (id,owner_id,projection_name,active_generation,projection_version,status,source_watermark,rebuild_job_id,failure_reference,created_at,updated_at)
                VALUES (:id,:owner_id,:projection_name,NULL,:projection_version,'failed','',:job_id,:diagnostic,:now,:now)
                ON CONFLICT(owner_id,projection_name) DO UPDATE SET
                  status='failed', rebuild_job_id=excluded.rebuild_job_id,
                  failure_reference=excluded.failure_reference,
                  updated_at=excluded.updated_at
            """),
            {
                "id": _digest(owner_id, PROJECTION_NAME),
                "owner_id": owner_id,
                "projection_name": PROJECTION_NAME,
                "projection_version": PROJECTION_VERSION,
                "job_id": job_id,
                "diagnostic": diagnostic,
                "now": now,
            },
        )

    def rebuild(self, owner_id: str, job_id: str) -> str:
        watermark = self.source_watermark(owner_id)
        generation = watermark
        now = utc_text(SystemClock().now())
        for document in self._source_documents(owner_id, generation, now):
            self._upsert(document, owner_id, generation)
        # Rebuilding FTS from its external-content table is deterministic and
        # makes replaying the same projection generation duplicate-free.
        self._session.execute(
            text("INSERT INTO search_fts(search_fts) VALUES('rebuild')")
        )
        self._session.execute(
            text("""
            INSERT INTO search_index_state
              (id,owner_id,projection_name,active_generation,projection_version,status,source_watermark,rebuild_job_id,failure_reference,created_at,updated_at)
            VALUES (:id,:owner_id,:projection_name,:generation,:projection_version,'ready',:watermark,:job_id,NULL,:now,:now)
            ON CONFLICT(owner_id,projection_name) DO UPDATE SET
              active_generation=excluded.active_generation,
              projection_version=excluded.projection_version, status='ready',
              source_watermark=excluded.source_watermark,
              rebuild_job_id=excluded.rebuild_job_id,
              failure_reference=NULL, updated_at=excluded.updated_at
        """),
            {
                "generation": generation,
                "id": _digest(owner_id, PROJECTION_NAME),
                "projection_version": PROJECTION_VERSION,
                "watermark": watermark,
                "job_id": job_id,
                "now": now,
                "owner_id": owner_id,
                "projection_name": PROJECTION_NAME,
            },
        )
        return generation

    def _upsert(self, document: SearchDocument, owner_id: str, generation: str) -> None:
        self._session.execute(
            text("""
            INSERT INTO search_documents
              (id,owner_id,goal_id,generation,entity_type,entity_id,topic_stable_id,version,body_hash,projection_version,updated_at)
            VALUES (:id,:owner_id,:goal_id,:generation,:entity_type,:entity_id,:topic_stable_id,NULL,:body_hash,:projection_version,:updated_at)
            ON CONFLICT(owner_id,goal_id,generation,entity_type,entity_id) DO UPDATE SET
              topic_stable_id=excluded.topic_stable_id,body_hash=excluded.body_hash,
              projection_version=excluded.projection_version,updated_at=excluded.updated_at
            RETURNING id
        """),
            {
                **document.__dict__,
                "owner_id": owner_id,
                "generation": generation,
                "body_hash": _body_hash(document.title, document.body, document.tags),
            },
        ).scalar_one()
        self._session.execute(
            text("""
            INSERT INTO search_document_bodies
              (document_id,owner_id,goal_id,title,body,tags)
            VALUES (:id,:owner_id,:goal_id,:title,:body,:tags)
            ON CONFLICT(document_id) DO UPDATE SET
              title=excluded.title,body=excluded.body,tags=excluded.tags
            """),
            {**document.__dict__, "owner_id": owner_id},
        )

    def _source_documents(
        self, owner_id: str, generation: str, now: str
    ) -> Iterable[SearchDocument]:
        rows = self._session.execute(
            text("""
          SELECT g.id goal_id, 'canonical-topic' entity_type, t.stable_id entity_id,
            t.stable_id topic_stable_id, t.title title, t.subject body, t.scope_tags || ' ' || t.level_tag tags
          FROM goal_workspaces g JOIN editorial_approvals a ON a.graph_version_id=g.graph_version_id
            JOIN topics t ON t.graph_version_id=g.graph_version_id
          WHERE g.owner_id=:owner_id AND g.status!='tombstoned'
          UNION ALL
          SELECT g.id, 'canonical-content', c.id, c.topic_stable_id, t.title || ' · ' || c.layer,
            CASE WHEN c.markdown_ref LIKE 'inline:%' THEN substr(c.markdown_ref,8) ELSE c.markdown_ref END,
            c.layer || ' ' || c.kind
          FROM goal_workspaces g JOIN editorial_approvals a ON a.graph_version_id=g.graph_version_id
            JOIN content_revisions c ON c.graph_version_id=g.graph_version_id
            JOIN topics t ON t.graph_version_id=c.graph_version_id AND t.stable_id=c.topic_stable_id
          WHERE g.owner_id=:owner_id AND g.status!='tombstoned' AND c.status='published'
          UNION ALL
          SELECT a.goal_id, 'generated-artifact', a.id, a.topic_stable_id, a.topic_stable_id || ' · ' || a.layer,
            CASE WHEN b.body_ref LIKE 'inline:%' THEN substr(b.body_ref,8) ELSE b.body_ref END, a.layer
          FROM generated_artifacts a JOIN generated_artifact_bodies b ON b.artifact_id=a.id AND b.owner_id=a.owner_id WHERE a.owner_id=:owner_id AND a.state='ready'
          UNION ALL
          SELECT n.goal_id, 'notebook-entry', n.id, n.topic_stable_id, 'Notebook entry', b.markdown, n.entry_kind
          FROM notebook_entries n JOIN notebook_entry_bodies b ON b.entry_id=n.id
          WHERE n.owner_id=:owner_id AND n.tombstoned_at IS NULL
          UNION ALL
          SELECT e.goal_id, 'evidence', e.id, e.topic_stable_id, b.summary, b.summary,
            e.evidence_type || ' ' || e.capability || ' ' || e.origin
          FROM evidence e JOIN evidence_summary_bodies b ON b.evidence_id=e.id
          WHERE e.owner_id=:owner_id
            AND NOT EXISTS (SELECT 1 FROM evidence_tombstones x WHERE x.evidence_id=e.id AND x.owner_id=e.owner_id)
          ORDER BY goal_id, entity_type, entity_id
        """),
            {"owner_id": owner_id},
        ).mappings()
        for row in rows:
            identity = f"{owner_id}:{row['goal_id']}:{generation}:{row['entity_type']}:{row['entity_id']}"
            yield SearchDocument(
                _digest(identity),
                projection_version=PROJECTION_VERSION,
                updated_at=now,
                **dict(row),
            )


def _digest(*values: str) -> str:
    return hashlib.sha256(":".join(values).encode()).hexdigest()


def _body_hash(title: str, body: str, tags: str) -> str:
    canonical = json.dumps(
        {"body": body, "tags": tags, "title": title},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _fts_query(raw: str) -> str:
    """Treat user input as literal tokens, never as FTS query syntax."""
    tokens = re.findall(r"[\w]+", raw, flags=re.UNICODE)
    return " AND ".join('"' + token.replace('"', '""') + '"' for token in tokens)
