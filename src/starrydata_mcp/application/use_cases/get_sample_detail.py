"""Use case backing the `get_sample_detail` MCP tool."""

from __future__ import annotations

from starrydata_mcp.domain.citation import format_citation
from starrydata_mcp.domain.repositories import CurveRepository, PaperRepository, SampleRepository

from ..dto import SampleDetailDTO
from ..mappers import curve_summary_to_dto


class GetSampleDetailUseCase:
    def __init__(
        self,
        sample_repo: SampleRepository,
        curve_repo: CurveRepository,
        paper_repo: PaperRepository,
    ) -> None:
        self._sample_repo = sample_repo
        self._curve_repo = curve_repo
        self._paper_repo = paper_repo

    def execute(self, sample_uid: str) -> SampleDetailDTO | None:
        sample = self._sample_repo.get_by_uid(sample_uid)
        if sample is None:
            return None

        curves = self._curve_repo.list_by_sample_uid(sample_uid)
        paper = self._paper_repo.get_by_sid(sample.sid)
        citation = format_citation(paper) if paper is not None else None

        return SampleDetailDTO(
            sample_uid=sample.sample_uid,
            sample_name=sample.sample_name,
            composition=sample.composition_raw,
            elements=sample.elements,
            composition_details=sample.composition_details,
            sample_info=sample.sample_info_raw,
            sid=sample.sid,
            paper_citation=citation,
            curves=tuple(curve_summary_to_dto(c) for c in curves),
        )
