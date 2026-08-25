"""The /health custom route registered on the MCPServer by build_server().

Exercised via the real streamable_http_app() (Starlette ASGI app), not by
calling the handler function directly, so this also proves the route is
actually wired into the HTTP app a deployment would serve.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import httpx

from starrydata_mcp.infrastructure.duckdb.schema import create_tables
from starrydata_mcp.interface.mcp_server import build_server


async def test_health_reports_ok_and_dataset_summary(db_path: Path) -> None:
    server = build_server(db_path)
    app = server.streamable_http_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["read_only"] is True
    assert "CC BY 4.0" in body["data_source"]
    assert body["totals"]["papers"] == 2
    assert body["totals"]["curves"] == 3
    assert "is_stale" in body


async def test_health_reports_503_when_dataset_meta_is_missing(tmp_path: Path) -> None:
    # A DB with tables but no dataset_meta row (e.g. never `ingest`ed) must
    # report unhealthy, not a bare 200 or an unhandled 500.
    dest = tmp_path / "empty.duckdb"
    con = duckdb.connect(str(dest))
    create_tables(con)
    con.close()

    server = build_server(dest)
    app = server.streamable_http_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
