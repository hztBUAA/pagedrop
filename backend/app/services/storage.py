"""Storage backends for binary assets.

Only a local-disk backend exists today. The Protocol keeps callers decoupled so
an S3/R2 backend can be dropped in later by config alone.
"""

from pathlib import Path
from typing import Protocol

from app.core.config import settings


class StorageBackend(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...


class LocalDiskBackend:
    def __init__(self, root: str):
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        # Keys are server-generated (workspace/hash-prefix/hash) — never user input.
        return self.root / key

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


_backend: StorageBackend | None = None


def get_backend() -> StorageBackend:
    global _backend
    if _backend is None:
        _backend = LocalDiskBackend(settings.assets_dir)
    return _backend
