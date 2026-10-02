# Project State — Diaper & Period Supply Bank Allocator

**Last updated:** October 2, 2026
**Current gate:** Week 2 closeout — Gate 2 technical acceptance met; practitioner outreach pending
**Repository:** `trnhokhai/supply-bank-allocator`
**Default branch:** `main`

---

## 1. Source-of-Truth Hierarchy

When continuing this project, use the following order of authority:

1. **ChiEAC Fellow Project Brief provided by Dr. Benjamin Drury**
   - Authoritative for project scope, weekly gates, benchmarks, required deliverables, and deadlines.

2. **GitHub repository**
   - Authoritative for the current implementation, tests, data contract, generated sample data, and committed documentation.

3. **This file (`docs/PROJECT_STATE.md`)**
   - Authoritative for the current working state, pending dependencies, and next implementation checkpoint.

4. **`docs/DECISIONS.md`**
   - Records durable technical and architectural decisions that should not be casually reversed.

If these sources appear inconsistent, stop and identify the inconsistency before changing code.

---

## 2. Project Identity

### Product

**Diaper & Period Supply Bank Allocator**

### Tagline

> Forecast demand, balance inventory, and allocate essential supplies where they’re needed most.

### Purpose

Build a free, public-facing planning application that helps diaper and period supply banks:

- forecast demand;
- understand inventory risk;
- identify product-size mismatches;
- allocate scarce inventory more consistently and equitably;
- run planning scenarios;
- generate a funder-ready report.

### Fellow

Khai Tran

### External Role Title

**Business Intelligence & Supply Chain Analytics Fellow**
Chicago Education Advocacy Cooperative (ChiEAC)

Use this title in external project communication unless Khai says otherwise.

---

## 3. Current Technical Environment

Development environment:

- Windows
- VS Code
- PowerShell
- Python 3.13
- Local virtual environment: `.venv`
- Git + GitHub
- Streamlit
- pandas
- openpyxl
- pandera
- statsforecast / statsmodels
- PuLP
- Plotly
- Kaleido
- fpdf2
- Faker
- pytest

On some new PowerShell sessions, activation may require:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

A successful activation shows:

```text
(.venv)
```

Prefer:

```powershell
python -m pytest
```

instead of bare `pytest`, so tests use the project virtual environment.

---

## 4. Week 1 Status

### Gate 1 — Discovery and Data Contract

The Week 1 technical foundation is complete and should be treated as **locked unless a real Week 2 issue requires a change**.

Completed:

- Public GitHub repository created.
- Python virtual environment configured.
- `requirements.txt` created.
- MIT license added.
- README created.
- Initial repository structure created.
- Four input templates created in CSV and XLSX.
- Data dictionary created.
- Deterministic synthetic-data generator completed.
- Partner survey synthetic generator completed.
- Current inventory generator completed.
- Incoming supply generator completed.
- Messy-data validation layer completed.
- Alternate-header validation files generated.
- Runtime synthetic-data validation completed.
- Sample datasets written to `data/sample/`.
- Partner intake Google Form drafted.
- Streamlit partner survey specification documented.
- Gate 1 validation charts generated.
- Week 1 project plan documented.
- Product name and tagline locked.
- Week 1 accountability report submitted.

---

## 5. Current Repository State

### Application

`app.py`

- Streamlit application home page.
- Introduces the product and current workflow.

`pages/1_Upload.py`

- Working Upload page.
- Supports user-uploaded CSV and XLSX files.
- Supports one-click Demo Mode.
- Shows raw-input previews.
- Suggests canonical header mappings with editable dropdowns.
- Runs cleaning and validation through the shared backend workflow.
- Displays data-quality corrections, warnings, row counts, and cleaned previews.
- Displays derived Week 2 planning tables:
  - ISO-weekly distribution;
  - inactive spans;
  - reconciled site master.

### Core source files

`src/create_templates.py`

- Generates the four CSV/XLSX blank input templates.

`src/synth.py`

- Deterministic synthetic-data pipeline.
- Week 1 generator remains locked unless a genuine downstream defect is identified.

`src/ingest.py`

- Canonical header mapping.
- Product and product-aware size normalization.
- Site-name normalization.
- Conservative pack-to-unit quantity parsing.
- Deterministic missing-site-ID generation.

`src/validate.py`

- Pandera schemas for all four canonical inputs.
- Friendly validation issues.
- Dataset-specific duplicate handling.

`src/clean.py`

- End-to-end cleaning pipelines for:
  - Distribution Log;
  - Current Inventory;
  - Incoming Supply;
  - Partner Survey.
- Produces explainable Data Quality Reports.

`src/aggregate.py`

- ISO-week aggregation.
- Active/inactive site calendar.
- Inactive-span detection.
- Zero-fills missing product-size weeks only when the site is otherwise active.

`src/site_master.py`

- Reconciles partner identities across distribution history and survey data.
- Distribution-history IDs remain authoritative.
- Supports deterministic IDs for survey-only partners.

`src/file_io.py`

- Reads CSV and XLSX inputs.
- Provides Demo Mode loading for all four synthetic inputs.

`src/workflow.py`

- Connects header mapping, cleaning, validation, and derived planning tables.
- Keeps Streamlit UI separate from business logic.

`src/validation_charts.py`

- Produces Gate 1 visual validation charts.

### Documentation

- `README.md`
- `docs/data_dictionary.md`
- `docs/synthetic_data.md`
- `docs/partner_survey_spec.md`
- `docs/project_plan.md`
- `docs/PROJECT_STATE.md`
- `docs/DECISIONS.md`
- `docs/figures/`

### Tests

Current automated suites include:

- `tests/test_templates.py`
- `tests/test_synth.py`
- `tests/test_ingest.py`
- `tests/test_validate.py`
- `tests/test_clean.py`
- `tests/test_aggregate.py`
- `tests/test_site_master.py`
- `tests/test_file_io.py`
- `tests/test_workflow.py`

Latest verified full-suite result:

```text
140 passed
0 warnings

---

## 6. Locked Week 1 Data Contract

There are four canonical inputs:

1. Distribution Log
2. Current Inventory
3. Incoming Supply
4. Partner Intake Survey

The canonical field definitions and controlled vocabularies are documented in:

```text
docs/data_dictionary.md
```

Do not silently rename or remove canonical fields during Week 2.

### Distribution Log

Core fields:

- `date`
- `site_id`
- `site_name`
- `product`
- `size`
- `quantity`
- `households_served`
- `children_served`

`quantity` represents **individual units**, not packs.

### Current Inventory

Core fields:

- `as_of_date`
- `product`
- `size`
- `quantity_on_hand`
- `location`

### Incoming Supply

Core fields:

- `expected_date`
- `source`
- `product`
- `size`
- `quantity`
- `status`

Allowed status values:

- `confirmed`
- `pending`

`size = unknown` may be used for donation drives whose size mix is not yet known.

### Partner Survey

Core fields:

- `site_name`
- `zip_code`
- `agency_type`
- `families_served_per_month`
- `children_under_4_per_month`
- `menstruating_clients_per_month`
- `poverty_share_band`
- `priority_population_flags`
- `storage_capacity_cases`
- `distribution_frequency`
- `recent_stockout_sizes`
- `preferred_contact`
- `languages_spoken`

---

## 7. Synthetic Data — Verified Design

Synthetic generation uses a deterministic random seed:

```python
SEED = 42
```

The current synthetic design includes:

- 25 partner sites.
- 78 weeks of historical distribution data.
- Mixed agency types.
- 10 sites with period-product activity.
- 8 sites with pull-up activity.
- 3 sites with adult-incontinence activity.
- Multi-product demand including diapers, wipes, pull-ups, period products, and adult incontinence.
- SITE_024 begins partway through history at week 30.
- SITE_025 begins partway through history at week 50.
- SITE_008 contains a six-week inactivity gap.
- Approximately 3% deliberately messy distribution records.
- Current inventory containing deliberate long and short positions.
- 52 weeks of future incoming supply.
- Both confirmed and pending incoming supply.
- Two large synthetic donation drives.
- Summer donation trough.
- Completed synthetic partner survey for all 25 sites.

### Intentional diaper demand pattern

Historical demand is concentrated in:

- Size 4
- Size 5

Lowest demand is concentrated in:

- Newborn (`N`)
- Size 7

Week 1 validation chart values were approximately:

- N: 2.84%
- 1: 7.65%
- 2: 11.67%
- 3: 16.93%
- 4: 24.42%
- 5: 23.55%
- 6: 10.01%
- 7: 2.92%

### Intentional donation mismatch

Donated diaper supply is skewed toward:

- Newborn (`N`)
- Size 1
- Size 2

Week 1 validation chart values were approximately:

- N: 22.06%
- 1: 23.95%
- 2: 20.04%
- 3: 13.93%
- 4: 8.99%
- 5: 6.04%
- 6: 4.00%
- 7: 0.99%

This mismatch is deliberate and should remain visible for later alert/allocation testing.

### Intentional inventory positions

The synthetic inventory is designed so that diaper sizes:

**Long:**

- N
- 1
- 2

**Short:**

- 5
- 6

These planted conditions will be used in later gate validation.

---

## 8. Sample Files Available for Week 2

`data/sample/` contains CSV and XLSX versions of:

- clean distribution log;
- messy distribution log;
- alternate-header distribution log;
- current inventory;
- incoming supply;
- partner survey.

The Week 2 ingestion layer should use these files as its primary controlled test bed.

No external operational dataset is required for Gate 2.

Do not place real practitioner/client data in the repository.

---

## 9. Messy-Data Test Bed

The clean distribution dataset is the ground truth.

The messy distribution dataset is a separate validation copy.

The clean dataset must not be mutated when testing cleaning logic.

Deliberately planted issues include:

- inconsistent product capitalization;
- surrounding whitespace;
- non-standard size labels;
- string-formatted quantities;
- pack-based quantity representations.

Examples may include:

```text
DIAPER
Period_Pad
SIZE5
 newborn
12 packs x 25 units
654 units
```

The repository also contains a separate alternate-header distribution file.

Header problems are treated as **file-level mapping problems**, not row-level dirty-data problems.

---

## 10. Week 2 Decisions Resolved

The Week 2 ingestion-contract questions identified at the beginning of the gate have been resolved and implemented.

### Partner Survey requiredness

Resolved by Decision 031.

The Partner Survey remains an optional application input.

When survey data is provided, the minimum required canonical fields are:

```text
site_name
zip_code
agency_type
families_served_per_month
```

The remaining survey fields are optional enrichment fields.

`docs/partner_survey_spec.md` was updated to match this implementation.

### Recent stockout identifiers

Resolved by Decision 032.

The preferred canonical format is:

```text
product:size
```

Examples:

```text
diaper:4
period_pad:overnight
adult_incontinence:L
```

Bare values are normalized only when their meaning is unambiguous.

### Pack-to-unit conversion

Resolved by Decision 033.

Canonical quantities are individual units.

The ingestion layer safely supports deterministic values such as:

```text
300
300.0
300 units
12 packs x 25 units
```

Ambiguous quantities are rejected instead of guessed.

### Missing site IDs

Resolved by Decision 034.

Existing valid site IDs are preserved.

Missing site IDs are generated deterministically from normalized site names using readable `AUTO_` identifiers.

### Duplicate handling

Resolved by Decision 035.

Duplicate behavior is dataset-specific rather than using a universal automatic deduplication rule.

---

## 11. Gate 2 — Technical Implementation Status

### Gate Name

**Ingestion, Validation, and the Upload Experience**

### Goal

A supply-bank staff member can upload imperfect real-world files and receive clean, trusted tables.

### Implemented

The Week 2 technical implementation now includes:

- Streamlit multipage application skeleton;
- Upload page;
- CSV and XLSX file reading;
- four canonical input domains;
- fuzzy/default header mapping with manual dropdown review;
- product normalization;
- product-aware size normalization;
- pack-to-unit quantity conversion;
- deterministic missing-site-ID generation;
- Pandera validation;
- dataset-specific duplicate handling;
- friendly validation errors;
- explainable Data Quality Reports;
- cleaned-data previews;
- ISO-week distribution aggregation;
- active/inactive site calendar;
- inactive-span detection;
- conditional zero filling only when a site is otherwise active;
- reconciled site master;
- optional survey enrichment;
- one-click Demo Mode;
- derived planning tables displayed in the Upload workflow.

Forecasting has intentionally not begun during Week 2.

---

## 12. Gate 2 Acceptance Results

The technical acceptance benchmarks have been exercised through automated tests and manual Streamlit checks.

### Messy synthetic data

Demo Distribution Log:

```text
Rows uploaded:   24,422
Rows cleaned:    24,422
Rows corrected:     733
Rows dropped:         0
```

Correction breakdown:

```text
product:   244 rows
size:      245 rows
quantity:  244 rows
```

The Data Quality Details panel explains each correction category.

### Alternate-header mapping

The controlled alternate-header Distribution Log was uploaded through the Streamlit UI.

Result:

```text
8 of 8 headers mapped correctly
0 manual dropdown changes required
```

This exceeds the Gate 2 benchmark of no more than two manual corrections.

### Friendly validation error

A temporary Distribution Log missing the required `quantity` field was manually uploaded.

The application did not crash.

It returned the user-facing message:

```text
Distribution Log: Map all required columns before cleaning.
Still missing: quantity.
```

The temporary test file was removed after testing.

### Demo Mode performance

Five local Demo Mode loads were benchmarked.

```text
Average: 29.6 ms
Slowest: 34.2 ms
```

The required benchmark is under five seconds.

### Derived planning outputs

Current Demo Mode result:

```text
Weekly distribution records: 25,731
Zero-filled product-size weeks: 1,309
Inactive spans: 1
Partner sites: 25
```

The one detected inactive span corresponds to the intentionally planted six-week gap for `SITE_008`.

Late onboarding for `SITE_024` and `SITE_025` is not misclassified as inactivity.

### Automated verification

Latest full-suite result:

```text
140 passed
0 warnings
```

Streamlit syntax verification:

```powershell
python -m py_compile app.py pages/1_Upload.py
```

completed without error.

---

## 13. Practitioner Outreach Status

On October 1, 2026, Khai sent practitioner interview outreach to:

1. **Share Our Spare**
   - Direct outreach to Jesseca Rhymes.
   - Topic: inventory, distribution, shortages, and planning-tool trust.

2. **Cradles to Crayons Chicago**
   - Sent to the Chicago general contact inbox.
   - Requested routing to an operations/programs staff member familiar with inventory and partner distribution.

3. **The Period Collective**
   - Sent to the organization contact inbox.
   - Focused on period-product supply and distribution.

Current status as of October 2, 2026:

**No practitioner has replied, scheduled an interview, or completed an interview yet.**

This remains an external dependency and does not block the completed technical Gate 2 work.

If a practitioner replies next week:

1. schedule the interview;
2. document approximately half a page of actual findings;
3. compare findings with the existing data contract;
4. change the contract only through a deliberate documented decision.

Do not fabricate practitioner findings.

---

## 14. Week 2 Closeout and Next Gate

### Week 2 status

**Technical Gate 2 acceptance criteria are met.**

Remaining closeout work:

1. finish documentation alignment;
2. run the final test suite;
3. commit and push Week 2 documentation;
4. preserve practitioner outreach as a pending external dependency.

### Next gate

**Week 3 — Forecasting**

Do not begin forecasting until the Week 2 closeout commit is pushed.

The first Week 3 checkpoint should begin with:

1. read the authoritative Week 3 section of the ChiEAC Project Brief;
2. read the committed GitHub state;
3. read this `PROJECT_STATE.md`;
4. read `docs/DECISIONS.md`;
5. verify the Week 2 handoff before writing forecasting code.

Week 3 should build on the trusted weekly distribution table produced by Week 2 rather than returning to raw uploaded data.

The Week 2 ingestion, validation, cleaning, aggregation, and site-identity layers should be treated as locked unless forecasting exposes a genuine defect.

---

## 15. Collaboration Protocol

Khai is learning Python project development and software-engineering workflow while building this project.

Act as an expert Supply Chain Data Scientist and technical mentor.

The quality standard is:

**portfolio-grade and credible to recruiters, not a homework exercise.**

When working with Khai:

- Explain what is being built and why.
- Keep explanations practical and concise.
- Do not assume he already knows software-engineering conventions.
- Do not make him blindly paste code without explaining the business/technical purpose.
- Do not invent additional scope just to make the project more complex.
- Follow the ChiEAC gate requirements.
- Prefer simple, defensible architecture over unnecessary sophistication.
- Test each meaningful component before locking it.
- Inspect real outputs after automated tests when visual/business validation matters.
- Commit logical checkpoints with descriptive Git messages.

When asking Khai to change code, always be precise:

**file → function/search string → exact block → what to add/replace**

Avoid vague directions such as:

> “Change the logic somewhere in the function.”

If a bug occurs, diagnose the actual error before proposing broad rewrites.

---

## 16. Handoff Protocol for Future Weekly Chats

At the end of each weekly working chat:

1. Ensure code is saved.
2. Run the relevant tests.
3. Inspect important output.
4. Commit and push completed work.
5. Update this `PROJECT_STATE.md`.
6. Update `docs/DECISIONS.md` only when a durable decision has been made.
7. Record external dependencies and pending replies.
8. Record the exact next gate and first checkpoint.
9. Prepare a short kickoff prompt for the next weekly chat.

The next chat must **read the Project Brief and GitHub state before writing code**.

Before implementation, the new chat should summarize:

1. current verified state;
2. locked work that should not be redone;
3. current gate requirements;
4. known unresolved questions;
5. exact next implementation checkpoint.

Khai should verify that summary before new code is written.