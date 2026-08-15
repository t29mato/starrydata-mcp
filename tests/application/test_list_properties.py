from starrydata_mcp.application.use_cases.list_properties import ListPropertiesUseCase


def test_ranked_by_curve_count_descending(curve_repo) -> None:
    use_case = ListPropertiesUseCase(curve_repo)
    results = use_case.execute()
    assert [(r.prop_x, r.prop_y) for r in results] == [
        ("Temperature", "Seebeck coefficient"),
        ("Temperature", "ZT"),
        ("Discharge capacity", "Voltage"),
    ]
    assert results[0].curve_count == 1


def test_project_filter_narrows_vocabulary(curve_repo) -> None:
    use_case = ListPropertiesUseCase(curve_repo)
    results = use_case.execute(project="BatteryMaterials")
    assert [(r.prop_x, r.prop_y) for r in results] == [("Discharge capacity", "Voltage")]


def test_top_n_truncates(curve_repo) -> None:
    use_case = ListPropertiesUseCase(curve_repo)
    results = use_case.execute(top_n=1)
    assert len(results) == 1
