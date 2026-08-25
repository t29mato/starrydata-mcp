#!/usr/bin/env python3
"""Real end-to-end verification of `starrydata-mcp serve --http`.

Starts the actual `starrydata-mcp serve --http :<port>` CLI as a subprocess
against whatever local DuckDB file `starrydata-mcp ingest` has already
built (default `~/.cache/starrydata-mcp/starrydata.duckdb`; override with
STARRYDATA_MCP_CACHE_DIR same as the CLI itself), waits for /health, then
connects a *real* MCP client (`mcp.client.Client`, streamable-HTTP
transport — the same client library an agent would use) and calls all 8
tools with realistic arguments.

Not a pytest test on purpose (HQ's HTTP-transport task, 2026-08-25 — see
docs/deploy/huggingface-spaces.md): meant to be run by a human against real
data before/after a deployment change, not as part of the fixture-data CI
suite. For a fast, CI-safe regression test of the same wiring (fixture DB,
no real network), see tests/interface/test_http_server_e2e.py.

Usage:
    uv run python scripts/verify_http_server.py [--port 18790]

Exit code is 0 iff every check passed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

from mcp.client import Client


def _wait_for_health(base_url: str, *, timeout_s: float) -> dict:
    deadline = time.monotonic() + timeout_s
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=2) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last_error = exc
            time.sleep(0.2)
    raise TimeoutError(f"/health never responded within {timeout_s}s") from last_error


async def _run_checks(mcp_url: str) -> list[str]:
    """Returns a list of failure descriptions; empty means everything passed."""
    failures: list[str] = []

    async with Client(mcp_url) as client:
        tools_result = await client.list_tools()
        tool_names = {t.name for t in tools_result.tools}
        expected = {
            "search_materials",
            "get_sample_detail",
            "list_properties",
            "search_curves",
            "get_curve_data",
            "search_papers",
            "get_paper_detail",
            "get_dataset_info",
        }
        if tool_names != expected:
            failures.append(f"tool set mismatch: got {sorted(tool_names)}, want {sorted(expected)}")

        def check(label: str, result) -> None:  # noqa: ANN001
            print(f"  {label} -> {result.structured_content}")
            if result.is_error:
                failures.append(f"{label} reported is_error")

        # get_dataset_info first, like the server's own instructions tell an agent to.
        info = await client.call_tool("get_dataset_info", {})
        check("get_dataset_info", info)

        materials = await client.call_tool(
            "search_materials", {"elements": ["Bi", "Te"], "limit": 3}
        )
        check("search_materials(elements=[Bi,Te])", materials)

        properties = await client.call_tool("list_properties", {"top_n": 5})
        check("list_properties(top_n=5)", properties)

        curves = await client.call_tool(
            "search_curves", {"prop_x": "Temperature", "prop_y": "ZT", "limit": 3}
        )
        check("search_curves(Temperature vs ZT)", curves)
        curve_summaries = curves.structured_content.get("result", [])

        if curve_summaries:
            curve_id = curve_summaries[0]["curve_id"]
            curve_data = await client.call_tool("get_curve_data", {"curve_ids": [curve_id]})
            check(f"get_curve_data(curve_ids=[{curve_id}])", curve_data)

            sample_uid = curve_summaries[0]["sample_uid"]
            detail = await client.call_tool("get_sample_detail", {"sample_uid": sample_uid})
            check(f"get_sample_detail({sample_uid!r})", detail)

        papers = await client.call_tool(
            "search_papers", {"title_keyword": "thermoelectric", "limit": 3}
        )
        check("search_papers(title_keyword='thermoelectric')", papers)
        paper_results = papers.structured_content.get("result", [])

        if paper_results:
            sid = paper_results[0]["sid"]
            paper_detail = await client.call_tool("get_paper_detail", {"sid": sid})
            check(f"get_paper_detail(sid={sid!r})", paper_detail)

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18790)
    parser.add_argument("--startup-timeout", type=float, default=15.0)
    args = parser.parse_args()

    base_url = f"http://127.0.0.1:{args.port}"
    print(f"Starting `starrydata-mcp serve --http :{args.port}` ...")
    proc = subprocess.Popen(
        ["uv", "run", "starrydata-mcp", "serve", "--http", f":{args.port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        health = _wait_for_health(base_url, timeout_s=args.startup_timeout)
        print(f"/health -> {health}")
        if health.get("status") != "ok":
            print("FAIL: /health did not report status=ok", file=sys.stderr)
            return 1

        failures = asyncio.run(_run_checks(f"{base_url}/mcp"))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    if failures:
        print("\nFAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("\nAll checks passed: 8/8 tools reachable over streamable-HTTP.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
