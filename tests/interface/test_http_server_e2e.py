"""Real end-to-end test of `starrydata-mcp serve --http`: a real subprocess,
a real MCP client (streamable-HTTP), against the small fixture DB — the
fast, CI-safe complement to scripts/verify_http_server.py (which does the
same thing against real production data, for a human to run before/after a
deployment change).
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from mcp.client import Client


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_health(base_url: str, *, timeout_s: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_s
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last_error = exc
        time.sleep(0.1)
    raise TimeoutError(f"/health never responded within {timeout_s}s") from last_error


@pytest.fixture
def running_server(db_path: Path, tmp_path: Path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    shutil.copy(db_path, cache_dir / "starrydata.duckdb")

    port = _free_port()
    env = {"STARRYDATA_MCP_CACHE_DIR": str(cache_dir), "PATH": os.environ["PATH"]}
    proc = subprocess.Popen(
        [sys.executable, "-m", "starrydata_mcp.cli", "serve", "--http", f":{port}"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_health(base_url)
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


async def test_health_endpoint_over_real_http(running_server: str) -> None:
    with urllib.request.urlopen(f"{running_server}/health") as resp:
        body = json.loads(resp.read())
    assert body["status"] == "ok"
    assert body["totals"]["papers"] == 2


async def test_real_mcp_client_can_call_every_tool_over_streamable_http(
    running_server: str,
) -> None:
    async with Client(f"{running_server}/mcp") as client:
        tools = await client.list_tools()
        assert {t.name for t in tools.tools} == {
            "search_materials",
            "get_sample_detail",
            "list_properties",
            "search_curves",
            "get_curve_data",
            "search_papers",
            "get_paper_detail",
            "get_dataset_info",
        }

        info = await client.call_tool("get_dataset_info", {})
        assert info.is_error is False
        assert info.structured_content["license"] == "CC BY 4.0"

        materials = await client.call_tool("search_materials", {"elements": ["Pb", "Te"]})
        assert materials.is_error is False
        [sample] = materials.structured_content["result"]
        assert sample["sample_uid"] == "6:113"

        curves = await client.call_tool("search_curves", {"prop_x": "Temperature", "prop_y": "ZT"})
        assert curves.is_error is False
        [curve] = curves.structured_content["result"]
        assert curve["curve_id"] == 2

        curve_data = await client.call_tool("get_curve_data", {"curve_ids": [2]})
        assert curve_data.is_error is False
        assert curve_data.structured_content["result"][0]["x"] == [300.0, 600.0]
