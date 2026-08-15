from starrydata_mcp.domain.citation import format_citation
from starrydata_mcp.domain.entities import Author, Paper


def _paper(**overrides: object) -> Paper:
    defaults: dict[str, object] = dict(
        sid="1",
        doi="10.1021/ar400290f",
        url="http://dx.doi.org/10.1021/ar400290f",
        issued_year=2014,
        issued_month=4,
        issued_day=15,
        authors=(
            Author(given="Chong", family="Xiao"),
            Author(given="Zhou", family="Li"),
        ),
        title=(
            "Decoupling Interrelated Parameters for Designing "
            "High Performance Thermoelectric Materials"
        ),
        container_title="Accounts of Chemical Research",
        container_title_short="Acc. Chem. Res.",
        volume="47",
        issue="4",
        page="1287-1295",
        issn="0001-4842,1520-4898",
        publisher="American Chemical Society (ACS)",
        project_names=("ThermoelectricMaterials", "GeneralDB"),
        created_at=None,
    )
    defaults.update(overrides)
    return Paper(**defaults)  # type: ignore[arg-type]


def test_full_citation_includes_authors_year_title_container_doi() -> None:
    text = format_citation(_paper())
    assert "Xiao, C." in text
    assert "Li, Z." in text
    assert "(2014)" in text
    assert "Decoupling Interrelated Parameters" in text
    assert "Accounts of Chemical Research" in text
    assert "47" in text and "4" in text and "1287-1295" in text
    assert "https://doi.org/10.1021/ar400290f" in text


def test_many_authors_are_truncated_with_et_al() -> None:
    authors = tuple(Author(given=f"G{i}", family=f"Family{i}") for i in range(8))
    text = format_citation(_paper(authors=authors))
    assert "et al." in text
    assert "Family0" in text
    assert "Family7" not in text


def test_missing_optional_fields_degrade_gracefully() -> None:
    text = format_citation(
        _paper(
            authors=(),
            issued_year=None,
            issued_month=None,
            issued_day=None,
            volume=None,
            issue=None,
            page=None,
            container_title=None,
        )
    )
    # Must not raise, must not contain "None", must still surface title + DOI.
    assert "None" not in text
    assert "Decoupling Interrelated Parameters" in text
    assert "https://doi.org/10.1021/ar400290f" in text


def test_missing_doi_omits_doi_url() -> None:
    text = format_citation(_paper(doi=None, url=None))
    assert "doi.org" not in text
