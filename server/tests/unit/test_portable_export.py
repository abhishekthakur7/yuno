from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from yuno.modules.settings_data.domain import ExportOperation
from yuno.modules.settings_data.service import (
    build_export_package,
    canonical_json,
    portable_export_document,
    portable_export_filename,
    require_supported_export_major,
)
from yuno.shared.domain.errors import UnsupportedExportVersionError


def test_portable_export_is_canonical_utf8_with_data_integrity() -> None:
    data = {"z": "évidence", "a": {"body": "available"}}
    document = portable_export_document(
        data, exported_at="2026-08-13T12:34:56Z", goal_id="goal-1"
    )

    assert document.encode("utf-8").decode("utf-8") == document
    assert not document.encode("utf-8").startswith(b"\xef\xbb\xbf")
    assert " " not in document
    assert document == canonical_json(json.loads(document))
    package = json.loads(document)
    assert sorted(package) == sorted(
        ["product", "format", "version", "exported_at", "scope", "data", "integrity"]
    )
    assert package["format"] == "yuno-portable-export"
    assert package["version"] == "1.0"
    assert package["scope"] == {"kind": "goal", "goal_id": "goal-1"}
    assert package["integrity"] == {
        "algorithm": "sha256",
        "digest": hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest(),
    }


def test_portable_export_uses_approved_utc_filename() -> None:
    assert (
        portable_export_filename("2026-08-13T18:04:56+05:30")
        == "yuno-export-v1-20260813T123456Z.json"
    )


@pytest.mark.parametrize("version", ["2.0", "10.2", "v1", "1", "1.0.0"])
def test_portable_export_rejects_unsupported_or_invalid_major_versions(
    version: str,
) -> None:
    with pytest.raises(UnsupportedExportVersionError):
        require_supported_export_major(version)


@pytest.mark.parametrize("version", ["1.0", "1.1", "1.999"])
def test_portable_export_reader_accepts_supported_major(version: str) -> None:
    require_supported_export_major(version)


def test_export_build_uses_configured_retention_without_publishing() -> None:
    operation = ExportOperation(
        id="export-1",
        owner_id="owner-1",
        goal_id=None,
        status="running",
        format_version="1.0",
        filename=None,
        package_hash=None,
        job_id="export-1",
        result_ref=None,
        failure_reference=None,
        completed_at=None,
        package_expires_at=None,
        metadata_expires_at=None,
        created_at="2026-08-13T00:00:00.000000Z",
        updated_at="2026-08-13T00:00:00.000000Z",
    )

    class Repository:
        published = False

        def get_export(self, owner_id: str, operation_id: str):
            assert (owner_id, operation_id) == ("owner-1", "export-1")
            return operation

        def read_export_data(self, owner_id: str, goal_id: str | None):
            assert (owner_id, goal_id) == ("owner-1", None)
            return {"profile": [{"experience": "développeur"}]}

        def publish_export(self, package):
            self.published = True

    repository = Repository()
    uow = SimpleNamespace(settings_data=repository)
    clock = SimpleNamespace(now=lambda: datetime(2026, 8, 13, 12, 34, 56, tzinfo=UTC))

    package = build_export_package(
        uow,
        "owner-1",
        "export-1",
        package_retention_seconds=90,
        metadata_retention_days=2,
        clock=clock,  # type: ignore[arg-type]
    )

    assert repository.published is False
    assert package.completed_at == "2026-08-13T12:34:56.000000Z"
    assert package.package_expires_at == "2026-08-13T12:36:26.000000Z"
    assert package.metadata_expires_at == "2026-08-15T12:34:56.000000Z"
    assert package.filename == "yuno-export-v1-20260813T123456Z.json"
    assert (
        package.package_hash
        == hashlib.sha256(package.document.encode("utf-8")).hexdigest()
    )
