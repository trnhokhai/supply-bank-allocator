# Project State — Diaper & Period Supply Bank Allocator

**Last updated:** October 1, 2026  
**Current gate:** Week 2 — Ingestion, Validation, and the Upload Experience  
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

- Currently empty.
- Week 2 will begin the actual Streamlit application.

The planned `pages/` directory is not currently tracked on GitHub because it has no committed files yet.

### Core source files

`src/create_templates.py`

- Generates the four CSV/XLSX blank input templates.

`src/synth.py`

- Main deterministic synthetic-data pipeline.
- Consider Week 1 generator logic locked unless a downstream ingestion requirement exposes a genuine defect.

`src/validation_charts.py`

- Produces Gate 1 visual validation charts.

### Documentation

- `README.md`
- `docs/data_dictionary.md`
- `docs/synthetic_data.md`
- `docs/partner_survey_spec.md`
- `docs/project_plan.md`
- `docs/figures/`

### Tests

- `tests/test_templates.py`
- `tests/test_synth.py`

Last verified during Week 1:

- `tests/test_templates.py`: 3 tests passed.
- `tests/test_synth.py`: 32 tests passed after the final Week 1 changes.

A complete combined suite should be run at the beginning of Week 2 to establish a fresh baseline:

```powershell
python -m pytest -v
```

Do not assume a combined total until that command is actually run.

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

## 10. Known Documentation / Design Questions to Resolve in Week 2

Do not silently resolve these. Discuss them before implementing validation rules.

### A. Partner survey requiredness

There is currently a documentation inconsistency:

`docs/data_dictionary.md` marks several partner-survey fields as optional, while `docs/partner_survey_spec.md` treats some of them as required for the proposed form experience.

Examples include:

- `children_under_4_per_month`
- `menstruating_clients_per_month`
- `poverty_share_band`
- `storage_capacity_cases`
- `distribution_frequency`

The ChiEAC project brief defines the fields but does not explicitly prescribe the required/optional status of each one.

Resolve this before locking the Pandera partner-survey schema.

### B. Recent stockout size identifiers

A raw size such as:

```text
regular
L
one_size
```

can be ambiguous across product categories.

The survey specification recommends explicit product-size identifiers such as:

```text
diaper:4
period_pad:regular
period_tampon:regular
adult_incontinence:L
```

Week 2 ingestion should decide and document the canonical normalization behavior.

### C. Pack conversion

Canonical quantities are individual units.

Messy input may contain values such as:

```text
12 packs x 25 units
```

Week 2 must define predictable parsing, conversion, error handling, and user messaging.

---

## 11. Current Gate — Week 2

### Gate Name

**Ingestion, Validation, and the Upload Experience**

### Goal

A supply-bank staff member can upload imperfect real-world files and receive clean, trusted tables.

### Required Week 2 Work

Build the Streamlit multipage application skeleton and Upload page with:

- file pickers;
- header mapping;
- fuzzy-matched header defaults;
- size normalization;
- pack-to-unit conversion;
- data-quality reporting.

Implement Pandera validation for all four canonical inputs.

Provide friendly user-facing errors for common failures such as:

- incorrect date format;
- unknown product or size;
- negative quantity;
- duplicate rows;
- missing site name;
- missing required columns;
- invalid categorical values;
- malformed numeric values;
- invalid incoming-supply status;
- other high-probability input problems identified during implementation.

Also:

- aggregate distribution data to ISO weeks;
- detect inactive spans;
- build the site master table from distribution history plus survey data;
- add one-click Demo Mode using the synthetic datasets;
- write tests for validators and aggregation;
- conduct stakeholder interviews if practitioners respond;
- write approximately half a page of findings per completed interview.

Do not begin Week 3 forecasting work until Gate 2 is sufficiently complete.

---

## 12. Gate 2 Acceptance Benchmarks

Before considering Week 2 complete:

1. The deliberately messy synthetic rows must be caught or corrected.
2. The data-quality experience must explain what was corrected, rejected, or dropped.
3. The alternate-header file should map correctly with no more than two manual dropdown corrections.
4. Validator and aggregation tests must pass.
5. Demo Mode should load the synthetic dataset in under five seconds.

Deliverables:

- working Upload page;
- validation test suite;
- practitioner interview notes if interviews occur;
- updated data dictionary if practitioner findings materially change the contract.

---

## 13. Week 2 External Dependencies

On **October 1, 2026**, Khai sent practitioner interview outreach to:

1. **Share Our Spare**
   - Direct outreach to Jesseca Rhymes.
   - Topic: inventory, distribution, shortages, and planning-tool trust.

2. **Cradles to Crayons Chicago**
   - Sent to the Chicago general contact inbox.
   - Requested routing to an operations/programs staff member familiar with inventory and partner distribution.

3. **The Period Collective**
   - Sent to the organization contact inbox.
   - Focused on period-product supply and distribution.

Current status:

**Waiting for replies. No practitioner interview has been completed or scheduled yet.**

Do not fabricate interview findings.

If a practitioner replies, prioritize scheduling the interview without blocking technical Week 2 work.

---

## 14. Week 2 Starting Point

The first technical checkpoint should be:

### Checkpoint 1 — Establish the Upload Application Foundation

Before building:

1. Read the authoritative Week 2 section of the ChiEAC Project Brief.
2. Read this file.
3. Read `docs/DECISIONS.md`.
4. Inspect:
   - `README.md`
   - `docs/data_dictionary.md`
   - `docs/partner_survey_spec.md`
   - `src/synth.py`
   - `data/sample/`
   - existing tests
5. Run the complete existing test suite:

```powershell
python -m pytest -v
```

6. Confirm the baseline before changing code.

Then begin:

- `app.py`
- the first committed Streamlit page under `pages/`
- the Week 2 ingestion architecture

Do not rewrite the Week 1 synthetic generator merely to begin Week 2.

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