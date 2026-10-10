"""Filesystem layout for the project.

The package is installed from ``src/exam_practice``, so the project root is two
levels up from this module.
"""

import os
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
ROOT = SRC.parent
# Vercel functions can only write /tmp; exams there are uploaded to Blob (see exams/blob_storage.py).
EXAMS = Path("/tmp/exams") if os.environ.get("VERCEL") else ROOT / "exams"
REGISTRY = EXAMS / "registry.json"
WEB = SRC / "web"
COOKIES = ROOT / "cookies.txt"
