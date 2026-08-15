"""Parsers for the JSON-in-CSV-cell fields the real Starrydata CSVs use
(docs/design/architecture.md §1.2), e.g. `issued`, `author`, `project_names`
on papers.csv, and the `x`/`y` point arrays on curves.csv.

Every parser here is best-effort and never raises: a malformed cell in one
of ~400k rows must degrade to an empty/None result, not abort the whole
daily ingestion run.
"""

from __future__ import annotations

import json


def parse_issued_date(raw: str | None) -> tuple[int | None, int | None, int | None]:
    """`{"date_parts":[[2014,4,15]]}` -> (2014, 4, 15); missing parts -> None."""
    if not raw:
        return (None, None, None)
    try:
        parts = json.loads(raw)["date_parts"][0]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        return (None, None, None)
    year = parts[0] if len(parts) > 0 and isinstance(parts[0], int) else None
    month = parts[1] if len(parts) > 1 and isinstance(parts[1], int) else None
    day = parts[2] if len(parts) > 2 and isinstance(parts[2], int) else None
    return (year, month, day)


def parse_authors(raw: str | None) -> list[dict[str, str]]:
    """`[{"given":"Chong","family":"Xiao"}, ...]` -> same, filtered/coerced."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    authors: list[dict[str, str]] = []
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        given = entry.get("given")
        family = entry.get("family")
        authors.append(
            {
                "given": given if isinstance(given, str) else "",
                "family": family if isinstance(family, str) else "",
            }
        )
    return authors


def parse_string_list(raw: str | None) -> list[str]:
    """`["ThermoelectricMaterials","GeneralDB"]` -> same, deduplicated, order kept.

    Used for both `project_names` (papers/curves) and JSON-quoted title-ish
    fields that CrossRef sometimes wraps in an extra pair of quotes.
    """
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for item in parsed:
        if isinstance(item, str) and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def parse_float_list(raw: str | None) -> list[float]:
    """`[299.8597,324.8683,...]` -> same as floats; non-numeric entries dropped."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    values: list[float] = []
    for item in parsed:
        if isinstance(item, int | float):
            values.append(float(item))
    return values


def strip_crossref_quoting(raw: str | None) -> str | None:
    """Some CrossRef-sourced fields (title, container_title, ...) arrive as a
    JSON-quoted string (e.g. `"\"My Title\""` in the CSV cell). Unwrap it if
    so; otherwise return the value unchanged.
    """
    if raw is None:
        return None
    text = raw.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        try:
            unwrapped = json.loads(text)
        except json.JSONDecodeError:
            return raw
        if isinstance(unwrapped, str):
            return unwrapped
    return raw


def parse_sample_info(raw: str | None) -> dict[str, object]:
    """`{"FabricationProcess":{"category":"...","comment":"..."}, ...}` -> same.

    Falls back to `{}` on malformed JSON rather than dropping the row.
    """
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
