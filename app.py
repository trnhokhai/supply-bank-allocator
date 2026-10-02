import streamlit as st


st.set_page_config(
    page_title="Diaper & Period Supply Bank Allocator",
    page_icon="📦",
    layout="wide",
)


st.title(
    "Diaper & Period Supply Bank Allocator"
)

st.caption(
    "Forecast demand, balance inventory, and allocate "
    "essential supplies where they're needed most."
)


st.markdown(
    """
This planning tool is being built to help diaper and period
supply banks turn operational files into trusted planning data.

### Current workflow

1. **Upload** distribution, inventory, incoming-supply, and
   partner-survey files.
2. **Clean and validate** imperfect real-world data.
3. **Review data quality** before analytics are used.
4. Later project gates will add forecasting, inventory-risk,
   allocation, scenarios, and reporting.
"""
)


st.info(
    "Use the sidebar and open **Upload** to begin. "
    "You can upload your own CSV/XLSX files or use Demo Mode."
)