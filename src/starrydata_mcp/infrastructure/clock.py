from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """The real `domain.repositories.Clock` implementation."""

    def now(self) -> datetime:
        return datetime.now(UTC)
