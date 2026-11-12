"""Pure UI calculations and download safety, independent of browser and solver."""

import pandas as pd
import pytest

from src.allocate import AllocationError
from src.allocation_ui import (
    comparison_summary,
    csv_download,
    input_signature,
    partner_decision_view,
    partner_summary,
    verified_capacity_overrides,
    worst_fill_display,
)


def _plan():
    return pd.DataFrame([
        {"site_id": "A", "site_name": "Alpha", "product": "diaper", "size": "5",
         "need_units": 100, "allocated_units": 60, "unmet_units": 40,
         "ready_now_units": 45, "awaiting_inbound_units": 15, "equity_weight": 1.5},
        {"site_id": "A", "site_name": "Alpha", "product": "diaper", "size": "6",
         "need_units": 50, "allocated_units": 30, "unmet_units": 20,
         "ready_now_units": 20, "awaiting_inbound_units": 10, "equity_weight": 1.5},
        {"site_id": "B", "site_name": "Beta", "product": "diaper", "size": "5",
         "need_units": 50, "allocated_units": 40, "unmet_units": 10,
         "ready_now_units": 40, "awaiting_inbound_units": 0, "equity_weight": 1.0},
    ])


def test_partner_decision_view_tells_staff_who_is_uncovered_and_what_is_planned():
    plan = _plan()
    extra = pd.DataFrame([
        {"site_id": "C", "site_name": "Gamma", "product": "diaper", "size": "6",
         "need_units": 20, "allocated_units": 0, "unmet_units": 20,
         "ready_now_units": 0, "awaiting_inbound_units": 0, "equity_weight": 1.0},
        {"site_id": "D", "site_name": "Delta", "product": "diaper", "size": "5",
         "need_units": 20, "allocated_units": 20, "unmet_units": 0,
         "ready_now_units": 20, "awaiting_inbound_units": 0, "equity_weight": 1.0},
    ])
    summary = partner_summary(pd.concat([plan, extra], ignore_index=True))
    original = summary.copy(deep=True)
    view = partner_decision_view(summary)
    assert view.iloc[0]["site_id"] == "C"
    assert view.set_index("site_id").loc["C", "coverage_status"] == "No allocation"
    assert view.set_index("site_id").loc["A", "coverage_status"] == "Partially covered"
    assert view.set_index("site_id").loc["D", "coverage_status"] == "Fully covered"
    assert view.set_index("site_id").loc["A", "ready_now_units"] == 65
    assert view.set_index("site_id").loc["A", "awaiting_inbound_units"] == 25
    pd.testing.assert_frame_equal(summary, original)


def test_site_rollup_uses_aggregate_units_not_average_of_size_rates():
    out = partner_summary(_plan()).set_index("site_id")
    assert out.loc["A", "fill_rate_pct"] == pytest.approx(60.0)
    assert out.loc["A", "ready_now_units"] == 65
    assert out.loc["A", "awaiting_inbound_units"] == 25
    assert out.loc["B", "fill_rate_pct"] == 80.0


def test_inconsistent_plan_rejected():
    bad = _plan()
    bad.loc[0, "awaiting_inbound_units"] = 55
    with pytest.raises(AllocationError, match="Ready-now"):
        partner_summary(bad)


def test_conflicting_partner_metadata_rejected():
    bad = _plan()
    bad.loc[1, "site_name"] = "Different"
    with pytest.raises(AllocationError, match="Conflicting"):
        partner_summary(bad)


def test_fair_comparison_sign_and_percentage_points():
    result = {"metrics": {"weighted_unmet_units": 80, "worst_site_fill_rate": 0.61},
              "baseline_metrics": {"weighted_unmet_units": 100, "worst_site_fill_rate": 0.65}}
    out = comparison_summary(result)
    assert out["weighted_units_improved"] == 20
    assert out["weighted_improvement_pct"] == 20
    assert out["worst_fill_delta_pp"] == pytest.approx(-4)


def test_no_fake_percentage_improvement_with_zero_baseline():
    result = {"metrics": {"weighted_unmet_units": 0, "worst_site_fill_rate": 1},
              "baseline_metrics": {"weighted_unmet_units": 0, "worst_site_fill_rate": 1}}
    assert comparison_summary(result)["weighted_improvement_pct"] is None


def test_signature_changes_when_inventory_only_changes():
    a = pd.DataFrame([{"size": "5", "quantity_on_hand": 100}])
    b = a.copy()
    b.loc[0, "quantity_on_hand"] = 101
    assert input_signature(a) != input_signature(b)
    assert input_signature(a, None) != input_signature(a, pd.DataFrame())
    assert input_signature(a) == input_signature(a.copy())


def test_verified_integer_cap_only():
    frame = pd.DataFrame([{"site_id": "A", "capacity_units": 20.0},
                          {"site_id": "B", "capacity_units": float("nan")}])
    assert verified_capacity_overrides(frame, {"A", "B"}) == {"A": 20}
    frame.loc[0, "capacity_units"] = 20.5
    with pytest.raises(AllocationError, match="whole number"):
        verified_capacity_overrides(frame, {"A", "B"})


def test_unknown_site_cap_rejected():
    frame = pd.DataFrame([{"site_id": "unknown", "capacity_units": 5}])
    with pytest.raises(AllocationError, match="outside"):
        verified_capacity_overrides(frame, {"A"})


def test_csv_formula_injection_guard():
    csv = csv_download(pd.DataFrame([{"site_name": "=SUM(1,1)", "label": "  @risk", "units": 2}]))
    assert b"'=SUM(1,1)" in csv
    assert b"'  @risk" in csv


@pytest.mark.parametrize(
    ("raw_delta_pp", "display_delta_pp", "direction"),
    [
        (0.0, 0.0, "unchanged"),
        (0.00001, 0.0, "unchanged"),
        (-0.00001, 0.0, "unchanged"),
        (0.0049, 0.0, "unchanged"),
        (-0.0049, 0.0, "unchanged"),
        (0.006, 0.01, "increased"),
        (-0.006, -0.01, "decreased"),
        (0.1, 0.1, "increased"),
        (-0.1, -0.1, "decreased"),
    ],
)
def test_worst_fill_display_uses_same_precision_as_label(raw_delta_pp, display_delta_pp, direction):
    shown, status = worst_fill_display(raw_delta_pp)
    assert shown == pytest.approx(display_delta_pp)
    assert status == direction


@pytest.mark.parametrize("raw", [float("nan"), float("inf"), None, "not a number"])
def test_worst_fill_display_rejects_unknown_change(raw):
    with pytest.raises(AllocationError, match="Worst-site fill change"):
        worst_fill_display(raw)


def test_allocate_staff_view_keeps_partner_and_size_action_drilldown():
    from pathlib import Path
    page = (Path(__file__).resolve().parents[1] / "pages" / "3_Allocate.py").read_text(encoding="utf-8")
    assert 'partner_decision_view(by_site)' in page
    assert 'Coverage review queue (first 8; not an urgency ranking)' in page
    assert 'lower unrounded fill rate first, then more uncovered units' in page
    assert 'apparent ties may still have different positions' in page
    assert '"Show all {len(partner_view)} partner plans"' in page
    assert '"Inspect what a partner is planned to receive by size"' in page
    assert '"Staff review action"' in page


def test_allocate_page_uses_display_precision_for_message():
    from pathlib import Path
    page = (Path(__file__).resolve().parents[1] / "pages" / "3_Allocate.py").read_text(encoding="utf-8")
    assert 'worst_fill_display(comparison["worst_fill_delta_pp"])' in page
    assert 'if fill_direction == "decreased":' in page
    assert 'elif fill_direction == "increased":' in page
    assert 'delta_color="off" if fill_direction == "unchanged" else "normal"' in page
    assert 'comparison["worst_fill_delta_pp"] > 1e-5' not in page
