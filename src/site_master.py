import pandas as pd

from src.ingest import (
    assign_site_ids,
    normalize_site_name,
)


class SiteMasterError(ValueError):
    """Raised when partner identities cannot be reconciled safely."""


SURVEY_FIELDS = [
    "zip_code",
    "agency_type",
    "families_served_per_month",
    "children_under_4_per_month",
    "menstruating_clients_per_month",
    "poverty_share_band",
    "priority_population_flags",
    "storage_capacity_cases",
    "distribution_frequency",
    "recent_stockout_sizes",
    "preferred_contact",
    "languages_spoken",
]


def _site_key(value):
    """
    Stable comparison key used only for exact partner
    reconciliation.

    Matching is case-insensitive and whitespace-normalized.
    Fuzzy matching is intentionally not used because two
    similarly named agencies may be different organizations.
    """

    return normalize_site_name(
        value
    ).casefold()


def _require_columns(
    dataframe,
    required_columns,
    table_name,
):
    missing = (
        set(required_columns)
        - set(dataframe.columns)
    )

    if missing:
        missing_text = ", ".join(
            sorted(missing)
        )

        raise SiteMasterError(
            f"{table_name} is missing required "
            f"column(s): {missing_text}."
        )


def build_site_master(
    distribution_df,
    survey_df=None,
):
    """
    Build one trusted partner record per site.

    Distribution history is authoritative for existing
    site IDs.

    Survey records are reconciled to distribution sites
    through normalized site_name.

    Survey-only partners receive deterministic AUTO_ site
    IDs and remain available for later cold-start workflows.
    """

    _require_columns(
        distribution_df,
        {
            "date",
            "site_id",
            "site_name",
        },
        table_name="Distribution history",
    )

    if distribution_df.empty:
        raise SiteMasterError(
            "Distribution history cannot be empty."
        )

    distribution = (
        distribution_df
        .copy()
        .reset_index(drop=True)
    )

    # -------------------------------------------------
    # Normalize and validate distribution identities
    # -------------------------------------------------

    distribution["site_name"] = (
        distribution["site_name"]
        .map(normalize_site_name)
    )

    missing_site_id = (
        distribution["site_id"].isna()
        |
        distribution["site_id"]
        .astype(str)
        .str.strip()
        .eq("")
    )

    if missing_site_id.any():
        raise SiteMasterError(
            "Distribution history must have resolved "
            "site IDs before building the site master."
        )

    distribution["site_id"] = (
        distribution["site_id"]
        .astype(str)
        .str.strip()
    )

    distribution["_site_key"] = (
        distribution["site_name"]
        .map(_site_key)
    )

    ids_per_name = (
        distribution
        .groupby("_site_key")[
            "site_id"
        ]
        .nunique()
    )

    if ids_per_name.gt(1).any():
        raise SiteMasterError(
            "The same normalized site name maps to "
            "multiple site IDs in distribution history."
        )

    names_per_id = (
        distribution
        .groupby("site_id")[
            "_site_key"
        ]
        .nunique()
    )

    if names_per_id.gt(1).any():
        raise SiteMasterError(
            "The same site ID maps to multiple "
            "different site names in distribution history."
        )

    parsed_dates = pd.to_datetime(
        distribution["date"],
        errors="coerce",
    )

    if parsed_dates.isna().any():
        raise SiteMasterError(
            "Distribution dates must be valid before "
            "building the site master."
        )

    distribution["date"] = (
        parsed_dates
    )

    distribution["_week_start"] = (
        parsed_dates
        - pd.to_timedelta(
            parsed_dates.dt.weekday,
            unit="D",
        )
    ).dt.normalize()

    # One authoritative identity row per historical site.
    distribution_identity = (
        distribution
        .sort_values("date")
        .drop_duplicates(
            subset="site_id",
            keep="first",
        )[
            [
                "site_id",
                "site_name",
                "_site_key",
            ]
        ]
        .reset_index(drop=True)
    )

    history_summary = (
        distribution
        .groupby(
            "site_id",
            as_index=False,
        )
        .agg(
            first_distribution_date=(
                "date",
                "min",
            ),
            last_distribution_date=(
                "date",
                "max",
            ),
            observed_distribution_weeks=(
                "_week_start",
                "nunique",
            ),
            distribution_record_count=(
                "date",
                "size",
            ),
        )
    )

    # -------------------------------------------------
    # Prepare survey
    # -------------------------------------------------

    if survey_df is None:
        survey = pd.DataFrame(
            columns=[
                "site_name",
                *SURVEY_FIELDS,
            ]
        )

    else:
        survey = (
            survey_df
            .copy()
            .reset_index(drop=True)
        )

        _require_columns(
            survey,
            {"site_name"},
            table_name="Partner survey",
        )

        survey["site_name"] = (
            survey["site_name"]
            .map(normalize_site_name)
        )

        survey["_site_key"] = (
            survey["site_name"]
            .map(_site_key)
        )

        duplicate_survey_sites = (
            survey["_site_key"]
            .duplicated(
                keep=False
            )
        )

        if duplicate_survey_sites.any():
            raise SiteMasterError(
                "Partner survey contains multiple "
                "records for the same normalized site."
            )

        # Keep a stable downstream schema even when
        # optional survey fields were not supplied.
        for column in SURVEY_FIELDS:
            if column not in survey.columns:
                survey[column] = pd.NA

    if "_site_key" not in survey.columns:
        survey["_site_key"] = pd.Series(
            dtype="object"
        )

    # -------------------------------------------------
    # Resolve survey-only partner identities
    # -------------------------------------------------

    distribution_keys = set(
        distribution_identity[
            "_site_key"
        ]
    )

    survey_only = (
        survey.loc[
            ~survey["_site_key"].isin(
                distribution_keys
            ),
            [
                "site_name",
                "_site_key",
            ],
        ]
        .copy()
    )

    # Important:
    # ignore any site_id already present on survey rows.
    # Distribution IDs are authoritative, while survey-only
    # IDs must be generated in the context of existing IDs
    # so collisions can be handled safely.
    identity_seed = pd.concat(
        [
            distribution_identity[
                [
                    "site_id",
                    "site_name",
                ]
            ],
            survey_only[
                ["site_name"]
            ].assign(
                site_id=None
            )[
                [
                    "site_id",
                    "site_name",
                ]
            ],
        ],
        ignore_index=True,
    )

    resolved_identity = assign_site_ids(
        identity_seed
    )

    resolved_identity["_site_key"] = (
        resolved_identity[
            "site_name"
        ].map(_site_key)
    )

    if (
        resolved_identity["site_id"]
        .duplicated()
        .any()
    ):
        raise SiteMasterError(
            "Site master contains duplicate site IDs "
            "after identity reconciliation."
        )

    # -------------------------------------------------
    # Attach history
    # -------------------------------------------------

    master = (
        resolved_identity
        .merge(
            history_summary,
            on="site_id",
            how="left",
            validate="one_to_one",
        )
    )

    historical_site_ids = set(
        distribution_identity[
            "site_id"
        ]
    )

    master[
        "has_distribution_history"
    ] = (
        master["site_id"]
        .isin(
            historical_site_ids
        )
    )

    # -------------------------------------------------
    # Attach survey enrichment by normalized site name
    # -------------------------------------------------

    survey_keys = set(
        survey["_site_key"]
    )

    master[
        "has_survey_data"
    ] = (
        master["_site_key"]
        .isin(
            survey_keys
        )
    )

    survey_payload = survey[
        [
            "_site_key",
            *SURVEY_FIELDS,
        ]
    ].copy()

    master = (
        master
        .merge(
            survey_payload,
            on="_site_key",
            how="left",
            validate="one_to_one",
        )
    )

    # -------------------------------------------------
    # Stable output schema
    # -------------------------------------------------

    leading_columns = [
        "site_id",
        "site_name",
        "has_distribution_history",
        "has_survey_data",
        "first_distribution_date",
        "last_distribution_date",
        "observed_distribution_weeks",
        "distribution_record_count",
    ]

    master = master[
        leading_columns
        + SURVEY_FIELDS
    ]

    return (
        master
        .sort_values(
            "site_id"
        )
        .reset_index(drop=True)
    )