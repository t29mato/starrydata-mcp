"""Maps raw DuckDB result rows back into domain entities.

Kept separate from the repository classes so the SQL-shape <-> entity-shape
mapping is easy to unit test in isolation from a live connection.
"""

from __future__ import annotations

import json

from starrydata_mcp.domain.entities import (
    Author,
    Curve,
    CurveSummary,
    Paper,
    Sample,
)

PAPER_COLUMNS = (
    "sid, doi, url, issued_year, issued_month, issued_day, authors, title, "
    "container_title, container_title_short, volume, issue, page, issn, "
    "publisher, project_names, created_at"
)

SAMPLE_COLUMNS = (
    "sample_uid, sid, sample_id, sample_name, composition_raw, elements, "
    "composition_details, sample_info_raw, created_at, updated_at"
)

CURVE_SUMMARY_COLUMNS = (
    "curve_id, sid, sample_uid, doi, composition_raw, figure_id, figure_name, "
    "prop_x, prop_y, unit_x, unit_y, point_count, x_min, x_max, y_min, y_max, "
    "project_names"
)

CURVE_FULL_COLUMNS = (
    "curve_id, sid, sample_uid, doi, composition_raw, figure_id, figure_name, "
    "prop_x, prop_y, unit_x, unit_y, x, y, project_names, comments"
)


def row_to_paper(row: tuple[object, ...]) -> Paper:
    (
        sid, doi, url, issued_year, issued_month, issued_day, authors_json,
        title, container_title, container_title_short, volume, issue, page,
        issn, publisher, project_names, created_at,
    ) = row
    authors = tuple(
        Author(given=a.get("given", ""), family=a.get("family", ""))
        for a in json.loads(authors_json or "[]")
    )
    return Paper(
        sid=sid,
        doi=doi,
        url=url,
        issued_year=issued_year,
        issued_month=issued_month,
        issued_day=issued_day,
        authors=authors,
        title=title,
        container_title=container_title,
        container_title_short=container_title_short,
        volume=volume,
        issue=issue,
        page=page,
        issn=issn,
        publisher=publisher,
        project_names=tuple(project_names or ()),
        created_at=created_at,
    )


def row_to_sample(row: tuple[object, ...]) -> Sample:
    (
        sample_uid, sid, sample_id, sample_name, composition_raw, elements,
        composition_details, sample_info_raw, created_at, updated_at,
    ) = row
    return Sample(
        sample_uid=sample_uid,
        sid=sid,
        sample_id=sample_id,
        sample_name=sample_name,
        composition_raw=composition_raw,
        elements=tuple(elements or ()),
        composition_details=composition_details,
        sample_info_raw=json.loads(sample_info_raw) if sample_info_raw else {},
        created_at=created_at,
        updated_at=updated_at,
    )


def row_to_curve_summary(row: tuple[object, ...]) -> CurveSummary:
    (
        curve_id, sid, sample_uid, doi, composition_raw, figure_id, figure_name,
        prop_x, prop_y, unit_x, unit_y, point_count, x_min, x_max, y_min, y_max,
        project_names,
    ) = row
    return CurveSummary(
        curve_id=curve_id,
        sid=sid,
        sample_uid=sample_uid,
        doi=doi,
        composition_raw=composition_raw,
        figure_id=figure_id,
        figure_name=figure_name,
        prop_x=prop_x,
        prop_y=prop_y,
        unit_x=unit_x,
        unit_y=unit_y,
        point_count=point_count,
        x_min=x_min,
        x_max=x_max,
        y_min=y_min,
        y_max=y_max,
        project_names=tuple(project_names or ()),
    )


def row_to_curve(row: tuple[object, ...]) -> Curve:
    (
        curve_id, sid, sample_uid, doi, composition_raw, figure_id, figure_name,
        prop_x, prop_y, unit_x, unit_y, x, y, project_names, comments,
    ) = row
    return Curve(
        curve_id=curve_id,
        sid=sid,
        sample_uid=sample_uid,
        doi=doi,
        composition_raw=composition_raw,
        figure_id=figure_id,
        figure_name=figure_name,
        prop_x=prop_x,
        prop_y=prop_y,
        unit_x=unit_x,
        unit_y=unit_y,
        x=tuple(x or ()),
        y=tuple(y or ()),
        project_names=tuple(project_names or ()),
        comments=comments,
    )
