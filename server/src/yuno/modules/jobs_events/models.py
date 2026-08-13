"""SQLAlchemy persistence model for the durable two-lane worker."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Computed,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from yuno.shared.application.jobs import JOB_PAYLOAD_SCHEMA_VERSION
from yuno.shared.infrastructure.base import (
    Base,
    boolean_column,
    id_column,
    utc_timestamp_column,
)

if TYPE_CHECKING:
    from yuno.modules.data_lifecycle.models import (
        JobAttemptBodyRow,
        JobBodyRow,
        JobResultBodyRow,
    )

_ACTIVE = "state IN ('queued','running','cancel-requested')"


class JobRow(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("length(trim(kind)) > 0", name="kind_valid"),
        CheckConstraint("lane IN ('interactive','background')", name="lane_valid"),
        CheckConstraint(
            "state IN ('queued','running','succeeded','failed','cancel-requested','cancelled')",
            name="state_valid",
        ),
        CheckConstraint("retryable IN (0,1)", name="retryable_valid"),
        CheckConstraint(
            "provider_name IS NULL OR provider_name IN ('codex','claude')",
            name="provider_name_valid",
        ),
        CheckConstraint("attempt >= 0", name="attempt_nonnegative"),
        CheckConstraint("priority >= 0", name="priority_nonnegative"),
        UniqueConstraint("id", "owner_id", name="uq_jobs_id_owner"),
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_jobs_goal_owner",
        ),
        Index("ix_jobs_lane_state_queue", "lane", "state", "priority", "queued_at"),
        Index(
            "uq_jobs_active_dedupe",
            "owner_id",
            "kind",
            "dedupe_key",
            unique=True,
            sqlite_where=text(f"dedupe_key IS NOT NULL AND {_ACTIVE}"),
        ),
    )

    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), nullable=False, index=True
    )
    goal_id: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[str] = mapped_column(
        Text, nullable=False, default=JOB_PAYLOAD_SCHEMA_VERSION
    )
    lane: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    retryable: Mapped[int] = boolean_column("retryable", default=False)
    dedupe_key: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    payload_hash: Mapped[str] = mapped_column(Text, nullable=False)
    request_ref: Mapped[str | None] = mapped_column(Text)
    disclosure_ref: Mapped[str | None] = mapped_column(Text)
    provider_name: Mapped[str | None] = mapped_column(Text)
    confirmation_ref: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[str] = mapped_column(Text, nullable=False)
    request_id: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str | None] = mapped_column(Text)
    substitution_ref: Mapped[str | None] = mapped_column(Text)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    result_ref: Mapped[str | None] = mapped_column(Text)
    result_hash: Mapped[str | None] = mapped_column(Text)
    worker_id: Mapped[str | None] = mapped_column(Text)
    queued_at: Mapped[str] = utc_timestamp_column()
    started_at: Mapped[str | None] = utc_timestamp_column(nullable=True)
    terminal_at: Mapped[str | None] = utc_timestamp_column(nullable=True)
    updated_at: Mapped[str] = utc_timestamp_column()
    body: Mapped["JobBodyRow | None"] = relationship(  # noqa: UP037
        "JobBodyRow", uselist=False, cascade="all, delete-orphan", lazy="joined"
    )

    @property
    def payload_json(self) -> str:
        return self.body.payload_json if self.body else "{}"

    @property
    def diagnostic(self) -> str | None:
        return self.body.diagnostic if self.body else None

    @diagnostic.setter
    def diagnostic(self, value: str | None) -> None:
        if self.body:
            self.body.diagnostic = value


class JobAttemptRow(Base):
    __tablename__ = "job_attempts"
    __table_args__ = (
        CheckConstraint("attempt_number >= 1", name="attempt_number_positive"),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('succeeded','failed','cancelled')",
            name="outcome_valid",
        ),
        UniqueConstraint("id", "owner_id", name="uq_job_attempts_id_owner"),
        UniqueConstraint(
            "job_id", "attempt_number", name="uq_job_attempts_job_attempt"
        ),
        ForeignKeyConstraint(
            ["job_id", "owner_id"],
            ["jobs.id", "jobs.owner_id"],
            ondelete="CASCADE",
            name="fk_job_attempts_job_owner",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), nullable=False, index=True
    )
    job_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    substitution_ref: Mapped[str | None] = mapped_column(Text)
    confirmation_ref: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[str] = utc_timestamp_column()
    ended_at: Mapped[str | None] = utc_timestamp_column(nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text)
    body: Mapped["JobAttemptBodyRow | None"] = relationship(  # noqa: UP037
        "JobAttemptBodyRow", uselist=False, cascade="all, delete-orphan", lazy="joined"
    )

    @property
    def process_identity(self) -> str | None:
        return self.body.process_identity if self.body else None

    @process_identity.setter
    def process_identity(self, value: str | None) -> None:
        if self.body:
            self.body.process_identity = value

    @property
    def pid(self) -> int | None:
        return self.body.pid if self.body else None

    @pid.setter
    def pid(self, value: int | None) -> None:
        if self.body:
            self.body.pid = value

    @property
    def pgid(self) -> int | None:
        return self.body.pgid if self.body else None

    @pgid.setter
    def pgid(self, value: int | None) -> None:
        if self.body:
            self.body.pgid = value

    @property
    def temp_path(self) -> str | None:
        return self.body.temp_path if self.body else None

    @temp_path.setter
    def temp_path(self, value: str | None) -> None:
        if self.body:
            self.body.temp_path = value

    @property
    def diagnostic(self) -> str | None:
        return self.body.diagnostic if self.body else None

    @diagnostic.setter
    def diagnostic(self, value: str | None) -> None:
        if self.body:
            self.body.diagnostic = value


class JobEventRow(Base):
    __tablename__ = "job_events"
    __table_args__ = (
        CheckConstraint("length(trim(type)) > 0", name="type_valid"),
        CheckConstraint(
            "state IN ('queued','running','succeeded','failed','cancel-requested','cancelled')",
            name="state_valid",
        ),
        CheckConstraint("retryable IN (0,1)", name="retryable_valid"),
        ForeignKeyConstraint(
            ["job_id", "owner_id"],
            ["jobs.id", "jobs.owner_id"],
            ondelete="CASCADE",
            name="fk_job_events_job_owner",
        ),
        ForeignKeyConstraint(
            ["goal_id", "owner_id"],
            ["goal_workspaces.id", "goal_workspaces.owner_id"],
            name="fk_job_events_goal_owner",
        ),
        Index("ix_job_events_owner_event", "owner_id", "event_id"),
        Index("ix_job_events_job_event", "job_id", "event_id"),
    )
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        Text,
        Computed("printf('%020d', sequence)", persisted=True),
        nullable=False,
    )
    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), nullable=False, index=True
    )
    job_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    goal_id: Mapped[str | None] = mapped_column(Text)
    run_id: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    progress: Mapped[str | None] = mapped_column(Text)
    result_ref: Mapped[str | None] = mapped_column(Text)
    retryable: Mapped[int] = boolean_column("retryable", default=False)
    correlation_id: Mapped[str] = mapped_column(Text, nullable=False)
    request_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = utc_timestamp_column()


class JobResultRow(Base):
    __tablename__ = "job_results"
    __table_args__ = (
        CheckConstraint("length(trim(kind)) > 0", name="kind_valid"),
        UniqueConstraint("id", "owner_id", name="uq_job_results_id_owner"),
        UniqueConstraint("job_id", name="uq_job_results_job"),
        ForeignKeyConstraint(
            ["job_id", "owner_id"],
            ["jobs.id", "jobs.owner_id"],
            ondelete="CASCADE",
            name="fk_job_results_job_owner",
        ),
    )
    id: Mapped[str] = id_column()
    owner_id: Mapped[str] = mapped_column(
        Text, ForeignKey("owners.id"), nullable=False, index=True
    )
    job_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[str] = mapped_column(
        Text, nullable=False, default=JOB_PAYLOAD_SCHEMA_VERSION
    )
    result_ref: Mapped[str] = mapped_column(Text, nullable=False)
    result_hash: Mapped[str] = mapped_column(Text, nullable=False)
    committed_at: Mapped[str] = utc_timestamp_column()
    body: Mapped["JobResultBodyRow | None"] = relationship(  # noqa: UP037
        "JobResultBodyRow", uselist=False, cascade="all, delete-orphan", lazy="joined"
    )

    @property
    def warnings_json(self) -> str:
        return self.body.warnings_json if self.body else "[]"

    @property
    def diagnostic_ref(self) -> str | None:
        return self.body.diagnostic_ref if self.body else None
