"""DuckDBConnectionProvider: reuse-until-mtime-changes + hot-swap behavior.

Not exercised by the repository fixtures elsewhere (they only ever read
from one connection lifetime), but this is exactly the mechanism that lets
a running MCP server pick up a fresh daily ingest without restarting (see
the module docstring) — worth testing directly.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from starrydata_mcp.infrastructure.duckdb.connection import DuckDBConnectionProvider


def test_same_connection_object_is_reused_while_file_is_unchanged(db_path: Path) -> None:
    provider = DuckDBConnectionProvider(db_path)
    first = provider.connection
    second = provider.connection
    assert first is second
    provider.close()


def test_connection_is_reopened_after_the_file_is_replaced(db_path: Path) -> None:
    provider = DuckDBConnectionProvider(db_path)
    first = provider.connection
    assert first.execute("SELECT count(*) FROM papers").fetchone() == (2,)

    # Simulate the daily ingest's atomic rename: a new file lands at the same
    # path with a newer mtime.
    time.sleep(0.01)
    os.utime(db_path, None)  # bump mtime without changing content

    second = provider.connection
    assert second is not first
    assert second.execute("SELECT count(*) FROM papers").fetchone() == (2,)
    provider.close()


def test_close_is_safe_to_call_when_never_connected(tmp_path: Path) -> None:
    provider = DuckDBConnectionProvider(tmp_path / "does-not-exist.duckdb")
    provider.close()  # must not raise


def test_close_is_idempotent(db_path: Path) -> None:
    provider = DuckDBConnectionProvider(db_path)
    _ = provider.connection  # open a connection so there's something to close
    provider.close()
    provider.close()  # must not raise
