from fastapi.testclient import TestClient

from exam_practice import server
from exam_practice.fetch import LoginRequired

THREAD = "https://fuoverflow.com/threads/x.1/"


def client(crawl):
    return TestClient(server.create_app(crawl))


def test_thread_url_accepts_only_fuoverflow_threads():
    assert server.thread_url(" https://fuoverflow.com/threads/x.1/?page=2 ") == THREAD
    assert server.thread_url("https://www.fuoverflow.com/threads/x.1/") == THREAD
    assert server.thread_url("http://fuoverflow.com/threads/x.1/") is None
    assert server.thread_url("https://evil.com/threads/x.1/") is None
    assert server.thread_url("https://fuoverflow.com/media/x.1/") is None


def test_crawl_returns_summary_and_normalized_request():
    calls = []

    def crawl(request):
        calls.append(request)
        return {"code": "x", "title": "X", "stats": {"questions": 1}}

    response = client(crawl).post("/api/crawl", json={"url": THREAD, "name": " X ", "minutes": 300})
    assert response.status_code == 200
    assert response.json() == {"code": "x", "title": "X", "stats": {"questions": 1}}
    assert calls == [{"url": THREAD, "name": "X", "minutes": None, "cookie": ""}]


def test_rejects_non_fuoverflow_url_without_crawling():
    calls = []
    response = client(calls.append).post("/api/crawl", json={"url": "https://example.com/threads/x.1/"})
    assert response.status_code == 400
    assert "fuoverflow" in response.json()["detail"]
    assert calls == []


def test_login_error_is_reported():
    def crawl(request):
        raise LoginRequired("cookie hết hạn")

    response = client(crawl).post("/api/crawl", json={"url": THREAD})
    assert (response.status_code, response.json()) == (401, {"detail": "cookie hết hạn"})


def test_serves_web_app_and_exams():
    app = client(lambda r: {})
    assert "app.js" in app.get("/").text
    assert app.get("/exams/registry.json").status_code == 200


def test_unusable_thread_is_a_bad_request():
    from exam_practice.crawler import CrawlError

    def crawl(request):
        raise CrawlError("Could not read the exam code")

    response = client(crawl).post("/api/crawl", json={"url": THREAD})
    assert (response.status_code, response.json()) == (400, {"detail": "Could not read the exam code"})


def test_rename_and_delete_exam(tmp_path, monkeypatch):
    from exam_practice import build, paths

    monkeypatch.setattr(paths, "EXAMS", tmp_path)
    monkeypatch.setattr(paths, "REGISTRY", tmp_path / "registry.json")
    build.write_exam(tmp_path / "demo", {"code": "demo", "title": "Old", "questions": []})
    app = client(lambda r: {})

    assert app.patch("/api/exams/demo", json={"title": "  "}).status_code == 400
    assert app.patch("/api/exams/demo", json={"title": " Mới "}).json() == {"code": "demo", "title": "Mới"}
    assert app.get("/exams/index.json").json()[0]["title"] == "Mới"

    assert app.delete("/api/exams/demo").json() == {"code": "demo"}
    assert not (tmp_path / "demo").exists()
    missing = app.delete("/api/exams/demo")
    assert (missing.status_code, missing.json()) == (404, {"detail": "Không có đề demo."})


def hosted_client(crawl, monkeypatch):
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "vercel_blob_rw_StoreAbc_secret")
    return TestClient(server.create_app(crawl, hosted=True))


def test_info_reports_mode(monkeypatch):
    assert client(lambda r: {}).get("/api/info").json() == {"hosted": False}
    assert hosted_client(lambda r: {}, monkeypatch).get("/api/info").json() == {"hosted": True}


def test_hosted_crawl_requires_the_visitors_own_cookie(monkeypatch):
    calls = []
    monkeypatch.setattr(server.crawler, "crawl_exam", lambda entry, cookies: calls.append(cookies))
    response = hosted_client(server.crawl_and_publish, monkeypatch).post("/api/crawl", json={"url": THREAD})
    assert response.status_code == 401
    assert "cookie" in response.json()["detail"]
    assert calls == []  # never falls back to cookies.txt or the server's Chrome


def test_hosted_crawl_publishes_and_cleans_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(server.paths, "EXAMS", tmp_path)
    published = []

    def crawl_exam(entry, cookies):
        (tmp_path / "x").mkdir()
        return {"code": "x", "title": "X", "stats": {}, "cookies": cookies}

    monkeypatch.setattr(server.crawler, "crawl_exam", crawl_exam)
    monkeypatch.setattr(server.blobstore, "publish", lambda exam_dir: published.append(exam_dir.name))
    response = hosted_client(server.crawl_and_publish, monkeypatch).post("/api/crawl", json={"url": THREAD, "cookie": "abc"})
    assert response.status_code == 200
    assert published == ["x"]
    assert not (tmp_path / "x").exists()


def test_hosted_refuses_rename_and_delete(monkeypatch):
    app = hosted_client(lambda r: {}, monkeypatch)
    assert app.patch("/api/exams/x", json={"title": "Y"}).status_code == 403
    assert app.delete("/api/exams/x").status_code == 403


def test_hosted_serves_index_from_blob_and_redirects_files(monkeypatch):
    monkeypatch.setattr(server.blobstore, "index", lambda: [{"code": "x"}])
    app = hosted_client(lambda r: {}, monkeypatch)
    assert app.get("/exams/index.json").json() == [{"code": "x"}]
    response = app.get("/exams/x/images/q01.png", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "https://storeabc.public.blob.vercel-storage.com/exams/x/images/q01.png"
