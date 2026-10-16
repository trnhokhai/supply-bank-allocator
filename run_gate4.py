"""Reproducible Week 4 / Gate 4 scientific audit on SYNTHETIC data only.

Run from the supply-bank-allocator repository root:
    python run_gate4.py

This script reuses the ACTUAL canonical upload/forecast/optimizer functions.
It neither mutates the application nor saves uploaded data. The 80 x 20
performance fixture is synthetic and constructed independently of outcomes.
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import subprocess
import sys
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd


PENALTY_SHARES = (0.0, 0.01, 0.04, 0.10, 0.20, 0.50, 1.00)


def _pct_change(old: float, new: float) -> float | None:
    if old == 0:
        return None
    return (old - new) / old * 100.0


def _label_ratio(value: float | None) -> str:
    return "N/A" if value is None else f"{value:+.3f}%"


def _assert_solution(result: dict, needs: pd.DataFrame, supply: pd.DataFrame) -> None:
    """Independent material-balance and eligibility checks, not just solver status."""
    demand = needs.set_index(["site_id", "product", "size"])["need_units"]
    limits = supply.set_index(["product", "size"])["available_units"]
    for name in ("allocation", "proportional_baseline"):
        plan = result[name].copy()
        assert not plan.duplicated(["site_id", "product", "size"]).any(), name
        assert len(plan) == len(needs), name
        assert (plan["allocated_units"] >= 0).all(), name
        assert (plan["unmet_units"] >= 0).all(), name
        assert (plan["allocated_units"] + plan["unmet_units"] == plan["need_units"]).all(), name
        assert (plan["allocated_units"] >= plan["fairness_min_units"]).all(), name
        assert np.equal(plan["allocated_units"], np.floor(plan["allocated_units"])).all(), name
        joined = plan.set_index(["site_id", "product", "size"])["need_units"]
        pd.testing.assert_series_equal(joined.sort_index(), demand.sort_index(), check_names=False)
        by_sku = plan.groupby(["product", "size"])["allocated_units"].sum()
        for sku, count in by_sku.items():
            assert count <= int(limits.get(sku, 0)), f"{name} oversupplies {sku}"
    metrics = result["metrics"]
    assert metrics["total_unmet_units"] == int(result["allocation"]["unmet_units"].sum())
    assert -1e-9 <= metrics["worst_site_fill_rate"] <= 1 + 1e-9


def build_scale_fixture(prepared: dict, seed: int = 2026) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Full 80-sites x 20-variants stress scenario, fixed before solving.

    Uses product/size identifiers and size-scale medians from the original
    synthetic demo. Does not cherry-pick results. All 1,600 site/SKU
    combinations have positive need. Capacity overrides are deliberately
    absent here so they do not confound the speed acceptance criterion.
    """
    rng = np.random.default_rng(seed)
    source = prepared["needs"]
    variants = (source[["product", "size"]]
                .drop_duplicates().sort_values(["product", "size"])
                .reset_index(drop=True))
    if len(variants) < 20:
        raise RuntimeError(f"Only {len(variants)} variants in demo; need 20.")
    variants = variants.head(20)
    rows = []
    inventory = []
    for sku in variants.itertuples(index=False):
        matched = source.loc[source["product"].eq(sku.product) & source["size"].eq(sku.size), "need_units"]
        positive = matched[matched > 0]
        typical = float(positive.median()) if not positive.empty else 30.0
        # Vary volume across partners but keep the observed category scale.
        quantities = np.maximum(1, np.rint(typical * rng.lognormal(0.0, 0.5, 80)).astype(int))
        for i, need in enumerate(quantities):
            rows.append({"site_id": f"STRESS_{i+1:03d}",
                         "product": sku.product, "size": sku.size,
                         "need_units": int(need)})
        # Fixed test shortage fractions, not tuned to the optimizer's output.
        fraction = 0.72 if sku.product == "diaper" and sku.size in ("5", "6") else 0.87
        inventory.append({"product": sku.product, "size": sku.size,
                          "available_units": int(round(int(quantities.sum()) * fraction))})
    needs = pd.DataFrame(rows)
    supply = pd.DataFrame(inventory)
    weights = {f"STRESS_{i+1:03d}": float(1.0 + 0.05 * (i % 8))
               for i in range(80)}
    assert len(needs) == 1600 and len(supply) == 20
    assert needs[["site_id", "product", "size"]].drop_duplicates().shape[0] == 1600
    return needs, supply, weights


def prepare_demo() -> dict:
    """Rebuild the exact synthetic application inputs, once per audit run."""
    from src.file_io import load_demo_inputs
    from src.ingest import suggest_header_mapping
    from src.workflow import build_derived_outputs, prepare_input
    from src.forecast_pipeline import build_unified_forecasts
    from src.prediction_bands import add_empirical_plausible_ranges
    from src.allocation_inputs import prepare_allocation_inputs

    print("\n=== A. SAME synthetic Demo Mode pipeline as the app ===", flush=True)
    started = perf_counter()
    raw = load_demo_inputs()
    cleaned = {}
    for kind, frame in raw.items():
        mapping = suggest_header_mapping(frame.columns, kind)
        cleaned[kind] = prepare_input(frame, mapping, kind)
    derived = build_derived_outputs(cleaned)
    weekly = derived.weekly_distribution
    master = derived.site_master
    origin = pd.Timestamp(weekly["week_start"].max()).normalize()
    base = build_unified_forecasts(weekly, master, origin, horizon=4,
                                   allow_undated_survey_for_demo=False)
    banded = add_empirical_plausible_ranges(base["forecasts"], weekly, origin, horizon=4)
    incoming = cleaned.get("incoming_supply")
    prepared = prepare_allocation_inputs(
        banded["forecasts"], cleaned["current_inventory"].cleaning_result.dataframe,
        incoming.cleaning_result.dataframe if incoming else None, master,
        cycle_weeks=4, alpha=0.5, beta=0.25,
        forecast_issues=base["issues"],
    )
    print(f"Demo origin={origin.date()}, partners={prepared['needs']['site_id'].nunique()}, "
          f"site/SKU rows={len(prepared['needs'])}, SKUs={len(prepared['supply'])}", flush=True)
    print(f"Unresolved sites={len(base['issues'])}; flagged cycle series={len(prepared['review_rows'])}", flush=True)
    print(f"Preparing the verified demo pipeline took {perf_counter()-started:.2f}s", flush=True)
    return prepared


def _worker_run():
    """Private one-solve child entrypoint. Payload travels through stdin, not files."""
    try:
        payload = pickle.load(sys.stdin.buffer)
        kind = payload["kind"]
        if kind == "demo":
            from src.allocation_inputs import run_operational_allocation
            prepared = payload["prepared"]
            result = run_operational_allocation(
                prepared, fairness_floor=0.6,
                worst_shortfall_penalty_share=payload["share"],
                time_limit_seconds=8,
            )
            _assert_solution(result, prepared["needs"], prepared["supply"])
            summary = result["operational_summary"]
            assert (summary["ready_now_units"] + summary["awaiting_inbound_units"]
                    == summary["allocated_cycle_units"])
            on_hand = prepared["on_hand"].set_index(["product", "size"])["on_hand_units"]
            picking = (result["ready_now_pick_list"]
                       .groupby(["product", "size"])["ready_now_units"].sum())
            for sku, units in picking.items():
                assert int(units) <= int(on_hand.get(sku, 0)), "Pick exceeds on-hand."
            output = {"metrics": result["metrics"], "baseline": result["baseline_metrics"],
                      "elapsed_seconds": result["elapsed_seconds"], "operational": summary}
        elif kind == "scale":
            from src.allocate import solve_allocation
            needs, supply, weights = payload["needs"], payload["supply"], payload["weights"]
            result = solve_allocation(needs, supply, equity_weights=weights,
                                      fairness_floor=0.6,
                                      worst_shortfall_penalty_share=0.01,
                                      protect_baseline_fill=True,
                                      solver="highs", time_limit_seconds=8)
            _assert_solution(result, needs, supply)
            if result["metrics"]["worst_site_fill_rate"] + 1e-6 < result["baseline_metrics"]["worst_site_fill_rate"]:
                raise AssertionError("Production protection violated baseline fill.")
            if result["certified_mip_gap"] > 1e-5 + 1e-8:
                raise AssertionError("Production HiGHS did not certify MIP gap.")
            output = {"metrics": result["metrics"], "baseline": result["baseline_metrics"],
                      "elapsed_seconds": result["elapsed_seconds"],
                      "solver_backend": result["solver_backend"],
                      "certified_mip_gap": result["certified_mip_gap"],
                      "solver_seconds": result["solver_seconds"],
                      "baseline_fill_protection": result["baseline_fill_protection"]}
        else:
            raise ValueError("Unknown audit worker request.")
        sys.stdout.write(json.dumps(output) + "\n")
        sys.stdout.flush()
    except Exception:
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


def _kill_process_tree(proc: subprocess.Popen):
    """Stop the optimization worker and any descendants after deadline."""
    if proc.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=8, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass
    if proc.poll() is None:
        proc.kill()
    try:
        proc.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        pass


def _guarded_solve(payload: dict, hard_timeout: int) -> tuple[dict | None, str, float]:
    """Independent OS-level timeout; CBC solver's own timeLimit is not sufficient."""
    creation = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    begin = perf_counter()
    proc = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--_worker"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=creation,
    )
    try:
        stdout, stderr = proc.communicate(
            input=pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL),
            timeout=hard_timeout,
        )
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        return None, f"HARD TIMEOUT (>{hard_timeout}s): optimization worker did not return", perf_counter() - begin
    except KeyboardInterrupt:
        _kill_process_tree(proc)
        raise
    elapsed = perf_counter() - begin
    if proc.returncode != 0:
        detail = stderr.decode("utf-8", errors="replace").strip()
        return None, ("WORKER ERROR: " + detail[-1300:]), elapsed
    try:
        return json.loads(stdout.decode("utf-8")), "PASS", elapsed
    except (ValueError, UnicodeDecodeError):
        return None, "WORKER ERROR: invalid JSON result", elapsed


def run_demo_audit(prepared: dict, hard_timeout: int):
    print("\n=== B. MAXIMUM SHORTFALL penalty sensitivity ===", flush=True)
    print("   share | weighted_unmet | vs baseline | worst_site_fill | vs baseline | total_unmet | solver_s")
    records = []
    default = None
    for share in PENALTY_SHARES:
        print(f"Checking penalty={share:.2f} (hard timeout: {hard_timeout}s)...", flush=True)
        output, status, wall = _guarded_solve(
            {"kind": "demo", "prepared": prepared, "share": share}, hard_timeout)
        if output is None:
            print(f"{share:8.2f} | NOT VERIFIED | {status} | worker_wall={wall:.1f}s", flush=True)
            continue
        m, b = output["metrics"], output["baseline"]
        improvement = _pct_change(b["weighted_unmet_units"], m["weighted_unmet_units"])
        worst_delta_pp = 100.0 * (m["worst_site_fill_rate"] - b["worst_site_fill_rate"])
        print(f"{share:8.2f} | {m['weighted_unmet_units']:14,.1f} | "
              f"{_label_ratio(improvement):>11} | {m['worst_site_fill_rate']*100:14.2f}% | "
              f"{worst_delta_pp:+11.2f}pp | {m['total_unmet_units']:11,d} | "
              f"{output['elapsed_seconds']:.3f}", flush=True)
        records.append((share, improvement, worst_delta_pp))
        if share == 0.01:
            default = output
    if default is not None:
        summary = default["operational"]
        print(f"\nDefault: cycle_allocated={summary['allocated_cycle_units']:,}, "
              f"ready_now={summary['ready_now_units']:,}, "
              f"awaiting_inbound={summary['awaiting_inbound_units']:,}")
        print("Verified in child: material balances, floor constraints, "
              "integer units, stock-only pick totals: PASS")
    else:
        print("Default 0.01 setting was not re-verified in this run.")
    both = [share for share, improve, worst in records
            if improve is not None and improve > 0 and worst > 0]
    if both:
        print(f"Measured penalties improving BOTH metrics: {both} (synthetic only).")
    else:
        print("No SUCCESSFULLY SOLVED tested setting improved both metrics. "
              "Timed-out values are unknown, not failures of feasibility.")


def run_scale_audit(prepared: dict, hard_timeout: int):
    print("\n=== C. 80 partners x 20 variants (1,600 decision cells) ===", flush=True)
    needs, supply, weights = build_scale_fixture(prepared)
    print(f"Fixed stress case: sites=80, variants=20, cells={len(needs)}, "
          f"total_need={int(needs['need_units'].sum()):,}; "
          f"available={int(supply['available_units'].sum()):,}", flush=True)
    print(f"Solving in isolated worker (hard limit {hard_timeout}s)...", flush=True)
    output, status, wall = _guarded_solve(
        {"kind": "scale", "needs": needs, "supply": supply, "weights": weights},
        hard_timeout)
    if output is None:
        print(f"GATE 4 SCALE: NOT VERIFIED — {status} (worker wall={wall:.2f}s)")
        print("The <10-second benchmark has NOT been met/proved on this run.")
        return
    solve_time = output["elapsed_seconds"]
    print(f"Production backend={output['solver_backend']} · guard={output['baseline_fill_protection']} · "
          f"certified MIP gap={output['certified_mip_gap']:.2g}")
    print(f"Solver-only: {output['solver_seconds']:.3f}s; solver + comparator: {solve_time:.3f}s; "
          f"isolated worker total: {wall:.3f}s")
    print(f"Weighted unmet: optimized={output['metrics']['weighted_unmet_units']:,.1f}; "
          f"baseline={output['baseline']['weighted_unmet_units']:,.1f}")
    print(f"Worst-site fill: optimized={output['metrics']['worst_site_fill_rate']:.3%}; "
          f"baseline={output['baseline']['worst_site_fill_rate']:.3%}")
    print("GATE 4 SCALE SPEED:", "PASS (<10s)" if solve_time < 10 else "NOT MET (>=10s)")
    print("GATE 4 GUARDED FAIRNESS:", "PASS" if output["metrics"]["worst_site_fill_rate"] + 1e-6 >= output["baseline"]["worst_site_fill_rate"] else "FAIL")


def main():
    if "--_worker" in sys.argv:
        _worker_run()
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--section", choices=("all", "demo", "scale"), default="demo",
                        help="Demo penalty sweep, 80x20 stress case, or both. Default: demo.")
    parser.add_argument("--hard-timeout", type=int, default=18,
                        help="OS wall-time watchdog for each solve, in seconds (default 18).")
    args = parser.parse_args()
    if args.hard_timeout < 10 or args.hard_timeout > 90:
        parser.error("--hard-timeout must be between 10 and 90 seconds")
    print("Gate 4 scientific audit (synthetic data only; nothing saved to disk).", flush=True)
    start = perf_counter()
    prepared = prepare_demo()
    if args.section in {"demo", "all"}:
        run_demo_audit(prepared, args.hard_timeout)
    if args.section in {"scale", "all"}:
        run_scale_audit(prepared, args.hard_timeout)
    print(f"\nAudit wall time: {perf_counter()-start:.2f}s", flush=True)


if __name__ == "__main__":
    main()
