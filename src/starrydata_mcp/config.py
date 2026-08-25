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


def rate_limit_max_requests() -> int:
    """Max requests per client IP per window, for `serve --http` deployments.

    Tunable without a code change (e.g. on the HF Spaces free tier) since
    the right number depends on expected traffic, not on the code.
    """
    return int(os.environ.get("STARRYDATA_MCP_RATE_LIMIT_MAX", "60"))


def rate_limit_window_seconds() -> float:
    return float(os.environ.get("STARRYDATA_MCP_RATE_LIMIT_WINDOW_SECONDS", "60"))
