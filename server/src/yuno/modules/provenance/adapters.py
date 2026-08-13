"""Constrained HTTP source retrieval and content-addressed local storage."""

from __future__ import annotations

import hashlib
import ipaddress
import os
import socket
import stat
from collections.abc import Callable, Iterable
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from yuno.modules.provenance.domain import (
    SourceRetrievalRequest,
    SourceRetrievalResult,
)
from yuno.shared.domain.clock import SystemClock, now_text
from yuno.shared.domain.errors import DomainValidationError


class HttpSourceRetrievalAdapter:
    MAX_RESPONSE_BYTES = 10 * 1024 * 1024
    _ALLOWED_CONTENT_TYPES = frozenset(
        {
            "application/json",
            "application/pdf",
            "application/xhtml+xml",
            "application/xml",
        }
    )

    def __init__(
        self,
        snapshot_root: Path,
        *,
        client: httpx.Client | None = None,
        resolve: Callable[[str, int], Iterable[str]] | None = None,
    ) -> None:
        self._root = snapshot_root
        self._owns_client = client is None
        self._client = client or httpx.Client(
            follow_redirects=False,
            timeout=30.0,
            trust_env=False,
        )
        self._resolve = resolve or self._resolve_host

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def retrieve(
        self,
        request: SourceRetrievalRequest,
        *,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> SourceRetrievalResult:
        if cancelled():
            raise DomainValidationError("Source retrieval was cancelled.")
        try:
            parsed = urlsplit(request.canonical_url)
            hostname = parsed.hostname
            requested_port = parsed.port
        except (UnicodeError, ValueError):
            raise DomainValidationError("Source retrieval URL is invalid.") from None
        if parsed.scheme not in {"http", "https"} or not hostname:
            raise DomainValidationError(
                "Source retrieval permits only absolute HTTP(S) URLs."
            )
        if parsed.username is not None or parsed.password is not None:
            raise DomainValidationError(
                "Source retrieval URLs must not contain credentials."
            )
        expected_port = 443 if parsed.scheme == "https" else 80
        if requested_port not in {None, expected_port}:
            raise DomainValidationError(
                "Source retrieval permits only the standard HTTP(S) port."
            )
        addresses = self._resolve_public_addresses(hostname, expected_port)
        pinned_url = self._pinned_url(parsed, addresses[0], expected_port)
        host_header = f"[{hostname}]" if ":" in hostname else hostname
        if requested_port is not None:
            host_header = f"{host_header}:{requested_port}"
        try:
            with self._client.stream(
                "GET",
                pinned_url,
                headers={"Host": host_header},
                follow_redirects=False,
                extensions={"sni_hostname": hostname},
            ) as response:
                if response.is_redirect:
                    raise DomainValidationError(
                        "Source retrieval does not permit redirects."
                    )
                response.raise_for_status()
                self._validate_content_type(response)
                content = self._read_bounded(response, cancelled)
                version_label = response.headers.get("etag") or response.headers.get(
                    "last-modified"
                )
        except DomainValidationError:
            raise
        except httpx.HTTPError:
            raise DomainValidationError("Source retrieval failed safely.") from None
        content_hash = hashlib.sha256(content).hexdigest()
        self._prepare_root()
        path = self._root / content_hash
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError:
            self._verify_existing(path, content)
        else:
            with os.fdopen(descriptor, "wb") as handle:
                os.fchmod(handle.fileno(), 0o600)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        return SourceRetrievalResult(
            content_ref=f"source-snapshot:{content_hash}",
            content_hash=content_hash,
            retrieved_at=now_text(SystemClock()),
            version_label=version_label,
        )

    def _resolve_public_addresses(self, hostname: str, port: int) -> tuple[str, ...]:
        try:
            addresses = tuple(dict.fromkeys(self._resolve(hostname, port)))
        except (OSError, UnicodeError, ValueError):
            raise DomainValidationError(
                "Source hostname could not be resolved safely."
            ) from None
        if not addresses:
            raise DomainValidationError("Source hostname could not be resolved safely.")
        try:
            parsed_addresses = tuple(ipaddress.ip_address(item) for item in addresses)
        except ValueError:
            raise DomainValidationError(
                "Source hostname could not be resolved safely."
            ) from None
        # Reject the hostname if any answer is unsafe. This prevents an attacker from
        # mixing a public answer with a private rebinding target. The request then uses
        # one validated address directly, so the transport cannot resolve it again.
        if any(
            not address.is_global
            or address.is_loopback
            or address.is_private
            or address.is_link_local
            or address.is_reserved
            or address.is_unspecified
            or address.is_multicast
            for address in parsed_addresses
        ):
            raise DomainValidationError(
                "Source hostname does not resolve to a public address."
            )
        return tuple(str(address) for address in parsed_addresses)

    @staticmethod
    def _resolve_host(hostname: str, port: int) -> tuple[str, ...]:
        return tuple(
            result[4][0]
            for result in socket.getaddrinfo(
                hostname,
                port,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            )
        )

    @staticmethod
    def _pinned_url(parsed, address: str, port: int) -> httpx.URL:
        host = f"[{address}]" if ":" in address else address
        path = parsed.path or "/"
        target = f"{parsed.scheme}://{host}:{port}{path}"
        if parsed.query:
            target = f"{target}?{parsed.query}"
        return httpx.URL(target)

    @classmethod
    def _validate_content_type(cls, response: httpx.Response) -> None:
        raw_content_type = response.headers.get("content-type", "")
        content_type = raw_content_type.partition(";")[0].strip().lower()
        if not (
            content_type.startswith("text/")
            or content_type in cls._ALLOWED_CONTENT_TYPES
        ):
            raise DomainValidationError(
                "Source retrieval returned an unsupported content type."
            )
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                length = int(content_length)
            except ValueError:
                raise DomainValidationError(
                    "Source retrieval returned an invalid content length."
                ) from None
            if length < 0 or length > cls.MAX_RESPONSE_BYTES:
                raise DomainValidationError(
                    "Source retrieval response exceeds the size limit."
                )

    @classmethod
    def _read_bounded(
        cls, response: httpx.Response, cancelled: Callable[[], bool]
    ) -> bytes:
        content = bytearray()
        for chunk in response.iter_bytes():
            if cancelled():
                raise DomainValidationError("Source retrieval was cancelled.")
            if len(content) + len(chunk) > cls.MAX_RESPONSE_BYTES:
                raise DomainValidationError(
                    "Source retrieval response exceeds the size limit."
                )
            content.extend(chunk)
        return bytes(content)

    def _prepare_root(self) -> None:
        self._root.mkdir(mode=0o700, parents=True, exist_ok=True)
        root_status = self._root.lstat()
        if not stat.S_ISDIR(root_status.st_mode) or stat.S_ISLNK(root_status.st_mode):
            raise DomainValidationError(
                "Source snapshot root must be a real directory."
            )
        os.chmod(self._root, 0o700)

    @staticmethod
    def _verify_existing(path: Path, expected: bytes) -> None:
        before = path.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) != 0o600
        ):
            raise RuntimeError(
                "An existing source snapshot path is not a private regular file."
            )
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError as exc:
            raise RuntimeError(
                "An existing source snapshot could not be opened safely."
            ) from exc
        with os.fdopen(descriptor, "rb") as handle:
            opened = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_nlink != 1
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
            ):
                raise RuntimeError(
                    "An existing source snapshot changed during validation."
                )
            if handle.read() != expected:
                raise RuntimeError("A source snapshot hash collision was detected.")


def remove_unreferenced_snapshots(root: Path, referenced: set[str]) -> int:
    """Remove content-addressed files that no committed snapshot references."""
    if not root.exists():
        return 0
    status = root.lstat()
    if not stat.S_ISDIR(status.st_mode) or stat.S_ISLNK(status.st_mode):
        raise DomainValidationError("Source snapshot root must be a real directory.")
    removed = 0
    for path in root.iterdir():
        name = path.name
        if len(name) != 64 or any(char not in "0123456789abcdef" for char in name):
            continue
        file_status = path.lstat()
        if not stat.S_ISREG(file_status.st_mode) or file_status.st_nlink != 1:
            continue
        if f"source-snapshot:{name}" in referenced:
            continue
        path.unlink()
        removed += 1
    return removed
