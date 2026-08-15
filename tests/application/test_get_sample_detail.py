from starrydata_mcp.application.use_cases.get_sample_detail import GetSampleDetailUseCase

from .conftest import FakePaperRepository


def test_returns_none_for_unknown_sample(sample_repo, curve_repo, paper_repo) -> None:
    use_case = GetSampleDetailUseCase(sample_repo, curve_repo, paper_repo)
    assert use_case.execute("does-not-exist") is None


def test_returns_full_detail_with_curve_index_and_citation(
    sample_repo, curve_repo, paper_repo
) -> None:
    use_case = GetSampleDetailUseCase(sample_repo, curve_repo, paper_repo)
    detail = use_case.execute("6:113")
    assert detail is not None
    assert detail.sample_uid == "6:113"
    assert detail.composition == "Pb1.00025Zn0.02Te1.02I0.0005"
    assert detail.elements == ("Pb", "Zn", "Te", "I")
    assert {c.curve_id for c in detail.curves} == {1, 2}
    # curve entries are summaries only — no raw x/y payload leaks through
    assert all(not hasattr(c, "x") for c in detail.curves)
    assert detail.paper_citation is not None
    assert "Xiao" in detail.paper_citation


def test_sample_info_raw_is_passed_through(sample_repo, curve_repo, paper_repo) -> None:
    use_case = GetSampleDetailUseCase(sample_repo, curve_repo, paper_repo)
    detail = use_case.execute("6:113")
    assert detail is not None
    assert detail.sample_info["FabricationProcess"]["category"] == "SolidState"


def test_missing_paper_yields_none_citation(sample_repo, curve_repo) -> None:
    orphan_paper_repo = FakePaperRepository([])  # sample "6:113"'s paper is absent
    use_case = GetSampleDetailUseCase(sample_repo, curve_repo, orphan_paper_repo)
    detail = use_case.execute("6:113")
    assert detail is not None
    assert detail.paper_citation is None
