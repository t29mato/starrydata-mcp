"""Use case backing the `get_curve_data` MCP tool."""

from __future__ import annotations

from starrydata_mcp.domain.citation import format_citation
from starrydata_mcp.domain.repositories import CurveRepository, PaperRepository

from ..dto import CurveDataDTO


class GetCurveDataUseCase:
    def __init__(self, curve_repo: CurveRepository, paper_repo: PaperRepository) -> None:
        self._curve_repo = curve_repo
        self._paper_repo = paper_repo

    def execute(self, curve_ids: tuple[int, ...]) -> list[CurveDataDTO]:
        curves = self._curve_repo.get_by_ids(curve_ids)
        citation_cache: dict[str, str | None] = {}

        def citation_for(sid: str) -> str | None:
            if sid not in citation_cache:
                paper = self._paper_repo.get_by_sid(sid)
                citation_cache[sid] = format_citation(paper) if paper is not None else None
            return citation_cache[sid]

        return [
            CurveDataDTO(
                curve_id=c.curve_id,
                sample_uid=c.sample_uid,
                composition=c.composition_raw,
                prop_x=c.prop_x,
                prop_y=c.prop_y,
                unit_x=c.unit_x,
                unit_y=c.unit_y,
                x=c.x,
                y=c.y,
                comments=c.comments,
                paper_citation=citation_for(c.sid),
            )
            for c in curves
        ]
