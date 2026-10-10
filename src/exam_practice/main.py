"""HTTP API (FastAPI/uvicorn): ``POST /api/crawl`` adds an exam from the web form.

Also serves ``exams/`` and the static app, so ``uvicorn exam_practice.main:app``
alone is a working site; in dev, Vite on :5173 proxies ``/api`` and ``/exams`` here.
Bind to localhost only: a request may carry the user's FuOverflow login cookie.

Hosted on Vercel (``BLOB_READ_WRITE_TOKEN`` set) the same app is shared by many
users without accounts: each crawl must bring the user's own cookie (never the
server's), exams live in Vercel Blob, and rename/delete are refused because any
visitor could otherwise wipe everyone's exams. Vercel's CDN serves ``src/web``.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import crawler, paths
from .app_config import AppConfig, app_config
from .exams.blob_storage import BlobExamStorage
from .exams.exam_service import CrawlExam, ExamService
from .exams.local_storage import LocalExamStorage
from .exams.router import api_router, blob_files_router
from .exams.storage import ExamStorage


def create_app(configuration: AppConfig = app_config, crawl_exam: CrawlExam = crawler.crawl_exam) -> FastAPI:
    logging.basicConfig(level=configuration.log.level, format="%(asctime)s %(levelname)-8s %(name)s: %(message)s")
    storage: ExamStorage
    if configuration.hosted:
        storage = BlobExamStorage(configuration.blob_read_write_token, paths.EXAMS)
    else:
        storage = LocalExamStorage(paths.EXAMS, paths.REGISTRY)

    app = FastAPI(title="exam-practice")
    app.state.hosted = configuration.hosted
    app.state.exam_storage = storage
    app.state.needs_visitor_cookie = configuration.needs_visitor_cookie
    app.state.exam_service = ExamService(
        storage=storage, crawl_exam=crawl_exam, cookie_file=paths.COOKIES, shared_cookie=configuration.fuoverflow_cookie
    )
    app.include_router(api_router)
    if configuration.hosted:
        app.include_router(blob_files_router)
        return app

    paths.EXAMS.mkdir(parents=True, exist_ok=True)
    app.mount("/exams", StaticFiles(directory=paths.EXAMS), name="exams")
    app.mount("/", StaticFiles(directory=paths.WEB, html=True), name="web")
    return app


app = create_app()
