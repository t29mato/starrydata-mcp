"""Shared domain-entity -> DTO mappers, reused across use cases."""

from __future__ import annotations

from starrydata_mcp.domain.citation import format_citation
from starrydata_mcp.domain.entities import CurveSummary, Paper, Sample

from .dto import CurveSummaryDTO, PaperSummaryDTO, SampleSummaryDTO


def curve_summary_to_dto(summary: CurveSummary) -> CurveSummaryDTO:
    return CurveSummaryDTO(
        curve_id=summary.curve_id,
        sample_uid=summary.sample_uid,
        composition=summary.composition_raw,
        figure_id=summary.figure_id,
        figure_name=summary.figure_name,
        prop_x=summary.prop_x,
        prop_y=summary.prop_y,
        unit_x=summary.unit_x,
        unit_y=summary.unit_y,
        point_count=summary.point_count,
        x_min=summary.x_min,
        x_max=summary.x_max,
        y_min=summary.y_min,
        y_max=summary.y_max,
        paper_doi=summary.doi,
        project_names=summary.project_names,
    )


def sample_to_summary_dto(sample: Sample, curves: list[CurveSummary]) -> SampleSummaryDTO:
    """Derive a sample's `properties`/`project_names`/`paper_doi` from its
    curves — mirrors the real dataset's membership rule (docs/design/
    architecture.md §1.2): samples don't carry `project_names` themselves,
    only their curves do.
    """
    properties = sorted({f"{c.prop_x} vs {c.prop_y}" for c in curves})
    project_names = sorted({p for c in curves for p in c.project_names})
    paper_doi = curves[0].doi if curves else None
    return SampleSummaryDTO(
        sample_uid=sample.sample_uid,
        sample_name=sample.sample_name,
        composition=sample.composition_raw,
        elements=sample.elements,
        sid=sample.sid,
        paper_doi=paper_doi,
        project_names=tuple(project_names),
        properties=tuple(properties),
    )


def paper_to_summary_dto(paper: Paper) -> PaperSummaryDTO:
    return PaperSummaryDTO(
        sid=paper.sid,
        doi=paper.doi,
        title=paper.title,
        issued_year=paper.issued_year,
        citation=format_citation(paper),
        project_names=paper.project_names,
    )
