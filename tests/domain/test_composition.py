"""Unit tests for the best-effort chemical-formula parser.

Per docs/design/architecture.md §5 Q3: this is intentionally a simple,
dependency-free parser. It must never raise, and must fall back to an empty
tuple whenever the input doesn't look like a clean formula (free-text notes
are common in the real dataset) rather than guessing.
"""

from starrydata_mcp.domain.composition import parse_elements


def test_simple_formula_with_decimal_stoichiometry() -> None:
    assert parse_elements("Pb1Te1.01Na0.02") == ("Pb", "Te", "Na")


def test_formula_without_explicit_stoichiometry() -> None:
    assert parse_elements("TaFeSb") == ("Ta", "Fe", "Sb")


def test_pure_element() -> None:
    assert parse_elements("Bi2Te3") == ("Bi", "Te")


def test_duplicate_elements_are_deduplicated_preserving_first_occurrence() -> None:
    assert parse_elements("Cu1Cu2O3") == ("Cu", "O")


def test_empty_string_returns_empty_tuple() -> None:
    assert parse_elements("") == ()


def test_whitespace_only_returns_empty_tuple() -> None:
    assert parse_elements("   ") == ()


def test_free_text_note_returns_empty_tuple() -> None:
    text = "PH1000 with DMSO (dimethyl sulfoxide) doping agent."
    assert parse_elements(text) == ()


def test_unknown_element_symbol_returns_empty_tuple() -> None:
    # "Xx" is not a real element symbol.
    assert parse_elements("Xx2Te3") == ()


def test_formula_with_internal_whitespace_returns_empty_tuple() -> None:
    # Composite/mixture notations ("Bi2Te3 - Sb2Te3") are out of scope for v1;
    # bail out rather than mis-parse.
    assert parse_elements("Bi2Te3 - Sb2Te3") == ()


def test_trailing_garbage_returns_empty_tuple() -> None:
    assert parse_elements("Bi2Te3!!") == ()


def test_lowercase_start_returns_empty_tuple() -> None:
    assert parse_elements("bi2Te3") == ()


def test_never_raises_on_arbitrary_input() -> None:
    for junk in ["123", "!!!", "水素", "Bi" * 500, "NaN"]:
        parse_elements(junk)  # must not raise
