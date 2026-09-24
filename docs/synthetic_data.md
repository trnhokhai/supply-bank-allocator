# Synthetic Data Specification

## Purpose

This document defines the synthetic dataset used to develop, test, and demonstrate the Diaper and Period Supply Bank Allocator.

The synthetic data is designed to resemble realistic supply-bank operations while remaining fully artificial. No real partner, family, donor, or client data is included.

## 1. Requirements from the Project Brief

The synthetic dataset must include:

- 78 weeks of weekly distribution history
- 25 partner sites with mixed agency types
- 10 of the 25 partner sites distributing period products
- Diaper demand concentrated most heavily in sizes 4 and 5
- Newborn (`N`) and size 7 as the lowest-volume diaper sizes
- Pull-ups distributed at 8 partner sites
- Adult incontinence products distributed at 3 partner sites
- Donation inflow biased toward diaper sizes `N`, `1`, and `2`
- Two large donation drives per year
- A summer donation trough
- Two partner sites that begin operations partway through the 78-week history
- One partner site with a six-week gap in distribution activity
- Approximately 3% of distribution records containing deliberately messy values for validation testing
- A current inventory snapshot containing visible overstock and shortage conditions
- An incoming supply dataset containing both `confirmed` and `pending` records
- A completed partner intake survey for every partner site
- Reproducible generation using a fixed random seed

## 2. Files Generated

The generator will create four primary datasets:

1. `distribution_log`
2. `current_inventory`
3. `incoming_supply`
4. `partner_survey`

The files will follow the schemas defined in `docs/data_dictionary.md`.

## 3. Distribution History Design

### Time Horizon

- 78 consecutive weeks
- Weekly distribution behavior generated for each active partner
- Records stored using distribution dates and later aggregated by ISO week when needed

### Partner Sites

- 25 total partner sites
- Mixed agency types
- Two sites will begin partway through the historical period
- One site will contain a six-week inactive gap

### Product Coverage

The dataset will include:

- Diapers
- Pull-ups
- Wipes
- Period pads
- Period tampons
- Period liners
- Period cups
- Adult incontinence products

Period products will be present at 10 partner sites.

Pull-ups will be present at 8 partner sites.

Adult incontinence products will be present at 3 partner sites.

Product coverage will be assigned using agency-type-informed weighted random sampling rather than uniform random selection. The generator will still enforce exactly 10 period-product sites, 8 pull-up sites, and 3 adult-incontinence sites while giving higher selection probability to agency types that are more plausible for each product category.

## 4. Diaper Size-Mix Design

The generated demand pattern will intentionally place the highest demand in:

- Size 4
- Size 5

The lowest demand will occur in:

- Newborn (`N`)
- Size 7

The exact percentage mix will be defined before implementation and validated after generation.

## 5. Donation Supply Design

Synthetic incoming donations will intentionally differ from demand.

Donation inflow will be biased toward:

- Newborn (`N`)
- Size 1
- Size 2

The donation pattern will include:

- Two large donation drives per year
- Lower donation volume during the summer period
- Both confirmed and pending incoming supply

This mismatch is intentional so the application can identify inventory-versus-demand imbalance.

## 6. Inventory Snapshot Design

The current inventory snapshot will contain deliberately visible:

- Overstocked product-size combinations
- Understocked product-size combinations

The inventory design should allow the application to identify long and short sizes during later testing.

## 7. Data Quality Test Cases

Approximately 3% of distribution records will contain deliberately messy values.

Planned validation cases include:

- Inconsistent capitalization
- Non-standard size labels
- Renamed or inconsistent headers
- Pack quantities that require conversion to individual units

These cases exist only to test the application's ingestion and validation logic.

## 8. Partner Survey Design

Every partner site will receive a completed synthetic survey record.

Survey information will include operational and equity-related fields defined in the data dictionary, such as:

- Agency type
- Families served
- Children under age 4 served
- Menstruating clients served
- Poverty-share band
- Priority-population flags
- Storage capacity
- Distribution frequency
- Recent stockout sizes
- Preferred contact
- Languages spoken

## 9. Reproducibility

The synthetic data generator will use a fixed random seed.

Running the generator with the same seed should reproduce the same dataset.

Default seed:

`42`

## 10. Validation Checks

After generation, the dataset will be checked to confirm:

- 78 weeks are present
- 25 partner sites are present
- 10 sites contain period-product activity
- 8 sites contain pull-up activity
- 3 sites contain adult incontinence activity
- Sizes 4 and 5 lead diaper demand
- Newborn and size 7 have the lowest diaper demand
- Donations are weighted toward N, 1, and 2
- Two mid-series partner starts exist
- One six-week activity gap exists
- Approximately 3% of rows contain planted data-quality issues
- Both confirmed and pending incoming supply records exist
- Every partner has a survey record

Quick validation charts will be produced for:

- Diaper demand size mix
- Donation size mix

## 11. Finalized Synthetic Data Design Decisions

The following assumptions are implementation choices made to create a realistic and testable synthetic dataset. They are not fixed values from the project brief, but they are designed to satisfy the brief's required patterns and support later forecasting, allocation, alerting, and scenario testing.

### 11.1 Partner Agency Mix

The synthetic network will contain 25 partner sites with the following agency-type mix:

- 6 pantries
- 5 shelters
- 4 WIC clinics
- 4 schools
- 3 health centers
- 2 faith communities
- 1 community center / other

Product coverage across the 25 sites will include:

- 10 sites distributing period products
- 8 sites distributing pull-ups
- 3 sites distributing adult incontinence products

Not every site will distribute every product category.

### 11.2 Baseline Diaper Demand Size Mix

The network-level baseline diaper demand mix will be approximately:

| Size | Share of Diaper Demand |
|---|---:|
| N | 3% |
| 1 | 8% |
| 2 | 12% |
| 3 | 17% |
| 4 | 24% |
| 5 | 23% |
| 6 | 10% |
| 7 | 3% |

This design ensures that:

- Sizes 4 and 5 have the highest demand
- Newborn (`N`) and size 7 have the lowest demand

Agency-specific demand profiles will modify the network baseline.

Examples:

- Shelters will skew slightly toward larger diaper sizes
- WIC clinics will skew slightly toward smaller diaper sizes
- Pantries and community sites will remain closer to the network-average mix

### 11.3 Partner Demand Scale

Partner sites will be assigned to one of three approximate weekly demand tiers:

- Small: 400–800 units per week
- Medium: 800–1,500 units per week
- Large: 1,500–2,500 units per week

Each partner will receive its own:

- Agency type
- Demand tier
- Base weekly demand
- Product coverage
- Product and size mix

This creates heterogeneous demand patterns across the network rather than identical behavior across all sites.

### 11.4 Weekly Demand Generation

Weekly demand will be generated using a structure similar to:

`weekly demand = base demand × site profile × product/size mix × seasonal factor × random variation`

Random weekly demand variation will generally remain within approximately 10–15% of the expected value.

Rare products and low-volume size combinations may contain more intermittent demand and zero-demand weeks.

### 11.5 Donation Size Mix

Donation inflow will intentionally differ from actual diaper demand.

The approximate diaper donation size mix will be:

| Size | Share of Diaper Donations |
|---|---:|
| N | 22% |
| 1 | 24% |
| 2 | 20% |
| 3 | 14% |
| 4 | 9% |
| 5 | 6% |
| 6 | 4% |
| 7 | 1% |

This creates a deliberate supply-demand mismatch:

- Donations are concentrated in N, 1, and 2
- Demand is concentrated in 4 and 5

This mismatch will support later testing of inventory-risk and size-mismatch analytics.

### 11.6 Donation Seasonality

Donation volume will include:

- One large spring donation drive
- One large holiday donation drive
- A summer donation trough

Initial multipliers:

- Spring drive: approximately 2.0× normal volume
- Holiday drive: approximately 2.3× normal volume
- Summer trough: approximately 0.65× normal volume

These values may be adjusted during validation if the resulting donation pattern is unrealistic.

### 11.7 Current Inventory Test Conditions

The current inventory snapshot will intentionally contain visible long and short diaper sizes.

Target approximate weeks-of-supply conditions:

| Size | Target Weeks of Supply |
|---|---:|
| N | 16.0 |
| 1 | 15.0 |
| 2 | 13.0 |
| 3 | 7.0 |
| 4 | 4.0 |
| 5 | 1.8 |
| 6 | 2.2 |
| 7 | 5.0 |

This should create:

- Long inventory positions in N, 1, and 2
- Short inventory positions in 5 and 6

The planted conditions will later be used to validate the alerting logic.

### 11.8 New Partner and Activity-Gap Test Cases

Three special partner-history cases will be included:

- Site 24 begins activity around week 30
- Site 25 begins activity around week 50
- Site 08 contains a six-week inactive gap around weeks 35–40

These cases will support testing of:

- Mid-series onboarding
- Cold-start forecasting
- Inactive-span detection
- Missing-week handling

### 11.9 Deliberately Messy Data

Approximately 3% of distribution records will contain planted data-quality issues.

Planned row-level issues include:

- Mixed capitalization
- Non-standard size labels
- Extra whitespace
- Pack quantities that require conversion to individual units

Examples may include:

- `SIZE5`
- `size 5`
- `5 `
- Pack-based quantities rather than unit quantities

Header-mapping tests will be handled separately using alternate input files with renamed headers such as:

- `Agency`
- `Partner`
- `Qty`

This avoids treating header problems as row-level issues.

### 11.10 Partner Survey Generation

Every partner will receive one synthetic survey record.

Survey values will be generated in a way that is consistent with each partner's operating profile.

Examples:

- Larger shelters may serve more families and have more priority-population flags
- WIC clinics may serve more children under age 4
- Schools may report more student-related priority populations
- Storage capacity will vary by partner size and agency type
- Recent stockout sizes will be consistent with planted network shortages where appropriate

Survey values will support:

- Equity weighting
- Cold-start forecasts
- Storage-capacity constraints
- Scenario testing

### 11.11 Random Seed and Reproducibility

The default random seed will be:

`42`

Running the generator with the same seed should reproduce the same synthetic datasets.

### 11.12 Validation Expectations

After generation, validation should confirm that:

- Sizes 4 and 5 have the highest diaper demand
- N and size 7 have the lowest diaper demand
- Donations are concentrated in N, 1, and 2
- N, 1, and 2 appear long in inventory
- Sizes 5 and 6 appear short in inventory
- Site 24 and Site 25 begin partway through the history
- Site 08 contains a six-week inactivity gap
- Approximately 3% of distribution records contain planted data-quality issues
- Every partner has a survey record
- Product-coverage counts match the specification

Any design value may be adjusted if validation shows that the generated data does not realistically represent the intended planning problem.