from __future__ import annotations

import hashlib
import logging
import stat
from unittest.mock import Mock, patch

import httpx
import pytest

from yuno.modules.provenance.adapters import (
    HttpSourceRetrievalAdapter,
    remove_unreferenced_snapshots,
)
from yuno.modules.provenance.domain import SourceRetrievalRequest
from yuno.shared.domain.errors import DomainValidationError

PUBLIC_V4 = "8.8.8.8"


def _public_resolver(_hostname: str, _port: int) -> tuple[str, ...]:
    return (PUBLIC_V4,)


def test_http_source_retrieval_owned_client_ignores_proxy_environment(tmp_path) -> None:
    owned_client = Mock()
    with patch(
        "yuno.modules.provenance.adapters.httpx.Client", return_value=owned_client
    ) as client_type:
        adapter = HttpSourceRetrievalAdapter(tmp_path)

    client_type.assert_called_once_with(
        follow_redirects=False,
        timeout=30.0,
        trust_env=False,
    )
    adapter.close()
    owned_client.close.assert_called_once_with()


def _request(url: str) -> SourceRetrievalRequest:
    return SourceRetrievalRequest("owner", "source", url)


def test_http_source_retrieval_stores_content_by_hash_with_private_permissions(
    tmp_path,
) -> None:
    body = b"authoritative source bytes"
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            content=body,
            headers={"ETag": '"v1"', "Content-Type": "text/plain"},
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler), follow_redirects=False
    )
    adapter = HttpSourceRetrievalAdapter(
        tmp_path / "snapshots", client=client, resolve=_public_resolver
    )
    result = adapter.retrieve(_request("https://example.test/source"))

    digest = hashlib.sha256(body).hexdigest()
    path = tmp_path / "snapshots" / digest
    assert result.content_ref == f"source-snapshot:{digest}"
    assert result.content_hash == digest
    assert result.version_label == '"v1"'
    assert path.read_bytes() == body
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert seen[0].url == httpx.URL(f"https://{PUBLIC_V4}:443/source")
    assert seen[0].headers["host"] == "example.test"
    assert seen[0].extensions["sni_hostname"] == "example.test"


def test_http_source_retrieval_rejects_redirects_and_unsafe_urls(tmp_path) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                302, headers={"Location": "https://elsewhere.test/"}
            )
        ),
        follow_redirects=False,
    )
    adapter = HttpSourceRetrievalAdapter(
        tmp_path, client=client, resolve=_public_resolver
    )

    with pytest.raises(DomainValidationError, match="does not permit redirects"):
        adapter.retrieve(_request("https://example.test/source"))
    for url in (
        "file:///private/source",
        "https://user:secret@example.test/source",
        "https://example.test:8443/source",
        "https://example.test:not-a-port/source",
        "https://[invalid/source",
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
            lambda _request: httpx.Response(
                200, content=body, headers={"Content-Type": "text/plain"}
            )
        ),
        follow_redirects=False,
    )

    with pytest.raises(RuntimeError, match="not a private regular file"):
        HttpSourceRetrievalAdapter(
            root, client=client, resolve=_public_resolver
        ).retrieve(_request("https://example.test/source"))
    assert outside.read_bytes() == body

    (root / digest).unlink()
    (root / digest).write_bytes(body)
    (root / digest).chmod(0o644)
    with pytest.raises(RuntimeError, match="not a private regular file"):
        HttpSourceRetrievalAdapter(
            root, client=client, resolve=_public_resolver
        ).retrieve(_request("https://example.test/source"))

    symlinked_root = tmp_path / "symlinked-root"
    symlinked_root.symlink_to(root, target_is_directory=True)
    with pytest.raises(DomainValidationError, match="real directory"):
        HttpSourceRetrievalAdapter(
            symlinked_root, client=client, resolve=_public_resolver
        ).retrieve(_request("https://example.test/source"))


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.1.1",
        "0.0.0.0",
        "224.0.0.1",
        "192.0.2.1",
        "::1",
        "fd00::1",
        "fe80::1",
        "::",
        "ff02::1",
        "2001:db8::1",
    ],
)
def test_http_source_retrieval_rejects_non_public_addresses(tmp_path, address) -> None:
    called = False

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, headers={"Content-Type": "text/plain"})

    adapter = HttpSourceRetrievalAdapter(
        tmp_path,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        resolve=lambda _hostname, _port: (address,),
    )

    with pytest.raises(DomainValidationError, match="public address"):
        adapter.retrieve(_request("https://example.test/source"))
    assert not called
    assert list(tmp_path.iterdir()) == []


def test_http_source_retrieval_rejects_mixed_dns_answers_before_request(
    tmp_path,
) -> None:
    called = False

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, headers={"Content-Type": "text/plain"})

    adapter = HttpSourceRetrievalAdapter(
        tmp_path,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        resolve=lambda _hostname, _port: (PUBLIC_V4, "127.0.0.1"),
    )

    with pytest.raises(DomainValidationError, match="public address"):
        adapter.retrieve(_request("https://example.test/source"))
    assert not called


@pytest.mark.parametrize(
    ("headers", "message"),
    [
        ({}, "unsupported content type"),
        ({"Content-Type": "image/png"}, "unsupported content type"),
        (
            {
                "Content-Type": "text/plain",
                "Content-Length": str(
                    HttpSourceRetrievalAdapter.MAX_RESPONSE_BYTES + 1
                ),
            },
            "size limit",
        ),
        (
            {"Content-Type": "text/plain", "Content-Length": "secret-not-a-size"},
            "invalid content length",
        ),
    ],
)
def test_http_source_retrieval_rejects_unsafe_response_metadata(
    tmp_path, headers, message
) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, content=b"body", headers=headers)
        )
    )

    with pytest.raises(DomainValidationError, match=message):
        HttpSourceRetrievalAdapter(
            tmp_path, client=client, resolve=_public_resolver
        ).retrieve(_request("https://example.test/source"))
    assert list(tmp_path.iterdir()) == []


def test_http_source_retrieval_stream_size_limit_leaves_no_file(tmp_path) -> None:
    body = b"x" * (HttpSourceRetrievalAdapter.MAX_RESPONSE_BYTES + 1)
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200, content=body, headers={"Content-Type": "application/pdf"}
            )
        )
    )

    with pytest.raises(DomainValidationError, match="size limit"):
        HttpSourceRetrievalAdapter(
            tmp_path, client=client, resolve=_public_resolver
        ).retrieve(_request("https://example.test/source"))
    assert list(tmp_path.iterdir()) == []


def test_http_source_retrieval_hides_transport_details_and_url(
    tmp_path, caplog
) -> None:
    secret_url = "https://example.test/private?token=super-secret"

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("credential=super-secret internal=127.0.0.1")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with (
        caplog.at_level(logging.DEBUG),
        pytest.raises(
            DomainValidationError, match="Source retrieval failed safely"
        ) as caught,
    ):
        HttpSourceRetrievalAdapter(
            tmp_path, client=client, resolve=_public_resolver
        ).retrieve(_request(secret_url))
    combined = str(caught.value) + caplog.text
    assert "super-secret" not in combined
    assert "127.0.0.1" not in combined
    assert secret_url not in combined


def test_http_source_retrieval_pins_ipv6_and_preserves_authority(tmp_path) -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200, content=b"body", headers={"Content-Type": "application/json"}
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = HttpSourceRetrievalAdapter(
        tmp_path,
        client=client,
        resolve=lambda _hostname, _port: ("2606:4700:4700::1111",),
    )

    adapter.retrieve(_request("https://example.test/source?q=1"))

    assert seen[0].url == httpx.URL("https://[2606:4700:4700::1111]:443/source?q=1")
    assert seen[0].headers["host"] == "example.test"


def test_http_source_retrieval_honors_cancellation_without_writing(tmp_path) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200, content=b"body", headers={"Content-Type": "text/plain"}
            )
        )
    )
    with pytest.raises(DomainValidationError, match="cancelled"):
        HttpSourceRetrievalAdapter(
            tmp_path, client=client, resolve=_public_resolver
        ).retrieve(_request("https://example.test/source"), cancelled=lambda: True)
    assert list(tmp_path.iterdir()) == []


def test_startup_reconciliation_removes_only_unreferenced_hash_files(tmp_path) -> None:
    kept_name = "a" * 64
    removed_name = "b" * 64
    (tmp_path / kept_name).write_bytes(b"kept")
    (tmp_path / removed_name).write_bytes(b"removed")
    (tmp_path / "operator-note").write_text("preserve", encoding="utf-8")
    removed = remove_unreferenced_snapshots(tmp_path, {f"source-snapshot:{kept_name}"})
    assert removed == 1
    assert (tmp_path / kept_name).read_bytes() == b"kept"
    assert not (tmp_path / removed_name).exists()
    assert (tmp_path / "operator-note").read_text(encoding="utf-8") == "preserve"
