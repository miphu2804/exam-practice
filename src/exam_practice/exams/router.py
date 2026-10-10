"""HTTP routes: ``/api/*`` for the web app, and in hosted mode the Blob-backed ``/exams/*`` files."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from .. import catalog, crawler
from ..fetch import LoginRequired
from .blob_storage import BlobExamStorage
from .errors import ReadOnlyStorage, StorageBusy
from .exam_service import ExamService
from .schema import (
    CrawlRequest,
    CrawlResponse,
    DeleteResponse,
    HealthResponse,
    InfoResponse,
    RenameRequest,
    RenameResponse,
    thread_url,
)

logger = logging.getLogger(__name__)

BUSY_MESSAGE = "Đang có thao tác khác (crawl/xóa/đổi tên), thử lại sau."
READ_ONLY_MESSAGE = "Bản deploy dùng chung không cho đổi tên/xóa đề; làm việc này trên máy chạy local."

api_router = APIRouter(prefix="/api")
blob_files_router = APIRouter()


def get_exam_service(request: Request) -> ExamService:
    return request.app.state.exam_service


@api_router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@api_router.get("/info", response_model=InfoResponse)
def info(request: Request) -> InfoResponse:
    return InfoResponse(hosted=request.app.state.hosted)


@api_router.post("/crawl", response_model=CrawlResponse)
def crawl(body: CrawlRequest, service: ExamService = Depends(get_exam_service)) -> CrawlResponse:  # sync: runs in uvicorn's threadpool
    url = thread_url(body.url)
    if not url:
        raise HTTPException(400, "Link phải là thread FuOverflow: https://fuoverflow.com/threads/...")
    minutes = body.minutes if body.minutes and 1 <= body.minutes <= 240 else None
    try:
        data = service.crawl(url=url, name=body.name.strip(), minutes=minutes, cookie=body.cookie.strip())
    except LoginRequired as exc:
        raise HTTPException(401, str(exc)) from exc
    except crawler.CrawlError as exc:
        raise HTTPException(400, str(exc)) from exc
    except StorageBusy as exc:
        raise HTTPException(409, BUSY_MESSAGE) from exc
    except Exception as exc:
        logger.exception("crawl failed for %s", url)
        raise HTTPException(500, f"{type(exc).__name__}: {exc}") from exc
    return CrawlResponse(code=data["code"], title=data["title"], stats=data["stats"])


# Checked before the title: a hosted visitor gets 403 whatever the body contains.
@api_router.patch("/exams/{code}", response_model=RenameResponse)
def rename_exam(code: str, body: RenameRequest, request: Request, service: ExamService = Depends(get_exam_service)) -> RenameResponse:
    _refuse_when_hosted(request)
    title = body.title.strip()
    if not title:
        raise HTTPException(400, "Tên đề không được để trống.")
    with _storage_errors():
        service.rename(code, title)
    return RenameResponse(code=code, title=title)


@api_router.delete("/exams/{code}", response_model=DeleteResponse)
def delete_exam(code: str, request: Request, service: ExamService = Depends(get_exam_service)) -> DeleteResponse:
    _refuse_when_hosted(request)
    with _storage_errors():
        service.delete(code)
    return DeleteResponse(code=code)


@blob_files_router.get("/exams/index.json")
def hosted_index(request: Request) -> list[dict]:
    storage: BlobExamStorage = request.app.state.exam_storage
    return storage.index()


@blob_files_router.get("/exams/{path:path}")
def hosted_exam_file(path: str, request: Request) -> RedirectResponse:
    storage: BlobExamStorage = request.app.state.exam_storage
    return RedirectResponse(storage.public_url(f"exams/{path}"), status_code=307)


def _refuse_when_hosted(request: Request) -> None:
    if request.app.state.hosted:
        raise HTTPException(403, READ_ONLY_MESSAGE)


@contextmanager
def _storage_errors() -> Iterator[None]:
    try:
        yield
    except StorageBusy as exc:
        raise HTTPException(409, BUSY_MESSAGE) from exc
    except ReadOnlyStorage as exc:
        raise HTTPException(403, READ_ONLY_MESSAGE) from exc
    except catalog.ExamNotFound as exc:
        raise HTTPException(404, f"Không có đề {exc}.") from exc
