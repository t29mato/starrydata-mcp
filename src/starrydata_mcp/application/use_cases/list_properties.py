"""Use case backing the `list_properties` MCP tool."""

from __future__ import annotations

from starrydata_mcp.domain.repositories import CurveRepository

from ..dto import PropertyUsageDTO


class ListPropertiesUseCase:
    def __init__(self, curve_repo: CurveRepository) -> None:
        self._curve_repo = curve_repo

    def execute(self, *, project: str | None = None, top_n: int = 50) -> list[PropertyUsageDTO]:
        usages = self._curve_repo.list_properties(project=project, top_n=top_n)
        return [
            PropertyUsageDTO(
                prop_x=u.prop_x,
                prop_y=u.prop_y,
                unit_x=u.unit_x,
                unit_y=u.unit_y,
                curve_count=u.curve_count,
            )
            for u in usages
        ]
