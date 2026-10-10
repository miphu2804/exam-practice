"""Exams on the local disk: ``exams/<code>/``, ``registry.json`` and the index files."""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .. import build, catalog, registry
from .errors import StorageBusy

logger = logging.getLogger(__name__)


class LocalExamStorage:
    requires_visitor_cookie = False

    def __init__(self, exams_dir: Path, registry_path: Path) -> None:
        self._exams_dir = exams_dir
        self._registry_path = registry_path
        # Every change rewrites the index files and FuOverflow is rate-limited, so writes never overlap.
        self._lock = threading.Lock()

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        if not self._lock.acquire(blocking=False):
            raise StorageBusy()
        try:
            yield
        finally:
            self._lock.release()

    def save(self, entry: dict, data: dict) -> None:
        registry.register(self._registry_path, entry)
        build.write_index(self._exams_dir)
        logger.info("%s", build.report(data))

    def rename(self, code: str, title: str) -> None:
        catalog.rename(self._exams_dir, self._registry_path, code, title)

    def delete(self, code: str) -> None:
        catalog.delete(self._exams_dir, self._registry_path, code)
