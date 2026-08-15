from starrydata_mcp.domain.entities import Curve


def _curve(**overrides: object) -> Curve:
    defaults: dict[str, object] = dict(
        curve_id=1,
        sid="6",
        sample_uid="6:113",
        doi="10.1021/am405410e",
        composition_raw="Pb1.00025Zn0.02Te1.02I0.0005",
        figure_id="79",
        figure_name="6(b)",
        prop_x="Temperature",
        prop_y="Seebeck coefficient",
        unit_x="K",
        unit_y="V*K^(-1)",
        x=(300.0, 350.0, 400.0),
        y=(-1.0, -2.0, -1.5),
        project_names=("ThermoelectricMaterials",),
        comments=None,
    )
    defaults.update(overrides)
    return Curve(**defaults)  # type: ignore[arg-type]


def test_summary_derives_point_count_and_ranges() -> None:
    summary = _curve().summary()
    assert summary.curve_id == 1
    assert summary.point_count == 3
    assert summary.x_min == 300.0
    assert summary.x_max == 400.0
    assert summary.y_min == -2.0
    assert summary.y_max == -1.0
    # the summary must never carry the raw arrays (keeps search responses light)
    assert not hasattr(summary, "x")
    assert not hasattr(summary, "y")


def test_summary_of_empty_curve_has_none_ranges() -> None:
    summary = _curve(x=(), y=()).summary()
    assert summary.point_count == 0
    assert summary.x_min is None
    assert summary.x_max is None
    assert summary.y_min is None
    assert summary.y_max is None
