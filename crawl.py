#!/usr/bin/env python
"""Convenience wrapper: ``uv run crawl.py <thread-url>``.

Equivalent to the installed ``exam-practice`` console script.
"""

from exam_practice.cli import main

if __name__ == "__main__":
    main()
