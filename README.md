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

**Week 6A–6C:** Report contract, PDF and survey implemented and verified locally; **Week 6D** is undergoing public-readiness and deployment validation. Field practitioner review remains a separate workstream.

Built by **Khai Tran** as a ChiEAC Fellow, Chicago Education Advocacy Cooperative. MIT licensed.
