from pathlib import Path

import pandas as pd
import plotly.graph_objects as go


DATA_DIR = Path("data/sample")
OUTPUT_DIR = Path("docs/figures")

DIAPER_SIZE_ORDER = [
    "N",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
]

DONATION_SOURCES = [
    "Community Donations",
    "Spring Donation Drive",
    "Holiday Donation Drive",
]


def load_data():
    """
    Load the synthetic datasets required for Gate 1
    validation charts.
    """

    distribution = pd.read_csv(
        DATA_DIR / "distribution_log_clean.csv"
    )

    incoming_supply = pd.read_csv(
        DATA_DIR / "incoming_supply.csv"
    )

    return distribution, incoming_supply


def calculate_demand_mix(distribution):
    """
    Calculate historical diaper demand share by size.
    """

    diaper_demand = distribution.loc[
        distribution["product"] == "diaper"
    ]

    demand_by_size = (
        diaper_demand.groupby("size")["quantity"]
        .sum()
        .reindex(
            DIAPER_SIZE_ORDER,
            fill_value=0,
        )
    )

    demand_mix = (
        demand_by_size
        / demand_by_size.sum()
        * 100
    )

    return demand_mix


def calculate_donation_mix(incoming_supply):
    """
    Calculate donated diaper supply share by size.

    Purchases are excluded so the chart reflects the
    synthetic donation-size mismatch directly.
    """

    diaper_donations = incoming_supply.loc[
        (
            incoming_supply["product"]
            == "diaper"
        )
        & (
            incoming_supply["source"]
            .isin(DONATION_SOURCES)
        )
    ]

    donations_by_size = (
        diaper_donations
        .groupby("size")["quantity"]
        .sum()
        .reindex(
            DIAPER_SIZE_ORDER,
            fill_value=0,
        )
    )

    donation_mix = (
        donations_by_size
        / donations_by_size.sum()
        * 100
    )

    return donation_mix


def create_bar_chart(
    values,
    title,
    subtitle,
    y_axis_title,
    output_path,
):
    """
    Create and save a clean validation bar chart.
    """

    figure = go.Figure()

    figure.add_bar(
        x=values.index,
        y=values.values,
        text=[
            f"{value:.1f}%"
            for value in values.values
        ],
        textposition="outside",
    )

    figure.update_layout(
        title={
            "text": (
                f"{title}"
                f"<br><sup>{subtitle}</sup>"
            ),
            "x": 0.5,
            "xanchor": "center",
        },
        xaxis_title="Diaper size",
        yaxis_title=y_axis_title,
        template="plotly_white",
        showlegend=False,
        margin=dict(
            l=70,
            r=40,
            t=100,
            b=70,
        ),
    )

    figure.update_yaxes(
        ticksuffix="%",
        rangemode="tozero",
    )

    figure.write_image(
        output_path,
        width=1100,
        height=650,
        scale=2,
    )


def main():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    distribution, incoming_supply = (
        load_data()
    )

    demand_mix = calculate_demand_mix(
        distribution
    )

    donation_mix = calculate_donation_mix(
        incoming_supply
    )

    create_bar_chart(
        demand_mix,
        title="Synthetic Diaper Demand Size Mix",
        subtitle=(
            "Historical demand is intentionally "
            "concentrated in sizes 4 and 5."
        ),
        y_axis_title="Share of historical diaper demand",
        output_path=(
            OUTPUT_DIR
            / "diaper_demand_size_mix.png"
        ),
    )

    create_bar_chart(
        donation_mix,
        title="Synthetic Diaper Donation Size Mix",
        subtitle=(
            "Donated supply is intentionally "
            "skewed toward Newborn, size 1, and size 2."
        ),
        y_axis_title="Share of donated diaper units",
        output_path=(
            OUTPUT_DIR
            / "diaper_donation_size_mix.png"
        ),
    )

    print(
        "\nDiaper demand mix:"
    )

    print(
        demand_mix.round(2).to_string()
    )

    print(
        "\nDonation diaper mix:"
    )

    print(
        donation_mix.round(2).to_string()
    )

    print(
        "\nValidation charts saved to:"
    )

    print(
        OUTPUT_DIR
        / "diaper_demand_size_mix.png"
    )

    print(
        OUTPUT_DIR
        / "diaper_donation_size_mix.png"
    )


if __name__ == "__main__":
    main()