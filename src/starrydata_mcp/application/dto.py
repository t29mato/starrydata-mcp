"""DTOs returned by the application layer's use cases.

These are the shapes the interface layer (MCP tools) hands back to agents,
so field names/docstrings here double as part of the tool response contract.
Pydantic is used purely for JSON-friendly serialization/validation — no
domain logic lives here.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SampleSummaryDTO(BaseModel):
    sample_uid: str
    sample_name: str | None
    composition: str
    elements: tuple[str, ...]
    sid: str
    paper_doi: str | None
    project_names: tuple[str, ...]
    properties: tuple[str, ...]
    """Distinct "prop_x vs prop_y" strings measured on this sample."""


class CurveSummaryDTO(BaseModel):
    curve_id: int
    sample_uid: str
    composition: str
    figure_id: str | None
    figure_name: str | None
    prop_x: str
    prop_y: str
    unit_x: str | None
    unit_y: str | None
    point_count: int
    x_min: float | None
    x_max: float | None
    y_min: float | None
    y_max: float | None
    paper_doi: str | None
    project_names: tuple[str, ...]


class SampleDetailDTO(BaseModel):
    sample_uid: str
    sample_name: str | None
    composition: str
    elements: tuple[str, ...]
    composition_details: str | None
    sample_info: dict[str, object]
    sid: str
    paper_citation: str | None
    curves: tuple[CurveSummaryDTO, ...]


class CurveDataDTO(BaseModel):
    curve_id: int
    sample_uid: str
    composition: str
    prop_x: str
    prop_y: str
    unit_x: str | None
    unit_y: str | None
    x: tuple[float, ...]
    y: tuple[float, ...]
    comments: str | None
    paper_citation: str | None


class PropertyUsageDTO(BaseModel):
    prop_x: str
    prop_y: str
    unit_x: str | None
    unit_y: str | None
    curve_count: int


class PaperSummaryDTO(BaseModel):
    sid: str
    doi: str | None
    title: str | None
    issued_year: int | None
    citation: str
    project_names: tuple[str, ...]


class PaperDetailDTO(BaseModel):
    sid: str
    doi: str | None
    title: str | None
    citation: str
    project_names: tuple[str, ...]
    samples: tuple[SampleSummaryDTO, ...]
    curves: tuple[CurveSummaryDTO, ...]


class DatasetInfoDTO(BaseModel):
    db_snapshot: datetime | None
    generated_at: datetime | None
    papers: int
    figures: int
    samples: int
    curves: int
    license: str
    citation: str
    source_url: str
    is_stale: bool
    """True when `db_snapshot` is more than `stale_after` old (default 24h)."""
