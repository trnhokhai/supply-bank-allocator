# Diaper and Period Supply Bank Allocator

A free, open-source planning tool for diaper and period supply banks.

Supply banks often manage limited inventory across many partner agencies while facing uncertain demand and uneven product-size availability. Donations may not match the sizes families actually need, making shortages difficult to anticipate before distribution. This project helps banks use their existing distribution, inventory, donation, and partner data to make more informed planning decisions.

## What the App Does

- Forecasts demand by partner site, product, and size for the next 4–8 weeks
- Allocates limited inventory across partner agencies using equity and fairness constraints
- Identifies product-size shortages, excess inventory, and weeks-of-supply risks
- Runs what-if scenarios such as donation changes, new partners, and purchase budgets
- Generates a one-page funder-ready report summarizing projected unmet need

## Technology

Built with Python and Streamlit using pandas, statsforecast/statsmodels, PuLP, Plotly, pandera, and related open-source libraries.

## Run Locally

```bash
streamlit run app.py
```

## Privacy

The application does not store uploaded user data. Files are processed only during the active application session and are discarded when the session ends.

## Project Status

Currently under development as part of the Chicago Education Advocacy Cooperative (ChiEAC) Fellowship.

## Credit

Built by Khai Tran as a ChiEAC Fellow, Chicago Education Advocacy Cooperative.