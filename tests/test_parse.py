from exam_practice.parse import (
    Comment,
    collect_votes,
    extract_bare,
    extract_entries,
    parse_attachments,
    parse_comments,
    parse_first_post_id,
    parse_posts,
    resolve_answers,
    thread_meta,
)

THREAD_HTML = """
<html><head>
<title>Đề Thi PT - HCM202 - Q2 - 6 | FuOverflow Community</title>
<meta property="og:title" content="Đề Thi PT - HCM202 - Q2 - 6" />
<link rel="canonical" href="https://fuoverflow.com/threads/hcm202-q2-6.2757/" />
</head><body>
<div class="message" data-lb-id="post-5495"></div>
<article class="message-body">
  <div class="bbWrapper">HCM202 - Q2 - 6<br />30/09/2024 14h30</div>
</article>
<section class="message-attachments">
  <ul class="attachmentList">
    <li class="file file--linked">
      <a class="u-anchorTarget" id="attachment-147969"></a>
      <a class="file-preview" data-lb-sidebar-href="/media/hcm202_-_q2_-_6_2757-webp.70478/?lightbox=1"
         href="/attachments/hcm202_-_q2_-_6_2757-webp.147969/?fuo_h=abc&amp;fuo_e=1">
        <img src="https://data.fuoverflow.com/attachments/73/73207-x.jpg?hash=h" width="370" height="150" />
      </a>
      <div class="file-content"><div class="file-info">
        <span class="file-name" title="HCM202_-_Q2_-_6_2757.webp">HCM202_-_Q2_-_6_2757.webp</span>
        <div class="file-meta">79.7 KB &middot; Xem: 1,543</div>
      </div></div>
    </li>
    <li class="file file--linked">
      <a class="u-anchorTarget" id="attachment-147970"></a>
      <a class="file-preview" data-lb-sidebar-href="/media/hcm202_-_q2_-_6_2757-webp.70479/?lightbox=1"
         href="/attachments/hcm202_-_q2_-_6_2757-webp.147970/?fuo_h=def&amp;fuo_e=1">
        <img src="https://data.fuoverflow.com/attachments/73/73208-y.jpg?hash=h" width="370" height="150" />
      </a>
      <div class="file-content"><div class="file-info">
        <span class="file-name" title="HCM202_-_Q2_-_6_2757.webp">HCM202_-_Q2_-_6_2757.webp</span>
      </div></div>
    </li>
  </ul>
</section>
</body></html>
"""

MEDIA_HTML = """
<html><body>
<article class="comment" data-author="alice">
  <div class="comment-content"><div class="bbWrapper">A</div></div>
</article>
<article class="comment" data-author="bob">
  <div class="comment-content"><div class="bbWrapper">mình chọn A nha</div></div>
</article>
<article class="comment" data-author="carol">
  <div class="comment-content"><div class="bbWrapper">B</div></div>
</article>
<article class="comment" data-author="dave">
  <div class="comment-content"><div class="bbWrapper">Câu 1: A; Câu 2: B; Câu 3: C</div></div>
</article>
</body></html>
"""


def test_thread_meta():
    meta = thread_meta(THREAD_HTML)
    assert meta.title == "Đề Thi PT - HCM202 - Q2 - 6"
    assert meta.code == "hcm202-q2-6"
    assert meta.url == "https://fuoverflow.com/threads/hcm202-q2-6.2757/"


def test_parse_attachments():
    atts = parse_attachments(THREAD_HTML)
    assert [a.index for a in atts] == [1, 2]
    assert atts[0].attachment_id == 147969
    assert atts[0].media_path == "/media/hcm202_-_q2_-_6_2757-webp.70478/"
    assert atts[0].download_path.startswith("/attachments/")
    assert atts[1].filename == "HCM202_-_Q2_-_6_2757.webp"


def test_parse_attachments_numbers_by_filename_when_out_of_order():
    html = THREAD_HTML.replace("HCM202_-_Q2_-_6_2757.webp", "Q46.webp", 2).replace(
        "HCM202_-_Q2_-_6_2757.webp", "Q32.webp", 2
    )
    atts = parse_attachments(html)
    assert [(a.index, a.filename) for a in atts] == [(32, "Q32.webp"), (46, "Q46.webp")]


def test_parse_first_post_id():
    assert parse_first_post_id(THREAD_HTML) == 5495
    assert parse_first_post_id("<html></html>") is None


def test_parse_comments():
    comments = parse_comments(MEDIA_HTML)
    assert [c.author for c in comments] == ["alice", "bob", "carol", "dave"]
    assert comments[3].text == "Câu 1: A; Câu 2: B; Câu 3: C"


def test_extract_entries():
    assert extract_entries("Câu 1: A; Câu 2: B; Câu 3: C") == {1: {"A"}, 2: {"B"}, 3: {"C"}}
    assert extract_entries("1A 2B 3C") == {1: {"A"}, 2: {"B"}, 3: {"C"}}
    assert extract_entries("12. A,C") == {12: {"A", "C"}}
    assert extract_entries("câu 5 A B") == {5: {"A", "B"}}
    assert extract_entries("Câu 3: A và B") == {3: {"A", "B"}}
    assert extract_entries("câu 7: B hoặc C") == {7: {"B", "C"}}
    # "Câu" leading C must not be read as a choice, and years must be ignored.
    assert extract_entries("năm 2024") == {}
    assert extract_entries("câu 7 hình như là A") == {}


def test_extract_entries_ignores_long_numbers():
    # A 4+ digit number must not backtrack into a bogus question id.
    assert extract_entries("năm 2023 A") == {}
    assert extract_entries("mã 2705B") == {}
    assert extract_entries("attachment 147969A") == {}


def test_extract_bare():
    assert extract_bare("A") == {"A"}
    assert extract_bare("mình chọn a") == {"A"}
    assert extract_bare("A,B") == {"A", "B"}
    assert extract_bare("câu trả lời là D") == {"D"}
    # Too long, or letters glued to words, yields nothing.
    assert extract_bare("A " * 60) == set()
    assert extract_bare("chữ abcdef") == set()


def test_collect_votes_bare_and_numbered():
    comments = parse_comments(MEDIA_HTML)
    votes = collect_votes(comments, page_question=1)
    tally = {}
    for v in votes:
        tally.setdefault(v.question, []).append((v.author, sorted(v.letters)))
    assert tally[1].count(("alice", ["A"])) == 1
    assert ("bob", ["A"]) in tally[1]
    assert ("carol", ["B"]) in tally[1]
    # dave names questions explicitly, so his letters go to 1, 2 and 3 only.
    assert ("dave", ["A"]) in tally[1]
    assert tally[2] == [("dave", ["B"])]
    assert tally[3] == [("dave", ["C"])]


def test_collect_votes_skips_mismatched_reference():
    # "câu 9" on question 3's page must not vote for question 3.
    comments = [Comment(author="x", text="câu 9 là A")]
    assert collect_votes(comments, page_question=3) == []


def test_resolve_answers_majority():
    comments = parse_comments(MEDIA_HTML)
    votes = collect_votes(comments, page_question=1)
    answers = resolve_answers(votes, total=3)
    assert answers[1].letters == ["A"]
    assert answers[1].letter_counts == {"A": 3, "B": 1}
    assert answers[1].multi is False
    assert answers[2].letters == ["B"]
    assert answers[3].letters == ["C"]


def test_resolve_answers_multi_choice_mode_of_sets():
    comments = [
        Comment("a", "A,C"),
        Comment("b", "A,C"),
        Comment("c", "A"),
        Comment("d", "B"),
    ]
    answers = resolve_answers(collect_votes(comments, page_question=1), total=1)
    assert answers[1].letters == ["A", "C"]
    assert answers[1].multi is True


def test_resolve_answers_counts_author_once():
    comments = [Comment("spammer", "A"), Comment("spammer", "A"), Comment("real", "B")]
    answers = resolve_answers(collect_votes(comments, page_question=1), total=1)
    assert answers[1].vote_count == 2
    assert answers[1].letters == ["A"]


def test_resolve_answers_later_vote_by_author_wins():
    # A correction from the same author replaces the earlier pick, not adds to it.
    comments = [Comment("u", "A"), Comment("u", "A,B")]
    answers = resolve_answers(collect_votes(comments, page_question=1), total=1)
    assert answers[1].vote_count == 1
    assert answers[1].letters == ["A", "B"]


def test_parse_posts_skips_quotes():
    html = """
    <div data-author="a"><article class="message-body"><div class="bbWrapper">Câu 1: A
      <blockquote class="bbCodeBlock bbCodeBlock--quote"><div class="bbWrapper">Câu 1: B</div></blockquote>
    </div></article></div>"""
    posts = parse_posts(html)
    assert len(posts) == 1
    assert posts[0].author == "a"
    assert "B" not in posts[0].text


def test_resolve_answers_contested_and_empty():
    comments = [Comment("a", "A"), Comment("b", "B")]
    answers = resolve_answers(collect_votes(comments, page_question=1), total=2)
    assert answers[1].contested is True
    assert answers[2].letters == []
    assert answers[2].contested is True


def test_votes_keep_their_comment_as_evidence():
    from exam_practice.parse import Comment, collect_votes, resolve_answers

    long_list = "Đáp án của mình: " + " ".join(f"{n}A" for n in range(1, 40)) + " hết"
    votes = collect_votes([Comment("an", "B nhé"), Comment("binh", long_list)], page_question=7)
    answers = resolve_answers(votes, 30)
    assert [(v.author, v.text) for v in answers[7].evidence][0] == ("an", "B nhé")
    cut = answers[30].evidence[0].text  # long list: only the words around "30A"
    assert "30A" in cut and cut.startswith("…") and len(cut) < len(long_list)
