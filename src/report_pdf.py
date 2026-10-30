"""Gate 6B: deterministic, in-memory US-Letter PDF for Gate 6A report data.

No database, external calls, headless browser, static image renderer or repeated
forecast/optimization is involved. A size-gap chart uses PDF vector primitives
so the public Streamlit deployment does not require Chrome/Kaleido for reports.
"""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
import math
import numbers
import unicodedata

from fpdf import FPDF
import pandas as pd
from PIL import Image, UnidentifiedImageError

from src.report import ReportError

PAGE_W, PAGE_H = 612, 792  # Letter in points
MARGIN = 34
NAVY = (25, 43, 66)
INK = (30, 46, 61)
MUTED = (91, 106, 119)
TEAL = (24, 119, 129)
PALE = (238, 246, 246)
HAIR = (217, 226, 230)
WHITE = (255, 255, 255)


def _ascii(value: object) -> str:
    """Render text safely in core PDF fonts, without silent character loss.

    The report is English-language. Names with unmappable characters must be
    entered using supported Latin text until a bundled Unicode font is added.
    """
    if value is None:
        return ""
    s = str(value).replace("\u2013", "-").replace("\u2014", "-").replace("\u2019", "'")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    try:
        s.encode("cp1252", "strict")
    except UnicodeEncodeError as exc:
        raise ReportError("PDF text contains unsupported characters. Use a Latin-character bank name or remove unsupported symbols.") from exc
    return s


def _short(pdf: FPDF, text: object, max_width: float, *, font: str = "Helvetica", style: str = "", size: float = 9.0) -> str:
    msg = _ascii(text)
    pdf.set_font(font, style=style, size=size)
    if pdf.get_string_width(msg) <= max_width:
        return msg
    while msg and pdf.get_string_width(msg + "...") > max_width:
        msg = msg[:-1]
    return msg.rstrip() + "..."


def _fmt(n: int | float) -> str:
    if not isinstance(n, numbers.Real) or not math.isfinite(float(n)):
        raise ReportError("Report contains invalid numeric metrics.")
    return f"{n:,.0f}"


def _date(value: object) -> str:
    try:
        ts = pd.Timestamp(value)
        if pd.isna(ts):
            raise ValueError("NaT")
        return ts.strftime("%b %d, %Y")
    except (TypeError, ValueError) as exc:
        raise ReportError("Report contains an invalid reporting date.") from exc


def _validate(report: dict) -> None:
    if not isinstance(report, dict):
        raise ReportError("First calculate a valid Gate 6A report.")
    schema = {
        "periods": ["historical_start", "historical_end", "forecast_start", "forecast_end", "forecast_weeks", "inventory_as_of"],
        "observed": ["units_distributed", "partners_with_distributions", "record_count", "reported_household_service_count_sum", "reported_child_service_count_sum"],
        "planning": ["need_units", "allocated_units", "modeled_unmet_units", "supply_gap_units", "unresolved_forecast_sites"],
        "equity": ["planned_high_need_share_of_all_allocations_pct", "classification_coverage_of_allocations_pct", "classified_high_need_partners"],
        "pricing": ["fully_costed_ask_usd", "partially_costed_usd", "all_prices_verified_quotes", "sku_gaps"],
    }
    for key, fields in schema.items():
        if not isinstance(report.get(key), dict) or any(k not in report[key] for k in fields):
            raise ReportError(f"Missing trusted report section: {key}.")
    if report["periods"]["forecast_weeks"] != 8:
        raise ReportError("A one-page funder report requires exactly eight forecast weeks.")
    for sec, fields in (("observed", ("units_distributed", "partners_with_distributions", "record_count")),
                        ("planning", ("need_units", "allocated_units", "modeled_unmet_units", "supply_gap_units", "unresolved_forecast_sites"))):
        for field in fields:
            val = report[sec][field]
            if not isinstance(val, (int, float)) or not math.isfinite(float(val)) or val < 0:
                raise ReportError(f"Invalid {field} value in report.")
    plan = report["planning"]
    if plan["allocated_units"] + plan["modeled_unmet_units"] != plan["need_units"]:
        raise ReportError("Report planning totals do not reconcile.")
    for metric in ("planned_high_need_share_of_all_allocations_pct", "classification_coverage_of_allocations_pct"):
        val = report["equity"][metric]
        if val is not None and (not isinstance(val, (int,float)) or not math.isfinite(float(val)) or not 0 <= val <= 100):
            raise ReportError("Invalid equity coverage percentage.")
    gap = report.get("ask_by_sku")
    if not isinstance(gap, pd.DataFrame) or not {"product", "size", "supply_gap_units", "estimated_cost_usd", "price_basis"}.issubset(gap.columns):
        raise ReportError("Missing validated size-gap request table.")
    if gap[["product", "size"]].isna().any().any() or gap.duplicated(["product", "size"]).any():
        raise ReportError("Invalid size-gap identifiers.")
    quantities = pd.to_numeric(gap["supply_gap_units"], errors="coerce")
    if quantities.isna().any() or not quantities.ge(0).all() or not (quantities % 1 == 0).all():
        raise ReportError("Invalid size-gap request quantities.")
    if int(quantities.sum()) != plan["supply_gap_units"]:
        raise ReportError("PDF size-gap units do not reconcile with the validated report.")


def _logo_image(upload: bytes | None) -> BytesIO | None:
    if upload is None:
        return None
    if not isinstance(upload, bytes) or len(upload) > 2_000_000:
        raise ReportError("Logo must be a PNG or JPEG under 2 MB.")
    try:
        stream = BytesIO(upload)
        with Image.open(stream) as im:
            if im.format not in {"PNG", "JPEG"} or im.width > 1600 or im.height > 1600:
                raise ReportError("Logo must be PNG/JPEG and at most 1600 pixels per side.")
            im.verify()
        stream.seek(0)
        return stream
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ReportError("Logo could not be read as a valid PNG/JPEG.") from exc


def _text(pdf: FPDF, x: float, y: float, val: object, *, size: float = 9, style: str = "", color=INK, max_w: float | None = None):
    msg = _ascii(val)
    if max_w is not None:
        msg = _short(pdf, msg, max_w, size=size, style=style)
    pdf.set_font("Helvetica", style=style, size=size)
    pdf.set_text_color(*color)
    pdf.text(x, y, msg)


def _panel(pdf: FPDF, x: float, y: float, w: float, h: float, color=PALE):
    pdf.set_fill_color(*color)
    pdf.rect(x, y, w, h, style="F")


def _kpi(pdf: FPDF, x: float, y: float, w: float, label: str, number: int, subline: str):
    _panel(pdf, x, y, w, 56)
    _text(pdf, x+9, y+13, label.upper(), size=7.2, style="B", color=MUTED, max_w=w-17)
    _text(pdf, x+9, y+36, _fmt(number), size=17, style="B", color=NAVY, max_w=w-17)
    _text(pdf, x+9, y+48, subline, size=6.4, color=MUTED, max_w=w-17)


def _chart(pdf: FPDF, rows: pd.DataFrame, x: float, y: float, w: float, h: float):
    """Vector size-gap chart; no Chromium, plotly-to-PNG or font dependencies."""
    _panel(pdf, x, y, w, h, color=(248, 250, 251))
    _text(pdf, x+10, y+16, "LARGEST SIZE SUPPLY GAPS", size=9, style="B", color=NAVY)
    if rows.empty:
        _text(pdf, x+12, y+57, "No modeled supply gaps for this planning period.", size=8, color=MUTED, max_w=w-22)
        return
    order = rows.sort_values(["supply_gap_units", "product", "size"], ascending=[False, True, True])
    top = order.head(6)
    more = order.iloc[6:]
    # Remaining SKUs are mentioned below but deliberately NOT drawn as one
    # giant bar: such a bar would overwhelm and visually misrank each SKU.
    bars = [(f"{r.product}:{r.size}", int(r.supply_gap_units)) for r in top.itertuples(index=False)]
    maximum = max(v for _, v in bars) or 1
    row_h = 19
    first_y = y+35
    label_w = 106
    bar_w = w - label_w - 93
    for i, (label, count) in enumerate(bars):
        yy = first_y + i*row_h
        _text(pdf, x+10, yy+9, label, size=7.4, max_w=label_w-7)
        _panel(pdf, x+label_w+8, yy, bar_w, 10, color=(226, 236, 238))
        fill = max(0.0, bar_w*count/maximum)
        if fill > 0:
            _panel(pdf, x+label_w+8, yy, fill, 10, color=TEAL)
        _text(pdf, x+w-63, yy+9, _fmt(count), size=7.4, color=INK, max_w=56)
    note = (f"{len(more)} other SKUs: {_fmt(int(more.supply_gap_units.sum()))} units. " if len(more) else "")
    _text(pdf, x+10, y+h-9, note + "All amounts are modeled, not measured need.", size=6.3, color=MUTED, max_w=w-20)


def _price_label(row) -> str:
    amount = row.estimated_cost_usd
    if pd.isna(amount):
        return "Not priced"
    return f"${float(amount):,.2f}"


def render_funder_pdf(report: dict, *, bank_name: str = "Supply Bank", logo: bytes | None = None,
                      generated_on: date | datetime | None = None) -> bytes:
    """Render the validated report as in-memory PDF bytes (never write uploads to disk)."""
    _validate(report)
    clean_name = _ascii(bank_name).strip()
    if not clean_name or len(clean_name) > 120:
        raise ReportError("Enter a bank name between 1 and 120 characters.")
    if generated_on is None:
        generated_on = date.today()
    if not isinstance(generated_on, (date, datetime)):
        raise ReportError("The report generation date must be a date.")
    logo_stream = _logo_image(logo)
    pdf = FPDF(orientation="P", unit="pt", format="Letter")
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    pdf.set_title("Eight-week supply bank funder planning report")
    pdf.set_author("ChiEAC Diaper & Period Supply Bank Allocator")
    pdf.add_page()
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, PAGE_W, 84, style="F")
    if logo_stream is not None:
        pdf.image(logo_stream, x=PAGE_W-102, y=20, w=62, h=41, keep_aspect_ratio=True)
    _text(pdf, MARGIN, 27, "CHIEAC  /  SUPPLY PLANNING", size=8, style="B", color=(179, 223, 225))
    max_header_w = PAGE_W-MARGIN*2-(84 if logo_stream else 0)
    _text(pdf, MARGIN, 53, clean_name, size=17.5, style="B", color=WHITE, max_w=max_header_w)
    _text(pdf, MARGIN, 70, "8-WEEK FUNDER PLANNING SNAPSHOT", size=8.7, color=WHITE)

    period = report["periods"]
    _text(pdf, MARGIN, 104, f"Observed distributions: {_date(period['historical_start'])} - {_date(period['historical_end'])}", size=8.2, color=INK)
    _text(pdf, MARGIN, 118, f"Modeled planning: {_date(period['forecast_start'])} - {_date(period['forecast_end'])}  |  On-hand snapshot: {_date(period['inventory_as_of'])}", size=8.2, color=MUTED)

    obs, plan, eq, pricing = report["observed"], report["planning"], report["equity"], report["pricing"]
    w = (PAGE_W-2*MARGIN-3*8)/4
    for i, (lab, val, sub) in enumerate([
        ("Distributed", obs["units_distributed"], "Observed 8 weeks"),
        ("Partners served", obs["partners_with_distributions"], "Observed in log"),
        ("Planning shortfall", plan["modeled_unmet_units"], "Modeled, not measured"),
        ("SKU supply gap", plan["supply_gap_units"], "Potential size-based ask"),
    ]):
        _kpi(pdf, MARGIN+i*(w+8), 134, w, lab, val, sub)

    households = obs["reported_household_service_count_sum"]
    children = obs["reported_child_service_count_sum"]
    parts = [f"Recorded household service-count entries: {_fmt(households)}" if households is not None else "Household service counts: unavailable",
             f"Child service-count entries: {_fmt(children)}" if children is not None else "Child service counts: unavailable"]
    _text(pdf, MARGIN, 207, "  |  ".join(parts), size=7.5, color=MUTED, max_w=PAGE_W-2*MARGIN)
    _text(pdf, MARGIN, 219, "Service counts are recorded entries, NOT deduplicated unique families or children.", size=7.1, color=MUTED)

    left_w = 333
    _chart(pdf, report["ask_by_sku"], MARGIN, 233, left_w, 164)
    rx = MARGIN + left_w + 9
    rw = PAGE_W - MARGIN-rx
    _panel(pdf, rx, 233, rw, 164)
    _text(pdf, rx+10, 250, "EQUITY COVERAGE", size=9.1, style="B", color=NAVY)
    share = eq["planned_high_need_share_of_all_allocations_pct"]
    cov = eq["classification_coverage_of_allocations_pct"]
    _text(pdf, rx+10, 278, "N/A" if share is None else f"{share:.1f}%", size=19, style="B", color=TEAL)
    _text(pdf, rx+10, 290, "Modeled units allocated to", size=7.3, color=MUTED)
    _text(pdf, rx+10, 301, "classified high-need partners", size=7.3, color=MUTED)
    _text(pdf, rx+10, 325, "Classification coverage", size=7.1, style="B", color=NAVY)
    _text(pdf, rx+10, 340, "N/A" if cov is None else f"{cov:.1f}% of modeled allocated units", size=7.5, color=MUTED, max_w=rw-20)
    _text(pdf, rx+10, 365, f"High-need partners: {eq['classified_high_need_partners']}", size=7.3, color=INK)
    _text(pdf, rx+10, 384, "Planned, not actual delivery", size=6.6, color=MUTED)

    _text(pdf, MARGIN, 421, "SPECIFIC SUPPLY REQUEST BY PRODUCT / SIZE", size=10.2, style="B", color=NAVY)
    if pricing["sku_gaps"] == 0:
        subtitle = "No positive SKU gaps in the current eight-week planning model."
    elif pricing["fully_costed_ask_usd"] is not None:
        subtitle = f"Potential ask: {_fmt(plan['supply_gap_units'])} units  |  Estimated cost: ${pricing['fully_costed_ask_usd']:,.2f}"
    else:
        subtitle = f"Potential ask: {_fmt(plan['supply_gap_units'])} units  |  Dollar total unavailable: some unit prices missing"
    _text(pdf, MARGIN, 436, subtitle, size=8.3, color=TEAL, max_w=PAGE_W-2*MARGIN)

    pdf.set_fill_color(*NAVY)
    pdf.rect(MARGIN, 446, PAGE_W-2*MARGIN, 19, "F")
    _text(pdf, MARGIN+8, 459, "PRODUCT / SIZE", size=7.6, style="B", color=WHITE)
    _text(pdf, MARGIN+264, 459, "UNITS", size=7.6, style="B", color=WHITE)
    _text(pdf, MARGIN+346, 459, "COST ESTIMATE", size=7.6, style="B", color=WHITE)
    _text(pdf, MARGIN+458, 459, "BASIS", size=7.6, style="B", color=WHITE)
    requests = report["ask_by_sku"].sort_values(
        ["supply_gap_units", "product", "size"], ascending=[False, True, True]
    )
    # Eight rows plus a complete, disclosed 'remaining sizes' aggregate; the
    # Report UI exposes a full untruncated CSV for per-SKU review.
    visible = requests.head(8)
    remainder = requests.iloc[8:]
    y0, rh = 465, 15
    for j, row in enumerate(visible.itertuples(index=False)):
        yy = y0+j*rh
        if j % 2 == 0:
            _panel(pdf, MARGIN, yy, PAGE_W-2*MARGIN, rh, (248, 250, 251))
        _text(pdf, MARGIN+8, yy+10.8, f"{row.product} / {row.size}", size=7.4, max_w=247)
        _text(pdf, MARGIN+264, yy+10.8, _fmt(row.supply_gap_units), size=7.4)
        _text(pdf, MARGIN+346, yy+10.8, _price_label(row), size=7.4, max_w=104)
        basis = "Quote" if row.price_basis=="verified_quote" else "Assumed" if row.price_basis=="scenario_assumption" else "Missing"
        _text(pdf, MARGIN+458, yy+10.8, basis, size=7.2, max_w=70)
    shown_count = len(visible)
    if len(remainder):
        yy = y0+shown_count*rh
        _panel(pdf, MARGIN, yy, PAGE_W-2*MARGIN, rh, (236, 245, 246))
        _text(pdf, MARGIN+8, yy+10.8, f"Other {len(remainder)} product-size gaps (see full CSV)", size=7.2, style="B", max_w=247)
        _text(pdf, MARGIN+264, yy+10.8, _fmt(remainder["supply_gap_units"].sum()), size=7.4, style="B")
        _text(pdf, MARGIN+346, yy+10.8, "Mixed / see CSV", size=7.1)
    table_end = y0 + (shown_count+bool(len(remainder)))*rh
    if shown_count == 0:
        _text(pdf, MARGIN+8, 483, "No size-specific funding request for this period.", size=8.1, color=MUTED)
        table_end = 496
    footer_y = max(637, table_end+12)
    if footer_y > 666:
        raise ReportError("PDF rows exceed the safe one-page report area.")
    _text(pdf, MARGIN, footer_y, "COST BASIS / LIMITATIONS", size=8.6, style="B", color=NAVY)
    if pricing["sku_gaps"] and pricing["fully_costed_ask_usd"] is None:
        line1 = f"Only {pricing['priced_sku_gaps']}/{pricing['sku_gaps']} requested sizes priced; priced subtotal ${pricing['partially_costed_usd']:,.2f}. Total unknown."
    elif pricing["sku_gaps"] and not pricing["all_prices_verified_quotes"]:
        line1 = "Unit costs include scenario assumptions; estimates are not verified supplier quotations."
    elif pricing["sku_gaps"]:
        line1 = "Unit costs marked as supplier quotes; quantities are planning estimates, not approved purchases."
    else:
        line1 = "No funding shortfall calculated from verified available product-size balances."
    _text(pdf, MARGIN, footer_y+14, line1, size=7.4, color=MUTED, max_w=PAGE_W-2*MARGIN)
    _text(pdf, MARGIN, footer_y+28,
          "Model: eight-week forecast of historical distribution patterns; integer allocation with fairness and confirmed-cycle supply.",
          size=7.1, color=MUTED, max_w=PAGE_W-2*MARGIN)
    _text(pdf, MARGIN, footer_y+40,
          "Unmet planning units are NOT independently measured community need. Incoming confirmed units may arrive after distribution day.",
          size=7.1, color=MUTED, max_w=PAGE_W-2*MARGIN)
    if plan["unresolved_forecast_sites"]:
        _text(pdf, MARGIN, footer_y+52,
              f"REVIEW: {plan['unresolved_forecast_sites']} partner forecast(s) unresolved; modeled network coverage is incomplete.",
              size=7.4, color=(160, 81, 35), max_w=PAGE_W-2*MARGIN)
    elif plan.get("review_flagged_sku_site_rows", 0):
        _text(pdf, MARGIN, footer_y+52,
              f"REVIEW: {plan['review_flagged_sku_site_rows']} provisional partner/product-size forecast(s) flagged in planning.",
              size=7.4, color=(160, 81, 35), max_w=PAGE_W-2*MARGIN)
    if report.get("warnings"):
        _text(pdf, MARGIN, footer_y+64,
              f"Data quality: {len(report['warnings'])} caution(s); review full details in the application before sending.",
              size=7.0, color=MUTED, max_w=PAGE_W-2*MARGIN)

    pdf.set_draw_color(*HAIR)
    pdf.line(MARGIN, 745, PAGE_W-MARGIN, 745)
    _text(pdf, MARGIN, 762, f"Generated {_date(generated_on)}  |  ChiEAC planning tool  |  Not a purchase authorization", size=7.3, color=MUTED)
    _text(pdf, PAGE_W-62, 762, "1 / 1", size=7.3, color=MUTED)
    if pdf.page_no() != 1:
        raise ReportError("Funder report did not fit on one US Letter page.")
    output = bytes(pdf.output())
    if not output.startswith(b"%PDF"):
        raise ReportError("PDF generation failed.")
    return output
