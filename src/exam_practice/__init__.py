"""Crawl FuOverflow exam threads into per-exam practice data.

- ``exam_practice.parse``    pure HTML -> data
- ``exam_practice.fetch``    HTTP session, cookies, downloads
- ``exam_practice.crawler``  fetch a thread into ``exams/<code>/raw``
- ``exam_practice.build``    raw -> ``data.json``/``data.js`` and the index
- ``exam_practice.cli``      command line entry point
"""
