"""Rename and delete stored exams, keeping every copy of the exam in step.

An exam lives in ``exams/<code>/`` (``exam.json``, ``data.*``, ``raw/``, ``images/``),
may have a registry entry, and appears in ``exams/index.*``. A rename must reach the
raw manifest and the registry too, otherwise ``--rebuild`` / ``--sync`` would bring
the old name back.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from . import build, registry

# Codes come from URL slugs; this also keeps a code from escaping the exams folder.
CODE_RE = re.compile(r"[a-z0-9][a-z0-9._-]*")


class ExamNotFound(LookupError):
    """No stored exam has this code."""


def rename(root: Path, registry_path: Path, code: str, title: str) -> None:
    exam_dir = _exam_dir(root, code)
    data_file = exam_dir / "data.json"
    data = json.loads((data_file if data_file.exists() else exam_dir / "exam.json").read_text(encoding="utf-8"))
    build.write_exam(exam_dir, {**data, "title": title})

    manifest_file = exam_dir / "raw" / "manifest.json"
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        manifest_file.write_text(json.dumps({**manifest, "title": title}, ensure_ascii=False, indent=2), encoding="utf-8")

    entries = registry.load(registry_path)
    if any(entry.get("code") == code for entry in entries):
        registry.save(registry_path, [{**e, "name": title} if e.get("code") == code else e for e in entries])
    build.write_index(root)


def delete(root: Path, registry_path: Path, code: str) -> None:
    shutil.rmtree(_exam_dir(root, code))
    entries = registry.load(registry_path)
    if any(entry.get("code") == code for entry in entries):
        registry.save(registry_path, [e for e in entries if e.get("code") != code])
    build.write_index(root)


def _exam_dir(root: Path, code: str) -> Path:
    exam_dir = root / code
    if not CODE_RE.fullmatch(code) or not (exam_dir / "exam.json").is_file():
        raise ExamNotFound(code)
    return exam_dir
