from starrydata_mcp.application.use_cases.search_curves import SearchCurvesUseCase


def test_filter_by_property_pair(curve_repo) -> None:
    use_case = SearchCurvesUseCase(curve_repo)
    results = use_case.execute(prop_x="Temperature", prop_y="ZT")
    assert [r.curve_id for r in results] == [2]


def test_filter_by_x_range_overlap(curve_repo) -> None:
    use_case = SearchCurvesUseCase(curve_repo)
    # Seebeck curve spans 300-400K, ZT curve spans 300-600K.
    results = use_case.execute(prop_x="Temperature", x_min=500, x_max=700)
    assert [r.curve_id for r in results] == [2]


def test_filter_by_project(curve_repo) -> None:
    use_case = SearchCurvesUseCase(curve_repo)
    results = use_case.execute(project="BatteryMaterials")
    assert [r.curve_id for r in results] == [3]


def test_summaries_never_carry_raw_arrays(curve_repo) -> None:
    use_case = SearchCurvesUseCase(curve_repo)
    [result] = use_case.execute(prop_x="Temperature", prop_y="ZT")
    assert not hasattr(result, "x")
    assert not hasattr(result, "y")
    assert result.point_count == 2
    assert result.x_min == 300.0
    assert result.x_max == 600.0
