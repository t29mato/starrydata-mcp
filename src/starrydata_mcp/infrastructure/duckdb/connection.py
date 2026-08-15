"""Read-only DuckDB connection that transparently picks up a new file after
the daily ingestion pipeline atomically renames a fresh `.duckdb` into place
(docs/design/architecture.md §2.2) — no server restart required.
"""

from __future__ import annotations

from pathlib import Path

import duckdb


class DuckDBConnectionProvider:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._con: duckdb.DuckDBPyConnection | None = None
        self._opened_mtime: float | None = None

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        mtime = self._db_path.stat().st_mtime
        if self._con is None or mtime != self._opened_mtime:
            if self._con is not None:
                self._con.close()
            self._con = duckdb.connect(str(self._db_path), read_only=True)
            self._opened_mtime = mtime
        return self._con

    def close(self) -> None:
        if self._con is not None:
            self._con.close()
            self._con = None
