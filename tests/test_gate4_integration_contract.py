"""Gate 4 closeout: catch UI/backend keyword drift and validate exported plan bytes.

This is a light source contract check, not a substitute for an interactive
Streamlit smoke test. It would have caught the protect_baseline_fill error.
"""

import ast
from io import BytesIO
import inspect
from pathlib import Path

import pandas as pd
import pytest

from src.allocation_inputs import prepare_allocation_inputs, run_operational_allocation
from src.allocation_ui import csv_download, partner_summary

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_allocation_page_calls_backend_with_supported_keywords():
    module = ast.parse((PROJECT_ROOT / "pages" / "3_Allocate.py").read_text(encoding="utf-8-sig"))
    calls = [node for node in ast.walk(module)
             if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name)
             and node.func.id == "run_operational_allocation"]
    assert len(calls) == 1, "Allocation page must have exactly one reviewed backend call."
    assert not any(kw.arg is None for kw in calls[0].keywords), "Do not hide keywords behind **kwargs."
    ui_keywords = {kw.arg for kw in calls[0].keywords}
    backend = inspect.signature(run_operational_allocation)
    assert ui_keywords.issubset(backend.parameters), (
        f"UI supplies unsupported backend parameters: {ui_keywords - set(backend.parameters)}"
    )
    assert "protect_baseline_fill" in ui_keywords
    assert backend.parameters["protect_baseline_fill"].default is True


def _minimal_operational_inputs():
    mondays = pd.date_range("2026-09-28", periods=4, freq="W-MON")
    forecast = pd.DataFrame([
        {"site_id": site, "product": "diaper", "size": "5", "week_start": monday,
         "origin_week": pd.Timestamp("2026-09-21"), "forecast_units": 25.0,
         "requires_review": False, "quality_flags": ""}
        for site in ("A", "B") for monday in mondays
    ])
    inventory = pd.DataFrame([
        {"as_of_date": "2026-09-21", "product": "diaper", "size": "5",
         "quantity_on_hand": 100, "location": "Main"}
    ])
    inbound = pd.DataFrame([
        {"expected_date": "2026-10-02", "product": "diaper", "size": "5",
         "quantity": 40, "status": "confirmed"}
    ])
    site_master = pd.DataFrame([
        {"site_id": "A", "site_name": "Alpha Pantry",
         "poverty_share_band": "over_75_percent", "priority_population_flags": "students"},
        {"site_id": "B", "site_name": "Beta Pantry",
         "poverty_share_band": "under_25_percent", "priority_population_flags": ""},
    ])
    return prepare_allocation_inputs(forecast, inventory, inbound, site_master)


def test_operational_protection_flag_and_download_round_trip():
    prepared = _minimal_operational_inputs()
    result = run_operational_allocation(prepared, protect_baseline_fill=True)
    assert result["baseline_fill_protection"] is True
    assert result["metrics"]["worst_site_fill_rate"] + 1e-6 >= result["baseline_metrics"]["worst_site_fill_rate"]
    assert result["operational_summary"]["allocated_cycle_units"] == 140
    assert result["operational_summary"]["ready_now_units"] == 100
    assert result["operational_summary"]["awaiting_inbound_units"] == 40

    # These are exactly the tables the UI offers for downloading.
    for table in (result["allocation"], partner_summary(result["allocation"]), result["ready_now_pick_list"]):
        exported = csv_download(table)
        assert exported.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM for Excel
        opened = pd.read_csv(BytesIO(exported))
        assert len(opened) == len(table)
        assert list(opened.columns) == list(table.columns)
    pick = pd.read_csv(BytesIO(csv_download(result["ready_now_pick_list"])))
    assert int(pick["ready_now_units"].sum()) == 100
    assert set(pick["site_name"]) == {"Alpha Pantry", "Beta Pantry"}


def test_protection_opt_out_remains_available():
    prepared = _minimal_operational_inputs()
    result = run_operational_allocation(prepared, protect_baseline_fill=False)
    assert result["baseline_fill_protection"] is False
    assert result["operational_summary"]["ready_now_units"] <= 100
