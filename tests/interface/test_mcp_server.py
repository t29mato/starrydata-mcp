"""Smoke tests: build_server() against the fixture DB, call every tool
through the real MCP call_tool path (not by importing internals), and check
each returns something sane. This is what actually exercises the tool
descriptions/schemas an agent would see.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from starrydata_mcp.interface.mcp_server import build_server

EXPECTED_TOOL_NAMES = {
    "search_materials",
    "get_sample_detail",
    "list_properties",
    "search_curves",
    "get_curve_data",
    "search_papers",
    "get_paper_detail",
    "get_dataset_info",
}


@pytest.fixture
def server(db_path: Path):
    return build_server(db_path)


async def test_registers_exactly_the_eight_designed_tools(server) -> None:
    tools = await server.list_tools()
    assert {t.name for t in tools} == EXPECTED_TOOL_NAMES


async def test_every_tool_has_a_nonempty_description(server) -> None:
    tools = await server.list_tools()
    for tool in tools:
        assert tool.description and len(tool.description) > 30, tool.name


async def test_server_instructions_mention_dataset_info_first(server) -> None:
    assert "get_dataset_info" in (server._lowlevel_server.instructions or "")


async def test_search_materials_finds_the_pbte_sample(server) -> None:
    result = await server.call_tool("search_materials", {"composition": "Pb1.00025"})
    assert result.is_error is False
    [sample] = result.structured_content["result"]
    assert sample["sample_uid"] == "6:113"
    assert sample["properties"] == [
        "Temperature vs Seebeck coefficient",
        "Temperature vs ZT",
    ]


async def test_search_materials_by_elements(server) -> None:
    result = await server.call_tool("search_materials", {"elements": ["Li"]})
    [sample] = result.structured_content["result"]
    assert sample["sample_uid"] == "42:1"


async def test_get_sample_detail_round_trip(server) -> None:
    result = await server.call_tool("get_sample_detail", {"sample_uid": "6:113"})
    detail = result.structured_content["result"]
    assert detail["composition"] == "Pb1.00025Zn0.02Te1.02I0.0005"
    assert len(detail["curves"]) == 2
    assert "Xiao" in detail["paper_citation"]


async def test_get_sample_detail_unknown_uid_returns_null(server) -> None:
    result = await server.call_tool("get_sample_detail", {"sample_uid": "nope"})
    assert result.structured_content["result"] is None


async def test_list_properties_ranked(server) -> None:
    result = await server.call_tool("list_properties", {})
    usages = result.structured_content["result"]
    assert len(usages) == 3


async def test_search_curves_by_property_pair(server) -> None:
    result = await server.call_tool(
        "search_curves", {"prop_x": "Temperature", "prop_y": "ZT"}
    )
    [curve] = result.structured_content["result"]
    assert curve["curve_id"] == 2
    assert curve["point_count"] == 2


async def test_get_curve_data_returns_full_arrays(server) -> None:
    result = await server.call_tool("get_curve_data", {"curve_ids": [1]})
    [curve] = result.structured_content["result"]
    assert curve["x"] == [300.0, 350.0, 400.0]
    assert curve["y"] == [-0.00015, -0.00018, -0.00021]


async def test_search_papers_by_doi(server) -> None:
    result = await server.call_tool("search_papers", {"doi": "10.1000/battery.example"})
    [paper] = result.structured_content["result"]
    assert paper["sid"] == "42"
    assert "Ando" in paper["citation"]


async def test_get_paper_detail_round_trip(server) -> None:
    result = await server.call_tool("get_paper_detail", {"sid": "6"})
    detail = result.structured_content["result"]
    assert len(detail["samples"]) == 2
    assert len(detail["curves"]) == 2


async def test_get_dataset_info_reports_license_and_freshness(server) -> None:
    result = await server.call_tool("get_dataset_info", {})
    # A single-object (non-list) return isn't wrapped in {"result": ...}.
    info = result.structured_content
    assert info["license"] == "CC BY 4.0"
    assert info["papers"] == 2
    assert "is_stale" in info
