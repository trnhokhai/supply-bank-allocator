"""Week 3 CP6: presentation helpers for the Forecast page.

These functions never fit or select forecasting models. They filter, summarize,
and export the canonical output produced by CP5C + CP5D.
"""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from typing import Iterable

import numpy as np
import pandas as pd

FORECAST_KEYS = ["site_id", "product", "size", "week_start"]
REQUIRED = set(FORECAST_KEYS + [
    "forecast_units", "method", "wape_pct", "wape_reason", "parent_wape_pct",
    "lower_units", "upper_units", "quality_flags", "requires_review",
    "forecast_source",
])


class ForecastUIError(ValueError):
    """The Forecast view received an invalid output table."""


def data_signature(weekly: pd.DataFrame, master: pd.DataFrame) -> str:
    """Detect new uploaded/cleaned inputs without depending on file names."""
    if not isinstance(weekly, pd.DataFrame) or not isinstance(master, pd.DataFrame):
        raise ForecastUIError("Expected data tables for upload fingerprint.")
    digest = sha256()
    for frame in (weekly, master):
        digest.update(frame.to_json(
            orient="split", date_format="iso", default_handler=str
        ).encode("utf-8"))
    return digest.hexdigest()


def validate_forecast_table(forecasts: pd.DataFrame) -> None:
    if not isinstance(forecasts, pd.DataFrame):
        raise ForecastUIError("Forecast results must be a pandas table.")
    missing = REQUIRED - set(forecasts.columns)
    if missing:
        raise ForecastUIError(f"Forecast results are missing: {sorted(missing)}")
    if forecasts.empty:
        return
    if forecasts[FORECAST_KEYS].isna().any().any():
        raise ForecastUIError("Forecast results contain missing identifiers.")
    if forecasts.duplicated(FORECAST_KEYS).any():
        raise ForecastUIError("Duplicate site/product/size/week forecast keys.")
    numeric = pd.to_numeric(forecasts["forecast_units"], errors="coerce")
    if numeric.isna().any() or not np.isfinite(numeric.to_numpy(dtype=float)).all() or numeric.lt(0).any():
        raise ForecastUIError("Forecast quantities must be finite and nonnegative.")


def filter_forecasts(
    forecasts: pd.DataFrame,
    sites: Iterable[str] = (),
    products: Iterable[str] = (),
    variants: Iterable[tuple[str, str]] = (),
) -> pd.DataFrame:
    """Empty filter means all; variants are canonical (product, size) pairs."""
    validate_forecast_table(forecasts)
    result = forecasts.copy()
    if sites:
        result = result.loc[result["site_id"].isin(list(sites))]
    if products:
        result = result.loc[result["product"].isin(list(products))]
    if variants:
        allowed = {tuple(v) for v in variants}
        selector = [tuple(v) in allowed for v in zip(result["product"], result["size"])]
        result = result.loc[selector]
    return result.reset_index(drop=True)


def network_rollup(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Sum point forecasts ONLY: summed child ranges are not calibrated bands."""
    validate_forecast_table(forecasts)
    columns = ["week_start", "product", "size", "forecast_units"]
    if forecasts.empty:
        return pd.DataFrame(columns=columns)
    result = (
        forecasts.groupby(["week_start", "product", "size"], as_index=False,
                          dropna=False)["forecast_units"]
        .sum().sort_values(["product", "size", "week_start"])
    )
    return result.reset_index(drop=True)


def backtest_method_table(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Site-level parent metrics only, not fabricated product-size WAPE."""
    validate_forecast_table(forecasts)
    columns = ["site_id", "method", "parent_wape_pct", "forecast_source"]
    if forecasts.empty:
        return pd.DataFrame(columns=columns)
    records = forecasts[columns].drop_duplicates()
    # Per-site source and error should be stable across future weeks/children.
    if records["site_id"].duplicated().any():
        raise ForecastUIError("A site has conflicting method/accuracy metadata.")
    return records.sort_values("site_id").reset_index(drop=True)


def summary(forecasts: pd.DataFrame) -> dict:
    validate_forecast_table(forecasts)
    return {
        "rows": int(len(forecasts)),
        "sites": int(forecasts["site_id"].nunique()),
        "variants": int(forecasts[["product", "size"]].drop_duplicates().shape[0]),
        "review_rows": int(forecasts["requires_review"].fillna(False).astype(bool).sum()),
        "range_rows": int(forecasts["lower_units"].notna().sum()),
    }


def _spreadsheet_safe(frame: pd.DataFrame) -> pd.DataFrame:
    """Neutralize spreadsheet-formula prefixes in untrusted text fields."""
    result = frame.copy()
    for col in result.select_dtypes(include=["object", "string"]).columns:
        result[col] = result[col].map(
            lambda x: "'" + x if isinstance(x, str) and x.lstrip().startswith(("=", "+", "-", "@")) else x
        )
    return result


def export_forecasts(forecasts: pd.DataFrame, format: str) -> bytes:
    """In-memory download; never stores partner uploads on disk."""
    validate_forecast_table(forecasts)
    if format not in {"csv", "xlsx"}:
        raise ForecastUIError("Export format must be csv or xlsx.")
    data = _spreadsheet_safe(forecasts)
    if format == "csv":
        return data.to_csv(index=False, na_rep="N/A").encode("utf-8-sig")
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl", datetime_format="yyyy-mm-dd") as writer:
        data.to_excel(writer, index=False, sheet_name="Forecasts", na_rep="N/A")
    return buffer.getvalue()
