"""Request and response models for the ``/api`` routes, and the crawl URL check."""

from __future__ import annotations

from urllib.parse import urlparse

from pydantic import BaseModel


class CrawlRequest(BaseModel):
    url: str
    name: str = ""
    minutes: int | None = None
    cookie: str = ""


class CrawlResponse(BaseModel):
    code: str
    title: str
    stats: dict


class RenameRequest(BaseModel):
    title: str


class RenameResponse(BaseModel):
    code: str
    title: str


class DeleteResponse(BaseModel):
    code: str


class InfoResponse(BaseModel):
    hosted: bool


class HealthResponse(BaseModel):
    status: str


def thread_url(raw: str) -> str | None:
    """Accept only FuOverflow thread links; the URL is fetched with the user's cookie."""
    url = urlparse(raw.strip())
    if url.scheme == "https" and url.hostname in ("fuoverflow.com", "www.fuoverflow.com") and url.path.startswith("/threads/"):
        return f"https://fuoverflow.com{url.path}"
    return None
