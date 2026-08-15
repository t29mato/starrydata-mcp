from starrydata_mcp.application.use_cases.get_paper_detail import GetPaperDetailUseCase


def test_returns_none_for_unknown_sid(sample_repo, curve_repo, paper_repo) -> None:
    use_case = GetPaperDetailUseCase(paper_repo, sample_repo, curve_repo)
    assert use_case.execute("does-not-exist") is None


def test_returns_paper_with_samples_and_curves(sample_repo, curve_repo, paper_repo) -> None:
    use_case = GetPaperDetailUseCase(paper_repo, sample_repo, curve_repo)
    detail = use_case.execute("6")
    assert detail is not None
    assert detail.sid == "6"
    assert "Xiao" in detail.citation
    assert {s.sample_uid for s in detail.samples} == {"6:113", "6:114"}
    assert {c.curve_id for c in detail.curves} == {1, 2}


def test_sample_summaries_include_derived_properties(sample_repo, curve_repo, paper_repo) -> None:
    use_case = GetPaperDetailUseCase(paper_repo, sample_repo, curve_repo)
    detail = use_case.execute("6")
    assert detail is not None
    pbte = next(s for s in detail.samples if s.sample_uid == "6:113")
    assert pbte.properties == ("Temperature vs Seebeck coefficient", "Temperature vs ZT")
