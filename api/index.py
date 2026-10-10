"""Vercel entrypoint: ``/api/*`` and ``/exams/*`` are rewritten here (see ``vercel.json``)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from exam_practice.main import app  # noqa: E402,F401
