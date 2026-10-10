"""Fetch one exam thread into ``exams/<code>/`` (raw HTML, images, manifest)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from . import build, paths
from .fetch import LoginRequired, Session
from .parse import (
    Attachment,
    page_count,
    parse_attachments,
    parse_first_post_id,
    parse_posts,
    thread_meta,
)

IMAGE_EXTENSIONS = {".webp", ".png", ".jpg", ".jpeg", ".gif"}


class CrawlError(RuntimeError):
    """The thread cannot be turned into an exam (user-facing message)."""


# ``progress(done, total, label)``: one call per downloaded thread page or attachment.
Progress = Callable[[int, int, str], None]


def no_progress(done: int, total: int, label: str) -> None:
    pass


def crawl_exam(
    entry: dict,
    cookies: dict[str, str],
    *,
    delay: float = 0.6,
    no_images: bool = False,
    questions: int | None = None,
    default_minutes: int = 45,
    progress: Progress = no_progress,
) -> dict:
    """Crawl a registry-style entry and write its practice data; returns the data."""
    exam_dir, manifest = crawl_thread(
        entry["url"], cookies, delay=delay, no_images=no_images, code=entry.get("code"), progress=progress
    )
    if entry.get("name"):
        manifest["title"] = entry["name"]
    data = build.build_exam(manifest, exam_dir, minutes=entry.get("minutes") or default_minutes, questions=questions)
    build.write_exam(exam_dir, data)
    return data


def crawl_thread(
    url: str,
    cookies: dict[str, str],
    *,
    delay: float = 0.6,
    no_images: bool = False,
    code: str | None = None,
    progress: Progress = no_progress,
) -> tuple[Path, dict]:
    """Download a thread and its attachment media, returning (exam_dir, manifest)."""
    session = Session(cookies, delay=delay)
    with session:
        first = session.get_html(url)
        meta = thread_meta(first, url)
        code = code or meta.code
        if not code:
            raise CrawlError(f"Could not read the exam code from {url}")

        thread_path = urlparse(url).path.rstrip("/")
        post_id = parse_first_post_id(first)

        exam_dir = paths.EXAMS / code
        raw_dir = exam_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        pages = page_count(first)
        found = parse_attachments(first)
        total = pages + len(found)

        thread_files: list[str] = []
        posts: list[dict] = []
        for number in range(1, pages + 1):
            progress(number - 1, total, f"Tải trang thread {number}/{pages}")
            html = first if number == 1 else session.get_html(f"{urlparse(url).path}?page={number}")
            name = f"thread-p{number}.html"
            (raw_dir / name).write_text(html, encoding="utf-8")
            thread_files.append(f"raw/{name}")
            posts.extend({"author": post.author, "text": post.text} for post in parse_posts(html))

        attachments = []
        for done, attachment in enumerate(found, start=1):
            progress(pages + done - 1, total, f"Tải ảnh và bình luận {done}/{len(found)}")
            try:
                image_file = _download_image(session, exam_dir, attachment, skip=no_images)
                media_file = _fetch_media(session, raw_dir, attachment)
            except LoginRequired:
                raise
            except Exception as exc:  # one broken attachment must not abort the run
                print(f"warning: attachment {attachment.index} failed: {exc}")
                image_file = media_file = None
            attachments.append(
                {
                    "index": attachment.index,
                    "filename": attachment.filename,
                    "image_file": image_file,
                    "media_file": media_file,
                    "media_path": attachment.media_path,
                    "post_url": _post_url(thread_path, post_id, attachment),
                }
            )

    manifest = {
        "code": code,
        "title": meta.title,
        "url": meta.url or url,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "thread_files": thread_files,
        "attachments": attachments,
        "posts": posts,
    }
    (raw_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return exam_dir, manifest


def _post_url(thread_path: str, post_id: int | None, attachment: Attachment) -> str | None:
    """Deep link to the exact attachment inside its post, e.g. ``.../post-5495#attachment-147969``."""
    if not post_id or not attachment.attachment_id:
        return None
    return f"https://fuoverflow.com{thread_path}/post-{post_id}#attachment-{attachment.attachment_id}"


def _download_image(session: Session, exam_dir: Path, attachment: Attachment, *, skip: bool) -> str | None:
    if skip or not attachment.download_path:
        return None
    content = session.get_bytes(attachment.download_path)
    if not content:
        return None
    suffix = Path(attachment.filename).suffix.lower()
    extension = suffix if suffix in IMAGE_EXTENSIONS else ".webp"
    images = exam_dir / "images"
    images.mkdir(parents=True, exist_ok=True)
    target = images / f"q{attachment.index:02d}{extension}"
    target.write_bytes(content)
    return f"images/{target.name}"


def _fetch_media(session: Session, raw_dir: Path, attachment: Attachment) -> str | None:
    if not attachment.media_path:
        return None
    html = session.get_html(attachment.media_path)
    name = f"media-{attachment.index:02d}.html"
    (raw_dir / name).write_text(html, encoding="utf-8")
    return f"raw/{name}"
