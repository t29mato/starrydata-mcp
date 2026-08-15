"""One-off generator for tests/fixtures/raw/*.csv.

Not run by pytest — the checked-in CSVs are the fixture. Re-run this
manually (`python tests/fixtures/build_fixture_csvs.py`) if the shape needs
to change; keep values in sync with tests/application/conftest.py's fakes
where it's convenient, but this is exercising real-CSV-format parsing (JSON
cells, BOM, messy composition text), not the same objects.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

RAW_DIR = Path(__file__).parent / "raw"

PAPERS_HEADER = [
    "SID", "DOI", "URL", "issued", "author", "title", "container_title",
    "container_title_short", "volume", "issue", "page", "ISSN", "publisher",
    "project_names", "created_at",
]

SAMPLES_HEADER = [
    "sample_name", "sample_id", "composition", "composition_details", "SID",
    "DOI", "created_at", "updated_at", "sample_info",
]

CURVES_HEADER = [
    "SID", "DOI", "composition", "sample_id", "figure_id", "figure_name",
    "prop_x", "prop_y", "unit_x", "unit_y", "x", "y", "created_at",
    "updated_at", "project_names", "comments",
]

PAPERS_ROWS = [
    {
        "SID": "6",
        "DOI": "10.1021/am405410e",
        "URL": "http://dx.doi.org/10.1021/am405410e",
        "issued": json.dumps({"date_parts": [[2014, 1, 1]]}),
        "author": json.dumps([{"affiliation": [], "given": "Chong", "family": "Xiao"}]),
        "title": '"Thermoelectric properties of PbTe-based alloys"',
        "container_title": '"ACS Applied Materials & Interfaces"',
        "container_title_short": '"ACS Appl. Mater. Interfaces"',
        "volume": "6",
        "issue": "2",
        "page": '"100-110"',
        "ISSN": "1944-8244",
        "publisher": "American Chemical Society (ACS)",
        "project_names": json.dumps(["ThermoelectricMaterials"]),
        "created_at": "Fri Sep 01 2017 18:19:39 GMT+0900 (Japan Standard Time)",
    },
    {
        "SID": "42",
        "DOI": "10.1000/battery.example",
        "URL": "http://dx.doi.org/10.1000/battery.example",
        "issued": json.dumps({"date_parts": [[2020, 6, 1]]}),
        "author": json.dumps([{"affiliation": [], "given": "Yuki", "family": "Ando"}]),
        "title": '"Discharge behavior of layered oxide cathodes"',
        "container_title": '"Journal of Power Sources"',
        "container_title_short": '"J. Power Sources"',
        "volume": "450",
        "issue": "",
        "page": '"227-235"',
        "ISSN": "",
        "publisher": "Elsevier",
        "project_names": json.dumps(["BatteryMaterials"]),
        "created_at": "Tue Jun 02 2020 09:00:00 GMT+0900 (Japan Standard Time)",
    },
]

SAMPLES_ROWS = [
    {
        "sample_name": "PbTe-Zn-I sample",
        "sample_id": "113",
        "composition": "Pb1.00025Zn0.02Te1.02I0.0005",
        "composition_details": "",
        "SID": "6",
        "DOI": "10.1021/am405410e",
        "created_at": "Fri Sep 01 2017 18:19:39 GMT+0900 (Japan Standard Time)",
        "updated_at": "Fri Sep 01 2017 18:19:39 GMT+0900 (Japan Standard Time)",
        "sample_info": json.dumps(
            {"FabricationProcess": {"category": "SolidState", "comment": ""}}
        ),
    },
    {
        "sample_name": "PH1000 film",
        "sample_id": "114",
        "composition": "PH1000 with DMSO (dimethyl sulfoxide) doping agent.",
        "composition_details": "Bi2Te3 ball milled powders",
        "SID": "6",
        "DOI": "10.1021/am405410e",
        "created_at": "Wed May 29 2019 14:44:35 GMT+0900 (Japan Standard Time)",
        "updated_at": "Wed May 29 2019 14:44:35 GMT+0900 (Japan Standard Time)",
        "sample_info": "{}",
    },
    {
        "sample_name": "NMC cathode",
        "sample_id": "1",
        "composition": "LiNi0.8Co0.1Mn0.1O2",
        "composition_details": "",
        "SID": "42",
        "DOI": "10.1000/battery.example",
        "created_at": "Tue Jun 02 2020 09:00:00 GMT+0900 (Japan Standard Time)",
        "updated_at": "Tue Jun 02 2020 09:00:00 GMT+0900 (Japan Standard Time)",
        "sample_info": "{}",
    },
]

CURVES_ROWS = [
    {
        "SID": "6",
        "DOI": "10.1021/am405410e",
        "composition": "Pb1.00025Zn0.02Te1.02I0.0005",
        "sample_id": "113",
        "figure_id": "79",
        "figure_name": "6(b)",
        "prop_x": "Temperature",
        "prop_y": "Seebeck coefficient",
        "unit_x": "K",
        "unit_y": "V*K^(-1)",
        "x": json.dumps([300.0, 350.0, 400.0]),
        "y": json.dumps([-0.00015, -0.00018, -0.00021]),
        "created_at": "Fri Sep 01 2017 18:19:39 GMT+0900 (Japan Standard Time)",
        "updated_at": "Fri Sep 01 2017 18:19:39 GMT+0900 (Japan Standard Time)",
        "project_names": json.dumps(["ThermoelectricMaterials"]),
        "comments": "",
    },
    {
        "SID": "6",
        "DOI": "10.1021/am405410e",
        "composition": "Pb1.00025Zn0.02Te1.02I0.0005",
        "sample_id": "113",
        "figure_id": "80",
        "figure_name": "7(a)",
        "prop_x": "Temperature",
        "prop_y": "ZT",
        "unit_x": "K",
        "unit_y": "dimensionless",
        "x": json.dumps([300.0, 600.0]),
        "y": json.dumps([0.2, 1.1]),
        "created_at": "Fri Sep 01 2017 18:19:39 GMT+0900 (Japan Standard Time)",
        "updated_at": "Fri Sep 01 2017 18:19:39 GMT+0900 (Japan Standard Time)",
        "project_names": json.dumps(["ThermoelectricMaterials"]),
        "comments": "",
    },
    {
        "SID": "42",
        "DOI": "10.1000/battery.example",
        "composition": "LiNi0.8Co0.1Mn0.1O2",
        "sample_id": "1",
        "figure_id": "3",
        "figure_name": "2(b)",
        "prop_x": "Discharge capacity",
        "prop_y": "Voltage",
        "unit_x": "mAh/g",
        "unit_y": "V",
        "x": json.dumps([0.0, 50.0, 100.0]),
        "y": json.dumps([4.3, 3.8, 3.2]),
        "created_at": "Tue Jun 02 2020 09:00:00 GMT+0900 (Japan Standard Time)",
        "updated_at": "Tue Jun 02 2020 09:00:00 GMT+0900 (Japan Standard Time)",
        "project_names": json.dumps(["BatteryMaterials"]),
        "comments": "C/10 rate",
    },
]


def _write(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    _write(RAW_DIR / "papers.csv", PAPERS_HEADER, PAPERS_ROWS)
    _write(RAW_DIR / "samples.csv", SAMPLES_HEADER, SAMPLES_ROWS)
    _write(RAW_DIR / "curves.csv", CURVES_HEADER, CURVES_ROWS)
    print(f"wrote fixtures to {RAW_DIR}")
