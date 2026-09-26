# Partner Intake Survey Specification

## Purpose

The Partner Intake Survey collects organization-level information from partner agencies that may not exist in routine distribution records.

The survey supports two core functions in the Diaper & Period Supply Bank Allocator:

1. Cold-start demand forecasting for new or low-history partner sites.
2. Equity weighting for allocation decisions.

The survey is designed to take approximately five minutes to complete.

No individual-client data should be collected.

---

## Delivery Modes

The same survey structure should be supported in two formats:

1. Google Form
   - Used when partner agencies complete the survey directly.
   - Responses may be exported as CSV and uploaded to the application.

2. Streamlit Form
   - Used when supply bank staff enter or review partner information inside the app.
   - Uses the same controlled values and data contract as the Google Form.

The Streamlit implementation should preserve the same field names and controlled values used in the project data dictionary.

---

## Implementation Note

The project brief defines the information that must be collected but does not prescribe which individual questions must be required.

The required/optional choices below are project implementation decisions intended to balance data quality with ease of completion.

---

## Section 1 — Partner Information

### Partner Agency Name

**Canonical field**

`site_name`

**Question**

Partner agency name

**Streamlit widget**

`st.text_input`

**Required**

Yes

**Validation**

- Must not be blank.
- Leading and trailing whitespace should be removed.

**Purpose**

Identifies the partner site and connects survey information to distribution history.

---

### ZIP Code

**Canonical field**

`zip_code`

**Question**

ZIP code

**Streamlit widget**

`st.text_input`

**Required**

Yes

**Validation**

- Store as text rather than numeric.
- Preserve leading zeroes if present.
- Trim leading and trailing whitespace.

**Purpose**

Provides geographic context without collecting individual client addresses.

---

### Agency Type

**Canonical field**

`agency_type`

**Question**

Type of agency

**Streamlit widget**

`st.selectbox`

**Required**

Yes

**Allowed values**

- shelter
- wic_clinic
- school
- pantry
- health_center
- faith_community
- other

**Display labels**

- Shelter
- WIC clinic
- School
- Pantry
- Health center
- Faith community
- Other

**Purpose**

Agency type may be used in cold-start forecasting because different service environments may have different demand patterns.

---

## Section 2 — Monthly Service Population

Display helper text:

> Please provide approximate monthly figures. Best estimates are acceptable.

---

### Families Served Per Month

**Canonical field**

`families_served_per_month`

**Question**

Approximately how many families does your organization serve per month?

**Streamlit widget**

`st.number_input`

**Required**

Yes

**Validation**

- Minimum value: 0
- Integer values only

**Purpose**

Provides a scale variable for estimating demand when historical distribution data is limited.

---

### Children Under 4 Served Per Month

**Canonical field**

`children_under_4_per_month`

**Question**

Approximately how many children under age 4 does your organization serve per month?

**Streamlit widget**

`st.number_input`

**Required**

Yes

**Validation**

- Minimum value: 0
- Integer values only

**Purpose**

Supports diaper and pull-up demand estimation.

---

### Menstruating Clients Served Per Month

**Canonical field**

`menstruating_clients_per_month`

**Question**

Approximately how many menstruating clients does your organization serve per month?

**Streamlit widget**

`st.number_input`

**Required**

Yes

**Validation**

- Minimum value: 0
- Integer values only

**Purpose**

Supports demand estimation for period products.

---

## Section 3 — Community Need

### Poverty Share Band

**Canonical field**

`poverty_share_band`

**Question**

Approximately what share of your clients are below the federal poverty line?

**Streamlit widget**

`st.selectbox`

**Required**

Yes

**Allowed values**

- under_25_percent
- 25_to_50_percent
- 50_to_75_percent
- over_75_percent

**Display labels**

- Under 25%
- 25% to 50%
- 50% to 75%
- Over 75%

**Purpose**

Provides an input to the equity-weighting logic used during allocation.

---

### Priority Population Flags

**Canonical field**

`priority_population_flags`

**Question**

Which priority populations does your organization serve?

**Streamlit widget**

`st.multiselect`

**Required**

No

**Allowed values**

- emergency_shelter
- domestic_violence_program
- teen_parents
- refugee_or_newly_arrived_families
- students
- families_with_child_with_disability

**Display labels**

- Emergency shelter
- Domestic violence program
- Teen parents
- Refugee or newly arrived families
- Students
- Families with a child with a disability

**Storage format**

Store selected values as a list or serialize them consistently when exporting to CSV.

**Purpose**

Supports equity weighting by identifying organizations serving priority populations.

---

## Section 4 — Operations and Supply

### Storage Capacity

**Canonical field**

`storage_capacity_cases`

**Question**

Approximately how much storage capacity is available for these supplies?

**Help text**

Estimate the number of cases your organization can reasonably store at one time.

**Streamlit widget**

`st.number_input`

**Required**

Yes

**Validation**

- Minimum value: 0
- Integer values only

**Purpose**

May constrain allocation recommendations so the application does not recommend more product than a partner can reasonably store.

---

### Distribution Frequency

**Canonical field**

`distribution_frequency`

**Question**

How often does your organization typically distribute supplies?

**Streamlit widget**

`st.selectbox`

**Required**

Yes

**Allowed values**

- weekly
- biweekly
- monthly

**Display labels**

- Weekly
- Biweekly
- Monthly

**Purpose**

Provides operational context for planning and allocation cycles.

---

### Recent Stockout Sizes

**Canonical field**

`recent_stockout_sizes`

**Question**

Which product sizes has your organization run out of during the last 90 days?

**Streamlit widget**

`st.multiselect`

**Required**

No

**Instruction**

Select all that apply. Leave blank if there were no recent stockouts.

**Supported product-size options**

### Diapers

- N
- 1
- 2
- 3
- 4
- 5
- 6
- 7

### Pull-ups

- 2T-3T
- 3T-4T
- 4T-5T

### Adult incontinence

- S
- M
- L
- XL

### Period pads

- regular
- super
- overnight

### Tampons

- regular
- super
- super_plus

### Other period products

- period_liner: one_size
- period_cup: one_size

**Recommended storage format**

Use explicit product-size identifiers rather than storing size alone.

Examples:

- `diaper:4`
- `diaper:5`
- `pull_up:3T-4T`
- `period_pad:overnight`
- `period_tampon:super`
- `adult_incontinence:L`

This prevents ambiguity because the same size label may exist for multiple product categories.

**Purpose**

Provides qualitative evidence of recent demand-supply mismatches.

---

## Section 5 — Contact and Communication

### Preferred Contact

**Canonical field**

`preferred_contact`

**Question**

Preferred contact

**Help text**

Provide the preferred contact name and/or email or phone number for follow-up.

**Streamlit widget**

`st.text_input`

**Required**

No

**Purpose**

Allows supply bank staff to follow up with the partner organization when needed.

This field should not be used in forecasting, allocation, or equity calculations.

---

### Languages Spoken

**Canonical field**

`languages_spoken`

**Question**

What languages are commonly spoken by the clients your organization serves?

**Streamlit widget**

`st.multiselect` or `st.text_input`

**Required**

No

**Recommended implementation**

Use a multiselect containing common languages plus an "Other" option.

For the initial version, a free-text input is acceptable if language vocabulary has not yet been standardized.

**Purpose**

Provides communication and service-access context.

This field should not directly change forecast or allocation calculations in the initial version.

---

## Privacy Requirements

The form must collect organization-level information only.

Do not request:

- Client names
- Client addresses
- Dates of birth
- Medical information
- Immigration status
- Government identification numbers
- Individual household records

Display the following note near the beginning of the form:

> Please do not provide information about individual clients. Responses should contain organization-level estimates only.

---

## Streamlit Form Behavior

The Streamlit form should use:

```python
with st.form("partner_intake_form"):
```

The form should be divided visually into the following sections:

1. Partner Information
2. Monthly Service Population
3. Community Need
4. Operations and Supply
5. Contact and Communication

A single submit button should appear at the bottom:

```python
st.form_submit_button("Save Partner Survey")
```

Submission should not proceed if required fields are missing or invalid.

Validation errors should be written in plain language.

Example:

> Please enter the approximate number of families served per month.

Instead of:

> Invalid integer value.

---

## Output Schema

A successfully submitted survey should produce one record with the following canonical fields:

| Field | Expected Type |
|---|---|
| site_name | text |
| zip_code | text |
| agency_type | text |
| families_served_per_month | integer |
| children_under_4_per_month | integer |
| menstruating_clients_per_month | integer |
| poverty_share_band | text |
| priority_population_flags | list/text |
| storage_capacity_cases | integer |
| distribution_frequency | text |
| recent_stockout_sizes | list/text |
| preferred_contact | text |
| languages_spoken | list/text |

The exported result must remain compatible with the partner survey input defined in `docs/data_dictionary.md`.

---

## Downstream Use

Survey fields should be used only where their meaning supports the calculation.

### Cold-start Forecasting

Primary inputs may include:

- `agency_type`
- `families_served_per_month`
- `children_under_4_per_month`
- `menstruating_clients_per_month`

Survey-based forecasts should be clearly labeled as estimates until sufficient historical distribution data exists.

### Equity Weighting

Primary inputs may include:

- `poverty_share_band`
- `priority_population_flags`

### Allocation Constraints

Primary input:

- `storage_capacity_cases`

### Context Only

The following fields should initially remain informational rather than directly changing model calculations:

- `recent_stockout_sizes`
- `preferred_contact`
- `languages_spoken`

---

## Google Form Compatibility

The Google Form and Streamlit form should collect equivalent concepts.

Human-readable Google Form responses must be normalized to the canonical values in the data contract during ingestion.

Examples:

| Google Form Response | Canonical Value |
|---|---|
| WIC clinic | wic_clinic |
| Health center | health_center |
| Faith community | faith_community |
| 25% to 50% | 25_to_50_percent |
| Over 75% | over_75_percent |
| Biweekly | biweekly |

The ingestion layer should perform this normalization rather than requiring partner organizations to enter machine-readable codes.

---

## Recent Stockout Normalization

Because some size labels are shared across different product categories, stockout responses should be stored with both the product and size whenever possible.

Examples:

```text
diaper:4
diaper:5
pull_up:3T-4T
period_pad:overnight
period_tampon:regular
adult_incontinence:L
```

This avoids ambiguity in values such as:

```text
regular
L
one_size
```

The Google Form may display human-readable labels, while the ingestion layer converts them into canonical product-size identifiers.

---

## Privacy and Data Handling

The application should collect organization-level information only.

The survey should not request or store:

- Client names
- Client addresses
- Dates of birth
- Medical information
- Immigration status
- Government identification numbers
- Individual household records

The Streamlit survey should display the following privacy note:

> Please do not provide information about individual clients. Responses should contain organization-level estimates only.

Survey responses should be used only for planning, forecasting, allocation, and operational context within the application.

---

## Validation Rules

Before accepting a survey submission, the Streamlit form should validate the following:

### Required Text Fields

The following field must not be blank:

- `site_name`

Leading and trailing whitespace should be removed.

### Numeric Fields

The following fields must contain non-negative integer values:

- `families_served_per_month`
- `children_under_4_per_month`
- `menstruating_clients_per_month`
- `storage_capacity_cases`

Values below zero should not be accepted.

### Controlled Categories

The following fields must map to approved values from the data contract:

- `agency_type`
- `poverty_share_band`
- `distribution_frequency`

### Optional Multi-Select Fields

The following fields may be empty:

- `priority_population_flags`
- `recent_stockout_sizes`
- `languages_spoken`

An empty selection should be interpreted as no response or no applicable values rather than as invalid data.

---

## User Experience Requirements

The form should remain simple enough for a partner organization or supply bank staff member to complete in approximately five minutes.

The interface should:

- Use plain-language labels.
- Avoid technical field names in the visible form.
- Show short helper text where estimates are acceptable.
- Keep related questions grouped together.
- Avoid unnecessary questions.
- Avoid asking the same information more than once.
- Clearly distinguish required and optional fields.
- Use controlled selections where standardization matters.
- Allow free text only where controlled categories are not necessary.

Machine-readable field names should remain internal to the application.

For example:

```text
Visible label:
Approximately how many families does your organization serve per month?

Internal field:
families_served_per_month
```

---

## Submission Behavior

When the user selects:

```python
st.form_submit_button("Save Partner Survey")
```

the application should:

1. Validate required fields.
2. Normalize categorical values to the canonical data contract.
3. Normalize multi-select responses.
4. Trim unnecessary whitespace.
5. Create one partner survey record.
6. Display a clear success message if validation passes.

Example success message:

> Partner survey saved successfully.

If validation fails, the application should explain what needs to be corrected without clearing the user's other responses whenever possible.

---

## Streamlit Output Example

A normalized survey record may look like:

```python
{
    "site_name": "Community Family Center",
    "zip_code": "60608",
    "agency_type": "pantry",
    "families_served_per_month": 180,
    "children_under_4_per_month": 75,
    "menstruating_clients_per_month": 95,
    "poverty_share_band": "over_75_percent",
    "priority_population_flags": [
        "teen_parents",
        "refugee_or_newly_arrived_families"
    ],
    "storage_capacity_cases": 40,
    "distribution_frequency": "biweekly",
    "recent_stockout_sizes": [
        "diaper:4",
        "diaper:5",
        "period_pad:overnight"
    ],
    "preferred_contact": "program@example.org",
    "languages_spoken": [
        "English",
        "Spanish"
    ]
}
```

This example is illustrative only.

---

## Version 1 Scope

The initial Streamlit survey should remain intentionally simple.

Version 1 should:

- Collect the defined partner-level fields.
- Validate required numeric and categorical inputs.
- Normalize responses to the project data contract.
- Support cold-start forecasting.
- Support equity weighting.
- Support storage-capacity constraints.
- Avoid individual-client information.
- Remain compatible with Google Form exports.

Version 1 should not:

- Create user accounts.
- Store sensitive individual-level records.
- Require external databases.
- Introduce additional survey fields without updating the data dictionary.
- Automatically infer demographic characteristics not provided by the partner.
- Use contact information in forecasting or allocation calculations.

---

## Future Implementation Notes

When the Streamlit version is built, the survey logic should be separated from the user interface where practical.

Recommended responsibilities:

```text
Streamlit form
    ↓
collect raw responses
    ↓
validation
    ↓
normalization
    ↓
canonical survey record
    ↓
forecast / allocation pipeline
```

This separation will make the survey easier to test and will allow Google Form CSV exports and Streamlit submissions to use the same downstream normalization logic.

---

## Acceptance Criteria

The Partner Intake Survey specification is complete when:

- All canonical survey fields from the data contract are represented.
- Google Form and Streamlit concepts are aligned.
- Controlled categories have documented mappings.
- Required and optional fields are documented.
- Numeric validation rules are defined.
- Privacy requirements are documented.
- Cold-start forecasting fields are identified.
- Equity-weighting fields are identified.
- Storage-capacity usage is identified.
- Stockout responses can be normalized without product-size ambiguity.
- The specification can be implemented without changing the core survey data contract.