"""Week 3 Gate 3 Forecast page: session-only upload data, no persisted uploads."""

from time import perf_counter

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.forecast_pipeline import build_unified_forecasts
from src.forecast_ui import (
    ForecastUIError,
    backtest_method_table,
    data_signature,
    export_forecasts,
    filter_forecasts,
    network_rollup,
    summary,
)
from src.prediction_bands import add_empirical_plausible_ranges

st.set_page_config(page_title="Forecast | Supply Bank Allocator", page_icon="📈", layout="wide")
st.title("Forecast Demand")
st.caption("Weekly estimated distribution units by partner, product and size. Forecasts are planning estimates, not measured unmet demand.")

derived = st.session_state.get("derived_outputs")
if derived is None:
    st.warning("No cleaned data is ready. Open Upload, load Demo Mode (or your own files), and click Clean & Validate first.")
    st.page_link("pages/1_Upload.py", label="Go to Upload", icon="📤")
    st.stop()

weekly = derived.weekly_distribution
master = derived.site_master
if weekly is None or weekly.empty:
    st.error("The cleaned Distribution Log contains no weekly records.")
    st.stop()

try:
    origin = pd.to_datetime(weekly["week_start"], errors="raise").max().normalize()
    signature = data_signature(weekly, master)
except (ValueError, KeyError, ForecastUIError) as exc:
    st.error(f"The uploaded data cannot be used for forecasting: {exc}")
    st.stop()

st.caption(f"Forecast origin: **{origin.date()}** (last recorded ISO week). Data stays in your current app session.")

with st.form("forecast_parameters", clear_on_submit=False):
    horizon = st.slider("Forecast horizon (weeks)", min_value=4, max_value=8, value=4, step=1)
    demo_optin = st.checkbox(
        "Retrospective synthetic demonstration: explicitly allow an undated survey",
        value=False,
        help="For synthetic examples only. This does not establish that the survey was available on an earlier date.",
    )
    submitted = st.form_submit_button("Generate forecast", type="primary", use_container_width=True)

if submitted:
    started = perf_counter()
    try:
        with st.spinner("Calculating forecasts and plausible ranges..."):
            base = build_unified_forecasts(
                weekly, master, origin, horizon=horizon,
                allow_undated_survey_for_demo=demo_optin,
            )
            banded = add_empirical_plausible_ranges(
                base["forecasts"], weekly, origin, horizon=horizon,
            )
        st.session_state["cp6_forecast_result"] = {
            "signature": signature, "origin": origin, "horizon": horizon,
            "forecasts": banded["forecasts"], "issues": base["issues"],
            "coverage": base["coverage"], "range_coverage": banded["coverage"],
            "seconds": perf_counter() - started, "demo_optin": demo_optin,
        }
    except (ValueError, TypeError, KeyError, RuntimeError) as exc:
        st.session_state.pop("cp6_forecast_result", None)
        st.error(f"Cannot generate a safe forecast. Review your uploads and data quality. Details: {exc}")
        st.stop()

result = st.session_state.get("cp6_forecast_result")
if result is None or result["signature"] != signature:
    st.info("Choose a horizon and click **Generate forecast**. If you loaded new files, generate the forecast again.")
    st.stop()

forecasts = result["forecasts"]
issues = result["issues"]
if forecasts.empty:
    st.warning("There are no forecastable series at this origin. Check the unresolved sites below.")
    if not issues.empty:
        st.dataframe(issues, use_container_width=True, hide_index=True)
    st.stop()

stats = summary(forecasts)
st.success(f"Generated {stats['rows']:,} weekly forecasts covering {stats['sites']} partner sites in {result['seconds']:.2f} seconds (horizon: {result['horizon']} weeks).")
mc = st.columns(4)
mc[0].metric("Forecast rows", f"{stats['rows']:,}")
mc[1].metric("Partner sites", stats["sites"])
mc[2].metric("Rows needing review", stats["review_rows"])
mc[3].metric("Rows with plausible range", stats["range_rows"])

st.info(
    "**Accuracy disclaimer:** The current child-level WAPE remains N/A pending independent backtesting. "
    "Parent WAPE describes the site-total model, not individual product-size accuracy. "
    "The 80% plausible ranges are provisional, not independently validated coverage."
)
if result["demo_optin"]:
    st.warning("Undated survey accepted for a retrospective synthetic demo only; this is not a valid historical accuracy claim.")

st.subheader("Explore forecasts")
fc1, fc2, fc3 = st.columns(3)
site_options = sorted(forecasts["site_id"].astype(str).unique().tolist())
selected_sites = fc1.multiselect("Partner sites", site_options, placeholder="All sites")
site_filtered = filter_forecasts(forecasts, sites=selected_sites)
product_options = sorted(site_filtered["product"].astype(str).unique().tolist())
selected_products = fc2.multiselect("Products", product_options, placeholder="All products")
product_filtered = filter_forecasts(site_filtered, products=selected_products)
variants = sorted(set(zip(product_filtered["product"].astype(str), product_filtered["size"].astype(str))))
selected_variants = fc3.multiselect(
    "Product × size", variants, format_func=lambda v: f"{v[0]} / {v[1]}",
    placeholder="All sizes",
)
visible = filter_forecasts(product_filtered, variants=selected_variants)
if visible.empty:
    st.warning("No forecasts match these filters.")
    st.stop()

st.markdown("#### Network roll-up by product and size")
rollup = network_rollup(visible)
rollup["variant"] = rollup["product"].astype(str) + " / " + rollup["size"].astype(str)
chart = px.line(rollup, x="week_start", y="forecast_units", color="variant", markers=True,
                labels={"week_start": "Forecast week", "forecast_units": "Forecast units", "variant": "Product / Size"})
chart.update_layout(legend_title_text="Product / Size", hovermode="x unified")
st.plotly_chart(chart, use_container_width=True)
st.caption("Roll-up sums point forecasts only. It is not a calibrated network prediction band.")

st.markdown("#### Individual series")
series_options = sorted(set(zip(visible["site_id"], visible["product"], visible["size"])))
chosen = st.selectbox("Choose a partner / product / size", series_options,
                      format_func=lambda k: f"{k[0]} · {k[1]} · {k[2]}")
detail = visible.loc[
    visible["site_id"].eq(chosen[0]) & visible["product"].eq(chosen[1])
    & visible["size"].eq(chosen[2])
].sort_values("week_start")
first = detail.iloc[0]
parent_wape = first["parent_wape_pct"]
child_wape = first["wape_pct"]
mc2 = st.columns(3)
mc2[0].metric("Selected method", str(first["method"]))
mc2[1].metric("Site-total backtest WAPE", f"{parent_wape:.1f}%" if pd.notna(parent_wape) else "N/A")
mc2[2].metric("Product-size backtest WAPE", f"{child_wape:.1f}%" if pd.notna(child_wape) else "N/A")
if pd.isna(child_wape):
    st.caption(f"Product-size WAPE: N/A — {first['wape_reason']}. Site-total WAPE must not be reused here.")
if detail["requires_review"].fillna(False).any():
    flags = sorted(set(v for v in detail["quality_flags"].dropna().astype(str) if v))
    st.warning("This series needs review. Flags: " + "; ".join(flags) + ". A zero forecast is not proof of zero need.")

fig = go.Figure()
if detail["lower_units"].notna().all() and detail["upper_units"].notna().all():
    fig.add_trace(go.Scatter(x=detail["week_start"], y=detail["upper_units"], mode="lines",
                             line={"width": 0}, showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=detail["week_start"], y=detail["lower_units"], mode="lines",
                             line={"width": 0}, fill="tonexty", name="Provisional 80% plausible range",
                             fillcolor="rgba(31,119,180,0.16)"))
fig.add_trace(go.Scatter(x=detail["week_start"], y=detail["forecast_units"],
                         mode="lines+markers", name="Point forecast"))
fig.update_layout(xaxis_title="Week", yaxis_title="Individual units", hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

with st.expander("How was this forecast calculated?"):
    st.write("Method:", first["method"])
    st.write("Forecast source:", first["forecast_source"])
    st.write("Hierarchy:", first.get("hierarchy", "N/A"))
    st.write("Mix source:", first.get("mix_source", "N/A"))
    st.write("Range status:", first.get("range_reason", "N/A"))
    st.write("Forecasts represent historical distributions or survey-informed proxies, not necessarily unconstrained true demand.")

st.markdown("#### Forecast table and downloads")
show_cols = ["site_id", "product", "size", "week_start", "forecast_units",
             "lower_units", "upper_units", "method", "wape_pct", "wape_reason",
             "parent_wape_pct", "forecast_source", "requires_review", "quality_flags"]
st.dataframe(visible[[c for c in show_cols if c in visible.columns]], use_container_width=True, hide_index=True)

csv_col, excel_col = st.columns(2)
csv_col.download_button("Download filtered forecasts (CSV)", export_forecasts(visible, "csv"),
                        file_name="supply_bank_forecast.csv", mime="text/csv", use_container_width=True)
excel_col.download_button("Download filtered forecasts (XLSX)", export_forecasts(visible, "xlsx"),
                          file_name="supply_bank_forecast.xlsx",
                          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

with st.expander("Site-level backtest method report (provisional)"):
    st.caption("These are site-total historical backtest WAPEs, not child-level errors or independent Gate 3 accuracy.")
    methods = backtest_method_table(forecasts)
    st.dataframe(methods, use_container_width=True, hide_index=True)
    st.download_button("Download site-level method report (CSV)",
                       methods.to_csv(index=False).encode("utf-8-sig"),
                       file_name="site_method_report_provisional.csv", mime="text/csv")

if not issues.empty:
    st.warning(f"{issues['site_id'].nunique()} sites have unresolved forecasting issues. Do not interpret missing output as zero demand.")
    with st.expander("Unresolved sites and reasons", expanded=True):
        st.dataframe(issues, use_container_width=True, hide_index=True)

st.caption("Gate 3 remains in progress until independent network WAPE and runtime acceptance are verified.")
