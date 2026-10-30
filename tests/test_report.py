"""Gate 6A focused contract tests using three sites and an eight-week plan."""

import copy

import pandas as pd
import pytest

from src.report import ReportError, build_report_data


@pytest.fixture
def case():
    start = pd.Timestamp("2026-11-02")
    history = pd.DataFrame([
        {"date": str(date.date()), "site_id": site,
         "quantity": 2 + i, "households_served": 1 if i < 4 else None}
        for i, date in enumerate(pd.date_range("2026-09-07", periods=8, freq="W-MON"))
        for site in ["A", "B", "C"]
    ])
    master = pd.DataFrame([
        {"site_id": "A", "has_survey_data": True,
         "poverty_share_band": "over_75_percent", "priority_population_flags": ""},
        {"site_id": "B", "has_survey_data": True,
         "poverty_share_band": "under_25_percent", "priority_population_flags": ""},
        {"site_id": "C", "has_survey_data": False,
         "poverty_share_band": pd.NA, "priority_population_flags": pd.NA},
    ])
    needs = pd.DataFrame([
        {"site_id": "A", "product": "diaper", "size": "4", "need_units": 8, "requires_review": False},
        {"site_id": "B", "product": "diaper", "size": "4", "need_units": 12, "requires_review": False},
        {"site_id": "C", "product": "period_pad", "size": "regular", "need_units": 10, "requires_review": True},
    ])
    plan = needs.drop(columns="requires_review").copy()
    plan["allocated_units"] = [4, 6, 4]
    plan["unmet_units"] = [4, 6, 6]
    plan["equity_weight"] = [1.5, 1.0, 1.0]
    inventory = pd.DataFrame([
        {"product": "diaper", "size": "4", "on_hand_units": 10},
        {"product": "period_pad", "size": "regular", "on_hand_units": 4},
    ])
    inbound = pd.DataFrame(columns=["product", "size", "confirmed_inbound_units"])
    supply = inventory.rename(columns={"on_hand_units": "available_units"})
    saved = {
        "signature": "fixture-current-input-signature",
        "settings": {"cycle_weeks": 8, "alpha": 0.5, "beta": 0.25},
        "prepared": {"period": {"cycle_start": start,
                                "cycle_end": pd.Timestamp("2026-12-27"),
                                "cycle_weeks": 8,
                                "inventory_as_of": pd.Timestamp("2026-10-26")},
                     "needs": needs, "on_hand": inventory, "supply": supply,
                     "confirmed_inbound": inbound,
                     "forecast_issues": pd.DataFrame(columns=["site_id", "reason"])},
        "solved": {"allocation": plan,
                   "metrics": {"total_allocated_units": 14, "total_unmet_units": 16}},
    }
    return history, master, saved


def build(case, **kwargs):
    history, master, saved = case
    return build_report_data(history, master, saved,
                             expected_signature="fixture-current-input-signature", **kwargs)


def test_eight_week_plan_reports_observed_and_modeled_separately(case):
    result = build(case)
    assert result["periods"]["forecast_start"] == pd.Timestamp("2026-11-02")
    assert result["periods"]["forecast_end"] == pd.Timestamp("2026-12-27")
    assert result["periods"]["historical_start"] == pd.Timestamp("2026-09-07")
    assert result["observed"]["units_distributed"] == 132
    assert result["observed"]["partners_with_distributions"] == 3
    assert result["observed"]["reported_household_service_count_sum"] == 12
    assert result["planning"]["need_units"] == 30
    assert result["planning"]["allocated_units"] == 14
    assert result["planning"]["modeled_unmet_units"] == 16
    assert result["planning"]["supply_gap_units"] == 16
    assert result["planning"]["review_flagged_sku_site_rows"] == 1
    assert "NOT measured community need" in result["labels"]["modeled_unmet"]
    assert any("not deduplicated" in msg for msg in result["warnings"])


def test_equity_only_classifies_supported_survey_labels(case):
    result = build(case)
    assert result["equity"]["classified_high_need_partners"] == 1
    assert result["equity"]["unknown_classification_partners"] == 1
    assert result["equity"]["planned_high_need_share_of_all_allocations_pct"] == pytest.approx(100*4/14)
    assert result["equity"]["classification_coverage_of_allocations_pct"] == pytest.approx(100*10/14)


def test_missing_survey_means_no_equity_claim(case):
    case = copy.deepcopy(case)
    case[1]["has_survey_data"] = False
    result = build(case)
    assert result["equity"]["planned_high_need_share_of_all_allocations_pct"] is None
    assert result["equity"]["classification_coverage_of_allocations_pct"] == 0


def test_pricing_requires_per_unit_basis_and_complete_prices_for_total(case):
    only_diapers = pd.DataFrame([{"product": "diaper", "size": "4",
                                  "unit_cost_usd": 0.25, "price_basis": "verified_quote"}])
    partial = build(case, prices=only_diapers)
    assert partial["pricing"]["fully_costed_ask_usd"] is None
    assert partial["pricing"]["partially_costed_usd"] == 2.50
    both = pd.concat([only_diapers, pd.DataFrame([{
        "product": "period_pad", "size": "regular", "unit_cost_usd": 0.50,
        "price_basis": "scenario_assumption"}])], ignore_index=True)
    result = build(case, prices=both)
    assert result["pricing"]["fully_costed_ask_usd"] == 5.50
    assert result["pricing"]["all_prices_verified_quotes"] is False
    assert any("scenario assumptions" in msg for msg in result["warnings"])


def test_price_zero_or_unspecified_provenance_not_accepted(case):
    for cost, basis in [(0, "verified_quote"), (0.001, "verified_quote"),
                        (0.5, None), (-1, "verified_quote")]:
        frame = pd.DataFrame([{"product":"diaper", "size":"4",
                               "unit_cost_usd":cost, "price_basis":basis}])
        with pytest.raises(ReportError):
            build(case, prices=frame)


def test_four_week_and_stale_plan_fail_closed(case):
    sample = copy.deepcopy(case)
    sample[2]["prepared"]["period"]["cycle_weeks"] = 4
    with pytest.raises(ReportError, match="8-week"):
        build(sample)
    with pytest.raises(ReportError, match="stale"):
        build_report_data(*case[:2], case[2], expected_signature="other-snapshot")


def test_missing_inventory_row_not_silently_zeroed(case):
    sample = copy.deepcopy(case)
    prepared = sample[2]["prepared"]
    prepared["on_hand"] = prepared["on_hand"].iloc[:1].copy()
    prepared["supply"].loc[1, "available_units"] = 0
    sample[2]["solved"]["allocation"].loc[2, "allocated_units"] = 0
    sample[2]["solved"]["allocation"].loc[2, "unmet_units"] = 10
    sample[2]["solved"]["metrics"] = {"total_allocated_units": 10, "total_unmet_units": 20}
    with pytest.raises(ReportError, match="inventory snapshot"):
        build(sample)


def test_saved_plan_inconsistencies_fail_closed(case):
    sample = copy.deepcopy(case)
    sample[2]["solved"]["allocation"].loc[0, "unmet_units"] = 5
    with pytest.raises(ReportError, match="do not equal"):
        build(sample)
    sample = copy.deepcopy(case)
    sample[2]["prepared"]["supply"].loc[0, "available_units"] = 11
    with pytest.raises(ReportError, match="inconsistent"):
        build(sample)


def test_unresolved_partner_is_explicitly_disclosed(case):
    sample = copy.deepcopy(case)
    sample[2]["prepared"]["forecast_issues"] = pd.DataFrame([{
        "site_id": "D", "reason": "unavailable_history"}])
    result = build(sample)
    assert result["planning"]["unresolved_forecast_sites"] == 1
    assert any("network coverage is incomplete" in x for x in result["warnings"])


def test_original_inputs_remain_unchanged(case):
    orig = copy.deepcopy(case)
    build(case)
    for a, b in zip(case[:2], orig[:2]):
        pd.testing.assert_frame_equal(a, b)
    for section in ["needs", "on_hand", "supply", "confirmed_inbound"]:
        pd.testing.assert_frame_equal(case[2]["prepared"][section], orig[2]["prepared"][section])
    pd.testing.assert_frame_equal(case[2]["solved"]["allocation"], orig[2]["solved"]["allocation"])


def test_shortfall_may_differ_from_supply_gap_when_cap_binds(case):
    sample = copy.deepcopy(case)
    saved = sample[2]
    # Model can leave some need unallocated with excess network stock due
    # to verified site storage caps or other operational constraints.
    saved["prepared"]["supply"].loc[0, "available_units"] = 20
    saved["prepared"]["on_hand"].loc[0, "on_hand_units"] = 20
    result = build(sample)
    assert result["planning"]["modeled_unmet_units"] == 16
    assert result["planning"]["supply_gap_units"] == 6


def test_no_shortage_means_zero_cost_ask_without_quotes(case):
    sample = copy.deepcopy(case)
    prepared = sample[2]["prepared"]
    prepared["on_hand"]["on_hand_units"] = [20, 10]
    prepared["supply"]["available_units"] = [20, 10]
    result = build(sample)
    assert result["planning"]["supply_gap_units"] == 0
    assert result["pricing"]["fully_costed_ask_usd"] == 0


def test_site_master_mismatch_is_rejected(case):
    history, master, saved = copy.deepcopy(case)
    narrowed_master = master.loc[master["site_id"] != "C"].copy()
    with pytest.raises(ReportError, match="unknown partner"):
        build((history, narrowed_master, saved))


def test_prepared_operational_warnings_survive_in_report(case):
    sample = copy.deepcopy(case)
    sample[2]["prepared"]["warnings"] = pd.DataFrame([
        {"code": "stale_inventory", "message": "Inventory snapshot is over 14 days old.", "count": 1}
    ])
    result = build(sample)
    assert "Inventory snapshot is over 14 days old." in result["warnings"]
