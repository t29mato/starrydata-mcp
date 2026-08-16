"""Shared progress-callback type for the ingestion pipeline.

Bug fix (2026-08-16, reported by the owner): a silent multi-minute ingest
looked hung, got Ctrl+C'd, and the retry then failed with a raw DuckDB lock
error. `downloader.py`, `etl.py`, and `pipeline.py` all take an `on_progress`
callback so the CLI can print what's happening instead of going silent.
"""

from __future__ import annotations

from collections.abc import Callable

ProgressFn = Callable[[str], None]


def default_progress(_message: str) -> None:
    """No-op default so callers don't have to pass a callback."""
