"""Pure formatting of a `Paper` into a human-readable citation string.

Not a full CSL/APA implementation — good enough for an agent to quote back
to a user, and to degrade gracefully (no crashes, no stray "None") when
upstream metadata is incomplete, which happens often in the real dataset.
"""

from __future__ import annotations

from .entities import Author, Paper

_MAX_AUTHORS_LISTED = 3


def format_citation(paper: Paper) -> str:
    segments: list[str] = []

    author_text = _authors_text(paper.authors)
    if author_text:
        segments.append(author_text)

    if paper.issued_year:
        segments.append(f"({paper.issued_year})")

    if paper.title:
        title = paper.title.strip()
        segments.append(title if title.endswith((".", "?", "!")) else f"{title}.")

    venue_text = _venue_text(paper)
    if venue_text:
        segments.append(venue_text)

    if paper.doi:
        segments.append(f"https://doi.org/{paper.doi}")

    return " ".join(segments)


def _author_str(author: Author) -> str:
    given = (author.given or "").strip()
    family = (author.family or "").strip()
    if not family:
        return given
    if not given:
        return family
    return f"{family}, {given[0].upper()}."


def _authors_text(authors: tuple[Author, ...]) -> str:
    if not authors:
        return ""
    listed = [s for s in (_author_str(a) for a in authors[:_MAX_AUTHORS_LISTED]) if s]
    text = ", ".join(listed)
    if len(authors) > _MAX_AUTHORS_LISTED:
        text = f"{text} et al." if text else "et al."
    return text


def _venue_text(paper: Paper) -> str:
    bits: list[str] = []
    if paper.container_title:
        bits.append(paper.container_title)

    vol_issue = ""
    if paper.volume:
        vol_issue = paper.volume
        if paper.issue:
            vol_issue += f"({paper.issue})"
    if vol_issue:
        bits.append(vol_issue)

    if paper.page:
        bits.append(paper.page)

    if not bits:
        return ""
    return ", ".join(bits) + "."
