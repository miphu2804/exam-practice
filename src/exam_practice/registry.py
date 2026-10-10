"""Storage for ``exams/registry.json``: the exams to set up, by name and URL.

Hand-editable, and written by ``crawl.py <url> --register``. ``--sync`` reads it
to (re)build every exam, so a cron job can keep the set fresh.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return entries if isinstance(entries, list) else []


def save(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(entries, key=lambda entry: entry.get("code", ""))
    path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def upsert(entries: list[dict], entry: dict) -> list[dict]:
    """Merge ``entry`` into ``entries`` by code, keeping earlier fields."""
    merged = {existing.get("code"): existing for existing in entries}
    merged[entry["code"]] = {**merged.get(entry["code"], {}), **entry}
    return list(merged.values())


def register(path: Path, entry: dict) -> None:
    """Upsert ``entry`` into the registry file; blank fields keep the saved values."""
    fields = {key: value for key, value in entry.items() if value}
    save(path, upsert(load(path), {**fields, "added": date.today().isoformat()}))
