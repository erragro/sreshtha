"""Storage backends for uploaded contract files.

`Storage` is a small protocol — save/load/delete by opaque key. The
LocalStorage implementation writes to a directory tree on disk. A future
GCSStorage will follow the same shape for Cloud Run without any change
to the service or route code.

Key convention (mirrors what a future GCS layout will use):
    contracts/{user_id}/{contract_id}.{ext}

That way `gsutil cp -r` from a Cloud Run bucket into a local dir gives
you a working local corpus, and the reverse works too. No metadata is
encoded in the filename — mime type + original filename live in the DB.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class Storage(Protocol):
    """Minimal file-blob interface. All methods are synchronous — file
    sizes are capped at 10 MB (see settings.contract_max_bytes) so
    streaming would be premature complexity."""

    def save(self, key: str, content: bytes) -> None: ...

    def load(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None:
        """Idempotent — no error if the key is already gone."""
        ...

    def exists(self, key: str) -> bool: ...


# ---------------------------------------------------------------------------
# Local implementation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LocalStorage:
    """Writes to a directory tree rooted at `root`. Creates parent
    directories on save; treats missing files on delete as success."""

    root: Path

    def _abs(self, key: str) -> Path:
        # Defence against key traversal — every key must be relative and
        # resolve inside root. A key with '..' in it is rejected before
        # touching the filesystem.
        _validate_key(key)
        p = (self.root / key).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise ValueError(f"storage key escapes root: {key!r}")
        return p

    def save(self, key: str, content: bytes) -> None:
        path = self._abs(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write atomically via tempfile + rename so a crashed writer never
        # leaves a half-written file at the target path.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(content)
        os.replace(tmp, path)

    def load(self, key: str) -> bytes:
        return self._abs(key).read_bytes()

    def delete(self, key: str) -> None:
        try:
            self._abs(key).unlink()
        except FileNotFoundError:
            return

    def exists(self, key: str) -> bool:
        return self._abs(key).is_file()


@dataclass(frozen=True)
class GCSStorage:
    """Google Cloud Storage implementation used by Cloud Run deployments."""

    bucket_name: str
    prefix: str = ""

    def _blob(self, key: str):
        _validate_key(key)
        from google.cloud import storage  # deferred for local development

        name = f"{self.prefix}/{key}" if self.prefix else key
        return storage.Client().bucket(self.bucket_name).blob(name)

    def save(self, key: str, content: bytes) -> None:
        self._blob(key).upload_from_string(content)

    def load(self, key: str) -> bytes:
        return self._blob(key).download_as_bytes()

    def delete(self, key: str) -> None:
        from google.api_core.exceptions import NotFound

        try:
            self._blob(key).delete()
        except NotFound:
            return

    def exists(self, key: str) -> bool:
        return bool(self._blob(key).exists())


def _validate_key(key: str) -> None:
    if not key or key.startswith("/") or ".." in key.split("/"):
        raise ValueError(f"invalid storage key: {key!r}")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_storage(root: str) -> Storage:
    """Build local or persistent GCS storage from the configured root."""
    if root.startswith("gs://"):
        parsed = urlparse(root)
        if not parsed.netloc:
            raise ValueError("GCS storage root must include a bucket name")
        return GCSStorage(
            bucket_name=parsed.netloc,
            prefix=parsed.path.strip("/"),
        )
    return LocalStorage(root=Path(root).resolve())


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------


def build_key(user_id: uuid.UUID, contract_id: uuid.UUID, extension: str) -> str:
    """Assemble the storage key for a new contract. Extension is
    normalised to lowercase, dot-prefixed."""
    ext = extension.lstrip(".").lower()
    if not ext or not ext.isalnum() or len(ext) > 8:
        raise ValueError(f"invalid extension: {extension!r}")
    return f"contracts/{user_id}/{contract_id}.{ext}"
