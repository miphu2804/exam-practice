import json

import pytest
from fastapi.testclient import TestClient

from exam_practice import build, main, paths, registry
from exam_practice.app_config import AppConfig
from exam_practice.crawler import CrawlError
from exam_practice.exams.blob_storage import BlobExamStorage
from exam_practice.exams.schema import thread_url
from exam_practice.fetch import LoginRequired

THREAD = "https://fuoverflow.com/threads/x.1/"
HOSTED_TOKEN = "vercel_blob_rw_StoreAbc_secret"
LOCAL = AppConfig(blob_read_write_token=None, fuoverflow_cookie=None)
HOSTED = AppConfig(blob_read_write_token=HOSTED_TOKEN, fuoverflow_cookie=None)
SHARED = AppConfig(blob_read_write_token=HOSTED_TOKEN, fuoverflow_cookie="site-login")


@pytest.fixture(autouse=True)
def exams(tmp_path, monkeypatch):
    """Local storage writes exams/ and registry.json and reads cookies.txt; keep all three in tmp_path."""
    root = tmp_path / "exams"
    root.mkdir()
    (root / "registry.json").write_text("[]\n", encoding="utf-8")
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("fuoverflow.com\tTRUE\t/\tTRUE\t0\txf_user\tabc\n", encoding="utf-8")
    monkeypatch.setattr(paths, "EXAMS", root)
    monkeypatch.setattr(paths, "REGISTRY", root / "registry.json")
    monkeypatch.setattr(paths, "COOKIES", cookie_file)
    return root


def client(crawl_exam):
    return TestClient(main.create_app(LOCAL, crawl_exam))


def hosted_client(crawl_exam):
    return TestClient(main.create_app(HOSTED, crawl_exam))


def crawled(code="x", title="X"):
    """Crawl data as ``crawler.crawl_exam`` returns it; the local save logs ``build.report`` of every key."""
    stats = {"questions": 1, "answered": 0, "contested": 0, "multi": 0, "votes": 0}
    return {"code": code, "title": title, "source": THREAD, "stats": stats, "questions": []}


def test_thread_url_accepts_only_fuoverflow_threads():
    assert thread_url(" https://fuoverflow.com/threads/x.1/?page=2 ") == THREAD
    assert thread_url("https://www.fuoverflow.com/threads/x.1/") == THREAD
    assert thread_url("http://fuoverflow.com/threads/x.1/") is None
    assert thread_url("https://evil.com/threads/x.1/") is None
    assert thread_url("https://fuoverflow.com/media/x.1/") is None


def test_crawl_returns_summary_and_normalized_request(exams):
    calls = []

    def crawl_exam(entry, cookies, progress):
        calls.append((entry, cookies))
        return crawled()

    response = client(crawl_exam).post("/api/crawl", json={"url": THREAD, "name": " X ", "minutes": 300})
    assert response.status_code == 200
    assert response.json() == {"code": "x", "title": "X", "stats": crawled()["stats"]}
    assert calls == [({"code": "x", "name": "X", "url": THREAD, "minutes": None}, {"xf_user": "abc"})]
    assert [entry["code"] for entry in registry.load(exams / "registry.json")] == ["x"]


def test_crawl_stream_reports_progress_then_result(exams):
    def crawl_exam(entry, cookies, progress):
        progress(0, 2, "Tải trang thread 1/1")
        progress(1, 2, "Tải ảnh và bình luận 1/1")
        return crawled()

    response = client(crawl_exam).post("/api/crawl/stream", json={"url": THREAD})
    events = [json.loads(line) for line in response.text.splitlines()]
    assert response.headers["content-type"] == "application/x-ndjson"
    assert events == [
        {"done": 0, "total": 2, "label": "Tải trang thread 1/1"},
        {"done": 1, "total": 2, "label": "Tải ảnh và bình luận 1/1"},
        {"result": {"code": "x", "title": "X", "stats": crawled()["stats"]}},
    ]


def test_crawl_stream_ends_with_the_error_status():
    def crawl_exam(entry, cookies, progress):
        raise LoginRequired("cookie hết hạn")

    response = client(crawl_exam).post("/api/crawl/stream", json={"url": THREAD})
    assert [json.loads(line) for line in response.text.splitlines()] == [{"error": "cookie hết hạn", "status": 401}]
    assert client(crawl_exam).post("/api/crawl/stream", json={"url": "https://example.com/x"}).status_code == 400


def test_rejects_non_fuoverflow_url_without_crawling():
    calls = []
    response = client(calls.append).post("/api/crawl", json={"url": "https://example.com/threads/x.1/"})
    assert response.status_code == 400
    assert "fuoverflow" in response.json()["detail"]
    assert calls == []


def test_login_error_is_reported():
    def crawl_exam(entry, cookies, progress):
        raise LoginRequired("cookie hết hạn")

    response = client(crawl_exam).post("/api/crawl", json={"url": THREAD})
    assert (response.status_code, response.json()) == (401, {"detail": "cookie hết hạn"})


def test_serves_web_app_and_exams():
    app = client(lambda entry, cookies: {})
    assert "app.js" in app.get("/").text
    assert app.get("/exams/registry.json").status_code == 200


def test_unusable_thread_is_a_bad_request():
    def crawl_exam(entry, cookies, progress):
        raise CrawlError("Could not read the exam code")

    response = client(crawl_exam).post("/api/crawl", json={"url": THREAD})
    assert (response.status_code, response.json()) == (400, {"detail": "Could not read the exam code"})


def test_busy_storage_returns_conflict_without_crawling():
    calls = []
    app = main.create_app(LOCAL, lambda entry, cookies: calls.append(entry))

    with app.state.exam_storage.exclusive():
        response = TestClient(app).post("/api/crawl", json={"url": THREAD})

    assert (response.status_code, response.json()) == (409, {"detail": "Đang có thao tác khác (crawl/xóa/đổi tên), thử lại sau."})
    assert calls == []


def test_rename_and_delete_exam(exams):
    build.write_exam(exams / "demo", {"code": "demo", "title": "Old", "questions": []})
    app = client(lambda entry, cookies: {})

    assert app.patch("/api/exams/demo", json={"title": "  "}).status_code == 400
    assert app.patch("/api/exams/demo", json={"title": " Mới "}).json() == {"code": "demo", "title": "Mới"}
    assert app.get("/exams/index.json").json()[0]["title"] == "Mới"

    assert app.delete("/api/exams/demo").json() == {"code": "demo"}
    assert not (exams / "demo").exists()
    missing = app.delete("/api/exams/demo")
    assert (missing.status_code, missing.json()) == (404, {"detail": "Không có đề demo."})


def test_health_reports_ok():
    assert client(lambda entry, cookies: {}).get("/api/health").json() == {"status": "ok"}


def test_info_reports_mode():
    assert client(lambda entry, cookies: {}).get("/api/info").json() == {"hosted": False, "needs_cookie": False}
    assert hosted_client(lambda entry, cookies: {}).get("/api/info").json() == {"hosted": True, "needs_cookie": True}
    shared = TestClient(main.create_app(SHARED, lambda entry, cookies: {}))
    assert shared.get("/api/info").json() == {"hosted": True, "needs_cookie": False}


def test_hosted_crawl_requires_the_visitors_own_cookie():
    calls = []
    response = hosted_client(lambda entry, cookies: calls.append(cookies)).post("/api/crawl", json={"url": THREAD})
    assert response.status_code == 401
    assert "cookie" in response.json()["detail"]
    assert calls == []  # never falls back to cookies.txt or the server's Chrome


def test_hosted_crawl_uses_the_shared_cookie_unless_the_visitor_pastes_one(monkeypatch):
    monkeypatch.setattr(BlobExamStorage, "save", lambda self, entry, data: None)
    calls = []

    def crawl_exam(entry, cookies, progress):
        calls.append(cookies)
        return crawled()

    shared = TestClient(main.create_app(SHARED, crawl_exam))
    assert shared.post("/api/crawl", json={"url": THREAD}).status_code == 200
    assert shared.post("/api/crawl", json={"url": THREAD, "cookie": "mine"}).status_code == 200
    assert calls == [{"xf_user": "site-login"}, {"xf_user": "mine"}]


def test_hosted_crawl_publishes_and_cleans_tmp(exams, monkeypatch):
    published = []
    monkeypatch.setattr(BlobExamStorage, "_publish", lambda self, exam_dir: published.append(exam_dir.name))

    def crawl_exam(entry, cookies, progress):
        (exams / "x").mkdir()
        return {"code": "x", "title": "X", "stats": {}, "cookies": cookies}

    response = hosted_client(crawl_exam).post("/api/crawl", json={"url": THREAD, "cookie": "abc"})
    assert response.status_code == 200
    assert published == ["x"]
    assert not (exams / "x").exists()


def test_hosted_crawl_removes_tmp_even_when_publish_fails(exams, monkeypatch):
    def publish(self, exam_dir):
        raise OSError("blob down")

    def crawl_exam(entry, cookies, progress):
        (exams / "x").mkdir()
        return {"code": "x", "title": "X", "stats": {}}

    monkeypatch.setattr(BlobExamStorage, "_publish", publish)
    response = hosted_client(crawl_exam).post("/api/crawl", json={"url": THREAD, "cookie": "abc"})
    assert response.status_code == 500
    assert response.json() == {"detail": "OSError: blob down"}
    assert not (exams / "x").exists()


def test_hosted_refuses_rename_and_delete():
    app = hosted_client(lambda entry, cookies: {})
    assert app.patch("/api/exams/x", json={"title": "Y"}).status_code == 403
    assert app.patch("/api/exams/x", json={"title": " "}).status_code == 403  # refused before title validation
    assert app.delete("/api/exams/x").status_code == 403


def test_hosted_serves_index_from_blob_and_redirects_files(monkeypatch):
    monkeypatch.setattr(BlobExamStorage, "index", lambda self: [{"code": "x"}])
    app = hosted_client(lambda entry, cookies: {})
    assert app.get("/exams/index.json").json() == [{"code": "x"}]
    response = app.get("/exams/x/images/q01.png", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "https://storeabc.public.blob.vercel-storage.com/exams/x/images/q01.png"
