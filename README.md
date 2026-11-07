# Diaper & Period Supply Bank Allocator

**Forecast distributions · Balance inventory · Allocate essential supplies more fairly.**

Free, open-source **decision-support software** built as part of the Chicago Education Advocacy Cooperative (ChiEAC) Fellowship. This project helps supply banks analyze product-size mismatches, forecast recorded distribution patterns, compare allocation plans, run what-if scenarios, and generate an eight-week, one-page funder planning PDF.

> **Not a substitute for verified operational data.** Forecasted distribution proxies are not measured unconstrained community demand. Modeled unmet need, SKU supply gaps and hypothetical purchases are different concepts. Results must be reviewed before procurement or distribution decisions.

## Quick start

Use Python **3.13** to match the development environment.

```bash
python -m venv .venv
# Activate the environment for your operating system
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open **Upload**, enable **Demo Mode**, click **Clean & Validate**, then navigate to Forecast. For the funder PDF, use an **8-week forecast and an 8-week allocation** first; the Report page will not silently extrapolate a 4-week plan.

The Demo Mode datasets are synthetic. CSV/XLSX uploads also support column mapping and validation; partner survey records can be added through the built-in form or imported from Google Forms CSV. See `docs/data_dictionary.md`, `docs/methods.md`, and `docs/partner_survey_spec.md` for the source contracts and caveats.

## Guides for nonprofit staff

- [Practical User Guide with genuine synthetic-app screenshots](docs/user_guide.md) - first-run workflow, how to read results, safe operational review and common errors.
- [Free Nonprofit Onboarding Checklist](docs/onboarding_checklist.md) - source-data readiness, a 60-minute training outline and review/sign-off worksheet.
- [Data Dictionary](docs/data_dictionary.md), [Partner Survey Specification](docs/partner_survey_spec.md) and [Methods Note](docs/methods.md) - exact input fields, survey choices and analytical limits.

Shareable Word and PDF versions of the first two guides are maintained separately as handoff artifacts; these Markdown files are the version-controlled text reference. All pictured data are synthetic or intentionally fictitious. They are **not** evidence of field implementation.

## Features

- **Upload**: clean, validate and reconcile distribution logs, inventory snapshots, incoming supply and optional partner surveys.
- **Forecast**: historical hierarchy, peer-calibrated survey cold starts, quality flags and provisional plausible ranges.
- **Allocate**: equity-aware integer planning, proportional comparison, and physical on-hand versus confirmed-inbound separation.
- **Alerts**: weeks-of-supply, size mismatches and provisional SKU supply gaps.
- **Scenarios**: donations, size mixes, hypothetical new partners and budgeted purchasing; scenarios never authorize physical picking or purchasing.
- **Report**: eight-week, one-page US Letter funder planning PDF and full SKU CSV, with provenance and unpriced cost disclosure.
- **Survey**: organisation-level form and Google Forms CSV import (active session only).

Blank CSV input templates are available for download on the home page.

## Privacy and limitations

This application handles uploads in the active Streamlit server session. Its code does **not intentionally save uploaded partner data to a permanent database**. If deployed publicly, uploaded files are sent to the server operated by the hosting service; do not assume public cloud hosting is suitable for confidential partner information. **Do not upload individual client records, client names, home addresses, medical details, immigration status or other sensitive records.** Export any needed survey data before the session ends. No real-world data validation, vendor pricing verification or supply-bank operating approval is implied by the synthetic demonstration.

## Optional report branding configuration

A nonprofit maintainer may set the default PDF bank name and optional logo in
[`config/report_branding.json`](config/report_branding.json), for example:

```json
{
  "bank_name": "Example Community Supply Bank",
  "logo_path": "config/branding_assets/example-logo.png"
}
```

Place approved PNG/JPEG logos (maximum 2 MB; 1600 pixels per side) inside
`config/branding_assets/`. Only add organization-authorized, publicly shareable
logo assets to this **public GitHub repository**. Leave `logo_path: null` for no
logo. Defaults are deliberately neutral: **Supply Bank**, no logo. Invalid
configuration or outside-folder paths are rejected rather than silently used.

On the Report page, staff may override these defaults for a single PDF with the
existing bank-name field and logo uploader. Such changes are session-only and
do not write to the config, server filesystem, or repository. A report generated
before a branding config change is invalidated on the next Streamlit rerun. The
logo and title do not verify or change any underlying planning data.

## Deploy to Streamlit Community Cloud

Official guide: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy

1. Verify that local tests pass: `python -m pytest -q`.
2. Commit/review the intended files and push to the public GitHub repository.
3. In https://share.streamlit.io select **Create app** and choose the existing GitHub repo.
4. Select `trnhokhai/supply-bank-allocator`, branch `main`, main file path **`app.py`**.
5. Open **Advanced settings** and select **Python 3.13**. The project uses the root `requirements.txt`; the PDF generator draws native vectors and needs no separate Chrome/Chromium install.
6. Deploy and check the build logs. **Do not claim a successful deployment until a real hosted Demo Mode → Forecast → Allocate → Report → PDF download run passes** (plus a mobile-view review).
7. Check memory and cold-load behavior on the hosted app. Community Cloud has resource limits and may hibernate inactive apps; a sleeping app is not a valid cold-load performance pass.

The app does not require secrets for its current synthetic demo workflow. Never add credentials or a `.streamlit/secrets.toml` file to a public GitHub repository. Any later credentials belong in the Streamlit Cloud Secrets interface.

## Technical stack

Python, Streamlit, pandas, pandera, statsforecast/statsmodels, SciPy/HiGHS, PuLP (reference comparison), Plotly, FPDF2, and pytest. `requirements.txt` records the Windows-validated environment; hosting compatibility remains subject to an actual Cloud build.

## Status / credit

**Week 6 technical checks:** Deployed Cloud core synthetic workflow, including the eight-week report PDF, passed manual smoke checks. On November 1, Windows regression reported **460 passed, 17 existing PuLP deprecation warnings**, with a genuine three-partner/eight-week report-to-PDF integration test. The user reported a **sub-10-second page load** and usable mobile interface (specific measurement and device details were not recorded; server wake-up was not independently certified). **Week 6 Gate closeout remains pending** two practitioner outreach requests, LinkedIn progress update, and formal acceptance. Public demo: https://chieac-supply-bank-allocator.streamlit.app/. These are synthetic planning demonstrations, not verified bank outcomes or supplier quotes.

**Week 7 update (November 6, 2026):** CP7.1 added automatic synthetic / uploaded / mixed / unknown-source PDF labeling and prevents reuse of old planning reports after input changes. The latest **user-run Windows local regression** reported 474 passed, zero failed and 17 previously existing PuLP warnings, with three local provenance smoke checks. This is **not** independent cloud acceptance or proof of field validation. Three practitioner feedback requests containing the live demo URL were verified sent November 2, after the earlier November 1 Week 6 checkpoint; replies and Benjamin's formal acceptance remain unverified. Guide and onboarding documentation are being finalized under CP7.2; the clean-machine setup-under-10-minutes benchmark remains to be independently measured.

Built by **Khai Tran** as a ChiEAC Fellow, Chicago Education Advocacy Cooperative. MIT licensed.
