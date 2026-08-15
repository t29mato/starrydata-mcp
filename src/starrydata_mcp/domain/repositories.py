"""Repository contracts the application layer depends on.

These are `Protocol`s, not ABCs with third-party base classes, so the domain
package stays free of infrastructure imports. `infrastructure/duckdb/*`
provides the real implementations; tests provide in-memory fakes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .entities import Curve, CurveSummary, DatasetInfo, Paper, PropertyUsage, Sample


class Clock(Protocol):
    def now(self) -> datetime: ...


class PaperRepository(Protocol):
    def get_by_sid(self, sid: str) -> Paper | None: ...

    def search(
        self,
        *,
        doi: str | None = None,
        author: str | None = None,
        title_keyword: str | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        project: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Paper]: ...


class SampleRepository(Protocol):
    def get_by_uid(self, sample_uid: str) -> Sample | None: ...

    def list_by_sid(self, sid: str) -> list[Sample]: ...

    def search(
        self,
        *,
        composition: str | None = None,
        elements: tuple[str, ...] | None = None,
        project: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Sample]: ...


class CurveRepository(Protocol):
    def get_by_ids(self, curve_ids: tuple[int, ...]) -> list[Curve]: ...

    def list_by_sample_uid(self, sample_uid: str) -> list[CurveSummary]: ...

    def list_by_sid(self, sid: str) -> list[CurveSummary]: ...

    def search(
        self,
        *,
        prop_x: str | None = None,
        prop_y: str | None = None,
        composition: str | None = None,
        elements: tuple[str, ...] | None = None,
        x_min: float | None = None,
        x_max: float | None = None,
        project: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[CurveSummary]: ...

    def list_properties(
        self, *, project: str | None = None, top_n: int = 50
    ) -> list[PropertyUsage]: ...


class DatasetInfoRepository(Protocol):
    def get_info(self) -> DatasetInfo: ...
