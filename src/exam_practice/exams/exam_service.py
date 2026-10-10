"""Exam workflows (crawl, rename, delete): the steps shared by every storage."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

from ..crawler import Progress, no_progress
from ..fetch import LoginRequired, load_cookies
from ..parse import slug_code
from .storage import ExamStorage

logger = logging.getLogger(__name__)

# ``crawler.crawl_exam(entry, cookies, progress=...)``: fetches the thread and returns the practice data.
CrawlExam = Callable[..., dict]


class ExamService:
    def __init__(self, storage: ExamStorage, crawl_exam: CrawlExam, cookie_file: Path) -> None:
        self._storage = storage
        self._crawl_exam = crawl_exam
        self._cookie_file = cookie_file

    def crawl(self, url: str, name: str, minutes: int | None, cookie: str, progress: Progress = no_progress) -> dict:
        if self._storage.requires_visitor_cookie and not cookie:
            raise LoginRequired("Dán cookie xf_user FuOverflow của bạn để crawl.")
        entry = {"code": slug_code(url), "name": name, "url": url, "minutes": minutes}
        with self._storage.exclusive():
            logger.info("crawl start %s", entry["code"])
            started = time.perf_counter()
            cookies = load_cookies(cookie, self._cookie_file)
            data = self._crawl_exam(entry, cookies, progress=progress)
            self._storage.save(entry, data)
        logger.info(
            "crawl done %s in %.1fs: %s questions",
            entry["code"],
            time.perf_counter() - started,
            data.get("stats", {}).get("questions"),
        )
        return data

    def rename(self, code: str, title: str) -> None:
        with self._storage.exclusive():
            self._storage.rename(code, title)

    def delete(self, code: str) -> None:
        with self._storage.exclusive():
            self._storage.delete(code)
