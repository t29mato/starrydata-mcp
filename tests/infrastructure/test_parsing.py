from starrydata_mcp.infrastructure.ingestion.parsing import (
    parse_authors,
    parse_float_list,
    parse_issued_date,
    parse_sample_info,
    parse_string_list,
    strip_crossref_quoting,
)


def test_parse_issued_date_full() -> None:
    assert parse_issued_date('{"date_parts":[[2014,4,15]]}') == (2014, 4, 15)


def test_parse_issued_date_year_only() -> None:
    assert parse_issued_date('{"date_parts":[[2014]]}') == (2014, None, None)


def test_parse_issued_date_missing_or_malformed() -> None:
    assert parse_issued_date(None) == (None, None, None)
    assert parse_issued_date("") == (None, None, None)
    assert parse_issued_date("not json") == (None, None, None)
    assert parse_issued_date("{}") == (None, None, None)


def test_parse_authors_real_shape() -> None:
    raw = '[{"affiliation":[],"given":"Chong","family":"Xiao"}]'
    assert parse_authors(raw) == [{"given": "Chong", "family": "Xiao"}]


def test_parse_authors_missing_or_malformed() -> None:
    assert parse_authors(None) == []
    assert parse_authors("not json") == []
    assert parse_authors('{"not":"a list"}') == []


def test_parse_authors_drops_non_dict_entries() -> None:
    assert parse_authors('[{"given":"A","family":"B"}, "junk", 5]') == [
        {"given": "A", "family": "B"}
    ]


def test_parse_string_list_dedupes_preserving_order() -> None:
    raw = '["ThermoelectricMaterials","GeneralDB","ThermoelectricMaterials"]'
    assert parse_string_list(raw) == ["ThermoelectricMaterials", "GeneralDB"]


def test_parse_string_list_missing_or_malformed() -> None:
    assert parse_string_list(None) == []
    assert parse_string_list("") == []
    assert parse_string_list("not json") == []
    assert parse_string_list('"not a list"') == []


def test_parse_float_list_real_shape() -> None:
    assert parse_float_list("[299.8597,324.8683]") == [299.8597, 324.8683]


def test_parse_float_list_drops_non_numeric() -> None:
    assert parse_float_list('[1.0, "bad", 2.0, null]') == [1.0, 2.0]


def test_parse_float_list_missing_or_malformed() -> None:
    assert parse_float_list(None) == []
    assert parse_float_list("not json") == []


def test_parse_float_list_valid_json_but_not_a_list() -> None:
    # Valid JSON (parses cleanly) but the wrong shape — a bare number, not
    # an array — must degrade to [] like any other malformed input.
    assert parse_float_list("42") == []
    assert parse_float_list('{"a": 1}') == []


def test_strip_crossref_quoting_unwraps_double_quoted_title() -> None:
    raw = '"Decoupling Interrelated Parameters"'
    assert strip_crossref_quoting(raw) == "Decoupling Interrelated Parameters"


def test_strip_crossref_quoting_leaves_plain_text_alone() -> None:
    assert strip_crossref_quoting("Plain Title") == "Plain Title"


def test_strip_crossref_quoting_invalid_json_inside_quotes_returns_raw() -> None:
    # Starts and ends with a quote character (so the fast-path check
    # triggers) but isn't valid JSON once parsed — must fall back to the
    # original string rather than raise.
    raw = '"a"b"'
    assert strip_crossref_quoting(raw) == raw


def test_strip_crossref_quoting_handles_none() -> None:
    assert strip_crossref_quoting(None) is None


def test_parse_sample_info_real_shape() -> None:
    raw = '{"FabricationProcess":{"category":"Film","comment":"dropcast"}}'
    assert parse_sample_info(raw) == {
        "FabricationProcess": {"category": "Film", "comment": "dropcast"}
    }


def test_parse_sample_info_missing_or_malformed() -> None:
    assert parse_sample_info(None) == {}
    assert parse_sample_info("") == {}
    assert parse_sample_info("not json") == {}
    assert parse_sample_info("[1,2,3]") == {}
