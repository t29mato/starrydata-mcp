from starrydata_mcp.application.use_cases.search_papers import SearchPapersUseCase


def test_filter_by_doi(paper_repo) -> None:
    use_case = SearchPapersUseCase(paper_repo)
    [result] = use_case.execute(doi="10.1021/am405410e")
    assert result.sid == "6"
    assert "Xiao" in result.citation


def test_filter_by_author(paper_repo) -> None:
    use_case = SearchPapersUseCase(paper_repo)
    results = use_case.execute(author="Ando")
    assert [r.sid for r in results] == ["42"]


def test_filter_by_title_keyword(paper_repo) -> None:
    use_case = SearchPapersUseCase(paper_repo)
    results = use_case.execute(title_keyword="cathode")
    assert [r.sid for r in results] == ["42"]


def test_filter_by_year_range(paper_repo) -> None:
    use_case = SearchPapersUseCase(paper_repo)
    results = use_case.execute(year_min=2015)
    assert [r.sid for r in results] == ["42"]


def test_filter_by_project(paper_repo) -> None:
    use_case = SearchPapersUseCase(paper_repo)
    results = use_case.execute(project="ThermoelectricMaterials")
    assert [r.sid for r in results] == ["6"]
