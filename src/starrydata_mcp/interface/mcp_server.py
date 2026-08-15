"""Composition root for the MCP server: wires DuckDB repositories into the
8 application use cases and exposes them as MCP tools.

Tool descriptions follow docs/design/architecture.md §3 — written for an
agent to read once and use correctly, not for a human skimming docs. The
"search -> narrow -> fetch" three-tier split (search_materials/search_curves
return light summaries; get_sample_detail/get_curve_data return the heavy
payload) exists specifically so an agent doesn't accidentally pull hundreds
of (x, y) arrays into context in one call.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from starrydata_mcp.application.dto import (
    CurveDataDTO,
    CurveSummaryDTO,
    DatasetInfoDTO,
    PaperDetailDTO,
    PaperSummaryDTO,
    PropertyUsageDTO,
    SampleDetailDTO,
    SampleSummaryDTO,
)
from starrydata_mcp.application.use_cases.get_curve_data import GetCurveDataUseCase
from starrydata_mcp.application.use_cases.get_dataset_info import GetDatasetInfoUseCase
from starrydata_mcp.application.use_cases.get_paper_detail import GetPaperDetailUseCase
from starrydata_mcp.application.use_cases.get_sample_detail import GetSampleDetailUseCase
from starrydata_mcp.application.use_cases.list_properties import ListPropertiesUseCase
from starrydata_mcp.application.use_cases.search_curves import SearchCurvesUseCase
from starrydata_mcp.application.use_cases.search_materials import SearchMaterialsUseCase
from starrydata_mcp.application.use_cases.search_papers import SearchPapersUseCase
from starrydata_mcp.infrastructure.clock import SystemClock
from starrydata_mcp.infrastructure.duckdb.connection import DuckDBConnectionProvider
from starrydata_mcp.infrastructure.duckdb.curve_repository import DuckDBCurveRepository
from starrydata_mcp.infrastructure.duckdb.dataset_info_repository import (
    DuckDBDatasetInfoRepository,
)
from starrydata_mcp.infrastructure.duckdb.paper_repository import DuckDBPaperRepository
from starrydata_mcp.infrastructure.duckdb.sample_repository import DuckDBSampleRepository

SERVER_INSTRUCTIONS = (
    "Tools for searching Starrydata, an open database of materials-science "
    "property data digitized from published papers (thermoelectric, battery, "
    "magnetic, and dielectric materials). Call get_dataset_info first to learn "
    "the data's snapshot date, license, and citation. Then search top-down: "
    "search_materials or search_curves to find candidates (lightweight "
    "summaries only), then get_sample_detail or get_curve_data to fetch the "
    "full details/data points for the ones you actually need."
)


def build_server(db_path: Path) -> MCPServer:
    provider = DuckDBConnectionProvider(db_path)
    paper_repo = DuckDBPaperRepository(provider)
    sample_repo = DuckDBSampleRepository(provider)
    curve_repo = DuckDBCurveRepository(provider)
    dataset_info_repo = DuckDBDatasetInfoRepository(provider)

    search_materials_uc = SearchMaterialsUseCase(sample_repo, curve_repo)
    get_sample_detail_uc = GetSampleDetailUseCase(sample_repo, curve_repo, paper_repo)
    list_properties_uc = ListPropertiesUseCase(curve_repo)
    search_curves_uc = SearchCurvesUseCase(curve_repo)
    get_curve_data_uc = GetCurveDataUseCase(curve_repo, paper_repo)
    search_papers_uc = SearchPapersUseCase(paper_repo)
    get_paper_detail_uc = GetPaperDetailUseCase(paper_repo, sample_repo, curve_repo)
    get_dataset_info_uc = GetDatasetInfoUseCase(dataset_info_repo, SystemClock())

    server: MCPServer = MCPServer(
        name="starrydata-mcp",
        instructions=SERVER_INSTRUCTIONS,
    )

    @server.tool(
        description=(
            "Search Starrydata samples by chemical composition, constituent elements, "
            "or research domain (thermoelectric/battery/magnetic/dielectric materials). "
            "Use this FIRST to find candidate samples before fetching their measured "
            "property curves. `composition` does a case-insensitive substring match "
            "against the raw formula string (e.g. \"Bi2Te3\"); if you want to ignore "
            "stoichiometry differences, pass `elements` instead (e.g. [\"Bi\",\"Te\"]) "
            "for an AND match on constituent elements. Returns lightweight summaries "
            "only (sample_uid, composition, project_names, and the list of properties "
            "measured on each sample) — no curve data points. Call get_sample_detail "
            "for full metadata on one sample, or search_curves/get_curve_data for the "
            "actual measured data."
        )
    )
    def search_materials(
        composition: str | None = None,
        elements: list[str] | None = None,
        project: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[SampleSummaryDTO]:
        return search_materials_uc.execute(
            composition=composition,
            elements=tuple(elements) if elements else None,
            project=project,
            limit=limit,
            offset=offset,
        )

    @server.tool(
        description=(
            "Fetch full metadata for one sample by its sample_uid (from search_materials "
            "or search_curves results): composition, fabrication/measurement metadata, "
            "the source paper's citation, and an index of every property curve measured "
            "on it (property names, units, point counts — no raw x/y arrays). Pass the "
            "curve_id values from that index to get_curve_data if you need the actual "
            "data points."
        )
    )
    def get_sample_detail(sample_uid: str) -> SampleDetailDTO | None:
        return get_sample_detail_uc.execute(sample_uid)

    @server.tool(
        description=(
            "List the (prop_x, prop_y) property-pair vocabulary recorded in Starrydata "
            "curves — e.g. Temperature vs Seebeck coefficient (V*K^-1), ranked by how "
            "many curves use each pair. Property names are extracted verbatim from "
            "plot axis labels, so they have some spelling variation. Call this BEFORE "
            "search_curves if you're not sure of the exact property name — passing a "
            "guessed name to search_curves will just return zero results."
        )
    )
    def list_properties(
        project: str | None = None, top_n: int = 50
    ) -> list[PropertyUsageDTO]:
        return list_properties_uc.execute(project=project, top_n=top_n)

    @server.tool(
        description=(
            "Search for measured property-vs-property curves (e.g. Seebeck coefficient "
            "vs Temperature), filterable by exact property-pair (use list_properties "
            "first to get the exact prop_x/prop_y strings), composition/elements, the "
            "numeric range of the x-axis (x_min/x_max — matches curves whose x-values "
            "overlap that range, e.g. only curves covering 300-500 K), and research "
            "domain. Returns lightweight summaries (curve_id, sample_uid, composition, "
            "units, point count, observed x/y ranges, source DOI) — NOT the raw data "
            "points. Call get_curve_data with the curve_id values you actually want."
        )
    )
    def search_curves(
        prop_x: str | None = None,
        prop_y: str | None = None,
        composition: str | None = None,
        elements: list[str] | None = None,
        x_min: float | None = None,
        x_max: float | None = None,
        project: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[CurveSummaryDTO]:
        return search_curves_uc.execute(
            prop_x=prop_x,
            prop_y=prop_y,
            composition=composition,
            elements=tuple(elements) if elements else None,
            x_min=x_min,
            x_max=x_max,
            project=project,
            limit=limit,
            offset=offset,
        )

    @server.tool(
        description=(
            "Fetch the full digitized (x, y) data points for one or more curves by "
            "curve_id, along with axis units and a citation for the source paper. Call "
            "this only after narrowing candidates with search_curves or "
            "get_sample_detail — arrays can hold dozens of points each, so keep "
            "requests to roughly 20 curve_ids or fewer at a time."
        )
    )
    def get_curve_data(curve_ids: list[int]) -> list[CurveDataDTO]:
        return get_curve_data_uc.execute(tuple(curve_ids))

    @server.tool(
        description=(
            "Search papers indexed in Starrydata by DOI, author name, title keyword, "
            "publication year range, or research domain. Use this to locate a specific "
            "paper's data (then call get_paper_detail), or to build a citation list for "
            "materials you've already found via search_materials/search_curves. Each "
            "result includes a ready-to-use citation string."
        )
    )
    def search_papers(
        doi: str | None = None,
        author: str | None = None,
        title_keyword: str | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        project: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PaperSummaryDTO]:
        return search_papers_uc.execute(
            doi=doi,
            author=author,
            title_keyword=title_keyword,
            year_min=year_min,
            year_max=year_max,
            project=project,
            limit=limit,
            offset=offset,
        )

    @server.tool(
        description=(
            "Fetch one paper's full record by its `sid` (from search_papers results): "
            "citation, and every sample and curve extracted from that paper (as "
            "lightweight summaries — no raw curve data points). Use this when you want "
            "everything a single publication contributed to Starrydata, e.g. \"show me "
            "all the materials and measurements from this paper.\""
        )
    )
    def get_paper_detail(sid: str) -> PaperDetailDTO | None:
        return get_paper_detail_uc.execute(sid)

    @server.tool(
        description=(
            "Report this server's local data snapshot date, record counts, license "
            "(CC BY 4.0), and the citation required when you use this data, plus "
            "whether the local copy is stale (db_snapshot older than 24h, which usually "
            "means the daily refresh job isn't running). Call this once at the start of "
            "a session so you can tell the user how current the data is and cite it "
            "correctly."
        )
    )
    def get_dataset_info() -> DatasetInfoDTO:
        return get_dataset_info_uc.execute()

    return server
