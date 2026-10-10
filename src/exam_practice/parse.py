"""Pure parsers for FuOverflow (XenForo 2.3 + XFMG) thread and media pages.

Every function here takes HTML text and returns plain data, with no I/O, so vote
extraction can be re-run offline against saved raw pages (see ``build.py``).
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from urllib.parse import urlparse

from bs4 import BeautifulSoup

BASE = "https://fuoverflow.com"
CHOICES = ("A", "B", "C", "D")
MAX_QUESTIONS = 300


def slug_code(url: str) -> str:
    """Exam code from a thread URL: ``.../hcm202-q2-6.2757/`` -> ``hcm202-q2-6``."""
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1] if url else ""
    return slug.rsplit(".", 1)[0] if "." in slug else slug


# --------------------------------------------------------------------------- #
# Thread page
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Attachment:
    """One exam image attached to the first post."""

    index: int
    attachment_id: int
    filename: str
    thumb_url: str
    download_path: str
    media_path: str | None


@dataclass(frozen=True)
class ThreadMeta:
    title: str
    code: str
    url: str


def thread_meta(html: str, url: str = "") -> ThreadMeta:
    """Title, short code and canonical URL of the thread."""
    soup = BeautifulSoup(html, "lxml")
    og_title = soup.find("meta", property="og:title")
    title = (og_title.get("content") if og_title else "") or ""
    if not title and soup.title:
        title = soup.title.get_text(strip=True).split("|")[0]
    title = title.strip()

    canonical = soup.find("link", rel="canonical")
    url = (canonical.get("href") if canonical else "") or url
    return ThreadMeta(title=title, code=slug_code(url), url=url)


_FILENAME_QUESTION_RE = re.compile(r"(?:q|câu|cau)[\s_.-]*(\d{1,3})\.\w+$", re.IGNORECASE)


def parse_attachments(html: str) -> list[Attachment]:
    """Exam images under the first post, numbered by question.

    Uploaders often attach images out of order (``Q46.webp`` first, then ``Q32``),
    so when every filename names its question (``Q12.webp``, ``Câu 12.png``) that
    number is the index; otherwise images are numbered in post order.
    """
    soup = BeautifulSoup(html, "lxml")
    out: list[Attachment] = []
    for li in soup.select("li.file--linked"):
        link = li.select_one("a.file-preview")
        if not link:
            continue
        anchor = li.select_one("a.u-anchorTarget[id^=attachment-]")
        attachment_id = int(anchor["id"].split("-")[-1]) if anchor and anchor.get("id") else 0
        img = link.find("img")
        sidebar = link.get("data-lb-sidebar-href") or ""
        name_el = li.select_one(".file-name")
        out.append(
            Attachment(
                index=len(out) + 1,
                attachment_id=attachment_id,
                filename=(name_el.get("title") if name_el else "") or "",
                thumb_url=(img.get("src") if img else "") or "",
                download_path=link.get("href") or "",
                media_path=sidebar.split("?")[0] or None,
            )
        )
    numbers = [_filename_question(a.filename) for a in out]
    if out and None not in numbers and len(set(numbers)) == len(numbers):
        return sorted((replace(a, index=n) for a, n in zip(out, numbers)), key=lambda a: a.index)
    return out


def _filename_question(filename: str) -> int | None:
    match = _FILENAME_QUESTION_RE.match(filename.strip())
    return int(match.group(1)) if match else None


def page_count(html: str) -> int:
    """Highest thread page number (1 when there is no pagination)."""
    soup = BeautifulSoup(html, "lxml")
    pages = [1]
    for a in soup.select("ul.pageNav-main a"):
        text = a.get_text(strip=True)
        if text.isdigit():
            pages.append(int(text))
    return max(pages)


def parse_first_post_id(html: str) -> int | None:
    """Id of the first post, for building per-attachment trace links."""
    match = re.search(r'data-lb-id="post-(\d+)"', html) or re.search(r"/post-(\d+)", html)
    return int(match.group(1)) if match else None


def parse_posts(html: str) -> list["Comment"]:
    """Forum post bodies (used as a secondary vote source to media comments).

    Quoted blocks are skipped so a reply that quotes someone else's answer list is
    not counted as the replier's own vote.
    """
    soup = BeautifulSoup(html, "lxml")
    posts: list[Comment] = []
    for body in soup.select(".message-body .bbWrapper"):
        for quote in body.select("blockquote, .bbCodeQuote, .bbCodeBlock--quote"):
            quote.decompose()
        text = body.get_text(" ", strip=True)
        if not text:
            continue
        holder = body.find_parent(attrs={"data-author": True})
        author = holder.get("data-author", "") if holder else ""
        posts.append(Comment(author=author, text=text))
    return posts


# --------------------------------------------------------------------------- #
# Media pages (attachment comments)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Comment:
    author: str
    text: str


_COMMENT_SELECTORS = (
    "article.comment",
    "li.comment",
    ".js-comment",
    "[data-comment-id]",
    ".comment-content",
)


def parse_comments(html: str) -> list[Comment]:
    """Comments on a media page, in document order.

    XenForo Media Gallery has shifted comment markup between versions, so try the
    known containers in order and fall back to any ``.bbWrapper`` that sits inside
    a comment-ish element.
    """
    soup = BeautifulSoup(html, "lxml")
    for selector in _COMMENT_SELECTORS:
        nodes = soup.select(selector)
        if not nodes:
            continue
        comments = [_comment_from(n) for n in nodes]
        comments = [c for c in comments if c.text]
        if comments:
            return comments

    comments: list[Comment] = []
    for body in soup.select(".bbWrapper"):
        container = body.find_parent(class_=re.compile("comment"))
        if container:
            comments.append(_comment_from(container))
    return [c for c in comments if c.text]


def _comment_from(node) -> Comment:
    author = node.get("data-author") or ""
    if not author:
        holder = node.find_parent(attrs={"data-author": True})
        if holder:
            author = holder.get("data-author", "")
    if not author:
        name = node.select_one(".comment-author, .username")
        author = name.get_text(strip=True) if name else ""
    body = node.select_one(".bbWrapper") or node.select_one(".comment-content") or node
    return Comment(author=author.strip(), text=body.get_text(" ", strip=True))


# --------------------------------------------------------------------------- #
# Vote extraction
# --------------------------------------------------------------------------- #
# A choice letter A-D that is not glued to a following letter (so the leading C
# of "Câu" never reads as choice C).
_LETTER = r"[A-Da-d](?![^\W\d_])"
# Multi-answer needs an explicit separator: "A,B", "A B", "A/B", "A và B".
# "AB" without a separator is too ambiguous to trust.
_SEP = r"(?:\s*[,/&+;\-]\s*|\s+(?:và|hay|hoặc|va|hoac|and)\s+|\s+)"
_LETTERS = rf"{_LETTER}(?:{_SEP}{_LETTER}){{0,3}}"
_ENTRY_RE = re.compile(rf"(?i:c[âa]u\s*)?(?<!\d)(\d{{1,3}})(?!\d)\s*[\.\):\-/]?\s*({_LETTERS})")
_BARE_RE = re.compile(r"(?<![^\W\d_])[A-Da-d](?![^\W\d_])")
_QREF_RE = re.compile(r"(?i:c[âa]u\s*)(\d{1,3})")


@dataclass(frozen=True)
class Vote:
    question: int
    author: str
    letters: frozenset[str]


@dataclass
class Answer:
    question: int
    letters: list[str]
    letter_counts: dict[str, int]
    vote_count: int
    multi: bool
    contested: bool


def extract_entries(text: str) -> dict[int, set[str]]:
    """Explicit ``<n> <letters>`` answer entries, e.g. ``"Câu 12: A"`` -> {12: {A}}."""
    entries: dict[int, set[str]] = defaultdict(set)
    for match in _ENTRY_RE.finditer(text):
        number = int(match.group(1))
        if not 1 <= number <= MAX_QUESTIONS:
            continue
        entries[number] |= {c.upper() for c in re.findall(r"[A-Da-d]", match.group(2))}
    return dict(entries)


def extract_bare(text: str) -> set[str]:
    """Choice letters in a short comment that names no question, e.g. ``"A"``."""
    if len(text) > 80:
        return set()
    return {c.upper() for c in _BARE_RE.findall(text)}


def question_reference(text: str) -> int | None:
    """First ``Câu N`` reference in a comment, if any."""
    match = _QREF_RE.search(text)
    return int(match.group(1)) if match else None


def collect_votes(comments: list[Comment], page_question: int | None) -> list[Vote]:
    """Turn one media page's comments into votes.

    A comment that lists numbered entries contributes to every question it names;
    a comment with bare letters contributes to the page's own question, unless it
    references a different question number.
    """
    votes: list[Vote] = []
    for comment in comments:
        entries = extract_entries(comment.text)
        if entries:
            votes.extend(
                Vote(n, comment.author, frozenset(letters))
                for n, letters in entries.items()
                if letters
            )
            continue
        if page_question is None:
            continue
        bare = extract_bare(comment.text)
        reference = question_reference(comment.text)
        if bare and reference in (None, page_question):
            votes.append(Vote(page_question, comment.author, frozenset(bare)))
    return votes


def resolve_answers(votes: list[Vote], total: int) -> dict[int, Answer]:
    """Majority-vote answer per question.

    The winning answer is the most common *set* of letters; ties prefer the
    smaller set (a single choice over a multi-choice). ``contested`` marks a
    question whose runner-up is within 25% of the winner.
    """
    unique: dict[tuple[int, str], Vote] = {}
    for vote in votes:
        # One author counts once per question; a later vote (e.g. a correction) wins.
        unique[(vote.question, vote.author)] = vote
    set_counts: dict[int, Counter[frozenset[str]]] = defaultdict(Counter)
    letter_counts: dict[int, Counter[str]] = defaultdict(Counter)
    for vote in unique.values():
        set_counts[vote.question][vote.letters] += 1
        for letter in vote.letters:
            letter_counts[vote.question][letter] += 1

    answers: dict[int, Answer] = {}
    for q in range(1, total + 1):
        counts = set_counts.get(q)
        if not counts:
            answers[q] = Answer(q, [], {}, 0, False, True)
            continue
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], len(kv[0]), sorted(kv[0])))
        winner, wins = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0
        answers[q] = Answer(
            question=q,
            letters=sorted(winner),
            letter_counts=dict(sorted(letter_counts[q].items())),
            vote_count=sum(counts.values()),
            multi=len(winner) > 1,
            contested=runner_up * 4 >= wins * 3,
        )
    return answers
