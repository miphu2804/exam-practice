"""Exam storage in Vercel Blob for the hosted (Vercel) deployment.

A Vercel function only has a throwaway ``/tmp``, so a crawl still writes
``exams/<code>/`` there and the files the browser needs are copied to Blob under
the same ``exams/<code>/...`` paths the local site serves. ``raw/`` stays out: it
only feeds ``--rebuild``, which runs locally.
"""

from __future__ import annotations

import mimetypes
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from vercel import blob

TOKEN_ENV = "BLOB_READ_WRITE_TOKEN"
PUBLISHED = ("exam.json", "data.json", "data.js")
# A re-crawl overwrites files in place; the Blob CDN may serve the old copy this long.
MAX_AGE_SECONDS = 60


def enabled() -> bool:
    return bool(os.environ.get(TOKEN_ENV))


def public_url(path: str) -> str:
    """Public URL of ``path`` in the store; the store id is the 4th ``_`` field of the token."""
    store_id = os.environ[TOKEN_ENV].split("_")[3].lower()
    return f"https://{store_id}.public.blob.vercel-storage.com/{path}"


def publish(exam_dir: Path) -> None:
    """Upload one crawled exam's browser-facing files to ``exams/<code>/``."""
    files = [exam_dir / name for name in PUBLISHED if (exam_dir / name).exists()]
    files += sorted((exam_dir / "images").glob("*"))
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(lambda path: _put(path, exam_dir.parent), files))


def _put(path: Path, root: Path) -> None:
    blob.put(
        f"exams/{path.relative_to(root).as_posix()}",
        path.read_bytes(),
        access="public",
        content_type=mimetypes.guess_type(path.name)[0],
        overwrite=True,
        cache_control_max_age=MAX_AGE_SECONDS,
    )


def index() -> list[dict]:
    """Summaries of every stored exam, like ``exams/index.json`` locally."""
    urls = [item.url for item in blob.iter_objects(prefix="exams/") if item.pathname.endswith("/exam.json")]
    with httpx.Client(timeout=10) as client, ThreadPoolExecutor(8) as pool:
        entries = list(pool.map(lambda url: client.get(url).raise_for_status().json(), urls))
    return sorted((e for e in entries if e.get("code")), key=lambda e: e["code"])
