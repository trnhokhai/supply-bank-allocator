# Data Dictionary

## 1. Distribution Log

Historical distribution records used to estimate future demand by partner site, product, and size.

| Column | Type | Required | Description |
|---|---|---|---|
| `date` | date | Yes | Distribution date. Daily or weekly granularity is accepted. The application will aggregate records to ISO weeks. |
| `site_id` | text | No | Stable identifier for the partner site. If missing, the application may generate one from `site_name`. |
| `site_name` | text | Yes | Name of the partner agency receiving the distributed product. |
| `product` | text | Yes | Product category. Allowed values are defined below. |
| `size` | text | Yes | Product size or variant. Allowed values depend on the selected product category. |
| `quantity` | integer | Yes | Number of individual units distributed, not packs. |
| `households_served` | integer | No | Number of households served during the distribution record. Used for optional per-family reporting metrics. |
| `children_served` | integer | No | Number of children served during the distribution record. Used for optional impact reporting metrics. |

### Allowed Product Values

- `diaper`
- `pull_up`
- `wipes`
- `period_pad`
- `period_tampon`
- `period_liner`
- `period_cup`
- `adult_incontinence`

### Allowed Size Values

**Diapers**
- `N`
- `1`
- `2`
- `3`
- `4`
- `5`
- `6`
- `7`

**Pull-ups**
- `2T-3T`
- `3T-4T`
- `4T-5T`

**Adult incontinence**
- `S`
- `M`
- `L`
- `XL`

**Pads**
- `regular`
- `super`
- `overnight`

**Tampons**
- `regular`
- `super`
- `super_plus`

**Liners and cups**
- `one_size`

**Wipes**
- `one_size`

### Notes

- `quantity` must represent individual units rather than packages or cases.
- A pack-to-unit conversion will be supported in the template/application.
- The application will normalize size values to the controlled vocabulary above.

## 2. Current Inventory

Current inventory snapshot used to determine available supply by product and size.

| Column | Type | Required | Description |
|---|---|---|---|
| `as_of_date` | date | Yes | Date when the inventory count was taken. The application will warn the user if the inventory snapshot is more than 14 days old. |
| `product` | text | Yes | Product category. Uses the same controlled product values as the Distribution Log. |
| `size` | text | Yes | Product size or variant. Uses the same controlled size vocabulary as the Distribution Log. |
| `quantity_on_hand` | integer | Yes | Number of individual units currently available in inventory. |
| `location` | text | No | Warehouse or storage location. If multiple locations are provided, the application will sum inventory across locations by default. |

### Notes

- Inventory quantities must be reported in individual units.
- The application uses this file as the current on-hand supply baseline.
- If multiple storage locations exist, each location may be listed separately.
- The application will aggregate inventory across locations unless the user chooses otherwise.

## 3. Incoming Donations and Purchases

Expected future supply from donors, drives, or purchases. This file helps the application determine what inventory is expected to become available during the planning horizon.

| Column | Type | Required | Description |
|---|---|---|---|
| `expected_date` | date | Yes | Date when the incoming product is expected to become available for allocation. |
| `source` | text | Yes | Name of the donor, donation drive, vendor, or other supply source. |
| `product` | text | Yes | Product category. Uses the same controlled product values as the Distribution Log. |
| `size` | text | Yes | Product size or variant. Uses the same controlled size vocabulary as the Distribution Log. The value `unknown` is allowed for donation drives when the size mix is not yet known. |
| `quantity` | integer | Yes | Number of expected individual units. |
| `status` | text | Yes | Supply status. Allowed values are `confirmed` and `pending`. |

### Allowed Status Values

- `confirmed`
- `pending`

### Notes

- Confirmed incoming supply is included in the baseline planning calculation if it is expected to arrive within the planning cycle.
- Pending incoming supply is excluded from the baseline plan by default.
- Pending supply may be included through the scenario analysis feature.
- For donation drives with an unknown size mix, `size` may be recorded as `unknown`.
- When `size = unknown`, the application may apply the bank's historical donation size mix to estimate the expected breakdown by size.

## 4. Partner Intake Survey

Partner-level information used to support equity weighting, storage constraints, cold-start forecasting, and operational context for each participating agency.

| Field | Type | Required | Description |
|---|---|---|---|
| `site_name` | text | Yes | Name of the partner agency. Should match the site name used in the Distribution Log when possible. |
| `zip_code` | text | Yes | ZIP code of the partner agency. |
| `agency_type` | text | Yes | Type of partner organization. Allowed values are defined below. |
| `families_served_per_month` | integer | Yes | Approximate number of families served by the partner each month. |
| `children_under_4_per_month` | integer | No | Approximate number of children under age 4 served each month. |
| `menstruating_clients_per_month` | integer | No | Approximate number of menstruating clients served each month. |
| `poverty_share_band` | text | No | Approximate share of clients below the federal poverty line. Used as an input to equity weighting. |
| `priority_population_flags` | text/list | No | Indicates whether the partner serves one or more priority populations. Multiple values may apply. |
| `storage_capacity_cases` | integer | No | Approximate storage capacity in cases. May be used as an allocation constraint. |
| `distribution_frequency` | text | No | How often the partner distributes products. |
| `recent_stockout_sizes` | text/list | No | Product sizes the partner has run out of during the last 90 days. |
| `preferred_contact` | text | No | Preferred contact person or contact method for the partner. |
| `languages_spoken` | text/list | No | Languages commonly spoken by the partner's clients or staff. |

### Allowed Agency Type Values

- `shelter`
- `wic_clinic`
- `school`
- `pantry`
- `health_center`
- `faith_community`
- `other`

### Allowed Poverty Share Bands

- `under_25_percent`
- `25_to_50_percent`
- `50_to_75_percent`
- `over_75_percent`

### Priority Population Flags

Possible flags include:

- `emergency_shelter`
- `domestic_violence_program`
- `teen_parents`
- `refugee_or_newly_arrived_families`
- `students`
- `families_with_child_with_disability`

### Allowed Distribution Frequencies

- `weekly`
- `biweekly`
- `monthly`

### Notes

- The survey may be completed directly in the Streamlit application or collected through Google Forms and uploaded as CSV.
- Survey information enables equity weighting and cold-start forecasts for new partners with limited or no historical distribution data.
- If survey data is unavailable, the application will use equal equity weights.
- Storage capacity may be used to prevent allocation plans from assigning more product than a partner can reasonably store.