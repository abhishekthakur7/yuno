from __future__ import annotations

import hashlib
import stat

import httpx
import pytest

from yuno.modules.provenance.adapters import HttpSourceRetrievalAdapter
from yuno.modules.provenance.domain import SourceRetrievalRequest
from yuno.shared.domain.errors import DomainValidationError


def _request(url: str) -> SourceRetrievalRequest:
    return SourceRetrievalRequest("owner", "source", url)


def test_http_source_retrieval_stores_content_by_hash_with_private_permissions(
    tmp_path,
) -> None:
    body = b"authoritative source bytes"
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=body, headers={"ETag": '"v1"'})

    client = httpx.Client(
        transport=httpx.MockTransport(handler), follow_redirects=False
    )
    adapter = HttpSourceRetrievalAdapter(tmp_path / "snapshots", client=client)
    result = adapter.retrieve(_request("https://example.test/source"))

    digest = hashlib.sha256(body).hexdigest()
    path = tmp_path / "snapshots" / digest
    assert result.content_ref == f"source-snapshot:{digest}"
    assert result.content_hash == digest
    assert result.version_label == '"v1"'
    assert path.read_bytes() == body
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert seen[0].url == httpx.URL("https://example.test/source")


def test_http_source_retrieval_rejects_redirects_and_unsafe_urls(tmp_path) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                302, headers={"Location": "https://elsewhere.test/"}
            )
        ),
        follow_redirects=False,
    )
    adapter = HttpSourceRetrievalAdapter(tmp_path, client=client)

    with pytest.raises(httpx.HTTPStatusError):
        adapter.retrieve(_request("https://example.test/source"))
    for url in (
        "file:///private/source",
        "https://user:secret@example.test/source",
        "relative/source",
    ):
        with pytest.raises(DomainValidationError):
            adapter.retrieve(_request(url))
    assert list(tmp_path.iterdir()) == []


def test_http_source_retrieval_rejects_symlinked_storage_paths(tmp_path) -> None:
    body = b"authoritative source bytes"
    digest = hashlib.sha256(body).hexdigest()
    outside = tmp_path / "outside"
    outside.write_bytes(body)
    root = tmp_path / "snapshots"
    root.mkdir()
    (root / digest).symlink_to(outside)
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, content=body)
        ),
        follow_redirects=False,
    )

    with pytest.raises(RuntimeError, match="not a private regular file"):
        HttpSourceRetrievalAdapter(root, client=client).retrieve(
            _request("https://example.test/source")
        )
    assert outside.read_bytes() == body

    symlinked_root = tmp_path / "symlinked-root"
    symlinked_root.symlink_to(root, target_is_directory=True)
    with pytest.raises(DomainValidationError, match="real directory"):
        HttpSourceRetrievalAdapter(symlinked_root, client=client).retrieve(
            _request("https://example.test/source")
        )
