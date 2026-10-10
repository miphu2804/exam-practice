"""Turn a crawled manifest into practice data and the cross-exam index.

The answer key is produced by cross-checking the answers people left in the
comments of each exam image: the most common *set* of choices wins. Questions
whose runner-up is close are flagged as contested, empty ones as unanswered.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .parse import BASE, Comment, collect_votes, parse_comments, resolve_answers

CHOICES = ["A", "B", "C", "D"]
INK = 110  # grey level below which a pixel counts as text
VIEW_PAD = 16
# FuOverflow stamps a grey logo in the bottom-left corner; it is not question content.
WATERMARK = (160, 110)  # width, height in pixels, with margin around the logo


def build_exam(manifest: dict, exam_dir: Path, *, minutes: int = 45, questions: int | None = None) -> dict:
    """Cross-check comment votes into a question list with answer keys."""
    attachments = manifest.get("attachments", [])
    posts = [Comment(author=p.get("author", ""), text=p.get("text", "")) for p in manifest.get("posts", [])]

    votes = []
    for attachment in attachments:
        media_file = attachment.get("media_file")
        raw = exam_dir / media_file if media_file else None
        if raw and raw.exists():
            votes.extend(
                collect_votes(parse_comments(raw.read_text(encoding="utf-8")), page_question=attachment["index"])
            )
    votes.extend(collect_votes(posts, page_question=None))

    total = questions or max((a["index"] for a in attachments), default=0)  # indexes may skip numbers
    referenced = max((vote.question for vote in votes), default=0)
    if referenced > total:
        print(
            f"warning: comments reference question {referenced} but only {total} are configured; "
            f"re-run with --questions {referenced} if each image holds several questions."
        )

    answers = resolve_answers(votes, total)
    questions = []
    for n in range(1, total + 1):
        attachment = _attachment_at(attachments, n)
        questions.append(_question(n, answers[n], attachment, manifest.get("url", "")))
    return {
        "code": manifest.get("code", ""),
        "title": manifest.get("title", ""),
        "source": manifest.get("url", ""),
        "generated": manifest.get("generated", datetime.now(timezone.utc).isoformat(timespec="seconds")),
        "default_duration_min": minutes,
        "choices": CHOICES,
        "stats": _stats(answers, total, len(votes)),
        "view": text_view([exam_dir / q["image"] for q in questions if q["image"]]),
        "questions": questions,
    }


def text_view(images: list[Path]) -> dict | None:
    """One crop box covering the text of every image, so the app can zoom past blank space.

    Exam screenshots are mostly empty (1920x720 with text in the top-left), so the
    whole frame shown at page width leaves the text tiny. A single box for the
    exam keeps the zoom identical from question to question. ``None`` when the
    images differ in size or none can be read; the app then shows them whole.
    """
    size = None
    box = None
    for path in images:
        try:
            with Image.open(path) as image:
                gray = image.convert("L")
        except (OSError, UnidentifiedImageError):
            continue
        if size not in (None, gray.size):
            return None
        size = gray.size
        width, height = size
        ink = gray.point(lambda v: 255 if v < INK else 0)
        ink.paste(0, (0, height - WATERMARK[1], WATERMARK[0], height))
        found = ink.getbbox()
        if found:
            box = found if box is None else (
                min(box[0], found[0]), min(box[1], found[1]), max(box[2], found[2]), max(box[3], found[3])
            )
    if not size or not box:
        return None
    width, height = size
    left, top = max(0, box[0] - VIEW_PAD), max(0, box[1] - VIEW_PAD)
    right, bottom = min(width, box[2] + VIEW_PAD), min(height, box[3] + VIEW_PAD)
    return {"x": left, "y": top, "w": right - left, "h": bottom - top, "width": width, "height": height}


def _stats(answers: dict, total: int, vote_count: int) -> dict:
    values = list(answers.values())
    return {
        "questions": total,
        "answered": sum(1 for a in values if a.letters),
        "contested": sum(1 for a in values if a.letters and a.contested),
        "multi": sum(1 for a in values if a.multi),
        "votes": vote_count,
    }


def _attachment_at(attachments: list[dict], index: int) -> dict | None:
    """One image per question; a question beyond the images has no attachment."""
    return next((a for a in attachments if a["index"] == index), None)


def _source(attachment: dict | None, fallback: str) -> str:
    """Trace link to the exact question: post anchor, else media page, else the thread."""
    if attachment and attachment.get("post_url"):
        return attachment["post_url"]
    if attachment and attachment.get("media_path"):
        return BASE + attachment["media_path"]
    return fallback


def _media(attachment: dict | None, source: str) -> str | None:
    """The attachment's own comment page, when it differs from the trace link."""
    if attachment and attachment.get("media_path"):
        url = BASE + attachment["media_path"]
        return url if url != source else None
    return None


def _question(number: int, answer, attachment: dict | None, fallback_source: str) -> dict:
    multi = answer.multi
    source = _source(attachment, fallback_source)
    return {
        "n": number,
        "image": attachment.get("image_file") if attachment else None,
        "source": source,
        "media": _media(attachment, source),
        "choices": CHOICES,
        "type": "multi" if multi else "single",
        "answer": answer.letters,
        "multi": multi,
        "pick": len(answer.letters) if answer.letters else None,
        "contested": answer.contested,
        "letter_votes": answer.letter_counts,
        "vote_count": answer.vote_count,
    }


def write_exam(exam_dir: Path, data: dict) -> None:
    """Write ``exam.json`` (summary), ``data.json`` and ``data.js`` for one exam."""
    exam_dir.mkdir(parents=True, exist_ok=True)
    meta = {k: v for k, v in data.items() if k != "questions"}
    (exam_dir / "exam.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (exam_dir / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    (exam_dir / "data.js").write_text(f"window.EXAM_DATA={payload};\n", encoding="utf-8")


def write_index(exams_root: Path) -> list[dict]:
    """Rebuild ``exams/index.json`` and ``index.js`` from every ``exam.json``."""
    entries = []
    for exam_json in sorted(exams_root.glob("*/exam.json")):
        try:
            entry = json.loads(exam_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if entry.get("code"):
            entries.append(entry)
    entries.sort(key=lambda e: e["code"])
    exams_root.mkdir(parents=True, exist_ok=True)
    (exams_root / "index.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    payload = json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
    (exams_root / "index.js").write_text(f"window.EXAM_INDEX={payload};\n", encoding="utf-8")
    return entries


def report(data: dict) -> str:
    stats = data["stats"]
    lines = [
        "",
        f"{data['title']}  [{data['code']}]",
        f"  source    {data['source']}",
        f"  questions {stats['questions']}  answered {stats['answered']}  "
        f"contested {stats['contested']}  multi {stats['multi']}  votes {stats['votes']}",
        f"  {'Q':>3}  {'key':<4} {'votes':>5}  {'flags':<12} distribution",
    ]
    for question in data["questions"]:
        distribution = " ".join(f"{k}:{v}" for k, v in question["letter_votes"].items()) or "-"
        flags = " ".join(
            f for f, on in (("contested", question["contested"]), ("multi", question["multi"]), ("no-key", not question["answer"])) if on
        )
        lines.append(
            f"  {question['n']:>3}  {''.join(question['answer']) or '-':<4} "
            f"{question['vote_count']:>5}  {flags:<12} {distribution}"
        )
    return "\n".join(lines)
