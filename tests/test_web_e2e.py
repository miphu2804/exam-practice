"""End-to-end checks of every action in the web app, in the installed Chrome.

The real FastAPI app serves ``src/web`` and a temporary ``exams/`` fixture; only
the crawl itself is replaced, so no FuOverflow access or cookie is needed.
"""

import json
import shutil
import socket
import threading
import time

import pytest
import uvicorn
from PIL import Image, ImageDraw

from exam_practice import build, main, paths
from exam_practice.app_config import AppConfig
from exam_practice.exams.blob_storage import BlobExamStorage
from exam_practice.fetch import LoginRequired

playwright = pytest.importorskip("playwright.sync_api")
expect = playwright.expect

THREAD = "https://fuoverflow.com/threads/demo.1/"
LOCAL = AppConfig(blob_read_write_token=None)
HOSTED = AppConfig(blob_read_write_token="vercel_blob_rw_StoreAbc_secret")
# n, answer, votes; question 3 takes two answers, question 4 has no answer key.
QUESTIONS = [(1, ["A"], {"A": 5, "B": 1}), (2, ["C"], {"C": 4}), (3, ["B", "D"], {"B": 3, "D": 3}), (4, [], {})]


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        try:
            chrome = p.chromium.launch(channel="chrome")
        except Exception as exc:
            pytest.skip(f"Google Chrome not available: {exc}")
        yield chrome
        chrome.close()


@pytest.fixture
def exams(tmp_path, monkeypatch):
    root = tmp_path / "exams"
    monkeypatch.setattr(paths, "EXAMS", root)
    monkeypatch.setattr(paths, "REGISTRY", root / "registry.json")
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("fuoverflow.com\tTRUE\t/\tTRUE\t0\txf_user\tabc\n", encoding="utf-8")
    monkeypatch.setattr(paths, "COOKIES", cookie_file)
    write_exam(root, "demo", "Demo exam", QUESTIONS)
    build.write_index(root)
    return root


@pytest.fixture
def crawls(exams):
    """(entry, cookies) pairs the fake crawl received; a URL containing ``login`` fails like an expired cookie."""
    return []


@pytest.fixture
def site(exams, crawls):
    def fake_crawl(entry, cookies):
        crawls.append((entry, cookies))
        if "login" in entry["url"]:
            raise LoginRequired("cookie hết hạn")
        data = write_exam(exams, "new-exam", entry["name"] or "new-exam", QUESTIONS[:1], entry["minutes"] or 45)
        build.write_index(exams)
        return data

    port = free_port()
    uv = uvicorn.Server(uvicorn.Config(main.create_app(LOCAL, fake_crawl), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=uv.run, daemon=True)
    thread.start()
    while not uv.started:
        time.sleep(0.02)
    yield f"http://127.0.0.1:{port}"
    uv.should_exit = True
    thread.join()


@pytest.fixture
def page(browser, site):
    context = browser.new_context(viewport={"width": 1348, "height": 840})
    tab = context.new_page()
    errors = []
    tab.on("pageerror", lambda exc: errors.append(str(exc)))
    tab.goto(site + "/")
    yield tab
    context.close()
    assert errors == [], errors


def write_exam(root, code, title, questions, minutes=45):
    exam_dir = root / code
    (exam_dir / "images").mkdir(parents=True, exist_ok=True)
    items = []
    for n, answer, votes in questions:
        image = Image.new("RGB", (800, 300), "white")
        ImageDraw.Draw(image).rectangle((20, 20, 300, 90), fill="black")
        image.save(exam_dir / "images" / f"q{n:02d}.png")
        items.append(
            {
                "n": n,
                "image": f"images/q{n:02d}.png",
                "source": f"{THREAD}post-1#attachment-{n}",
                "media": f"https://fuoverflow.com/media/q{n}.{n}/",
                "choices": ["A", "B", "C", "D"],
                "type": "multi" if len(answer) > 1 else "single",
                "answer": answer,
                "multi": len(answer) > 1,
                "pick": len(answer) or None,
                "contested": False,
                "letter_votes": {c: votes.get(c, 0) for c in "ABCD"},
                "vote_count": sum(votes.values()),
                "evidence": [{"author": f"u{c}{i}", "letters": [c], "text": f"chọn {c}"}
                             for c, count in votes.items() for i in range(count)],
            }
        )
    data = {
        "code": code,
        "title": title,
        "source": THREAD,
        "generated": "2026-10-10T00:00:00+00:00",
        "default_duration_min": minutes,
        "choices": ["A", "B", "C", "D"],
        "stats": {"questions": len(items), "answered": sum(1 for q in items if q["answer"]), "contested": 0,
                  "multi": sum(1 for q in items if q["multi"]), "votes": sum(q["vote_count"] for q in items)},
        "view": build.text_view([exam_dir / q["image"] for q in items]),
        "questions": items,
    }
    build.write_exam(exam_dir, data)
    return data


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def card(page, title):
    return page.locator(".exam-card", has_text=title)


def open_demo(page, mode=None, minutes=None):
    card(page, "Demo exam").locator(".exam-main").click()
    if mode:
        page.locator(".chip.mode", has_text=mode).click()
    if minutes:
        page.fill("#minutes", str(minutes))
    page.click("#start")
    expect(page.locator("#counter")).to_contain_text("01")


def choice(page, letter):
    return page.locator(f'#choices .choice[data-c="{letter}"]')


def dot(page, n):
    return page.locator("#dots .dot", has_text=str(n)).first


# --------------------------------------------------------------------------- #
# Picker and crawl form
# --------------------------------------------------------------------------- #
def test_picker_lists_exams(page):
    expect(page.locator("h1")).to_have_text("Chọn đề để làm")
    expect(page.locator("#quiz-controls")).to_be_hidden()
    card = page.locator(".exam-card")
    expect(card).to_have_count(1)
    expect(card).to_contain_text("Demo exam")
    expect(card).to_contain_text("3/4")


def test_crawl_form_reports_bad_link_and_login_errors(page, crawls):
    status = page.locator("#crawl-status")
    page.fill('#crawl input[name="url"]', "https://example.com/threads/x.1/")
    page.click("#crawl button[type=submit]")
    expect(status).to_contain_text("Link phải là thread FuOverflow")
    expect(status).to_have_attribute("data-tone", "bad")

    page.fill('#crawl input[name="url"]', "https://fuoverflow.com/threads/login.2/")
    page.click("#crawl button[type=submit]")
    expect(status).to_have_text("cookie hết hạn")
    expect(page.locator("#crawl button[type=submit]")).to_be_enabled()
    assert [entry["url"] for entry, _ in crawls] == ["https://fuoverflow.com/threads/login.2/"]


def test_crawl_form_adds_exam_and_opens_it(page, crawls):
    page.fill('#crawl input[name="url"]', "https://www.fuoverflow.com/threads/new-exam.9/?page=2")
    page.click("#crawl summary")
    page.fill('#crawl input[name="name"]', "Đề mới")
    page.fill('#crawl input[name="minutes"]', "30")
    page.fill('#crawl input[name="cookie"]', "secret-xf-user")
    page.click("#crawl button[type=submit]")

    expect(page.locator(".start h1")).to_have_text("Đề mới")
    expect(page.locator("#minutes")).to_have_value("30")
    assert crawls == [
        ({"code": "new-exam", "name": "Đề mới", "url": "https://fuoverflow.com/threads/new-exam.9/", "minutes": 30}, {"xf_user": "secret-xf-user"})
    ]

    page.click("#back")
    expect(page.locator(".exam-card")).to_have_count(2)


def test_empty_index_shows_only_the_crawl_form(page, exams):
    shutil.rmtree(exams / "demo")
    build.write_index(exams)
    page.reload()
    expect(page.locator("h1")).to_have_text("Chưa có đề nào")
    expect(page.locator("#crawl")).to_be_visible()
    expect(page.locator(".exam-card")).to_have_count(0)


def test_exam_without_questions_shows_empty_screen(page, exams):
    (exams / "ghost").mkdir()
    (exams / "ghost" / "exam.json").write_text(json.dumps({"code": "ghost", "title": "Ghost"}), encoding="utf-8")
    build.write_index(exams)
    page.reload()
    card(page, "Ghost").locator(".exam-main").click()
    expect(page.locator(".empty")).to_contain_text("chưa có câu hỏi")
    page.click("#back")
    expect(page.locator("h1")).to_have_text("Chọn đề để làm")


def test_rename_exam_from_picker(page, exams):
    page.once("dialog", lambda dialog: dialog.dismiss())
    card(page, "Demo exam").locator("[data-act=rename]").click()
    expect(card(page, "Demo exam")).to_be_visible()

    page.once("dialog", lambda dialog: dialog.accept("  Đề đã đổi tên  "))
    card(page, "Demo exam").locator("[data-act=rename]").click()
    expect(page.locator(".exam-card h3")).to_have_text("Đề đã đổi tên")
    assert json.loads((exams / "demo" / "data.json").read_text(encoding="utf-8"))["title"] == "Đề đã đổi tên"

    card(page, "Đề đã đổi tên").locator(".exam-main").click()
    expect(page.locator(".start h1")).to_have_text("Đề đã đổi tên")


def test_delete_exam_asks_first(page, exams):
    messages = []

    def answer(dialog, accept):
        messages.append(dialog.message)
        dialog.accept() if accept else dialog.dismiss()

    page.once("dialog", lambda dialog: answer(dialog, False))
    card(page, "Demo exam").locator("[data-act=delete]").click()
    expect(card(page, "Demo exam")).to_be_visible()
    assert (exams / "demo").exists()

    page.once("dialog", lambda dialog: answer(dialog, True))
    card(page, "Demo exam").locator("[data-act=delete]").click()
    expect(page.locator(".exam-card")).to_have_count(0)
    expect(page.locator("h1")).to_have_text("Chưa có đề nào")
    assert not (exams / "demo").exists()
    assert 'Xóa đề "Demo exam"?' in messages[0]


def test_rename_reports_backend_errors(page, exams):
    shutil.rmtree(exams / "demo")  # gone on disk, still listed in the open page
    page.once("dialog", lambda dialog: dialog.accept("X"))
    card(page, "Demo exam").locator("[data-act=rename]").click()
    expect(page.locator("#picker-status")).to_have_text("Không có đề demo.")


# --------------------------------------------------------------------------- #
# Start screen
# --------------------------------------------------------------------------- #
def test_start_screen_controls(page):
    card(page, "Demo exam").locator(".exam-main").click()
    expect(page.locator(".start h1")).to_have_text("Demo exam")
    expect(page.locator(".start .source a")).to_have_attribute("href", THREAD)
    expect(page.locator("#minutes")).to_have_value("45")

    page.locator(".chip[data-min]", has_text="60").click()
    expect(page.locator("#minutes")).to_have_value("60")

    exam_chip = page.locator(".chip.mode", has_text="Thi thử")
    exam_chip.click()
    expect(exam_chip).to_have_attribute("aria-pressed", "true")
    expect(page.locator(".chip.mode", has_text="Luyện tập")).to_have_attribute("aria-pressed", "false")
    expect(page.locator("#mode-note")).to_contain_text("nộp bài mới chấm")

    page.click("#back")
    expect(page.locator("h1")).to_have_text("Chọn đề để làm")


# --------------------------------------------------------------------------- #
# Practice mode
# --------------------------------------------------------------------------- #
def test_practice_mode_grades_each_question_immediately(page):
    open_demo(page)
    expect(page.locator("#clock")).to_have_text("45:00")

    # Q1: image zoomed to the text box and linked to the full file, plus trace links.
    shot = page.locator("#image-pane a.shot")
    expect(shot).to_have_attribute("href", "../../exams/demo/images/q01.png")
    expect(shot).to_have_class("shot cropped")
    expect(page.locator("#image-pane a.trace").first).to_have_attribute("href", f"{THREAD}post-1#attachment-1")
    expect(page.locator("#image-pane a.trace").last).to_have_attribute("href", "https://fuoverflow.com/media/q1.1/")

    choice(page, "B").click()  # wrong
    expect(page.locator("#feedback .verdict")).to_have_text("Sai")
    expect(choice(page, "B")).to_have_attribute("data-state", "wrong")
    expect(choice(page, "A")).to_have_attribute("data-state", "correct")
    expect(choice(page, "C")).to_be_disabled()
    expect(dot(page, 1)).to_have_attribute("data-ok", "false")
    expect(page.locator("#feedback .vote-row.is-answer")).to_contain_text("A")

    # Q2: reveal without answering.
    page.click("#next")
    page.click("#reveal")
    expect(page.locator("#feedback .mini.key")).to_have_text("đáp án: C")
    expect(choice(page, "C")).to_have_attribute("data-state", "correct")

    # Q3: two answers, checked on demand.
    page.click("#next")
    expect(page.locator("#qtag")).to_have_text("chọn 2 đáp án")
    expect(page.locator("#check")).to_be_disabled()
    choice(page, "B").click()
    choice(page, "D").click()
    expect(choice(page, "B")).to_have_attribute("aria-pressed", "true")
    page.click("#check")
    expect(page.locator("#feedback .verdict")).to_have_text("Đúng")
    expect(dot(page, 3)).to_have_attribute("data-ok", "true")

    # Q4: no key, never counted as correct.
    page.click("#next")
    choice(page, "A").click()
    expect(page.locator("#feedback .verdict")).to_have_text("Chưa có đáp án")
    expect(page.locator("#next")).to_have_text("Nộp bài")

    page.click("#prev")
    expect(page.locator("#qnum")).to_have_text("Câu 3")
    dot(page, 4).click()
    page.click("#next")  # "Nộp bài" on the last question

    expect(page.locator(".score b")).to_have_text("1")
    expect(page.locator(".score")).to_contain_text("/ 4")
    expect(page.locator(".review-item")).to_have_count(4)
    expect(page.locator(".review-item").nth(3).locator(".verdict")).to_have_text("chưa có đáp án")
    expect(page.locator(".review-item").first.locator(".review-links a.trace")).to_have_count(2)

    page.click("#retry-wrong")
    expect(page.locator("#counter")).to_have_text("01 / 3")
    expect(page.locator("#qnum")).to_have_text("Câu 1")
    expect(choice(page, "A")).to_have_attribute("aria-pressed", "false")


# --------------------------------------------------------------------------- #
# Exam mode, keyboard, timer
# --------------------------------------------------------------------------- #
def test_exam_mode_with_keyboard_grades_only_on_submit(page):
    open_demo(page, mode="Thi thử")

    page.keyboard.press("1")  # A on Q1
    expect(choice(page, "A")).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#feedback")).to_be_empty()
    expect(page.locator("#reveal")).to_have_count(0)
    expect(dot(page, 1)).to_have_attribute("data-done", "true")

    page.keyboard.press("ArrowRight")
    page.keyboard.press("c")
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#qnum")).to_have_text("Câu 1")
    expect(choice(page, "A")).to_have_attribute("aria-pressed", "true")

    dot(page, 3).click()
    page.keyboard.press("b")
    page.keyboard.press("d")
    expect(choice(page, "D")).to_have_attribute("aria-pressed", "true")
    page.locator("body").press("Enter")  # next question in exam mode
    expect(page.locator("#qnum")).to_have_text("Câu 4")

    page.keyboard.press("p")
    expect(page.locator("#pause")).to_have_text("Tiếp tục")
    clock = page.locator("#clock").text_content()
    page.wait_for_timeout(1200)
    expect(page.locator("#clock")).to_have_text(clock)
    page.click("#pause")
    expect(page.locator("#pause")).to_have_text("Tạm dừng")

    page.click("#submit")
    expect(page.locator(".result-head .eyebrow")).to_contain_text("Kết quả")
    expect(page.locator(".result-head .eyebrow")).to_contain_text("thi thử")
    expect(page.locator(".score b")).to_have_text("3")
    expect(page.locator("#retry-wrong")).to_have_text("Ôn 1 câu sai")

    page.click("#again")
    expect(page.locator(".start h1")).to_have_text("Demo exam")


def test_timer_running_out_submits_automatically(page, site):
    page.clock.install()
    page.goto(site + "/")
    open_demo(page, minutes=1)
    page.clock.fast_forward("01:05")
    expect(page.locator(".result-head .eyebrow")).to_contain_text("Hết giờ")


# --------------------------------------------------------------------------- #
# Chrome: theme and exam switch
# --------------------------------------------------------------------------- #
def test_theme_cycles_and_persists(page):
    open_demo(page)
    html = page.locator("html")
    page.click("#theme")
    expect(html).to_have_attribute("data-theme", "light")
    page.click("#theme")
    expect(html).to_have_attribute("data-theme", "dark")
    page.reload()
    expect(html).to_have_attribute("data-theme", "dark")
    page.locator(".exam-main").click()
    page.click("#start")
    page.click("#theme")
    expect(html).to_have_attribute("data-theme", "")


def test_switch_exam_from_top_bar_stops_the_quiz(page):
    open_demo(page)
    page.click("#switch")
    expect(page.locator("h1")).to_have_text("Chọn đề để làm")
    expect(page.locator("#quiz-controls")).to_be_hidden()
    page.keyboard.press("1")  # shortcuts are inactive outside a quiz
    expect(page.locator("#choices")).to_have_count(0)


# --------------------------------------------------------------------------- #
# Result filters
# --------------------------------------------------------------------------- #
def test_result_filters_wrong_and_right_questions(page):
    open_demo(page, mode="Thi thử")
    page.keyboard.press("a")  # Q1 right
    page.keyboard.press("ArrowRight")
    page.keyboard.press("a")  # Q2 wrong; Q3 blank (wrong); Q4 has no key (wrong)
    page.click("#submit")

    items = page.locator(".review-item")
    visible = page.locator(".review-item:visible")
    expect(page.locator(".review-filter .chip")).to_have_text(["Tất cả · 4", "Sai · 3", "Đúng · 1"])
    expect(visible).to_have_count(4)

    page.locator(".review-filter .chip", has_text="Sai").click()
    expect(visible).to_have_count(3)
    expect(visible.locator(".qnum")).to_contain_text(["Câu 2", "Câu 3", "Câu 4"])
    expect(page.locator(".review-filter .chip", has_text="Sai")).to_have_attribute("aria-pressed", "true")

    page.locator(".review-filter .chip", has_text="Đúng").click()
    expect(visible).to_have_count(1)
    expect(visible.locator(".qnum")).to_have_text("Câu 1")
    expect(page.locator("#review-none")).to_be_hidden()

    page.locator(".review-filter .chip", has_text="Tất cả").click()
    expect(visible).to_have_count(4)
    expect(items).to_have_count(4)


def test_result_filter_with_no_match_says_so(page):
    open_demo(page, mode="Thi thử")
    page.click("#submit")  # nothing answered: no right answers
    page.locator(".review-filter .chip", has_text="Đúng").click()
    expect(page.locator(".review-item:visible")).to_have_count(0)
    expect(page.locator("#review-none")).to_be_visible()


# --------------------------------------------------------------------------- #
# Notes
# --------------------------------------------------------------------------- #
def test_notes_per_question_persist_and_list_on_notes_screen(page):
    open_demo(page)
    page.fill("#note", "nhớ: A là đáp án")
    expect(dot(page, 1)).to_have_attribute("data-note", "true")
    page.click("#next")
    expect(page.locator("#note")).to_have_value("")
    page.fill("#note", "câu 2")
    page.keyboard.press("B")  # typing in the note is not an answer
    expect(choice(page, "B")).to_have_attribute("aria-pressed", "false")
    page.click("#prev")
    expect(page.locator("#note")).to_have_value("nhớ: A là đáp án")

    page.reload()  # notes survive a reload: stored in this browser
    card(page, "Demo exam").locator(".exam-main").click()
    expect(page.locator("#notes")).to_have_text("Ghi chú · 2")
    page.click("#notes")
    expect(page.locator(".note-item")).to_have_count(2)
    expect(page.locator(".note-item textarea").first).to_have_value("nhớ: A là đáp án")

    page.locator(".note-item textarea").last.fill("")  # clearing removes the note
    page.click("#back")
    expect(page.locator("#notes")).to_have_text("Ghi chú · 1")

    page.click("#notes")
    page.click("#drill-notes")
    expect(page.locator("#counter")).to_have_text("01 / 1")
    choice(page, "B").click()
    page.click("#next")
    expect(page.locator(".review-note")).to_have_text("nhớ: A là đáp án")


def test_hosted_picker_asks_for_cookie_and_hides_destructive_actions(browser, exams, monkeypatch):
    monkeypatch.setattr(BlobExamStorage, "index", lambda self: json.loads((exams / "index.json").read_text()))
    port = free_port()
    uv = uvicorn.Server(uvicorn.Config(main.create_app(HOSTED, lambda entry, cookies: {}), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=uv.run, daemon=True)
    thread.start()
    while not uv.started:
        time.sleep(0.02)
    context = browser.new_context()
    tab = context.new_page()
    # Hosted, Vercel's CDN serves the web files; here the API app only has /api and /exams.
    tab.route("**/", lambda route: route.fulfill(path=paths.WEB / "index.html"))
    tab.route("**/app.js", lambda route: route.fulfill(path=paths.WEB / "app.js"))
    tab.route("**/styles.css", lambda route: route.fulfill(path=paths.WEB / "styles.css"))
    try:
        tab.goto(f"http://127.0.0.1:{port}/")
        expect(card(tab, "Demo exam")).to_be_visible()
        expect(tab.locator("[data-act=delete]")).to_have_count(0)
        expect(tab.locator("#crawl input[name=cookie]")).to_be_visible()
        expect(tab.locator("#crawl input[name=cookie]")).to_have_attribute("required", "")
    finally:
        context.close()
        uv.should_exit = True
        thread.join()



# --------------------------------------------------------------------------- #
# Mix, shuffle, evidence
# --------------------------------------------------------------------------- #
def test_mix_draws_questions_from_several_exams(page, exams):
    write_exam(exams, "other", "Other exam", QUESTIONS[:2])
    build.write_index(exams)
    page.reload()
    page.click("#mix button[type=submit]")
    expect(page.locator("#mix-status")).to_have_text("Chọn ít nhất 2 đề để trộn.")
    page.locator(".mix-item", has_text="Demo exam").locator("input").check()
    page.locator(".mix-item", has_text="Other exam").locator("input").check()
    page.fill("#mix input[name=count]", "5")
    page.click("#mix button[type=submit]")
    expect(page.locator(".start h1")).to_have_text("Trộn 5 câu từ 2 đề")
    page.click("#start")
    expect(page.locator("#counter")).to_have_text("01 / 5")
    labels = set()
    for i in range(5):
        code = page.locator("#qnum").inner_text().split(" · ")[1]  # "Câu 3 · demo"
        labels.add(code)
        # each question's image comes from its own exam folder
        assert page.locator("#image-pane img").get_attribute("src").startswith(f"../../exams/{code}/")
        if i < 4:
            page.click("#next")
    assert labels <= {"demo", "other"}


def test_shuffle_order_changes_queue_but_keeps_every_question(page):
    card(page, "Demo exam").locator(".exam-main").click()
    page.locator(".chip.order", has_text="Xáo trộn").click()
    page.click("#start")
    expect(page.locator("#dots .dot")).to_have_count(4)
    expect(page.locator("#dots .dot").first).to_have_text("1")
    seen = []
    for i in range(4):
        seen.append(page.locator("#qnum").inner_text())
        if i < 3:
            page.click("#next")
    assert sorted(seen) == ["Câu 1", "Câu 2", "Câu 3", "Câu 4"]


def test_evidence_lists_comments_against_the_key(page):
    open_demo(page)
    choice(page, "A").click()
    box = page.locator("#feedback .evidence")
    expect(box.locator("summary")).to_have_text("Bình luận đối chiếu · 5/6 khớp đáp án")
    box.locator("summary").click()
    expect(box.locator('li[data-tone="agree"]')).to_have_count(5)
    expect(box.locator('li[data-tone="differ"] .ev-letters')).to_have_text("B")
