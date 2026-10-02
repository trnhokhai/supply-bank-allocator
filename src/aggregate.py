import pandas as pd


class AggregationError(ValueError):
    """Raised when weekly aggregation cannot be performed safely."""


def _require_columns(
    dataframe,
    required_columns,
):
    missing_columns = (
        set(required_columns)
        - set(dataframe.columns)
    )

    if missing_columns:
        missing_text = ", ".join(
            sorted(missing_columns)
        )

        raise AggregationError(
            "Missing required column(s): "
            f"{missing_text}."
        )


def _add_week_start(dataframe):
    """
    Add the Monday start date of each ISO week.
    """

    result = dataframe.copy()

    parsed_dates = pd.to_datetime(
        result["date"],
        errors="coerce",
    )

    if parsed_dates.isna().any():
        raise AggregationError(
            "Distribution dates must be valid "
            "before weekly aggregation."
        )

    result["week_start"] = (
        parsed_dates
        - pd.to_timedelta(
            parsed_dates.dt.weekday,
            unit="D",
        )
    ).dt.normalize()

    return result


def build_site_activity_calendar(
    dataframe,
):
    """
    Build one row per site per historical ISO week.

    States:
        active
            The site has at least one distribution record
            during that week.

        inactive_gap
            No distribution records occurred during a week
            between the site's first and last observed weeks.

        pre_observation
            Week occurs before the site's first observed
            distribution record.

        post_observation
            Week occurs after the site's last observed
            distribution record.

    Pre/post-observation periods are intentionally different
    from inactive gaps so late onboarding is not treated as
    zero demand.
    """

    _require_columns(
        dataframe,
        {
            "date",
            "site_id",
            "site_name",
        },
    )

    if dataframe.empty:
        raise AggregationError(
            "Distribution data cannot be empty."
        )

    working = _add_week_start(
        dataframe
    )

    site_names_per_id = (
        working[
            ["site_id", "site_name"]
        ]
        .drop_duplicates()
        .groupby(
            "site_id",
            dropna=False,
        )["site_name"]
        .nunique()
    )

    if (
        site_names_per_id
        .gt(1)
        .any()
    ):
        raise AggregationError(
            "A site_id maps to multiple site names."
        )

    sites = (
        working[
            ["site_id", "site_name"]
        ]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    global_weeks = pd.date_range(
        start=working[
            "week_start"
        ].min(),
        end=working[
            "week_start"
        ].max(),
        freq="W-MON",
    )

    week_table = pd.DataFrame(
        {
            "week_start": global_weeks,
        }
    )

    sites["_join_key"] = 1
    week_table["_join_key"] = 1

    calendar = (
        sites
        .merge(
            week_table,
            on="_join_key",
        )
        .drop(
            columns="_join_key"
        )
    )

    observed_weeks = (
        working[
            ["site_id", "week_start"]
        ]
        .drop_duplicates()
        .assign(
            _observed=True
        )
    )

    site_bounds = (
        working
        .groupby(
            "site_id",
            as_index=False,
        )
        .agg(
            first_observed_week=(
                "week_start",
                "min",
            ),
            last_observed_week=(
                "week_start",
                "max",
            ),
        )
    )

    calendar = (
        calendar
        .merge(
            site_bounds,
            on="site_id",
            how="left",
        )
        .merge(
            observed_weeks,
            on=[
                "site_id",
                "week_start",
            ],
            how="left",
        )
    )

    calendar["_observed"] = (
    calendar["_observed"]
    .eq(True)
    )

    calendar[
        "activity_state"
    ] = "inactive_gap"

    calendar.loc[
        calendar["week_start"]
        < calendar[
            "first_observed_week"
        ],
        "activity_state",
    ] = "pre_observation"

    calendar.loc[
        calendar["week_start"]
        > calendar[
            "last_observed_week"
        ],
        "activity_state",
    ] = "post_observation"

    calendar.loc[
        calendar["_observed"],
        "activity_state",
    ] = "active"

    calendar["is_active"] = (
        calendar[
            "activity_state"
        ]
        .eq("active")
    )

    iso_calendar = (
        calendar["week_start"]
        .dt
        .isocalendar()
    )

    calendar["iso_year"] = (
        iso_calendar["year"]
        .astype(int)
    )

    calendar["iso_week"] = (
        iso_calendar["week"]
        .astype(int)
    )

    return (
        calendar[
            [
                "site_id",
                "site_name",
                "week_start",
                "iso_year",
                "iso_week",
                "activity_state",
                "is_active",
                "first_observed_week",
                "last_observed_week",
            ]
        ]
        .sort_values(
            [
                "site_id",
                "week_start",
            ]
        )
        .reset_index(drop=True)
    )


def find_inactive_spans(
    dataframe,
):
    """
    Summarize contiguous inactive gaps occurring between
    a site's first and last observed distribution weeks.

    Pre-onboarding and post-observation weeks are excluded.
    """

    calendar = (
        build_site_activity_calendar(
            dataframe
        )
    )

    gaps = (
        calendar.loc[
            calendar[
                "activity_state"
            ]
            .eq("inactive_gap")
        ]
        .copy()
    )

    if gaps.empty:
        return pd.DataFrame(
            columns=[
                "site_id",
                "site_name",
                "start_week",
                "end_week",
                "weeks_inactive",
            ]
        )

    gaps = gaps.sort_values(
        [
            "site_id",
            "week_start",
        ]
    )

    previous_week = (
        gaps
        .groupby("site_id")[
            "week_start"
        ]
        .shift()
    )

    new_span = (
        previous_week.isna()
        |
        (
            gaps["week_start"]
            - previous_week
        ).dt.days.ne(7)
    )

    gaps["_span_id"] = (
        new_span
        .groupby(
            gaps["site_id"]
        )
        .cumsum()
    )

    spans = (
        gaps
        .groupby(
            [
                "site_id",
                "site_name",
                "_span_id",
            ],
            as_index=False,
        )
        .agg(
            start_week=(
                "week_start",
                "min",
            ),
            end_week=(
                "week_start",
                "max",
            ),
            weeks_inactive=(
                "week_start",
                "size",
            ),
        )
        .drop(
            columns="_span_id"
        )
    )

    return (
        spans
        .sort_values(
            [
                "site_id",
                "start_week",
            ]
        )
        .reset_index(drop=True)
    )


def aggregate_distribution_to_iso_weeks(
    dataframe,
):
    """
    Aggregate cleaned distribution records to
    site/product/size/ISO-week grain.

    Missing product-size weeks receive quantity=0 only when:
        1. the series has observations before and after the
           missing week; and
        2. the site itself has distribution activity during
           that week.

    Entire site inactivity gaps are never converted to zero.
    """

    _require_columns(
        dataframe,
        {
            "date",
            "site_id",
            "site_name",
            "product",
            "size",
            "quantity",
        },
    )

    if dataframe.empty:
        raise AggregationError(
            "Distribution data cannot be empty."
        )

    working = _add_week_start(
        dataframe
    )

    quantities = pd.to_numeric(
        working["quantity"],
        errors="coerce",
    )

    if quantities.isna().any():
        raise AggregationError(
            "Distribution quantity must be numeric "
            "before weekly aggregation."
        )

    working["quantity"] = quantities

    group_columns = [
        "site_id",
        "site_name",
        "product",
        "size",
        "week_start",
    ]

    aggregation_rules = {
        "quantity": "sum",
    }

    for optional_column in [
        "households_served",
        "children_served",
    ]:
        if optional_column in working.columns:
            aggregation_rules[
                optional_column
            ] = (
                lambda values: (
                    values.sum(
                        min_count=1
                    )
                )
            )

    observed = (
        working
        .groupby(
            group_columns,
            as_index=False,
            dropna=False,
        )
        .agg(
            aggregation_rules
        )
    )

    series_bounds = (
        observed
        .groupby(
            [
                "site_id",
                "site_name",
                "product",
                "size",
            ],
            as_index=False,
        )
        .agg(
            first_series_week=(
                "week_start",
                "min",
            ),
            last_series_week=(
                "week_start",
                "max",
            ),
        )
    )

    grid_parts = []

    for series in (
        series_bounds
        .itertuples(index=False)
    ):
        weeks = pd.date_range(
            start=series.first_series_week,
            end=series.last_series_week,
            freq="W-MON",
        )

        grid_parts.append(
            pd.DataFrame(
                {
                    "site_id": (
                        series.site_id
                    ),
                    "site_name": (
                        series.site_name
                    ),
                    "product": (
                        series.product
                    ),
                    "size": (
                        series.size
                    ),
                    "week_start": weeks,
                }
            )
        )

    series_grid = pd.concat(
        grid_parts,
        ignore_index=True,
    )

    activity_calendar = (
        build_site_activity_calendar(
            working
        )[
            [
                "site_id",
                "week_start",
                "is_active",
            ]
        ]
    )

    series_grid = (
        series_grid
        .merge(
            activity_calendar,
            on=[
                "site_id",
                "week_start",
            ],
            how="left",
            validate="many_to_one",
        )
    )

    # Critical rule:
    # no zero-filling when the entire site was inactive.
    series_grid = (
        series_grid.loc[
            series_grid[
                "is_active"
            ]
            .eq(True)
        ]
        .drop(
            columns="is_active"
        )
    )

    weekly = (
        series_grid
        .merge(
            observed,
            on=group_columns,
            how="left",
            validate="one_to_one",
        )
    )

    imputed_zero_mask = (
        weekly["quantity"]
        .isna()
    )

    weekly[
        "is_imputed_zero"
    ] = imputed_zero_mask

    weekly.loc[
        imputed_zero_mask,
        "quantity",
    ] = 0

    weekly["quantity"] = (
        weekly["quantity"]
        .astype(int)
    )

    iso_calendar = (
        weekly["week_start"]
        .dt
        .isocalendar()
    )

    weekly["iso_year"] = (
        iso_calendar["year"]
        .astype(int)
    )

    weekly["iso_week"] = (
        iso_calendar["week"]
        .astype(int)
    )

    leading_columns = [
        "week_start",
        "iso_year",
        "iso_week",
        "site_id",
        "site_name",
        "product",
        "size",
        "quantity",
    ]

    optional_columns = [
        column
        for column in [
            "households_served",
            "children_served",
        ]
        if column in weekly.columns
    ]

    final_columns = (
        leading_columns
        + optional_columns
        + ["is_imputed_zero"]
    )

    return (
        weekly[
            final_columns
        ]
        .sort_values(
            [
                "site_id",
                "product",
                "size",
                "week_start",
            ]
        )
        .reset_index(drop=True)
    )