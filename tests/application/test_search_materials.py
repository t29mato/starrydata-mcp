from starrydata_mcp.application.use_cases.search_materials import SearchMaterialsUseCase


def test_search_by_composition_substring(sample_repo, curve_repo) -> None:
    use_case = SearchMaterialsUseCase(sample_repo, curve_repo)
    results = use_case.execute(composition="PbTe")
    assert results == []  # composition_raw is "Pb1.00025..." not literally "PbTe"

    results = use_case.execute(composition="Pb1.00025")
    assert [r.sample_uid for r in results] == ["6:113"]


def test_search_by_elements_and_semantics(sample_repo, curve_repo) -> None:
    use_case = SearchMaterialsUseCase(sample_repo, curve_repo)
    results = use_case.execute(elements=("Pb", "Te"))
    assert [r.sample_uid for r in results] == ["6:113"]

    # A sample containing only Pb (none) should not match a Pb+Au query.
    results = use_case.execute(elements=("Pb", "Au"))
    assert results == []


def test_search_by_project_uses_curve_membership(sample_repo, curve_repo) -> None:
    use_case = SearchMaterialsUseCase(sample_repo, curve_repo)
    results = use_case.execute(project="BatteryMaterials")
    assert [r.sample_uid for r in results] == ["42:1"]


def test_result_includes_derived_properties_and_project_names(sample_repo, curve_repo) -> None:
    use_case = SearchMaterialsUseCase(sample_repo, curve_repo)
    [result] = use_case.execute(composition="Pb1.00025")
    assert result.properties == (
        "Temperature vs Seebeck coefficient",
        "Temperature vs ZT",
    )
    assert result.project_names == ("ThermoelectricMaterials",)
    assert result.paper_doi == "10.1021/am405410e"


def test_sample_with_no_curves_has_empty_properties_and_no_doi(sample_repo, curve_repo) -> None:
    use_case = SearchMaterialsUseCase(sample_repo, curve_repo)
    [result] = use_case.execute(composition="PH1000")
    assert result.properties == ()
    assert result.project_names == ()
    assert result.paper_doi is None


def test_messy_composition_has_no_parsed_elements(sample_repo, curve_repo) -> None:
    use_case = SearchMaterialsUseCase(sample_repo, curve_repo)
    [result] = use_case.execute(composition="PH1000")
    assert result.elements == ()


def test_limit_and_offset_are_forwarded(sample_repo, curve_repo) -> None:
    use_case = SearchMaterialsUseCase(sample_repo, curve_repo)
    results = use_case.execute(limit=1, offset=1)
    assert len(results) == 1
