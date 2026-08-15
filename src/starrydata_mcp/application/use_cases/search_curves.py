"""Use case backing the `search_curves` MCP tool."""

from __future__ import annotations

from starrydata_mcp.domain.repositories import CurveRepository

from ..dto import CurveSummaryDTO
from ..mappers import curve_summary_to_dto


class SearchCurvesUseCase:
    def __init__(self, curve_repo: CurveRepository) -> None:
        self._curve_repo = curve_repo

    def execute(
        self,
        *,
        prop_x: str | None = None,
        prop_y: str | None = None,
        composition: str | None = None,
        elements: tuple[str, ...] | None = None,
        x_min: float | None = None,
        x_max: float | None = None,
        project: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[CurveSummaryDTO]:
        summaries = self._curve_repo.search(
            prop_x=prop_x,
            prop_y=prop_y,
            composition=composition,
            elements=elements,
            x_min=x_min,
            x_max=x_max,
            project=project,
            limit=limit,
            offset=offset,
        )
        return [curve_summary_to_dto(s) for s in summaries]
