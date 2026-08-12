"""Constrained HTTP source retrieval and content-addressed local storage."""

from __future__ import annotations

import hashlib
import os
import stat
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
    def __init__(
        self,
        snapshot_root: Path,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._root = snapshot_root
        self._owns_client = client is None
        self._client = client or httpx.Client(follow_redirects=False)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def retrieve(self, request: SourceRetrievalRequest) -> SourceRetrievalResult:
        parsed = urlsplit(request.canonical_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise DomainValidationError(
                "Source retrieval permits only absolute HTTP(S) URLs."
            )
        if parsed.username is not None or parsed.password is not None:
            raise DomainValidationError(
                "Source retrieval URLs must not contain credentials."
            )
        response = self._client.get(request.canonical_url, follow_redirects=False)
        response.raise_for_status()
        content = response.content
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
            version_label=response.headers.get("etag")
            or response.headers.get("last-modified"),
        )

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
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
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
