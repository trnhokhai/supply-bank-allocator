# Diaper & Period Supply Bank Allocator
*Forecast demand, balance inventory, and allocate essential supplies where they’re needed most.*

## Project Goal

Build a free, public-facing planning application that helps diaper and period supply banks forecast demand, understand inventory risk, and allocate limited essential supplies across partner agencies more consistently and equitably.

The project addresses a common operational mismatch: donated supply often concentrates in smaller diaper sizes while demand is higher in sizes 4–6. Supply banks may also lack a unified planning layer that combines historical demand, inventory, incoming supply, and partner-level need.

---

## Primary Users

The application is designed for:

- Supply bank executive directors
- Program managers
- Warehouse and operations staff
- Partner agency contacts completing the intake survey
- Funders reviewing the final reporting output

---

## Inputs

The application will use three operational uploads plus one partner intake survey:

1. Distribution log
2. Current inventory
3. Incoming supply
4. Partner intake survey

Each input will have:

- CSV and XLSX templates
- A documented data contract
- Validation rules
- Header mapping and normalization
- Support for imperfect real-world files

No individual-client data will be required.

---

## Core Outputs

The completed application will provide:

- 4–8 week demand forecasts by partner site, product, and size
- Forecast accuracy metrics and selected forecasting method
- Equity-weighted allocation recommendations
- Partner-level pick lists
- Weeks-of-supply and size-mismatch alerts
- Scenario analysis for changes in supply, demand, partners, and purchase budget
- A one-page funder report

---

## Analytical Approach

### Demand Forecasting

Historical distribution data will be aggregated to weekly demand.

Candidate forecasting methods will be backtested using rolling-origin evaluation, with model selection based primarily on WAPE.

New partners without sufficient history will receive clearly labeled survey-based cold-start estimates.

### Allocation

A linear programming model will allocate available inventory across partner sites while:

- respecting available supply;
- accounting for forecast need;
- incorporating equity weights;
- enforcing a fairness floor where feasible;
- respecting partner storage capacity when available.

A proportional allocation baseline will be used for comparison.

### Inventory Risk

Weeks of supply and inventory-to-demand mismatch metrics will identify products and sizes that are unusually long or short.

---

## Week 1 Decisions Locked

The following foundations have been completed and will serve as the initial data contract:

- Public GitHub repository and reproducible Python environment
- README, MIT license, and requirements file
- Four CSV/XLSX input templates
- Complete data dictionary
- Partner intake survey design
- Streamlit survey specification
- Deterministic synthetic-data generator
- 25 synthetic partner sites
- 78 weeks of synthetic demand history
- Multi-product demand coverage
- Current inventory snapshot
- 52-week incoming supply plan
- Approximately 3% deliberately messy validation records
- Alternate-header test file
- Automated validation and test suite
- Gate 1 demand-mix and donation-mix validation charts

Synthetic data intentionally reproduces the core planning problem:

- historical diaper demand is concentrated in sizes 4 and 5;
- donated diaper supply is concentrated in Newborn, size 1, and size 2;
- selected inventory positions contain both long and short sizes.

---

## Build Plan

### Week 1 — Discovery and Data Contract

Lock the input contract, synthetic dataset, survey design, project plan, and initial stakeholder outreach.

### Week 2 — Ingestion and Validation

Build the upload workflow, header mapping, data normalization, validation schemas, data-quality reporting, and demo-data mode.

### Week 3 — Forecasting

Build and backtest the forecasting engine and create the Forecast page.

### Week 4 — Allocation

Implement the optimization model, equity weighting, fairness logic, pick lists, and baseline comparison.

### Week 5 — Alerts and Scenarios

Add inventory-risk alerts and interactive planning scenarios.

### Week 6 — Deployment and Reporting

Deploy the Streamlit application and build the one-page funder report.

### Week 7 — Practitioner Feedback and Handoff

Incorporate practitioner feedback and complete documentation, demo materials, and project handoff.

### Buffer Week

Reserved for fixes and stabilization only.

---

## Scope Boundaries

Version 1 will remain intentionally focused.

### In Scope

- User-uploaded operational files
- Partner intake survey
- Forecasting
- Allocation optimization
- Inventory-risk analytics
- Scenario planning
- Funder reporting
- Synthetic demo data

### Out of Scope

- User accounts
- External operational databases
- Live external data feeds
- Individual-client records
- Sensitive personal data
- Large enterprise-system integrations

---

## Discovery and Practitioner Feedback

Two or more diaper or period supply-bank practitioners will be invited to short interviews focused on:

- how allocation decisions are made today;
- what operational files are currently maintained;
- where shortages and mismatches occur;
- what outputs would make a planning tool trustworthy and useful.

Material findings may refine validation rules, user experience, and documentation while preserving the core project scope.

---

## Week 1 Success Criteria

Gate 1 is complete when:

- templates open cleanly in Excel and Google Sheets;
- the data dictionary covers the complete input contract;
- the synthetic dataset is reproducible from one command;
- validation charts demonstrate the intended demand and donation size patterns;
- the partner intake survey is drafted;
- at least two practitioner interview requests have been sent;
- the repository is accessible to ChiEAC;
- the project plan and product positioning are documented.