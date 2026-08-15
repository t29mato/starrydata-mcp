"""Pure domain value objects. No I/O, no third-party dependencies.

Field shapes mirror the real dataset (docs/design/architecture.md §1.2 /
§2.3), but this module knows nothing about CSV, DuckDB, or MCP.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Author:
    given: str
    family: str


@dataclass(frozen=True, slots=True)
class Paper:
    sid: str
    doi: str | None
    url: str | None
    issued_year: int | None
    issued_month: int | None
    issued_day: int | None
    authors: tuple[Author, ...]
    title: str | None
    container_title: str | None
    container_title_short: str | None
    volume: str | None
    issue: str | None
    page: str | None
    issn: str | None
    publisher: str | None
    project_names: tuple[str, ...]
    created_at: str | None


@dataclass(frozen=True, slots=True)
class Sample:
    sample_uid: str
    """`f"{sid}:{sample_id}"` — `sample_id` alone is only unique within a paper."""

    sid: str
    sample_id: str
    sample_name: str | None
    composition_raw: str
    elements: tuple[str, ...]
    """Best-effort parse of `composition_raw` via `composition.parse_elements`."""

    composition_details: str | None
    sample_info_raw: dict[str, object]
    created_at: str | None
    updated_at: str | None


@dataclass(frozen=True, slots=True)
class CurveSummary:
    """A curve without its (x, y) payload — cheap to return in bulk from search."""

    curve_id: int
    sid: str
    sample_uid: str
    doi: str | None
    composition_raw: str
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
    project_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Curve:
    """A curve including its full digitized (x, y) data points."""

    curve_id: int
    sid: str
    sample_uid: str
    doi: str | None
    composition_raw: str
    figure_id: str | None
    figure_name: str | None
    prop_x: str
    prop_y: str
    unit_x: str | None
    unit_y: str | None
    x: tuple[float, ...]
    y: tuple[float, ...]
    project_names: tuple[str, ...]
    comments: str | None

    def summary(self) -> CurveSummary:
        return CurveSummary(
            curve_id=self.curve_id,
            sid=self.sid,
            sample_uid=self.sample_uid,
            doi=self.doi,
            composition_raw=self.composition_raw,
            figure_id=self.figure_id,
            figure_name=self.figure_name,
            prop_x=self.prop_x,
            prop_y=self.prop_y,
            unit_x=self.unit_x,
            unit_y=self.unit_y,
            point_count=len(self.x),
            x_min=min(self.x) if self.x else None,
            x_max=max(self.x) if self.x else None,
            y_min=min(self.y) if self.y else None,
            y_max=max(self.y) if self.y else None,
            project_names=self.project_names,
        )


@dataclass(frozen=True, slots=True)
class PropertyUsage:
    """One row of the `list_properties` catalog: a (prop_x, prop_y) pair and
    how common it is, so an agent can discover the controlled vocabulary
    before calling `search_curves`."""

    prop_x: str
    prop_y: str
    unit_x: str | None
    unit_y: str | None
    curve_count: int


@dataclass(frozen=True, slots=True)
class DatasetTotals:
    papers: int
    figures: int
    samples: int
    curves: int


@dataclass(frozen=True, slots=True)
class DatasetInfo:
    db_snapshot: datetime | None
    """When the upstream Starrydata DB was snapshotted (per manifest.json)."""

    generated_at: datetime | None
    """When this local DuckDB replica was built."""

    totals: DatasetTotals
    license: str
    citation: str
    source_url: str
