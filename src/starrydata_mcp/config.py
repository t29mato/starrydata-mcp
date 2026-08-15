"""Local paths/thresholds. No I/O at import time — safe for domain-adjacent
code and tests to import.
"""

from __future__ import annotations

import os
from pathlib import Path


def cache_dir() -> Path:
    override = os.environ.get("STARRYDATA_MCP_CACHE_DIR")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "starrydata-mcp"


def db_path() -> Path:
    return cache_dir() / "starrydata.duckdb"
