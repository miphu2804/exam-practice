"""The storage strategy ``ExamService`` writes through: a local folder or hosted Blob."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol


class ExamStorage(Protocol):
    # Hosted: a crawl must use the visitor's own cookie, never the server's.
    requires_visitor_cookie: bool

    def exclusive(self) -> AbstractContextManager[None]:
        """Guard one write; the local storage refuses a second one instead of queueing it."""

    def save(self, entry: dict, data: dict) -> None:
        """Store a crawl that ``crawler.crawl_exam`` has just written to ``exams/<code>``."""

    def rename(self, code: str, title: str) -> None: ...

    def delete(self, code: str) -> None: ...
