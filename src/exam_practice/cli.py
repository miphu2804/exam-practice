"""Command line entry point for exam-practice.

Modes:
  crawl   uv run crawl.py <url> [--name ...] [--register]
  sync    uv run crawl.py --sync [--force] [--ttl-days N] [--only CODE]   # for cron
  rebuild uv run crawl.py --rebuild [CODE]
  list    uv run crawl.py --list
  serve   uv run crawl.py --serve [--port 8000]   # API + built-in web app (dev: ./dev.sh)
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from . import build, crawler, paths, registry
from .fetch import LoginRequired, load_cookies
from .parse import slug_code


def main() -> None:
    args = _parse_args()
    paths.EXAMS.mkdir(parents=True, exist_ok=True)
    try:
        _run(args)
    except (LoginRequired, crawler.CrawlError) as exc:
        raise SystemExit(str(exc)) from None


def _run(args: argparse.Namespace) -> None:
    if args.list:
        _list()
    elif args.serve:
        _serve(args)
    elif args.rebuild is not None:
        _rebuild(args)
    elif args.sync:
        _sync(args)
    else:
        _crawl(args, register=args.register)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="exam-practice",
        description="Crawl FuOverflow exam threads and turn them into practice exams.",
        epilog=(
            "examples:\n"
            "  uv run crawl.py https://fuoverflow.com/threads/hcm202-q2-6.2757/\n"
            "  uv run crawl.py https://fuoverflow.com/threads/x.123/ --name 'MLN111 FE' --register\n"
            "  uv run crawl.py --sync --ttl-days 7      # cron: set up / refresh every registered exam\n"
            "  uv run crawl.py --serve                  # web app with a crawl form\n"
            "  uv run crawl.py --list\n"
            "  uv run crawl.py --rebuild"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("url", nargs="?", help="FuOverflow thread URL")
    parser.add_argument("--name", help="display name for the exam (đặt tên đề)")
    parser.add_argument("--code", help="folder/code override (default: from the URL slug)")
    parser.add_argument("--register", action="store_true", help="save this exam to exams/registry.json")
    parser.add_argument("--sync", action="store_true", help="crawl every registered exam (for cron)")
    parser.add_argument("--force", action="store_true", help="with --sync, re-crawl even when fresh")
    parser.add_argument("--ttl-days", type=int, default=7, help="with --sync, refresh exams older than N days")
    parser.add_argument("--only", metavar="CODE", help="with --sync, limit to one code")
    parser.add_argument("--rebuild", nargs="?", const="", metavar="CODE", help="rebuild data from raw (all exams if no code)")
    parser.add_argument("--list", action="store_true", help="list exams")
    parser.add_argument("--serve", action="store_true", help="serve the API and web app on localhost (uvicorn)")
    parser.add_argument("--port", type=int, default=8000, help="with --serve, port to listen on")
    parser.add_argument("--cookies", default=str(paths.COOKIES), help="Netscape cookies.txt")
    parser.add_argument("--cookie", help="raw 'Cookie:' header value, overrides --cookies")
    parser.add_argument("--delay", type=float, default=0.6, help="seconds between requests")
    parser.add_argument("--minutes", type=int, default=45, help="default quiz duration")
    parser.add_argument("--questions", type=int, help="override question count when one image holds several")
    parser.add_argument("--no-images", action="store_true", help="skip image downloads")
    args = parser.parse_args()
    if not (args.list or args.serve or args.sync or args.rebuild is not None or args.url):
        parser.error("a thread URL is required (or pass --sync / --rebuild / --list)")
    return args


def _cookies(args: argparse.Namespace) -> dict[str, str]:
    path = Path(args.cookies).expanduser()
    return load_cookies(args.cookie, path if path.is_absolute() else paths.ROOT / path)


# --------------------------------------------------------------------------- #
# Modes
# --------------------------------------------------------------------------- #
def _crawl(args: argparse.Namespace, *, register: bool) -> None:
    entry = {
        "code": args.code or slug_code(args.url),
        "name": args.name or "",
        "url": args.url,
        "minutes": args.minutes,
    }
    if register:
        registry.register(paths.REGISTRY, entry)
        print(f"registered {entry['code']} in {paths.REGISTRY}")
    data = _crawl_entry(entry, args)
    build.write_index(paths.EXAMS)
    print(build.report(data))
    _hint(data)


def _crawl_entry(entry: dict, args: argparse.Namespace) -> dict:
    return crawler.crawl_exam(
        entry,
        _cookies(args),
        delay=args.delay,
        no_images=args.no_images,
        questions=args.questions,
        default_minutes=args.minutes,
    )


def _sync(args: argparse.Namespace) -> None:
    entries = registry.load(paths.REGISTRY)
    if not entries:
        raise SystemExit(
            f"No exams in {paths.REGISTRY}.\n"
            "Add one with: uv run crawl.py <url> --name \"...\" --register"
        )
    for entry in entries:
        if args.only and entry.get("code") != args.only:
            continue
        exam_dir = paths.EXAMS / entry["code"]
        if not args.force and not _stale(exam_dir, args.ttl_days):
            print(f"skip {entry['code']} (fresh)")
            continue
        print(f"crawl {entry['code']} <- {entry['url']}")
        print(build.report(_crawl_entry(entry, args)))
    build.write_index(paths.EXAMS)


def _stale(exam_dir: Path, ttl_days: int) -> bool:
    data_file = exam_dir / "data.json"
    if not data_file.exists():
        return True
    return (time.time() - data_file.stat().st_mtime) > ttl_days * 86400


def _list() -> None:
    entries = build.write_index(paths.EXAMS)
    if not entries:
        print("No exams yet. Run: uv run crawl.py <thread-url>")
        return
    for entry in entries:
        stats = entry.get("stats", {})
        print(f"  {entry['code']:<26} {stats.get('answered', '?')}/{stats.get('questions', '?')} câu   {entry.get('title', '')}")


def _rebuild(args: argparse.Namespace) -> None:
    wanted = args.rebuild or None
    minutes_by_code = {entry.get("code"): entry.get("minutes") for entry in registry.load(paths.REGISTRY)}
    manifests = sorted(paths.EXAMS.glob("*/raw/manifest.json"))
    if not manifests:
        raise SystemExit("No raw manifests found under exams/*/raw/. Crawl a thread first.")
    for manifest_path in manifests:
        code = manifest_path.parent.parent.name
        if wanted and code != wanted:
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        exam_dir = manifest_path.parent.parent
        minutes = minutes_by_code.get(code) or args.minutes
        data = build.build_exam(manifest, exam_dir, minutes=minutes, questions=args.questions)
        build.write_exam(exam_dir, data)
        print(build.report(data))
    build.write_index(paths.EXAMS)


def _serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run("exam_practice.server:app", host="127.0.0.1", port=args.port)


def _hint(data: dict) -> None:
    print(
        f"\n  data  exams/{data['code']}/data.json\n"
        "  mở   ./dev.sh   ->   http://localhost:5173/\n"
    )
