import json

from exam_practice import build

MEDIA_ONE = """
<html><body>
<article class="comment" data-author="alice"><div class="comment-content">
  <div class="bbWrapper">A</div></div></article>
<article class="comment" data-author="bob"><div class="comment-content">
  <div class="bbWrapper">A</div></div></article>
<article class="comment" data-author="carol"><div class="comment-content">
  <div class="bbWrapper">B</div></div></article>
</body></html>
"""

MEDIA_TWO = """
<html><body>
<article class="comment" data-author="alice"><div class="comment-content">
  <div class="bbWrapper">B</div></div></article>
<article class="comment" data-author="bob"><div class="comment-content">
  <div class="bbWrapper">B, C</div></div></article>
<article class="comment" data-author="carol"><div class="comment-content">
  <div class="bbWrapper">B, C</div></div></article>
</body></html>
"""


def _manifest() -> dict:
    return {
        "code": "hcm202-q2-6",
        "title": "Đề Thi PT - HCM202 - Q2 - 6",
        "url": "https://fuoverflow.com/threads/hcm202-q2-6.2757/",
        "generated": "2026-10-09T00:00:00+00:00",
        "thread_files": [],
        "attachments": [
            {
                "index": 1,
                "filename": "exam.webp",
                "image_file": "images/q01.webp",
                "media_file": "raw/media-01.html",
                "media_path": "/media/thread-webp.70478/",
                "post_url": "https://fuoverflow.com/threads/hcm202-q2-6.2757/post-5495#attachment-147969",
            },
            {
                "index": 2,
                "filename": "exam.webp",
                "image_file": "images/q02.webp",
                "media_file": "raw/media-02.html",
                "media_path": "/media/thread-webp.70479/",
                "post_url": "https://fuoverflow.com/threads/hcm202-q2-6.2757/post-5495#attachment-147970",
            },
        ],
        "posts": [],
    }


def _write_media(exam_dir):
    raw = exam_dir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "media-01.html").write_text(MEDIA_ONE, encoding="utf-8")
    (raw / "media-02.html").write_text(MEDIA_TWO, encoding="utf-8")


def test_build_exam_cross_checks_votes(tmp_path):
    _write_media(tmp_path)
    data = build.build_exam(_manifest(), tmp_path, minutes=30)

    assert data["code"] == "hcm202-q2-6"
    assert data["default_duration_min"] == 30
    assert data["stats"] == {"questions": 2, "answered": 2, "contested": 0, "multi": 1, "votes": 6}

    first, second = data["questions"]
    assert first["answer"] == ["A"] and first["image"] == "images/q01.webp"
    assert first["source"] == "https://fuoverflow.com/threads/hcm202-q2-6.2757/post-5495#attachment-147969"
    assert first["media"] == "https://fuoverflow.com/media/thread-webp.70478/"
    assert first["letter_votes"] == {"A": 2, "B": 1}
    assert second["answer"] == ["B", "C"] and second["multi"] is True
    assert second["image"] == "images/q02.webp"
    assert second["source"] == "https://fuoverflow.com/threads/hcm202-q2-6.2757/post-5495#attachment-147970"
    assert second["media"] == "https://fuoverflow.com/media/thread-webp.70479/"


def test_unanswered_question_has_no_key(tmp_path):
    _write_media(tmp_path)
    manifest = _manifest()
    manifest["attachments"][1]["media_file"] = None
    data = build.build_exam(manifest, tmp_path, minutes=45)
    assert data["stats"]["questions"] == 2
    assert data["stats"]["answered"] == 1
    assert data["questions"][0]["answer"] == ["A"]
    assert data["questions"][1]["answer"] == []
    assert data["questions"][1]["contested"] is True


def test_source_falls_back_when_no_links(tmp_path):
    _write_media(tmp_path)
    manifest = _manifest()
    manifest["attachments"][0].pop("post_url")
    manifest["attachments"][0].pop("media_path")
    data = build.build_exam(manifest, tmp_path, minutes=45)
    assert data["questions"][0]["source"] == manifest["url"]
    assert data["questions"][0]["media"] is None


def test_questions_override_maps_extra_questions(tmp_path):
    _write_media(tmp_path)
    manifest = _manifest()
    manifest["posts"] = [{"author": "u", "text": "Câu 4: D"}]
    data = build.build_exam(manifest, tmp_path, minutes=45, questions=4)
    assert data["stats"]["questions"] == 4
    assert data["questions"][3]["answer"] == ["D"]


def test_write_exam_and_index(tmp_path):
    exam_dir = tmp_path / "exams" / "hcm202-q2-6"
    _write_media(exam_dir)
    build.write_exam(exam_dir, build.build_exam(_manifest(), exam_dir, minutes=15))

    assert json.loads((exam_dir / "data.json").read_text(encoding="utf-8"))["code"] == "hcm202-q2-6"
    assert (exam_dir / "data.js").read_text(encoding="utf-8").startswith("window.EXAM_DATA=")
    assert json.loads((exam_dir / "exam.json").read_text(encoding="utf-8"))["default_duration_min"] == 15

    entries = build.write_index(tmp_path / "exams")
    assert [e["code"] for e in entries] == ["hcm202-q2-6"]
    assert "window.EXAM_INDEX" in (tmp_path / "exams" / "index.js").read_text(encoding="utf-8")


def test_text_view_unions_text_and_ignores_watermark(tmp_path):
    from PIL import Image, ImageDraw

    paths = []
    for name, rect in (("a.png", (40, 20, 200, 60)), ("b.png", (50, 30, 300, 120))):
        image = Image.new("RGB", (800, 400), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle(rect, fill="black")
        draw.rectangle((0, 340, 100, 399), fill="black")  # watermark corner
        image.save(tmp_path / name)
        paths.append(tmp_path / name)

    view = build.text_view(paths)
    assert view == {"x": 24, "y": 4, "w": 293, "h": 133, "width": 800, "height": 400}


def test_text_view_none_when_sizes_differ_or_missing(tmp_path):
    from PIL import Image

    Image.new("RGB", (100, 50), "black").save(tmp_path / "a.png")
    Image.new("RGB", (200, 50), "black").save(tmp_path / "b.png")
    assert build.text_view([tmp_path / "a.png", tmp_path / "b.png"]) is None
    assert build.text_view([tmp_path / "missing.png"]) is None
