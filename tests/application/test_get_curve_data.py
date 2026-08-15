from starrydata_mcp.application.use_cases.get_curve_data import GetCurveDataUseCase


def test_fetches_full_xy_arrays_for_requested_ids(curve_repo, paper_repo) -> None:
    use_case = GetCurveDataUseCase(curve_repo, paper_repo)
    results = use_case.execute((1, 2))
    assert [r.curve_id for r in results] == [1, 2]
    assert results[0].x == (300.0, 350.0, 400.0)
    assert results[0].y == (-0.00015, -0.00018, -0.00021)


def test_unknown_ids_are_silently_skipped(curve_repo, paper_repo) -> None:
    use_case = GetCurveDataUseCase(curve_repo, paper_repo)
    results = use_case.execute((1, 999))
    assert [r.curve_id for r in results] == [1]


def test_includes_paper_citation(curve_repo, paper_repo) -> None:
    use_case = GetCurveDataUseCase(curve_repo, paper_repo)
    [result] = use_case.execute((1,))
    assert result.paper_citation is not None
    assert "Xiao" in result.paper_citation
