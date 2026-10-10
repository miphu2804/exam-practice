"""HTTP API (FastAPI/uvicorn): ``POST /api/crawl`` adds an exam from the web form.

Also serves ``exams/`` and the static app, so ``uvicorn exam_practice.server:app``
alone is a working site; in dev, Vite on :5173 proxies ``/api`` and ``/exams`` here.
Bind to localhost only: a request may carry the user's FuOverflow login cookie.

Hosted on Vercel (``BLOB_READ_WRITE_TOKEN`` set) the same app is shared by many
users without accounts: each crawl must bring the user's own cookie (never the
server's), exams live in Vercel Blob, and rename/delete are refused because any
visitor could otherwise wipe everyone's exams. Vercel's CDN serves ``src/web``.
"""

from __future__ import annotations

import shutil
import threading
from collections.abc import Callable
from contextlib import contextmanager, nullcontext
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import blobstore, build, catalog, crawler, paths, registry
from .fetch import LoginRequired, load_cookies
from .parse import slug_code

Crawl = Callable[[dict], dict]


@contextmanager
def _exclusive(lock: threading.Lock):
    if not lock.acquire(blocking=False):
        raise HTTPException(409, "Đang có thao tác khác (crawl/xóa/đổi tên), thử lại sau.")
    try:
        yield
    finally:
        lock.release()


class CrawlRequest(BaseModel):
    url: str
    name: str = ""
    minutes: int | None = None
    cookie: str = ""


class RenameRequest(BaseModel):
    title: str


def thread_url(raw: str) -> str | None:
    """Accept only FuOverflow thread links; the URL is fetched with the user's cookie."""
    url = urlparse(raw.strip())
    if url.scheme == "https" and url.hostname in ("fuoverflow.com", "www.fuoverflow.com") and url.path.startswith("/threads/"):
        return f"https://fuoverflow.com{url.path}"
    return None


def crawl_and_register(request: dict) -> dict:
    """Crawl a thread submitted from the web form and register it for ``--sync``."""
    entry = {
        "code": slug_code(request["url"]),
        "name": request["name"],
        "url": request["url"],
        "minutes": request["minutes"],
    }
    data = crawler.crawl_exam(entry, load_cookies(request["cookie"], paths.COOKIES))
    registry.register(paths.REGISTRY, entry)
    build.write_index(paths.EXAMS)
    print(build.report(data))
    return data


def crawl_and_publish(request: dict) -> dict:
    """Hosted crawl: the visitor's own cookie only, result copied to Blob."""
    if not request["cookie"]:
        raise LoginRequired("Dán cookie xf_user FuOverflow của bạn để crawl.")
    entry = {"code": slug_code(request["url"]), "name": request["name"], "url": request["url"], "minutes": request["minutes"]}
    data = crawler.crawl_exam(entry, load_cookies(request["cookie"], paths.COOKIES))
    exam_dir = paths.EXAMS / data["code"]
    try:
        blobstore.publish(exam_dir)
    finally:
        shutil.rmtree(exam_dir, ignore_errors=True)
    return data


def create_app(crawl: Crawl = crawl_and_register, *, hosted: bool = False) -> FastAPI:
    app = FastAPI(title="exam-practice")
    # Local: one write at a time, FuOverflow is rate-limited and every change rewrites
    # the index files. Hosted: crawls are independent (one Blob folder each), so
    # concurrent users must not block each other.
    lock = threading.Lock()

    def exclusive():
        return nullcontext() if hosted else _exclusive(lock)

    @app.get("/api/info")
    def info() -> dict:
        return {"hosted": hosted}

    @app.post("/api/crawl")
    def crawl_endpoint(body: CrawlRequest) -> dict:  # sync: runs in uvicorn's threadpool
        url = thread_url(body.url)
        if not url:
            raise HTTPException(400, "Link phải là thread FuOverflow: https://fuoverflow.com/threads/...")
        request = {
            "url": url,
            "name": body.name.strip(),
            "minutes": body.minutes if body.minutes and 1 <= body.minutes <= 240 else None,
            "cookie": body.cookie.strip(),
        }
        with exclusive():
            try:
                data = crawl(request)
            except LoginRequired as exc:
                raise HTTPException(401, str(exc)) from exc
            except crawler.CrawlError as exc:
                raise HTTPException(400, str(exc)) from exc
            except Exception as exc:
                raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc
        return {"code": data["code"], "title": data["title"], "stats": data["stats"]}

    @app.patch("/api/exams/{code}")
    def rename_endpoint(code: str, body: RenameRequest) -> dict:
        _refuse_when_hosted(hosted)
        title = body.title.strip()
        if not title:
            raise HTTPException(400, "Tên đề không được để trống.")
        with _exclusive(lock):
            catalog.rename(paths.EXAMS, paths.REGISTRY, code, title)
        return {"code": code, "title": title}

    @app.delete("/api/exams/{code}")
    def delete_endpoint(code: str) -> dict:
        _refuse_when_hosted(hosted)
        with _exclusive(lock):
            catalog.delete(paths.EXAMS, paths.REGISTRY, code)
        return {"code": code}

    @app.exception_handler(catalog.ExamNotFound)
    def exam_not_found(request, exc: catalog.ExamNotFound) -> JSONResponse:
        return JSONResponse({"detail": f"Không có đề {exc}."}, status_code=404)

    if hosted:
        @app.get("/exams/index.json")
        def hosted_index() -> list[dict]:
            return blobstore.index()

        @app.get("/exams/{path:path}")
        def hosted_exam_file(path: str) -> RedirectResponse:
            return RedirectResponse(blobstore.public_url(f"exams/{path}"), status_code=307)

        return app

    paths.EXAMS.mkdir(parents=True, exist_ok=True)
    app.mount("/exams", StaticFiles(directory=paths.EXAMS), name="exams")
    app.mount("/", StaticFiles(directory=paths.WEB, html=True), name="web")
    return app


def _refuse_when_hosted(hosted: bool) -> None:
    if hosted:
        raise HTTPException(403, "Bản deploy dùng chung không cho đổi tên/xóa đề; làm việc này trên máy chạy local.")


app = create_app(crawl_and_publish, hosted=True) if blobstore.enabled() else create_app()
