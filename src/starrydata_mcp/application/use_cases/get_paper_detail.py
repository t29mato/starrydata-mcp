"""Use case backing the `get_paper_detail` MCP tool."""

from __future__ import annotations

from starrydata_mcp.domain.citation import format_citation
from starrydata_mcp.domain.entities import CurveSummary
from starrydata_mcp.domain.repositories import CurveRepository, PaperRepository, SampleRepository

from ..dto import PaperDetailDTO
from ..mappers import curve_summary_to_dto, sample_to_summary_dto


class GetPaperDetailUseCase:
    def __init__(
        self,
        paper_repo: PaperRepository,
        sample_repo: SampleRepository,
        curve_repo: CurveRepository,
    ) -> None:
        self._paper_repo = paper_repo
        self._sample_repo = sample_repo
        self._curve_repo = curve_repo

    def execute(self, sid: str) -> PaperDetailDTO | None:
        paper = self._paper_repo.get_by_sid(sid)
        if paper is None:
            return None

        samples = self._sample_repo.list_by_sid(sid)
        curve_summaries = self._curve_repo.list_by_sid(sid)
        curves_by_sample: dict[str, list[CurveSummary]] = {}
        for c in curve_summaries:
            curves_by_sample.setdefault(c.sample_uid, []).append(c)

        return PaperDetailDTO(
            sid=paper.sid,
            doi=paper.doi,
            title=paper.title,
            citation=format_citation(paper),
            project_names=paper.project_names,
            samples=tuple(
                sample_to_summary_dto(s, curves_by_sample.get(s.sample_uid, [])) for s in samples
            ),
            curves=tuple(curve_summary_to_dto(c) for c in curve_summaries),
        )
