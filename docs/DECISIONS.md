# Decision Log — Diaper & Period Supply Bank Allocator

This file records durable project decisions that should not be casually reversed in future development.

The purpose of this document is to preserve the reasoning behind important technical, analytical, data, and workflow choices so that future contributors or future ChatGPT sessions do not unknowingly undo prior work.

For the current working state, see:

```text
docs/PROJECT_STATE.md
```

For authoritative project scope and gate requirements, use the ChiEAC Fellow Project Brief provided by Dr. Benjamin Drury.

---

# Decision 001 — Source-of-Truth Hierarchy

**Status:** Accepted

The project uses the following source-of-truth hierarchy:

1. ChiEAC Fellow Project Brief
2. GitHub repository
3. `docs/PROJECT_STATE.md`
4. `docs/DECISIONS.md`

### Rationale

The project brief defines required scope and gate benchmarks.

GitHub represents the actual committed implementation.

`PROJECT_STATE.md` records the current working state.

`DECISIONS.md` preserves durable reasoning.

### Consequence

A future contributor should not rely only on chat history or memory.

If sources conflict, the conflict should be identified explicitly before changing implementation.

---

# Decision 002 — Product Positioning

**Status:** Accepted

The product name is:

**Diaper & Period Supply Bank Allocator**

The tagline is:

> Forecast demand, balance inventory, and allocate essential supplies where they’re needed most.

### Rationale

The name directly communicates the problem domain.

The tagline maps to the three primary analytical capabilities:

1. Forecasting
2. Inventory planning
3. Allocation

The project should remain easy for practitioners, recruiters, and non-technical stakeholders to understand.

---

# Decision 003 — Portfolio Quality Standard

**Status:** Accepted

This project should be developed as a:

**portfolio-grade, recruiter-credible Supply Chain Data Science application**

and not as a classroom exercise or isolated coding demonstration.

### Rationale

The project is intended to demonstrate:

- analytical thinking;
- business understanding;
- data engineering discipline;
- forecasting;
- optimization;
- practical software development;
- stakeholder communication.

### Consequence

Implementation decisions should favor:

- defensibility;
- reproducibility;
- clear documentation;
- business usefulness;
- testing;
- explainability.

Avoid unnecessary complexity that exists only to appear technically advanced.

---

# Decision 004 — Version 1 Remains Narrowly Scoped

**Status:** Accepted

Version 1 will focus on:

- file uploads;
- data validation;
- demand forecasting;
- inventory-risk analysis;
- allocation optimization;
- scenario analysis;
- partner survey inputs;
- funder reporting;
- synthetic demo data.

Version 1 will not require:

- user authentication;
- enterprise databases;
- live ERP integrations;
- external operational APIs;
- client-level records;
- sensitive personal data;
- large-scale infrastructure.

### Rationale

The ChiEAC fellowship project has a fixed timeline.

The strongest portfolio outcome is a complete and usable end-to-end application rather than an over-expanded architecture.

---

# Decision 005 — Four Canonical Input Domains

**Status:** Accepted

The application has four canonical input domains:

1. Distribution Log
2. Current Inventory
3. Incoming Supply
4. Partner Intake Survey

The canonical schema is documented in:

```text
docs/data_dictionary.md
```

### Rationale

These four inputs contain the information necessary for the planned forecasting, allocation, inventory-risk, and equity workflows.

### Consequence

Week 2 ingestion may normalize user-provided headers and values, but it should ultimately map data into these canonical schemas.

Do not silently introduce additional required input datasets.

---

# Decision 006 — Canonical Quantities Use Individual Units

**Status:** Accepted

All canonical quantity fields represent **individual units**, not packs or cases.

Examples:

```text
quantity
quantity_on_hand
```

should ultimately represent individual units.

### Rationale

Forecasting, inventory calculations, and allocation optimization require a consistent unit of measure.

Mixing packs and units would produce invalid analytical results.

### Consequence

If users upload pack quantities, the ingestion layer must convert them into individual units before downstream analytics.

A value such as:

```text
12 packs x 25 units
```

should normalize to:

```text
300
```

if the format is valid and unambiguous.

Ambiguous pack quantities should be flagged rather than guessed.

---

# Decision 007 — Controlled Product and Size Vocabulary

**Status:** Accepted

Products and sizes should normalize to controlled canonical values.

Examples include:

```text
diaper
pull_up
wipes
period_pad
period_tampon
period_liner
period_cup
adult_incontinence
```

Diaper sizes:

```text
N
1
2
3
4
5
6
7
```

Other product-specific sizes are defined in:

```text
docs/data_dictionary.md
```

### Rationale

Consistent product-size identifiers are required for:

- aggregation;
- forecasting;
- inventory matching;
- allocation;
- alerts;
- exports.

### Consequence

Week 2 should normalize reasonable variants such as:

```text
DIAPER
Diaper
 diaper
SIZE5
 newborn
```

into canonical values where the intended meaning is clear.

Unknown values should be surfaced to the user rather than silently forced into a category.

---

# Decision 008 — Synthetic Data Is the Primary Controlled Development Dataset

**Status:** Accepted

The project will use deterministic synthetic data as the primary development, testing, and demonstration dataset until real operational data is explicitly and appropriately provided.

### Rationale

Synthetic data allows the project to:

- reproduce known business conditions;
- test edge cases;
- avoid privacy risks;
- validate analytical behavior;
- remain publicly shareable.

### Consequence

No external dataset is required merely to complete Week 2.

Practitioner interviews may influence design, but practitioners are not expected to provide operational data.

---

# Decision 009 — Synthetic Generation Must Remain Reproducible

**Status:** Accepted

Synthetic generation uses:

```python
SEED = 42
```

and should remain deterministic.

### Rationale

A reproducible dataset makes:

- automated tests reliable;
- validation charts stable;
- debugging easier;
- demonstrations repeatable.

### Consequence

Do not replace the deterministic generator with uncontrolled randomness.

If the generator must change later, tests and validation benchmarks should be updated deliberately.

---

# Decision 010 — Clean Data and Messy Data Stay Separate

**Status:** Accepted

The synthetic distribution dataset has two distinct roles:

### Clean distribution data

Represents the synthetic ground truth.

### Messy distribution data

Represents intentionally imperfect user input for ingestion testing.

### Rationale

If dirty values are injected into the only copy of the data, there is no reliable reference for evaluating cleaning behavior.

### Consequence

Cleaning or validation tests should compare against or reason from the clean dataset without mutating it.

The Week 2 ingestion pipeline should never overwrite the clean synthetic ground truth.

---

# Decision 011 — Header Problems Are File-Level Mapping Problems

**Status:** Accepted

Renamed or inconsistent headers are tested using a separate alternate-header input file rather than randomly changing headers on individual rows.

### Rationale

Headers belong to an entire uploaded file, not individual records.

Treating header problems as row-level dirtiness would be structurally unrealistic.

### Consequence

Week 2 should implement a header-mapping layer before row-level validation.

The alternate-header synthetic file is the primary Gate 2 benchmark for this behavior.

---

# Decision 012 — Messy Data Should Be Corrected When Safe, Rejected When Ambiguous

**Status:** Accepted

The Week 2 ingestion philosophy is:

> Correct obvious and deterministic issues automatically; reject or flag ambiguous issues.

Examples suitable for automatic correction:

```text
DIAPER → diaper
" Site 01 " → "Site 01"
SIZE5 → 5
newborn → N
12 packs x 25 units → 300
```

Examples that may require user intervention:

```text
unknown product category
ambiguous size without product context
pack quantity without pack size
invalid date with multiple possible interpretations
```

### Rationale

A professional data pipeline should reduce unnecessary user work without inventing information.

### Consequence

The application must distinguish:

- corrected records;
- valid records;
- rejected records;
- unresolved records.

---

# Decision 013 — Data Quality Must Be Explainable

**Status:** Accepted

The application should not only reject bad data.

It should explain what happened.

### Rationale

Supply-bank staff need confidence in the cleaned dataset.

A user should be able to understand:

- what was corrected;
- what was dropped;
- why it was dropped;
- what they can fix.

### Consequence

Week 2 will include a data-quality summary/card.

Validation messages should use plain language instead of exposing technical Pandera or Python errors directly.

---

# Decision 014 — Synthetic Business Mismatch Is Intentional

**Status:** Accepted

Synthetic diaper demand is intentionally concentrated in sizes:

```text
4
5
```

Synthetic donated supply is intentionally concentrated in:

```text
N
1
2
```

### Rationale

The project needs a visible supply-demand mismatch to demonstrate:

- shortage identification;
- weeks-of-supply analysis;
- allocation optimization;
- scenario planning.

### Consequence

Future development should not “fix” this mismatch by making synthetic donations resemble demand.

The mismatch is a feature of the test environment.

---

# Decision 015 — Inventory Must Contain Both Long and Short Positions

**Status:** Accepted

Synthetic inventory intentionally produces different weeks-of-supply conditions.

Current planted diaper behavior includes approximately:

### Long

```text
N
1
2
```

### Short

```text
5
6
```

### Rationale

Later alert and allocation functionality requires realistic inventory imbalances.

### Consequence

Do not normalize synthetic inventory toward equal weeks of supply.

---

# Decision 016 — Site Activity Edge Cases Are Deliberate

**Status:** Accepted

The synthetic history includes:

- two sites that onboard partway through history;
- one site with a six-week inactive span.

Current design:

```text
SITE_024 → begins at week 30
SITE_025 → begins at week 50
SITE_008 → six-week inactive gap
```

### Rationale

The application must distinguish:

- new partners;
- inactive periods;
- normal zero demand.

These cases also support later cold-start forecasting and data-quality testing.

### Consequence

Week 2 should detect inactive spans rather than filling every missing week blindly as demand equal to zero.

---

# Decision 017 — Survey Data Supports Cold Start and Equity, Not Individual-Level Profiling

**Status:** Accepted

The partner survey exists to provide organization-level information for:

- cold-start demand estimation;
- equity weighting;
- storage constraints;
- operational context.

### Rationale

Some partner agencies may have little or no historical distribution data.

Survey inputs can provide reasonable organizational context without collecting client-level records.

### Consequence

The project must not request or infer sensitive individual-client information.

No client names, addresses, dates of birth, immigration status, medical details, or individual household records should be required.

---

# Decision 018 — Google Form and Streamlit Survey Should Map to the Same Canonical Schema

**Status:** Accepted

The Google Form uses human-readable labels.

The Streamlit form and ingestion layer should normalize responses to the canonical survey fields in the data dictionary.

Example:

```text
WIC clinic
```

maps to:

```text
wic_clinic
```

### Rationale

Partners should not have to enter machine-readable codes.

The data pipeline should handle normalization.

### Consequence

The human-facing survey vocabulary and internal canonical vocabulary may differ in presentation while remaining semantically equivalent.

---

# Decision 019 — Recent Stockout Values Need Product Context

**Status:** Provisional design direction

Size-only values can be ambiguous.

Examples:

```text
regular
L
one_size
```

may refer to different products.

The preferred future representation is:

```text
diaper:4
pull_up:3T-4T
period_pad:regular
period_tampon:regular
adult_incontinence:L
```

### Rationale

Product-size identifiers remove ambiguity.

### Consequence

Week 2 must finalize normalization behavior before locking the survey ingestion schema.

Do not treat this decision as fully finalized until Week 2 implementation confirms it.

---

# Decision 020 — Forecasting Work Does Not Begin During Week 2

**Status:** Accepted

Week 2 focuses on:

- ingestion;
- normalization;
- validation;
- upload experience;
- aggregation;
- site master;
- demo mode.

Forecasting belongs to Week 3.

### Rationale

Forecast quality depends on trustworthy input data.

Building forecasting before ingestion is stable would create unnecessary rework.

### Consequence

Do not begin `forecast.py` merely because Week 2 technical work becomes interesting or complex.

Complete Gate 2 first.

---

# Decision 021 — Streamlit Is the Application Interface

**Status:** Accepted

The public-facing application will use Streamlit.

### Rationale

Streamlit supports:

- rapid development;
- file uploads;
- interactive controls;
- visualization;
- downloadable outputs;
- straightforward public deployment.

It also matches the project timeline and existing Python stack.

### Consequence

The project does not need a separate JavaScript frontend for Version 1.

---

# Decision 022 — Uploaded User Data Should Not Persist Beyond the Session

**Status:** Accepted

The Version 1 application should process uploaded data during the active application session rather than storing user operational files in a permanent database.

### Rationale

This:

- reduces privacy risk;
- reduces infrastructure complexity;
- supports a public demonstration application;
- aligns with the current project scope.

### Consequence

Do not introduce permanent upload storage without an explicit future decision.

---

# Decision 023 — Practitioner Feedback Can Refine the Contract but Does Not Automatically Override It

**Status:** Accepted

Practitioner interviews are used to validate real-world assumptions.

Feedback may lead to changes in:

- input terminology;
- validation rules;
- user experience;
- data documentation;
- useful outputs.

### Rationale

Practitioner insight is valuable, but one interview should not automatically trigger major architecture changes.

### Consequence

If feedback suggests a schema or scope change:

1. document the finding;
2. compare it with the project brief;
3. discuss the tradeoff;
4. update the data dictionary deliberately if warranted.

Do not silently change the schema during or immediately after an interview.

---

# Decision 024 — No Fabricated Practitioner Findings

**Status:** Accepted

Interview findings must reflect actual practitioner conversations.

### Rationale

Practitioner research is part of the professional credibility of the project.

### Consequence

If outreach receives no response during a gate:

- record outreach attempts;
- document the scheduling dependency;
- continue technical work.

Do not invent quotes, observations, or findings.

---

# Decision 025 — GitHub Is the Implementation Handoff Layer

**Status:** Accepted

Future weekly ChatGPT sessions should read the committed GitHub repository rather than relying on pasted source code from prior chats.

### Rationale

Long chat histories become inefficient and incomplete.

GitHub provides a stable and inspectable representation of:

- source code;
- tests;
- documentation;
- sample data;
- project state.

### Consequence

Work that exists only locally in VS Code is not considered available to the next chat.

Before weekly handoff:

```text
save
→ test
→ inspect
→ commit
→ push
→ update handoff documents
```

---

# Decision 026 — Weekly Chats Should Be Replaceable

**Status:** Accepted

No single ChatGPT conversation should become a critical dependency for the project.

### Rationale

The project will span multiple weeks and conversations.

The durable project state must live outside any one chat.

### Consequence

Every weekly working chat should end by updating:

```text
docs/PROJECT_STATE.md
```

and, when needed:

```text
docs/DECISIONS.md
```

The next chat should be able to reconstruct the project using:

- ChiEAC Project Brief;
- GitHub;
- Project State;
- Decision Log.

---

# Decision 027 — New Weekly Chats Must Verify Handoff Before Coding

**Status:** Accepted

A new weekly chat should not immediately generate implementation code.

It must first summarize:

1. current state;
2. completed and locked work;
3. current gate requirements;
4. unresolved questions;
5. next implementation checkpoint.

Khai verifies this summary before development continues.

### Rationale

This catches misunderstandings before they become code changes.

### Consequence

A successful handoff is demonstrated by accurate state reconstruction, not by simply having access to the repository.

---

# Decision 028 — Code Guidance Must Be Precise

**Status:** Accepted

When guiding Khai through code changes, instructions should specify:

```text
file
→ function or search string
→ exact block
→ what to add or replace
```

### Rationale

The codebase will grow substantially.

Vague instructions create unnecessary errors and make learning harder.

### Consequence

Avoid directions such as:

> Change the logic near the middle of the file.

Prefer:

> Open `src/ingest.py`, search for `normalize_size()`, replace the block beginning with X and ending before Y.

---

# Decision 029 — Khai Should Understand the Build, Not Merely Receive Generated Code

**Status:** Accepted

The working model is:

```text
ChatGPT → technical mentor / pair designer
VS Code → Khai's development workspace
GitHub → shared implementation source of truth
```

### Rationale

The fellowship project should strengthen Khai's ability to discuss and defend the work in:

- interviews;
- portfolio reviews;
- future technical work.

### Consequence

Explain meaningful technical and business reasoning before or alongside implementation.

Do not unnecessarily automate away the learning process.

---

# Decision 030 — External Role Title

**Status:** Accepted

When representing the ChiEAC role externally, use:

**Business Intelligence & Supply Chain Analytics Fellow**

### Rationale

This is the title stated on Khai's job offer and accurately reflects the supply-chain analytics focus of the project.

### Consequence

Do not default to:

```text
Data Science Fellow
```

in outreach, signatures, portfolio descriptions, or professional communication unless Khai explicitly chooses to use that designation in a specific context.

---

# Decision 031 — Partner Survey Minimum Required Fields

**Status:** Accepted

The Partner Intake Survey is optional as an application input.

When a survey file or survey record is provided, the minimum required canonical fields are:

```text
site_name
zip_code
agency_type
families_served_per_month
```

The following fields remain optional enrichment fields:

```text
children_under_4_per_month
menstruating_clients_per_month
poverty_share_band
priority_population_flags
storage_capacity_cases
distribution_frequency
recent_stockout_sizes
preferred_contact
languages_spoken
```

### Rationale

The project brief treats the Partner Intake Survey itself as optional.

Requiring every enrichment field would unnecessarily reject usable partner data and make adoption harder.

Optional fields may improve later forecasting, equity weighting, storage constraints, or reporting, but their absence should not make the entire survey invalid.

### Consequence

Pandera validation must require only the four minimum fields above when survey data is supplied.

Missing optional fields may reduce available functionality or trigger a clearly explained fallback, but should not invalidate the whole survey.

The Streamlit survey form may still encourage users to provide additional fields without making them mandatory at the ingestion-contract level.

---

# Decision 032 — Recent Stockouts Use Product-Qualified Identifiers

**Status:** Accepted

The preferred canonical representation for `recent_stockout_sizes` is:

```text
product:size
```

Examples:

```text
diaper:4
pull_up:3T-4T
period_pad:regular
period_tampon:super
adult_incontinence:L
```

### Rationale

Some size labels are shared across multiple products.

Examples such as:

```text
regular
one_size
```

are ambiguous without product context.

### Consequence

Week 2 ingestion should normalize product-qualified identifiers directly.

A bare size value may be automatically converted only when it maps unambiguously to exactly one canonical product-size combination.

Ambiguous bare values must be flagged rather than guessed.

Existing synthetic bare diaper sizes such as:

```text
4
5
6
```

may be safely normalized to:

```text
diaper:4
diaper:5
diaper:6
```

because those values are unambiguous in the current controlled vocabulary.

---

# Decision 033 — Conservative Pack-to-Unit Parsing

**Status:** Accepted

Canonical quantities remain individual units.

Version 1 will automatically normalize only quantity formats whose meaning is deterministic.

Examples that may be accepted:

```text
300
300.0
300 units
12 packs x 25 units
12 pack x 25 units
```

when they resolve to a non-negative whole number of individual units.

### Rationale

Forecasting, inventory analysis, and allocation depend on a consistent unit of measure.

Guessing pack sizes or interpreting ambiguous text could silently corrupt all downstream analytics.

### Consequence

Values such as:

```text
12 packs
about 300
12 cases x ?
```

must be flagged for user correction rather than guessed.

Negative quantities are invalid.

Numeric values containing a fractional unit are invalid unless the numeric value is mathematically equivalent to a whole number, such as `300.0`.

The data-quality summary must report quantity conversions and unresolved quantity errors.

---

# Decision 034 — Missing Site IDs Are Generated Deterministically

**Status:** Accepted

If a Distribution Log provides a valid `site_id`, the application's ingestion layer preserves it.

If `site_id` is missing, the application generates a deterministic identifier from normalized `site_name`.

The generated identifier should use a readable normalized slug with an `AUTO_` prefix.

Example:

```text
Hope Community Center
```

may normalize to:

```text
AUTO_HOPE_COMMUNITY_CENTER
```

If normalized site names collide, the identifier must receive a short deterministic suffix rather than depending on row order.

### Rationale

Row-number-based identifiers such as:

```text
SITE_001
SITE_002
```

could change when new records are inserted or file ordering changes.

A deterministic identifier provides more stable reconciliation across uploads.

### Consequence

Generated identifiers must not depend on dataframe row position.

Survey records, which do not currently contain `site_id`, will be reconciled to distribution-history sites through normalized `site_name`.

Survey-only new partners may receive a generated identifier using the same deterministic rule.

---

# Decision 035 — Duplicate Handling Depends on Input Semantics

**Status:** Accepted

Duplicate detection is required, but Version 1 must not apply a universal automatic `drop_duplicates()` rule.

### Distribution Log

Exact duplicate rows are detected and reported as warnings.

They are preserved by default because the current data contract has no transaction identifier and identical distributions may represent separate valid transactions.

### Incoming Supply

Exact duplicate rows are detected and reported as warnings.

They are preserved by default because separate donations, purchases, or shipments may share the same visible attributes.

### Current Inventory

Multiple rows with the same canonical snapshot key:

```text
as_of_date
product
size
location
```

are treated as an unresolved validation problem.

The application must not silently sum or drop them until the user resolves the ambiguity.

### Partner Survey

More than one row for the same normalized `site_name` is treated as an unresolved validation problem because the canonical expectation is one current survey record per partner.

### Rationale

The meaning of a duplicate differs by dataset.

Automatically dropping records could understate real transactions, while automatically summing duplicated inventory could materially overstate available supply.

### Consequence

The data-quality experience must distinguish:

```text
warnings
blocking validation problems
automatic corrections
```

Duplicate behavior must be tested separately for each canonical input.

---

# Pending Decisions

The original Week 2 ingestion questions have been resolved as follows:

- P1 — Partner Survey requiredness → resolved by Decision 031.
- P2 — Recent stockout representation → resolved by Decision 032.
- P3 — Pack parsing rules → resolved by Decision 033.
- P4 — Missing `site_id` behavior → resolved by Decision 034.
- P5 — Duplicate definition and handling → resolved by Decision 035.

No additional ingestion-contract decision is currently blocking Week 2 implementation.

---

# Decision Log Maintenance

Add a new decision when a choice:

- affects future architecture;
- changes the data contract;
- changes analytical behavior;
- affects multiple future gates;
- would be easy for a future contributor to unknowingly reverse.

Do not add routine implementation details.

For a new accepted decision, document:

```text
Decision
Status
Rationale
Consequence
```

If an accepted decision is later changed:

1. do not delete the original history;
2. mark it superseded;
3. reference the new decision;
4. explain why the change was necessary.