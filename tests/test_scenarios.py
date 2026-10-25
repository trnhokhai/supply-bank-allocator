"""Gate 5 pure transformation tests. These do not certify the full solver."""

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from src.scenarios import (
    ScenarioError, assume_pending_confirmed, change_source_supply,
    prospective_partner, shift_forecast_mix, reconcile_scenario_demand,
)


@pytest.fixture
def period():
    return {
        "cycle_start": pd.Timestamp("2026-09-28"),
        "cycle_end": pd.Timestamp("2026-10-25"),
        "inventory_as_of": pd.Timestamp("2026-09-21"), "cycle_weeks": 4,
    }


@pytest.fixture
def incoming():
    return pd.DataFrame([
        {"expected_date": "2026-10-01", "source": "Donation A", "product": "diaper", "size": "5", "quantity": 11, "status": "confirmed"},
        {"expected_date": "2026-10-03", "source": "Donation B", "product": "diaper", "size": "5", "quantity": 9, "status": "confirmed"},
        {"expected_date": "2026-10-04", "source": "Planned Purchase", "product": "diaper", "size": "5", "quantity": 30, "status": "confirmed"},
        {"expected_date": "2026-10-05", "source": "Donation A", "product": "diaper", "size": "5", "quantity": 7, "status": "pending"},
        {"expected_date": "2026-10-06", "source": "Donation A", "product": "diaper", "size": "unknown", "quantity": 19, "status": "pending"},
        {"expected_date": "2026-11-02", "source": "Donation A", "product": "diaper", "size": "5", "quantity": 14, "status": "pending"},
        {"expected_date": "2026-09-21", "source": "Donation A", "product": "diaper", "size": "5", "quantity": 15, "status": "confirmed"},
    ])


@pytest.fixture
def forecasts():
    return pd.DataFrame([
        {"site_id": site, "week_start": week, "product": "diaper", "size": size,
         "forecast_units": float(value), "requires_review": False, "quality_flags": "", "forecast_source": "site_total_historical"}
        for site, values in (("A", {"1": 20, "5": 10}), ("B", {"1": 12, "5": 24}))
        for week in pd.date_range("2026-09-28", periods=4, freq="W-MON")
        for size, value in values.items()
    ])


@pytest.fixture
def master():
    return pd.DataFrame([
        {"site_id": "A", "site_name": "Alpha", "families_served_per_month": 100, "agency_type": "school", "has_distribution_history": True, "has_survey_data": True},
        {"site_id": "B", "site_name": "Beta", "families_served_per_month": 120, "agency_type": "school", "has_distribution_history": True, "has_survey_data": True},
        {"site_id": "C", "site_name": "Gamma", "families_served_per_month": 30, "agency_type": "school", "has_distribution_history": False, "has_survey_data": True},
    ])


def test_scaling_only_selected_confirmed_sources(incoming, period):
    original = incoming.copy(deep=True)
    changed, info = change_source_supply(incoming, period, ["Donation A"], -50)
    assert changed.iloc[0]["quantity"] == 6  # 11*0.5 rounds half-up
    assert changed.iloc[1]["quantity"] == 9
    assert changed.iloc[2]["quantity"] == 30  # purchases never implicitly scaled
    assert changed.iloc[3]["quantity"] == 7  # pending untouched
    assert changed.iloc[6]["quantity"] == 15  # pre-snapshot untouched
    assert info["changed_inbound_units"] == -5
    pd.testing.assert_frame_equal(incoming, original)


@pytest.mark.parametrize("factor", [51, -51, True, float("nan"), "30"])
def test_reject_invalid_scaling(incoming, period, factor):
    with pytest.raises(ScenarioError):
        change_source_supply(incoming, period, ["Donation A"], factor)


def test_reject_unselected_source(incoming, period):
    with pytest.raises(ScenarioError):
        change_source_supply(incoming, period, ["Not Found"], -10)


def test_pending_promotion_excludes_unknown_late(incoming, period):
    original = incoming.copy(deep=True)
    changed, info = assume_pending_confirmed(incoming, period)
    assert changed.iloc[3]["status"] == "confirmed"
    assert changed.iloc[4]["status"] == "pending"  # unknown size
    assert changed.iloc[5]["status"] == "pending"  # after cycle
    assert info == {"assumed_confirmed_rows": 1, "assumed_inbound_units": 7}
    pd.testing.assert_frame_equal(incoming, original)


def test_size_mix_conserves_site_week_total(forecasts, period):
    original = forecasts.copy(deep=True)
    shifted, info = shift_forecast_mix(forecasts, "diaper", "1", "5", 25, period)
    before = forecasts.groupby(["site_id", "week_start", "product"])["forecast_units"].sum()
    after = shifted.groupby(["site_id", "week_start", "product"])["forecast_units"].sum()
    pd.testing.assert_series_equal(before, after)
    assert float(shifted.loc[(shifted.site_id == "A") & (shifted["size"] == "1"), "forecast_units"].iloc[0]) == 15
    assert float(shifted.loc[(shifted.site_id == "A") & (shifted["size"] == "5"), "forecast_units"].iloc[0]) == 15
    assert shifted["requires_review"].all()
    assert shifted["forecast_source"].eq("scenario_adjusted_point_forecast").all()
    assert info["demand_total_conserved"] is True
    pd.testing.assert_frame_equal(original, forecasts)


def test_size_mix_missing_pair_rejected(forecasts, period):
    incomplete = forecasts.loc[~((forecasts["site_id"] == "B") & (forecasts["size"] == "5") & (forecasts["week_start"] == pd.Timestamp("2026-09-28")))].copy()
    with pytest.raises(ScenarioError, match="both sizes"):
        shift_forecast_mix(incomplete, "diaper", "1", "5", 20, period)


@pytest.mark.parametrize("pct", [-1, 0, 51, float("inf"), True])
def test_size_mix_reject_invalid_rates(forecasts, period, pct):
    with pytest.raises(ScenarioError):
        shift_forecast_mix(forecasts, "diaper", "1", "5", pct, period)


def test_new_partner_requires_explicit_ack(forecasts, master, period):
    with pytest.raises(ScenarioError, match="Acknowledge"):
        prospective_partner(forecasts, master, period, site_id="C")


def test_existing_survey_only_partner_is_prospective(forecasts, master, period):
    fc0, master0 = forecasts.copy(deep=True), master.copy(deep=True)
    fc, site_master, info = prospective_partner(forecasts, master, period, site_id="C", acknowledged=True)
    assert fc["site_id"].nunique() == 3
    added = fc.loc[fc["site_id"].eq("C")]
    assert len(added) == 8
    assert added["requires_review"].all()
    assert added["forecast_source"].eq("prospective_scenario_peer_scaling").all()
    assert np.isclose(added["forecast_units"].sum(), forecasts["forecast_units"].sum() * (30 / 220))
    assert info["peer_sites"] == 2
    pd.testing.assert_frame_equal(forecasts, fc0)
    pd.testing.assert_frame_equal(master, master0)
    pd.testing.assert_frame_equal(site_master, master)


def test_hypothetical_partner_is_not_added_to_input_master(forecasts, master, period):
    fc, ms, info = prospective_partner(forecasts, master, period, name="Prospective Site", families=80, agency_type="school", acknowledged=True)
    assert len(ms) == len(master) + 1
    assert info["new_partner_id"].startswith("scenario_")
    assert len(fc) == len(forecasts) + 8
    assert "Prospective Site" not in master["site_name"].tolist()
    assert info["provenance"] == "provisional_prospective_scenario_not_backtested"


def test_new_partner_cannot_duplicate_existing_forecast(forecasts, master, period):
    with pytest.raises(ScenarioError):
        prospective_partner(forecasts, master, period, site_id="A", acknowledged=True)


def test_new_partner_requires_positive_integer_families(forecasts, master, period):
    with pytest.raises(ScenarioError):
        prospective_partner(forecasts, master, period, name="Prospective Site", families=1.5, agency_type="school", acknowledged=True)


def test_size_mix_clears_stale_accuracy_and_ranges(forecasts, period):
    forecasts["wape_pct"] = 12.0
    forecasts["parent_wape_pct"] = 10.0
    forecasts["lower_units"] = 1.0
    forecasts["upper_units"] = 100.0
    forecasts["wape_reason"] = "old_model_backtest"
    forecasts["method"] = "naive"
    new, _ = shift_forecast_mix(forecasts, "diaper", "1", "5", 20, period)
    for column in ("wape_pct", "parent_wape_pct", "lower_units", "upper_units"):
        assert new[column].isna().all()
    assert new["wape_reason"].eq("scenario_shift_not_backtested").all()
    assert new["method"].eq("assumed_size_mix_shift").all()
    assert forecasts["wape_pct"].eq(12).all()  # original forecast untouched


def test_size_mix_zero_source_volume_rejected(forecasts, period):
    forecasts.loc[forecasts["size"].eq("1"), "forecast_units"] = 0.0
    with pytest.raises(ScenarioError, match="no positive volume"):
        shift_forecast_mix(forecasts, "diaper", "1", "5", 25, period)


def test_size_mix_family_selector_is_outside_form():
    """Dependent size selectors must rerender as soon as family changes.

    Streamlit forms defer widget updates until submit. A family selector nested
    inside the same form would show the *previous* family's sizes and could
    submit incompatible values. Keep product outside and size selectors inside.
    """
    import ast
    from pathlib import Path

    page = Path(__file__).resolve().parents[1] / "pages" / "5_Scenarios.py"
    tree = ast.parse(page.read_text(encoding="utf-8-sig"))

    def selectboxes(root, label):
        return [node for node in ast.walk(root)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "selectbox"
                and node.args and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == label]

    forms = [node for node in ast.walk(tree) if isinstance(node, ast.With)
             and any(isinstance(item.context_expr, ast.Call)
                     and isinstance(item.context_expr.func, ast.Attribute)
                     and item.context_expr.func.attr == "form"
                     for item in node.items)]
    assert len(forms) == 1
    form = forms[0]
    family = selectboxes(tree, "Product family")
    assert len(family) == 1
    assert family[0].lineno < form.lineno
    assert not selectboxes(form, "Product family")
    assert len(selectboxes(form, "Move demand FROM size")) == 1
    assert len(selectboxes(form, "Move demand TO size")) == 1


def test_size_mix_reconciliation_explains_one_integer_unit_without_changing_needs():
    """Conserved fractional forecast can round to +1 across two product sizes."""
    original = {"needs": pd.DataFrame([
        {"site_id": "A", "product": "diaper", "size": "2", "forecast_units": 2.2, "need_units": 2},
        {"site_id": "A", "product": "diaper", "size": "5", "forecast_units": 1.2, "need_units": 1},
    ])}
    scenario = {"needs": pd.DataFrame([
        {"site_id": "A", "product": "diaper", "size": "2", "forecast_units": 1.76, "need_units": 2},
        {"site_id": "A", "product": "diaper", "size": "5", "forecast_units": 1.64, "need_units": 2},
    ])}
    original_before, scenario_before = original["needs"].copy(deep=True), scenario["needs"].copy(deep=True)
    audit = reconcile_scenario_demand(original, scenario, "size_mix")
    assert audit["expected_delta_units"] == pytest.approx(0, abs=1e-10)
    assert audit["integer_need_delta_units"] == 1
    assert audit["rounding_delta_units"] == pytest.approx(1)
    pd.testing.assert_frame_equal(original["needs"], original_before)
    pd.testing.assert_frame_equal(scenario["needs"], scenario_before)


def test_size_mix_reconciliation_rejects_unexplained_demand_change():
    old = {"needs": pd.DataFrame([{"site_id":"A", "product":"diaper", "size":"2", "forecast_units":2.2,"need_units":2}])}
    changed = {"needs": pd.DataFrame([{"site_id":"A", "product":"diaper", "size":"2", "forecast_units":3.2,"need_units":3}])}
    with pytest.raises(ScenarioError, match="fractional demand"):
        reconcile_scenario_demand(old, changed, "size_mix")


def test_supply_only_reconciliation_requires_same_integer_demand():
    old = {"needs": pd.DataFrame([{"site_id":"A", "product":"diaper", "size":"2", "forecast_units":2.2,"need_units":2}])}
    changed = {"needs": pd.DataFrame([{"site_id":"A", "product":"diaper", "size":"2", "forecast_units":2.2,"need_units":3}])}
    with pytest.raises(ScenarioError, match="integer planning demand"):
        reconcile_scenario_demand(old, changed, "pending_confirmed")


def test_size_mix_reconciliation_rejects_multiple_integer_drift():
    old = {"needs": pd.DataFrame([{"site_id":"A", "product":"diaper", "size":"2", "forecast_units":2.2,"need_units":2}])}
    changed = {"needs": pd.DataFrame([{"site_id":"A", "product":"diaper", "size":"2", "forecast_units":2.2,"need_units":4}])}
    with pytest.raises(ScenarioError, match="rounding bound"):
        reconcile_scenario_demand(old, changed, "size_mix")


def test_assumption_details_collapsed_and_hypothetical_exports_labeled():
    from pathlib import Path
    page = (Path(__file__).resolve().parents[1] / "pages" / "5_Scenarios.py").read_text(encoding="utf-8")
    assert 'with st.expander("Technical assumptions / audit JSON"' in page
    assert '"submitted_params": dict(params)' in page
    assert 'HYPOTHETICAL_NOT_PICK_AUTHORIZATION' in page
    assert '"ready_now_units": "on_hand_backed_planning_units"' in page
    assert '"awaiting_inbound_units": "future_inbound_backed_planning_units"' in page


def test_stale_scenario_results_never_reach_demand_audit_rendering():
    """Regression: new UI + old session/backend caused KeyError demand_audit."""
    import ast
    from pathlib import Path

    page = Path(__file__).resolve().parents[1] / "pages" / "5_Scenarios.py"
    source = page.read_text(encoding="utf-8-sig")
    parsed = ast.parse(source)
    helper = next(n for n in parsed.body if isinstance(n, ast.FunctionDef)
                  and n.name == "_has_current_demand_audit")
    # Test the actual guard implementation without importing the Streamlit app.
    mod = ast.Module(body=[helper], type_ignores=[])
    ns = {}
    exec(compile(ast.fix_missing_locations(mod), str(page), "exec"), ns)
    current = ns["_has_current_demand_audit"]
    assert not current({})
    assert not current(None)
    assert not current({"demand_audit": None})
    assert not current({"demand_audit": {"expected_delta_units": 0}})
    assert current({"demand_audit": {"expected_delta_units": 0,
                                       "integer_need_delta_units": 1}})

    # Both fresh solver results and saved in-session results are checked.
    assert source.count("if not _has_current_demand_audit(result):") == 2
    assert source.index('st.session_state.pop("g5_scenario_result", None)',
                        source.index('result = saved["result"]')) < source.index('audit = result["demand_audit"]')

    # Execute the real stale-saved-result guard to prove it stops rendering,
    # clears ONLY the stale what-if result, and leaves the baseline intact.
    guard = next(node for node in parsed.body
                 if isinstance(node, ast.If)
                 and isinstance(node.test, ast.UnaryOp)
                 and isinstance(node.test.operand, ast.Call)
                 and isinstance(node.test.operand.func, ast.Name)
                 and node.test.operand.func.id == "_has_current_demand_audit")
    code = compile(ast.fix_missing_locations(ast.Module(body=[guard], type_ignores=[])),
                   str(page), "exec")

    class StopRendering(Exception):
        pass

    class FakeStreamlit:
        def __init__(self):
            self.session_state = {"g5_scenario_result": {"old": True},
                                  "g4_allocation_result": "preserved baseline"}
            self.messages = []

        def warning(self, msg):
            self.messages.append(msg)

        def stop(self):
            raise StopRendering()

    fake = FakeStreamlit()
    with pytest.raises(StopRendering):
        exec(code, {"_has_current_demand_audit": current, "result": {}, "st": fake})
    assert "g5_scenario_result" not in fake.session_state
    assert fake.session_state["g4_allocation_result"] == "preserved baseline"
    assert "older code version" in fake.messages[0]

    valid = {"demand_audit": {"expected_delta_units": 0, "integer_need_delta_units": 1}}
    fresh = FakeStreamlit()
    exec(code, {"_has_current_demand_audit": current, "result": valid, "st": fresh})
    assert "g5_scenario_result" in fresh.session_state
    assert not fresh.messages
