#!/usr/bin/env python3
"""IDK-504: server-side representative performance measurements (spec §8.6).

§8.6 invents no pass threshold, and this file is the hard boundary that rule
lives inside: nothing below ever writes a target, baseline, budget, SLA or
guarantee, and nothing below asserts that a measured value is "fast enough".
Every function here either records every value it actually observed, or -- if
a measurement cannot be taken reproducibly -- records a gap explaining why,
never a fabricated, estimated or interpolated number.

This script measures the real service/unit-of-work layer directly (no HTTP,
no ASGI app, exactly like `scripts/publish_canonical.py` and
`scripts/seed_performance_dataset.py`) against the fixed, already-seeded
database at the given `--database-url`. It owns exactly one producer id,
`server-measurements`, and writes one sample file in the shape
`tests/perf/samples.ts` defines for every producer, constructed here by hand
since that TypeScript helper is not reachable from Python.

Measurements produced:
  - fts-query: FTS latency for a representative set of queries against the
    seeded index, at least 5 repetitions each.
  - fts-stale-fallback: latency of the deterministic stale/degraded search
    path (spec §8.4) -- reached the way the shipped code actually reaches
    it: an owned-projection source row changes after the index was built,
    so `SearchRepository.state` recomputes a source watermark that no
    longer matches the stored one and falls back to the owned
    `search_documents`/`search_document_bodies` tables with stable
    ordering and `degraded=True` labelling, never a raw FTS row.
  - import-parse-effect / index-rebuild-effect: not the duration of the
    import parse or index rebuild itself, but its *effect* -- the latency
    of a representative navigation-ish read and a representative search
    query taken on a separate connection while the operation runs
    concurrently on its own thread and connection. The operation's own
    duration is recorded too, under its own subject, clearly labelled as
    the operation duration rather than the effect.
  - cpu-usage / memory-usage: `resource.getrusage(RUSAGE_SELF)` around a
    representative workload run by this script -- explicitly the
    measuring process performing that workload, not a deployed server
    under learner load.
  - sqlite-size: the seeded database file's size, plus its `-wal` and
    `-shm` files when present, each its own subject.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import platform
import resource
import sys
import threading
import time
from pathlib import Path
from typing import Any

from yuno.api.routes.roadmap import get_goal_roadmap
from yuno.modules.identity.service import ensure_local_owner
from yuno.modules.imports.domain import ImportType
from yuno.modules.imports.service import (
    create_import,
    mark_import_parsing,
    parse_import,
)
from yuno.modules.notebook_review.domain import NotebookEntryKind
from yuno.modules.notebook_review.service import create_notebook_entry
from yuno.modules.search.domain import SearchIndexStatus
from yuno.shared.domain.clock import SystemClock
from yuno.shared.infrastructure.database import (
    create_engine_for,
    create_session_factory,
)
from yuno.unit_of_work import create_unit_of_work_factory

DEFAULT_DATABASE_URL = "sqlite+pysqlite:///./perf.db"
PRODUCER = "server-measurements"

# The seeder (`scripts/seed_performance_dataset.py`) names its two goals
# exactly this way; reading them back by name (rather than hardcoding an
# id the seeder never fixes) is how this script finds the fixed dataset
# without importing anything from that script or from `server/tests`.
_GOAL_ONE_NAME = "Representative perf goal one"

_FTS_QUERIES = ("java", "aws", "Representative", "notebook", "evidence")


class Sample:
    __slots__ = ("measurement", "method", "notes", "subject", "unit", "values")

    def __init__(
        self,
        measurement: str,
        subject: str,
        unit: str,
        values: list[float],
        *,
        method: str | None = None,
        notes: str | None = None,
    ) -> None:
        self.measurement = measurement
        self.subject = subject
        self.unit = unit
        self.values = values
        self.method = method
        self.notes = notes

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "measurement": self.measurement,
            "subject": self.subject,
            "unit": self.unit,
            "values": self.values,
        }
        if self.method:
            payload["method"] = self.method
        if self.notes:
            payload["notes"] = self.notes
        return payload


class Gap:
    __slots__ = ("measurement", "reason", "subject")

    def __init__(
        self, measurement: str, reason: str, *, subject: str | None = None
    ) -> None:
        self.measurement = measurement
        self.subject = subject
        self.reason = reason

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "measurement": self.measurement,
            "reason": self.reason,
        }
        if self.subject:
            payload["subject"] = self.subject
        return payload


def _ms(start: float, end: float) -> float:
    return (end - start) * 1000.0


def _resolve_owner_and_goal(uow_factory) -> tuple[str, str]:
    """Resolve the seeded owner and its first goal without hardcoding either
    id: `ensure_local_owner` is idempotent (existence of the singleton
    local owner *is* the idempotency check, per its own docstring), and the
    goal is looked up by the seeder's fixed name.
    """
    with uow_factory() as uow:
        owner = ensure_local_owner(uow, "Performance dataset owner")
        uow.commit()
    with uow_factory() as uow:
        goal = next(
            (
                candidate
                for candidate in uow.profiles_goals.list_goals(owner.id)
                if candidate.name == _GOAL_ONE_NAME
            ),
            None,
        )
    if goal is None:
        raise RuntimeError(
            f"No goal named {_GOAL_ONE_NAME!r} was found for the seeded owner; "
            "run scripts/seed_performance_dataset.py against --database-url first."
        )
    return owner.id, goal.id


def _measure_fts_query(uow_factory, owner_id: str, goal_id: str) -> list[Sample]:
    samples = []
    for query in _FTS_QUERIES:
        values = []
        for _ in range(5):
            with uow_factory() as uow:
                start = time.perf_counter()
                uow.search.state(owner_id)
                uow.search.search(owner_id, goal_id, query, ())
                end = time.perf_counter()
            values.append(_ms(start, end))
        samples.append(
            Sample(
                "fts-query",
                query,
                "ms",
                values,
                method="SearchRepositoryPort.state + .search against the seeded index, "
                "in-process, 5 repetitions.",
            )
        )
    return samples


def _measure_fts_stale_fallback(
    uow_factory, owner_id: str, goal_id: str
) -> list[Sample | Gap]:
    # Force a known-ready index deterministically, regardless of ambient
    # state, then change an owned projection source row (a new notebook
    # entry) without rebuilding -- exactly how `SearchRepository.state`
    # (server/src/yuno/modules/search/repository.py) reaches STALE: the
    # recomputed source watermark stops matching the stored one.
    with uow_factory() as uow:
        uow.search.rebuild(owner_id, "measure-performance-warmup")
        uow.commit()
    with uow_factory() as uow:
        create_notebook_entry(
            uow,
            owner_id,
            goal_id,
            entry_kind=NotebookEntryKind.USER,
            markdown="Representative perf dataset stale-fallback trigger entry.",
        )
        uow.commit()
    with uow_factory() as uow:
        state = uow.search.state(owner_id)
    if state.status is not SearchIndexStatus.STALE:
        return [
            Gap(
                "fts-stale-fallback",
                f"Could not deterministically reach SearchIndexStatus.STALE: "
                f"observed status was {state.status.value!r} after writing an "
                "unindexed notebook entry.",
            )
        ]
    values = []
    for _ in range(5):
        with uow_factory() as uow:
            start = time.perf_counter()
            results = uow.search.search(owner_id, goal_id, "Representative", ())
            end = time.perf_counter()
        if not all(result.degraded for result in results):
            return [
                Gap(
                    "fts-stale-fallback",
                    "The stale-index search returned at least one non-degraded "
                    "result; the deterministic stale-fallback path was not "
                    "exercised as expected.",
                )
            ]
        values.append(_ms(start, end))
    return [
        Sample(
            "fts-stale-fallback",
            "Representative",
            "ms",
            values,
            method="Index forced READY, then an unindexed notebook entry write "
            "moves the source watermark, driving SearchIndexStatus.STALE; "
            "search() then falls back to the owned search_documents/"
            "search_document_bodies tables (degraded=True), 5 repetitions.",
        )
    ]


def _concurrent_effect(
    database_url: str,
    owner_id: str,
    goal_id: str,
    *,
    measurement: str,
    background_iterations: int,
    background_op,
    background_label: str,
) -> list[Sample | Gap]:
    """Measure the *effect* of `background_op` running repeatedly on its own
    thread/connection on a representative read and a representative search
    query taken concurrently on a separate connection -- not the duration of
    `background_op` itself, which is recorded separately under its own
    subject.
    """
    op_durations: list[float] = []
    op_lock = threading.Lock()

    def worker() -> None:
        engine = create_engine_for(database_url)
        try:
            session_factory = create_session_factory(engine)
            uow_factory = create_unit_of_work_factory(session_factory)
            for iteration in range(background_iterations):
                start = time.perf_counter()
                background_op(uow_factory, iteration)
                end = time.perf_counter()
                with op_lock:
                    op_durations.append(_ms(start, end))
        finally:
            engine.dispose()

    thread = threading.Thread(target=worker)
    read_samples: list[float] = []
    query_samples: list[float] = []
    engine = create_engine_for(database_url)
    try:
        session_factory = create_session_factory(engine)
        uow_factory = create_unit_of_work_factory(session_factory)
        thread.start()
        while thread.is_alive():
            start = time.perf_counter()
            with uow_factory() as uow:
                get_goal_roadmap(goal_id, owner_id, uow, SystemClock())
            end = time.perf_counter()
            read_samples.append(_ms(start, end))

            start = time.perf_counter()
            with uow_factory() as uow:
                uow.search.state(owner_id)
                uow.search.search(owner_id, goal_id, "java", ())
            end = time.perf_counter()
            query_samples.append(_ms(start, end))
    finally:
        thread.join()
        engine.dispose()

    results: list[Sample | Gap] = []
    if not read_samples or not query_samples:
        results.append(
            Gap(
                measurement,
                f"The background {background_label} loop ({background_iterations} "
                "iterations) finished before any concurrent read/query sample "
                "could be taken on this run, so no effect was observed.",
            )
        )
    else:
        results.append(
            Sample(
                measurement,
                f"concurrent-read:goal-roadmap-during-{background_label}",
                "ms",
                read_samples,
                method=f"get_goal_roadmap sampled repeatedly on a separate "
                f"connection while {background_iterations} {background_label} "
                "iterations ran concurrently on their own thread/connection.",
            )
        )
        results.append(
            Sample(
                measurement,
                f"concurrent-query:search-during-{background_label}",
                "ms",
                query_samples,
                method=f"A representative search() call sampled repeatedly on a "
                f"separate connection while {background_iterations} "
                f"{background_label} iterations ran concurrently.",
            )
        )
    if op_durations:
        results.append(
            Sample(
                measurement,
                f"operation-duration:{background_label}",
                "ms",
                op_durations,
                notes=f"This is the {background_label} operation's own duration, "
                "not its effect on concurrent responsiveness -- recorded here "
                "under its own subject rather than mixed into the effect samples "
                "above.",
            )
        )
    return results


def _measure_import_parse_effect(
    database_url: str, owner_id: str, goal_id: str
) -> list[Sample | Gap]:
    def background_import_parse(uow_factory, iteration: int) -> None:
        text = "\n".join(
            f"Representative perf dataset import-effect statement {iteration}-{line}."
            for line in range(50)
        )
        with uow_factory() as uow:
            record = create_import(
                uow,
                owner_id,
                goal_id=None,
                import_type=ImportType.PLAIN_TEXT,
                source_text=text,
            )
            uow.commit()
            import_id = record.id
        with uow_factory() as uow:
            mark_import_parsing(uow, owner_id, import_id)
            uow.commit()
        with uow_factory() as uow:
            parse_import(uow, owner_id, import_id)
            uow.commit()

    return _concurrent_effect(
        database_url,
        owner_id,
        goal_id,
        measurement="import-parse-effect",
        background_iterations=25,
        background_op=background_import_parse,
        background_label="import-parse",
    )


def _measure_index_rebuild_effect(
    database_url: str, owner_id: str, goal_id: str
) -> list[Sample | Gap]:
    counter = itertools.count()

    def op(uow_factory, iteration: int) -> None:
        with uow_factory() as uow:
            uow.search.rebuild(
                owner_id, f"measure-performance-rebuild-effect-{next(counter)}"
            )
            uow.commit()

    return _concurrent_effect(
        database_url,
        owner_id,
        goal_id,
        measurement="index-rebuild-effect",
        background_iterations=15,
        background_op=op,
        background_label="index-rebuild",
    )


def _representative_workload(uow_factory, owner_id: str, goal_id: str) -> None:
    """The workload cpu-usage/memory-usage measure this process performing:
    a handful of representative reads, queries and one index rebuild --
    small, deterministic, and identical to work already exercised above.
    """
    for _ in range(10):
        with uow_factory() as uow:
            get_goal_roadmap(goal_id, owner_id, uow, SystemClock())
    for query in _FTS_QUERIES:
        with uow_factory() as uow:
            uow.search.state(owner_id)
            uow.search.search(owner_id, goal_id, query, ())
    with uow_factory() as uow:
        uow.search.rebuild(owner_id, "measure-performance-resource-workload")
        uow.commit()


def _maxrss_bytes(raw_maxrss: int) -> int:
    # `ru_maxrss` is already bytes on Darwin; every other POSIX platform
    # (Linux, the CI runner this is most likely to also run on) reports it
    # in kilobytes. This is a unit conversion of a real observed value, not
    # an estimate.
    return raw_maxrss if sys.platform == "darwin" else raw_maxrss * 1024


def _measure_cpu_and_memory(uow_factory, owner_id: str, goal_id: str) -> list[Sample]:
    cpu_values: list[float] = []
    memory_values: list[float] = []
    for _ in range(3):
        before = resource.getrusage(resource.RUSAGE_SELF)
        wall_start = time.perf_counter()
        _representative_workload(uow_factory, owner_id, goal_id)
        wall_end = time.perf_counter()
        after = resource.getrusage(resource.RUSAGE_SELF)

        wall_elapsed = wall_end - wall_start
        cpu_elapsed = (after.ru_utime - before.ru_utime) + (
            after.ru_stime - before.ru_stime
        )
        cpu_percent = (cpu_elapsed / wall_elapsed * 100.0) if wall_elapsed > 0 else 0.0
        cpu_values.append(cpu_percent)
        memory_values.append(float(_maxrss_bytes(after.ru_maxrss)))

    return [
        Sample(
            "cpu-usage",
            "measuring-process:representative-workload",
            "percent",
            cpu_values,
            method="resource.getrusage(RUSAGE_SELF) user+system time delta over "
            "wall-clock time delta, around 3 repetitions of a representative "
            "read/query/rebuild workload. This is the measuring process (this "
            "script) running that workload, not a deployed server under "
            "learner load.",
        ),
        Sample(
            "memory-usage",
            "measuring-process:representative-workload",
            "bytes",
            memory_values,
            method="resource.getrusage(RUSAGE_SELF).ru_maxrss (peak resident set "
            "size) after each of 3 repetitions of the same representative "
            "workload. This is the measuring process (this script), not a "
            "deployed server under learner load.",
        ),
    ]


def _sqlite_path(database_url: str) -> Path:
    prefix = "sqlite+pysqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError(
            f"Expected a sqlite+pysqlite database URL, got {database_url!r}."
        )
    return Path(database_url[len(prefix) :]).resolve()


def _measure_sqlite_size(database_url: str) -> list[Sample | Gap]:
    results: list[Sample | Gap] = []
    try:
        db_path = _sqlite_path(database_url)
    except ValueError as exc:
        return [Gap("sqlite-size", str(exc))]

    for suffix, label in (
        ("", "perf.db"),
        ("-wal", "perf.db-wal"),
        ("-shm", "perf.db-shm"),
    ):
        candidate = db_path.with_name(db_path.name + suffix)
        if candidate.exists():
            results.append(
                Sample(
                    "sqlite-size",
                    label,
                    "bytes",
                    [float(os.path.getsize(candidate))],
                    method="os.path.getsize on the seeded database file.",
                )
            )
        else:
            results.append(
                Gap("sqlite-size", f"{candidate} does not exist.", subject=label)
            )
    return results


def run(database_url: str) -> tuple[list[Sample], list[Gap]]:
    engine = create_engine_for(database_url)
    try:
        session_factory = create_session_factory(engine)
        uow_factory = create_unit_of_work_factory(session_factory)
        owner_id, goal_id = _resolve_owner_and_goal(uow_factory)

        all_results: list[Sample | Gap] = []
        all_results.extend(_measure_fts_query(uow_factory, owner_id, goal_id))
        all_results.extend(_measure_fts_stale_fallback(uow_factory, owner_id, goal_id))
        all_results.extend(
            _measure_import_parse_effect(database_url, owner_id, goal_id)
        )
        all_results.extend(
            _measure_index_rebuild_effect(database_url, owner_id, goal_id)
        )
        all_results.extend(_measure_cpu_and_memory(uow_factory, owner_id, goal_id))
        all_results.extend(_measure_sqlite_size(database_url))
    finally:
        engine.dispose()

    samples = [item for item in all_results if isinstance(item, Sample)]
    gaps = [item for item in all_results if isinstance(item, Gap)]
    return samples, gaps


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record representative server-side performance measurements "
        "(spec §8.6) against an already-seeded database. Invents no threshold."
    )
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    samples, gaps = run(args.database_url)

    payload = {
        "producer": PRODUCER,
        "samples": [sample.to_dict() for sample in samples],
        "gaps": [gap.to_dict() for gap in gaps],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")

    print(
        f"Wrote {len(samples)} sample(s) and {len(gaps)} gap(s) for producer "
        f"{PRODUCER!r} to {args.out} (platform={platform.platform()})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
