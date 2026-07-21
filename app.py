import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.claims_analysis import load_data
from src.reserving import (
    build_loss_triangle,
    cumulative_factors,
    development_factors,
    estimate_tail_factor,
    project_reserves,
)

st.set_page_config(page_title="P&C Actuarial Claims Reserving Console", layout="wide")

st.title("P&C Actuarial Claims Reserving & Loss Ratio Console")
st.caption(
    "Synthetic illustrative triangle. Undiscounted best estimate with no risk margin, "
    "so this is an input to a Solvency II technical provision, not a substitute for one."
)

base_dir = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(base_dir, 'data', 'pc_claims_dataset.csv')
df = load_data(data_path)

st.sidebar.header("Model Parameters")
selected_lob = st.sidebar.selectbox("Line of business", df['line_of_business'].unique())
ielr_pct = st.sidebar.slider(
    "Bornhuetter-Ferguson a priori loss ratio (%)",
    min_value=50, max_value=110, value=75, step=5,
)
ielr = ielr_pct / 100.0

paid_triangle = build_loss_triangle(df, selected_lob, metric='paid_claims')
incurred_triangle = build_loss_triangle(df, selected_lob, metric='incurred_claims')
derived_tail = estimate_tail_factor(paid_triangle, incurred_triangle)

use_derived = st.sidebar.checkbox(
    f"Use derived tail factor ({derived_tail:.6f})", value=True,
    help="Derived from the oldest accident year's open case reserve at its final "
         "observed development year. Unticking this assumes the triangle is fully "
         "run off, which understates the reserve when case reserves are still open.",
)
tail = derived_tail if use_derived else 1.0

st.subheader(f"1. Cumulative paid loss development triangle (£) — {selected_lob}")
st.dataframe(paid_triangle.style.format("£{:,.0f}", na_rep="-"))

factors = development_factors(paid_triangle)
cdfs = cumulative_factors(factors, list(paid_triangle.columns), tail)

st.subheader("2. Development factors")
col1, col2 = st.columns(2)
with col1:
    st.table(pd.DataFrame({
        'Development stage': [f'DY {k} -> {k + 1}' for k in sorted(factors)],
        'Link ratio (LDF)': [round(factors[k], 4) for k in sorted(factors)],
    }))
with col2:
    st.table(pd.DataFrame({
        'Development year': sorted(cdfs),
        'CDF to ultimate': [round(cdfs[k], 4) for k in sorted(cdfs)],
    }))
st.caption(
    f"Tail factor applied: {tail:.6f}. The terminal link ratio rests on a single "
    "accident year, so it carries no credibility weighting."
)

premium_map = (df[df['line_of_business'] == selected_lob]
               .groupby('accident_year')['earned_premium'].first().to_dict())
result = project_reserves(paid_triangle, incurred_triangle, premium_map, ielr, tail)

st.subheader("3. Reserve decomposition and method comparison")
st.caption(
    "Total unpaid = ultimate less paid. Case reserves = incurred less paid. "
    "IBNR = ultimate less incurred. These are three different numbers."
)
st.dataframe(result.style.format({
    'latest_paid_claims': "£{:,.0f}",
    'latest_incurred_claims': "£{:,.0f}",
    'case_reserves': "£{:,.0f}",
    'cdf_to_ultimate': "{:.4f}",
    'cl_ultimate_claims': "£{:,.0f}",
    'cl_total_unpaid_reserve': "£{:,.0f}",
    'cl_ibnr_reserve': "£{:,.0f}",
    'cl_reserve_standard_error': "£{:,.0f}",
    'cl_reserve_cv_pct': "{:.2f}%",
    'cl_reserve_75th_percentile': "£{:,.0f}",
    'cl_reserve_95th_percentile': "£{:,.0f}",
    'bf_ultimate_claims': "£{:,.0f}",
    'bf_total_unpaid_reserve': "£{:,.0f}",
    'bf_ibnr_reserve': "£{:,.0f}",
    'cl_loss_ratio': "{:.1%}",
    'bf_loss_ratio': "{:.1%}",
    'earned_premium': "£{:,.0f}",
}))

total_unpaid = result['cl_total_unpaid_reserve'].sum()
total_ibnr = result['cl_ibnr_reserve'].sum()
total_case = result['case_reserves'].sum()
c1, c2, c3 = st.columns(3)
c1.metric("Total unpaid reserve", f"£{total_unpaid:,.0f}")
c2.metric("of which case reserves", f"£{total_case:,.0f}")
c3.metric("of which IBNR", f"£{total_ibnr:,.0f}")

st.subheader("4. Projected ultimate loss ratio: chain ladder vs Bornhuetter-Ferguson")
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=result['accident_year'], y=result['cl_loss_ratio'] * 100,
    mode='lines+markers', name='Chain ladder',
))
fig.add_trace(go.Scatter(
    x=result['accident_year'], y=result['bf_loss_ratio'] * 100,
    mode='lines+markers', name='Bornhuetter-Ferguson', line=dict(dash='dash'),
))
fig.update_layout(
    title=f"{selected_lob}: projected ultimate loss ratio by accident year",
    xaxis_title="Accident year", yaxis_title="Loss ratio (%)",
    template="plotly_white", xaxis=dict(tickmode='array',
                                        tickvals=result['accident_year'].tolist()),
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("5. Reserve uncertainty (Mack 1993)")
fig2 = go.Figure()
fig2.add_trace(go.Bar(
    x=result['accident_year'], y=result['cl_total_unpaid_reserve'],
    name='Best estimate',
    error_y=dict(type='data', array=result['cl_reserve_standard_error'], visible=True),
))
fig2.update_layout(
    title="Best-estimate unpaid reserve with Mack standard error",
    xaxis_title="Accident year", yaxis_title="Reserve (£)",
    template="plotly_white", xaxis=dict(tickmode='array',
                                        tickvals=result['accident_year'].tolist()),
)
st.plotly_chart(fig2, use_container_width=True)
st.caption(
    "The synthetic triangle is unusually smooth, so Mack's process variance is near "
    "zero and these intervals are narrower than a real book would produce."
)
