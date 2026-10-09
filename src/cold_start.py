"""Week 3 CP5B: provenance-aware, survey-based cold-start estimates.

Uses only logged site activity <= forecast origin and peer survey data.
No fabricated demand, implicit survey dates, or claimed backtested WAPE.
"""

from datetime import timedelta

import numpy as np
import pandas as pd

from src.forecast_output import OUTPUT_COLUMNS

COLD_START_COLUMNS = OUTPUT_COLUMNS
ISSUE_COLUMNS = ["site_id", "reason", "detail"]
CHILD_KEYS = ["site_id", "product", "size"]


class ColdStartError(ValueError):
    """Unsafe or invalid cold-start forecasting input."""


def _origin_date(value):
    try:
        origin = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ColdStartError("Invalid forecast origin.") from exc
    if pd.isna(origin) or origin.tzinfo is not None or origin.weekday() != 0:
        raise ColdStartError("Origin must be a timezone-naive ISO Monday.")
    return origin.normalize()


def _validate_inputs(weekly, site_master):
    wk_required = set(CHILD_KEYS + ["week_start", "quantity", "is_imputed_zero"])
    ms_required = {"site_id", "site_name", "families_served_per_month", "agency_type"}
    if not wk_required.issubset(weekly.columns):
        raise ColdStartError(f"Weekly data missing: {sorted(wk_required - set(weekly.columns))}")
    if not ms_required.issubset(site_master.columns):
        raise ColdStartError(f"Site master missing: {sorted(ms_required - set(site_master.columns))}")
    if site_master.empty:
        raise ColdStartError("Site master must not be empty.")

    df = weekly.copy()
    df["week_start"] = pd.to_datetime(df["week_start"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    if (df[CHILD_KEYS + ["week_start"]].isna().any().any()
            or df.duplicated(CHILD_KEYS + ["week_start"]).any()
            or (df["week_start"].dt.weekday != 0).any()
            or not np.isfinite(df["quantity"].to_numpy(dtype=float)).all()
            or df["quantity"].lt(0).any()
            or df["is_imputed_zero"].isna().any()
            or not df["is_imputed_zero"].isin([True, False]).all()):
        raise ColdStartError("Invalid canonical weekly history.")

    ms = site_master.copy()
    if ms["site_id"].isna().any() or ms["site_id"].duplicated().any():
        raise ColdStartError("Invalid or duplicated site IDs in site master.")
    if "survey_as_of_week" in ms.columns:
        # Null dates mean undated; non-null dates must be valid.
        raw_dates = ms["survey_as_of_week"]
        dates = pd.to_datetime(raw_dates, errors="coerce")
        if (raw_dates.notna() & dates.isna()).any():
            raise ColdStartError("Invalid survey_as_of_week.")
        ms["survey_as_of_week"] = dates
    return df, ms


def build_survey_cold_start(
    weekly,
    site_master,
    origin_week,
    target_site_ids,
    horizon=4,
    lookback_weeks=12,
    min_peer_sites=2,
    allow_undated_survey_for_demo=False,
):
    """Forecast specified sites with 0..7 observed SITE weeks.

    At each origin, fit an empirical network weekly-units/family rate:
      sum(peer observed distribution units in recent valid site-weeks)
      / sum(peer family counts repeated over those observed site-weeks).
    Only >=8-week-history peers with >=4 observed weeks in the lookback
    and valid, positive family counts are included. Target is excluded.

    For product-size shares, prefer a same-agency peer mix when >=2 peers
    of that agency are available; otherwise use the network peer mix.
    Both are observed distribution proxies, NOT unconstrained demand.

    Survey date provenance is required for a historical claim. Undated
    synthetic surveys can be used only with explicit DEMO opt-in, and all
    resulting forecasts are flagged as retrospective assumptions.
    """
    origin = _origin_date(origin_week)
    if type(horizon) is not int or not 4 <= horizon <= 8:
        raise ColdStartError("Forecast horizon must be 4..8 whole weeks.")
    if type(lookback_weeks) is not int or lookback_weeks < 4:
        raise ColdStartError("Lookback must be at least four weeks.")
    if type(min_peer_sites) is not int or min_peer_sites < 2:
        raise ColdStartError("Require at least two eligible peer sites.")
    if not isinstance(allow_undated_survey_for_demo, bool):
        raise ColdStartError("Demo flag must be boolean.")
    if not isinstance(target_site_ids, (list, tuple)) or not target_site_ids:
        raise ColdStartError("Supply a nonempty list of target site IDs.")
    if len(set(target_site_ids)) != len(target_site_ids):
        raise ColdStartError("Duplicate target site ID.")

    data, master = _validate_inputs(weekly, site_master)
    hist = data.loc[data["week_start"] <= origin].copy()
    ms = master.set_index("site_id", drop=False)
    weeks_per_site = hist.groupby("site_id")["week_start"].nunique().to_dict()
    last_site_week = hist.groupby("site_id")["week_start"].max().to_dict()
    start = origin - timedelta(days=7 * (lookback_weeks - 1))
    recent = hist.loc[hist["week_start"].between(start, origin)].copy()

    forecasts = []
    issues = []
    calibrations = []
    future_weeks = pd.date_range(origin + timedelta(days=7), periods=horizon, freq="W-MON")

    for target in target_site_ids:
        if target not in ms.index:
            issues.append({"site_id": target, "reason": "unknown_site_id", "detail": "Site absent from site master."})
            continue
        s = ms.loc[target]
        n_observed = int(weeks_per_site.get(target, 0))
        if n_observed >= 8:
            issues.append({"site_id": target, "reason": "historical_method_eligible", "detail": f"{n_observed} observed site-weeks; use history-based engine."})
            continue
        if n_observed > 0 and last_site_week[target] != origin:
            issues.append({"site_id": target, "reason": "site_inactive_at_origin", "detail": "Last site-observed week differs from forecast origin; manual review."})
            continue

        families = pd.to_numeric(pd.Series([s["families_served_per_month"]]), errors="coerce").iloc[0]
        if not np.isfinite(families) or families <= 0 or families != int(families):
            issues.append({"site_id": target, "reason": "missing_family_denominator", "detail": "Survey family count must be a positive whole number."})
            continue
        if pd.isna(s["agency_type"]) or not str(s["agency_type"]).strip():
            issues.append({"site_id": target, "reason": "missing_agency_type", "detail": "Agency type unavailable."})
            continue
        if "has_survey_data" in s.index and not bool(s["has_survey_data"]):
            issues.append({"site_id": target, "reason": "survey_missing", "detail": "Site has no survey record."})
            continue

        survey_date = s.get("survey_as_of_week", pd.NaT)
        undated = pd.isna(survey_date)
        if not undated and pd.Timestamp(survey_date).normalize() > origin:
            issues.append({"site_id": target, "reason": "survey_not_yet_available", "detail": "Survey timestamp follows historical forecast origin."})
            continue
        if undated and not allow_undated_survey_for_demo:
            issues.append({"site_id": target, "reason": "survey_date_unverified", "detail": "Undated survey: opt in explicitly for a retrospective synthetic demonstration."})
            continue

        # Peer survey denominators and week counts are origin-safe only if
        # survey vintages are supplied, or the caller explicitly accepts the
        # limitation of using an undated synthetic snapshot.
        peers = master.loc[master["site_id"].ne(target)].copy()
        peers["families"] = pd.to_numeric(peers["families_served_per_month"], errors="coerce")
        peers = peers.loc[
            peers["families"].gt(0) & np.isfinite(peers["families"])
            & peers["agency_type"].notna()
        ].copy()
        peers["history_weeks"] = peers["site_id"].map(weeks_per_site).fillna(0).astype(int)
        recent_weeks = recent.groupby("site_id")["week_start"].nunique().to_dict()
        peers["recent_weeks"] = peers["site_id"].map(recent_weeks).fillna(0).astype(int)
        peers = peers.loc[(peers["history_weeks"] >= 8) & (peers["recent_weeks"] >= 4)]
        if "has_survey_data" in peers.columns:
            peers = peers.loc[peers["has_survey_data"].eq(True)]
        if "survey_as_of_week" in peers.columns:
            ok = peers["survey_as_of_week"].le(origin)
            if allow_undated_survey_for_demo:
                ok |= peers["survey_as_of_week"].isna()
            peers = peers.loc[ok]

        if len(peers) < min_peer_sites:
            issues.append({"site_id": target, "reason": "insufficient_calibration_peers", "detail": "Not enough history-eligible sites with usable family counts at origin."})
            continue

        peer_weekly = recent.loc[recent["site_id"].isin(peers["site_id"])].copy()
        site_week_counts = peer_weekly.groupby("site_id")["week_start"].nunique()
        family_map = peers.set_index("site_id")["families"]
        exposure = float((site_week_counts * family_map.reindex(site_week_counts.index)).sum())
        numerator = float(peer_weekly["quantity"].sum())
        if exposure <= 0 or numerator <= 0:
            issues.append({"site_id": target, "reason": "unusable_peer_calibration", "detail": "No positive distribution or family exposure in calibration cohort."})
            continue

        units_per_family_week = numerator / exposure
        agency_peers = peers.loc[peers["agency_type"].eq(s["agency_type"]), "site_id"]
        if len(agency_peers) >= min_peer_sites:
            mix_rows = peer_weekly.loc[peer_weekly["site_id"].isin(agency_peers)]
            mix_source = "agency_type_observed_mix"
        else:
            mix_rows = peer_weekly
            mix_source = "network_observed_mix"

        child_totals = (
            mix_rows.groupby(["product", "size"], as_index=False)["quantity"]
            .sum().sort_values(["product", "size"]).reset_index(drop=True)
        )
        weight_total = float(child_totals["quantity"].sum())
        if weight_total <= 0:
            issues.append({"site_id": target, "reason": "unusable_peer_mix", "detail": "No positive observed product-size mix for peer cohort."})
            continue
        child_totals = child_totals.loc[child_totals["quantity"].gt(0)].copy()
        child_totals["weight"] = child_totals["quantity"] / weight_total
        weekly_parent = float(families * units_per_family_week)
        provenance_flag = "undated_survey_retrospective_demo" if undated else "survey_dated_at_or_before_origin"

        for row in child_totals.itertuples(index=False):
            for week in future_weeks:
                record = {name: np.nan for name in COLD_START_COLUMNS}
                record.update({
                    "site_id": target, "product": row.product, "size": row.size,
                    "week_start": week, "forecast_units": weekly_parent * float(row.weight),
                    "hierarchy": "site_total", "method": "survey_based", "method_level": "site_total",
                    "forecast_source": "survey_based_peer_calibration", "weight": float(row.weight),
                    "mix_source": mix_source, "origin_week": origin,
                    "parent_wape_pct": np.nan, "parent_bias_pct": np.nan,
                    "parent_backtest_folds": 0, "wape_pct": np.nan,
                    "wape_reason": "survey_based_no_leakage_safe_backtest",
                    "quality_flags": provenance_flag + ";" + "distribution_proxy_not_unconstrained_demand",
                    "requires_review": True, "forecast_status": "provisional_cp5_survey",
                })
                forecasts.append(record)
        calibrations.append({
            "site_id": target, "observed_site_weeks": n_observed,
            "calibration_peer_sites": len(peers), "mix_peer_sites": len(agency_peers) if mix_source.startswith("agency") else len(peers),
            "units_per_family_week": units_per_family_week,
            "site_forecast_units_per_week": weekly_parent,
            "mix_source": mix_source,
            "survey_provenance": provenance_flag,
        })

    result = pd.DataFrame(forecasts, columns=COLD_START_COLUMNS)
    if not result.empty:
        if result.duplicated(CHILD_KEYS + ["week_start"]).any():
            raise ColdStartError("Duplicate forecast keys.")
        if not np.isfinite(result["forecast_units"].to_numpy(dtype=float)).all():
            raise ColdStartError("Non-finite cold-start output.")
        if result["forecast_units"].lt(0).any():
            raise ColdStartError("Negative cold-start units.")
    return {
        "forecasts": result,
        "issues": pd.DataFrame(issues, columns=ISSUE_COLUMNS),
        "calibration": pd.DataFrame(calibrations),
    }
