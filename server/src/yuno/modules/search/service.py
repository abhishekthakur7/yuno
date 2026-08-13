from __future__ import annotations

from collections.abc import Callable

from yuno.modules.search.domain import SearchRebuild
from yuno.modules.search.ports import SearchUnitOfWork
from yuno.shared.application.jobs import JobPreparedFailure


def rebuild_search_projection(
    uow_factory: Callable[[], SearchUnitOfWork], owner_id: str, job_id: str
) -> SearchRebuild:
    with uow_factory() as uow:
        try:
            generation = uow.search.rebuild(owner_id, job_id)
        except Exception as exc:
            uow.search.mark_failed(owner_id, job_id, f"job:{job_id}:failed")
            uow.commit()
            raise JobPreparedFailure(f"{type(exc).__name__}: {exc}") from exc
        else:
            uow.commit()
    return SearchRebuild(id="default", generation=generation)
