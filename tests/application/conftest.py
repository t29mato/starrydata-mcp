"""In-memory fakes implementing the domain repository Protocols, seeded with
data shaped like real Starrydata rows (see docs/design/architecture.md §1.2)
so use-case tests exercise realistic filtering/composition scenarios.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from starrydata_mcp.domain.composition import parse_elements
from starrydata_mcp.domain.entities import (
    Author,
    Curve,
    CurveSummary,
    DatasetInfo,
    DatasetTotals,
    Paper,
    PropertyUsage,
    Sample,
)

_PAPER_TE = Paper(
    sid="6",
    doi="10.1021/am405410e",
    url="http://dx.doi.org/10.1021/am405410e",
    issued_year=2014,
    issued_month=1,
    issued_day=1,
    authors=(Author(given="Chong", family="Xiao"),),
    title="Thermoelectric properties of PbTe-based alloys",
    container_title="ACS Applied Materials & Interfaces",
    container_title_short="ACS Appl. Mater. Interfaces",
    volume="6",
    issue="2",
    page="100-110",
    issn="1944-8244",
    publisher="American Chemical Society (ACS)",
    project_names=("ThermoelectricMaterials",),
    created_at="2017-09-01T00:00:00Z",
)

_PAPER_BATTERY = Paper(
    sid="42",
    doi="10.1000/battery.example",
    url="http://dx.doi.org/10.1000/battery.example",
    issued_year=2020,
    issued_month=6,
    issued_day=1,
    authors=(Author(given="Yuki", family="Ando"),),
    title="Discharge behavior of layered oxide cathodes",
    container_title="Journal of Power Sources",
    container_title_short="J. Power Sources",
    volume="450",
    issue=None,
    page="227-235",
    issn=None,
    publisher="Elsevier",
    project_names=("BatteryMaterials",),
    created_at="2020-06-02T00:00:00Z",
)

_SAMPLE_PBTE = Sample(
    sample_uid="6:113",
    sid="6",
    sample_id="113",
    sample_name="PbTe-Zn-I sample",
    composition_raw="Pb1.00025Zn0.02Te1.02I0.0005",
    elements=parse_elements("Pb1.00025Zn0.02Te1.02I0.0005"),
    composition_details=None,
    sample_info_raw={"FabricationProcess": {"category": "SolidState", "comment": ""}},
    created_at="2017-09-01T00:00:00Z",
    updated_at="2017-09-01T00:00:00Z",
)

_SAMPLE_MESSY = Sample(
    sample_uid="6:114",
    sid="6",
    sample_id="114",
    sample_name="PH1000 film",
    composition_raw="PH1000 with DMSO (dimethyl sulfoxide) doping agent.",
    elements=parse_elements("PH1000 with DMSO (dimethyl sulfoxide) doping agent."),
    composition_details="Bi2Te3 ball milled powders",
    sample_info_raw={},
    created_at="2019-05-29T00:00:00Z",
    updated_at="2019-05-29T00:00:00Z",
)

_SAMPLE_BATTERY = Sample(
    sample_uid="42:1",
    sid="42",
    sample_id="1",
    sample_name="NMC cathode",
    composition_raw="LiNi0.8Co0.1Mn0.1O2",
    elements=parse_elements("LiNi0.8Co0.1Mn0.1O2"),
    composition_details=None,
    sample_info_raw={},
    created_at="2020-06-02T00:00:00Z",
    updated_at="2020-06-02T00:00:00Z",
)

_CURVE_SEEBECK = Curve(
    curve_id=1,
    sid="6",
    sample_uid="6:113",
    doi="10.1021/am405410e",
    composition_raw="Pb1.00025Zn0.02Te1.02I0.0005",
    figure_id="79",
    figure_name="6(b)",
    prop_x="Temperature",
    prop_y="Seebeck coefficient",
    unit_x="K",
    unit_y="V*K^(-1)",
    x=(300.0, 350.0, 400.0),
    y=(-0.00015, -0.00018, -0.00021),
    project_names=("ThermoelectricMaterials",),
    comments=None,
)

_CURVE_ZT = Curve(
    curve_id=2,
    sid="6",
    sample_uid="6:113",
    doi="10.1021/am405410e",
    composition_raw="Pb1.00025Zn0.02Te1.02I0.0005",
    figure_id="80",
    figure_name="7(a)",
    prop_x="Temperature",
    prop_y="ZT",
    unit_x="K",
    unit_y="dimensionless",
    x=(300.0, 600.0),
    y=(0.2, 1.1),
    project_names=("ThermoelectricMaterials",),
    comments=None,
)

_CURVE_DISCHARGE = Curve(
    curve_id=3,
    sid="42",
    sample_uid="42:1",
    doi="10.1000/battery.example",
    composition_raw="LiNi0.8Co0.1Mn0.1O2",
    figure_id="3",
    figure_name="2(b)",
    prop_x="Discharge capacity",
    prop_y="Voltage",
    unit_x="mAh/g",
    unit_y="V",
    x=(0.0, 50.0, 100.0),
    y=(4.3, 3.8, 3.2),
    project_names=("BatteryMaterials",),
    comments="C/10 rate",
)

ALL_PAPERS = [_PAPER_TE, _PAPER_BATTERY]
ALL_SAMPLES = [_SAMPLE_PBTE, _SAMPLE_MESSY, _SAMPLE_BATTERY]
ALL_CURVES = [_CURVE_SEEBECK, _CURVE_ZT, _CURVE_DISCHARGE]


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class FakePaperRepository:
    def __init__(self, papers: list[Paper]) -> None:
        self._papers = papers

    def get_by_sid(self, sid: str) -> Paper | None:
        return next((p for p in self._papers if p.sid == sid), None)

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
    ) -> list[Paper]:
        results = self._papers
        if doi:
            results = [p for p in results if p.doi == doi]
        if author:
            results = [
                p
                for p in results
                if any(author.lower() in a.family.lower() for a in p.authors)
            ]
        if title_keyword:
            results = [
                p for p in results if p.title and title_keyword.lower() in p.title.lower()
            ]
        if year_min is not None:
            results = [p for p in results if p.issued_year and p.issued_year >= year_min]
        if year_max is not None:
            results = [p for p in results if p.issued_year and p.issued_year <= year_max]
        if project:
            results = [p for p in results if project in p.project_names]
        return results[offset : offset + limit]


class FakeSampleRepository:
    def __init__(self, samples: list[Sample]) -> None:
        self._samples = samples

    def get_by_uid(self, sample_uid: str) -> Sample | None:
        return next((s for s in self._samples if s.sample_uid == sample_uid), None)

    def list_by_sid(self, sid: str) -> list[Sample]:
        return [s for s in self._samples if s.sid == sid]

    def search(
        self,
        *,
        composition: str | None = None,
        elements: tuple[str, ...] | None = None,
        project: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Sample]:
        results = self._samples
        if composition:
            results = [s for s in results if composition.lower() in s.composition_raw.lower()]
        if elements:
            results = [s for s in results if set(elements).issubset(set(s.elements))]
        if project:
            # Membership mirrors the real dataset's rule: a sample belongs to a
            # project iff one of its curves is tagged with that project.
            matching_uids = {c.sample_uid for c in ALL_CURVES if project in c.project_names}
            results = [s for s in results if s.sample_uid in matching_uids]
        return results[offset : offset + limit]


class FakeCurveRepository:
    def __init__(self, curves: list[Curve]) -> None:
        self._curves = curves

    def get_by_ids(self, curve_ids: tuple[int, ...]) -> list[Curve]:
        by_id = {c.curve_id: c for c in self._curves}
        return [by_id[i] for i in curve_ids if i in by_id]

    def list_by_sample_uid(self, sample_uid: str) -> list[CurveSummary]:
        return [c.summary() for c in self._curves if c.sample_uid == sample_uid]

    def list_by_sid(self, sid: str) -> list[CurveSummary]:
        return [c.summary() for c in self._curves if c.sid == sid]

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
    ) -> list[CurveSummary]:
        results = self._curves
        if prop_x:
            results = [c for c in results if c.prop_x == prop_x]
        if prop_y:
            results = [c for c in results if c.prop_y == prop_y]
        if composition:
            results = [c for c in results if composition.lower() in c.composition_raw.lower()]
        if elements:
            sample_by_uid = {s.sample_uid: s for s in ALL_SAMPLES}
            results = [
                c
                for c in results
                if set(elements).issubset(set(sample_by_uid[c.sample_uid].elements))
            ]
        if project:
            results = [c for c in results if project in c.project_names]
        if x_min is not None:
            results = [c for c in results if c.x and max(c.x) >= x_min]
        if x_max is not None:
            results = [c for c in results if c.x and min(c.x) <= x_max]
        summaries = [c.summary() for c in results]
        return summaries[offset : offset + limit]

    def list_properties(
        self, *, project: str | None = None, top_n: int = 50
    ) -> list[PropertyUsage]:
        curves = self._curves
        if project:
            curves = [c for c in curves if project in c.project_names]
        counts: dict[tuple[str, str, str | None, str | None], int] = {}
        for c in curves:
            key = (c.prop_x, c.prop_y, c.unit_x, c.unit_y)
            counts[key] = counts.get(key, 0) + 1
        usages = [
            PropertyUsage(prop_x=k[0], prop_y=k[1], unit_x=k[2], unit_y=k[3], curve_count=v)
            for k, v in counts.items()
        ]
        usages.sort(key=lambda u: u.curve_count, reverse=True)
        return usages[:top_n]


class FakeDatasetInfoRepository:
    def __init__(self, info: DatasetInfo) -> None:
        self._info = info

    def get_info(self) -> DatasetInfo:
        return self._info


@pytest.fixture
def paper_repo() -> FakePaperRepository:
    return FakePaperRepository(list(ALL_PAPERS))


@pytest.fixture
def sample_repo() -> FakeSampleRepository:
    return FakeSampleRepository(list(ALL_SAMPLES))


@pytest.fixture
def curve_repo() -> FakeCurveRepository:
    return FakeCurveRepository(list(ALL_CURVES))


@pytest.fixture
def fresh_dataset_info() -> DatasetInfo:
    return DatasetInfo(
        db_snapshot=datetime(2026, 8, 15, 2, 0, 0, tzinfo=UTC),
        generated_at=datetime(2026, 8, 15, 2, 5, 0, tzinfo=UTC),
        totals=DatasetTotals(papers=17399, figures=60302, samples=105397, curves=234390),
        license="CC BY 4.0",
        citation=(
            "Katsura et al. (2025). Starrydata: from published plots to shared materials data."
        ),
        source_url="https://github.com/starrydata/starrydata_datasets",
    )


@pytest.fixture
def dataset_info_repo(fresh_dataset_info: DatasetInfo) -> FakeDatasetInfoRepository:
    return FakeDatasetInfoRepository(fresh_dataset_info)
