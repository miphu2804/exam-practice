"""Failures of the exam workflows; the router maps each one to an HTTP status."""

from __future__ import annotations


class StorageBusy(RuntimeError):
    """Another crawl, rename or delete holds the storage lock."""


class ReadOnlyStorage(RuntimeError):
    """The storage refuses rename and delete (the shared hosted deployment)."""
