import os
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from src.claims_analysis import load_data, build_loss_triangle, calculate_chainladder_factors, project_ultimate_and_ibnr

st.set_page_config(page_title="P&C Actuarial Claims Reserving Console", layout="wide")

st.title("📊 P&C Actuarial Claims Reserving & Loss Ratio Console")
st.markdown("**Author:** Sachin Sharma | Senior Business Analyst & Insurance Analytics Specialist")

base_dir = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(base_dir, 'data', 'pc_claims_dataset.csv')

df = load_data(data_path)

st.sidebar.header("⚙️ Model Parameters")
selected_lob = st.sidebar.selectbox("Select Line of Business", df['line_of_business'].unique())
ielr_pct = st.sidebar.slider("Bornhuetter-Ferguson Initial Expected Loss Ratio (IELR %)", min_value=50, max_value=110, value=75, step=5)
ielr = ielr_pct / 100.0

st.subheader(f"1. Loss Development Triangle (£) — {selected_lob}")
paid_triangle = build_loss_triangle(df, selected_lob, metric='paid_claims')
st.dataframe(paid_triangle.style.format("£{:,.0f}", na_rep="-"))

ldfs, cdfs = calculate_chainladder_factors(paid_triangle)

st.subheader("2. Loss Development Factors (LDF & CDF)")
col1, col2 = st.columns(2)

with col1:
    ldf_df = pd.DataFrame({
        'Development Stage': [f'DY {i} -> {i+1}' for i in range(len(ldfs))],
        'Link Ratio (LDF)': [round(x, 4) for x in ldfs]
    })
    st.table(ldf_df)

with col2:
    cdf_df = pd.DataFrame({
        'Development Year': paid_triangle.columns,
        'Cumulative LDF (CDF)': [round(x, 4) for x in cdfs]
    })
    st.table(cdf_df)

# Reserving Projections
lob_df = df[df['line_of_business'] == selected_lob]
premium_map = lob_df.groupby('accident_year')['earned_premium'].first().to_dict()

res_df = project_ultimate_and_ibnr(paid_triangle, cdfs, premium_map, initial_expected_loss_ratio=ielr)

st.subheader("3. Actuarial Reserving Comparison: ChainLadder vs. Bornhuetter-Ferguson")
st.dataframe(res_df.style.format({
    'latest_paid_claims': "£{:,.0f}",
    'cl_ultimate_claims': "£{:,.0f}",
    'cl_ibnr_reserve': "£{:,.0f}",
    'cl_loss_ratio': "{:.1%}",
    'bf_ultimate_claims': "£{:,.0f}",
    'bf_ibnr_reserve': "£{:,.0f}",
    'bf_loss_ratio': "{:.1%}",
    'earned_premium': "£{:,.0f}"
}))

# Chart Comparison
st.subheader("4. Projected Ultimate Loss Ratio Trend Comparison")
fig = go.Figure()
fig.add_trace(go.Scatter(x=res_df['accident_year'], y=res_df['cl_loss_ratio']*100, mode='lines+markers', name='ChainLadder Loss Ratio (%)'))
fig.add_trace(go.Scatter(x=res_df['accident_year'], y=res_df['bf_loss_ratio']*100, mode='lines+markers', name='Bornhuetter-Ferguson Loss Ratio (%)', line=dict(dash='dash')))
fig.update_layout(title=f"{selected_lob} - Loss Ratio Comparison", xaxis_title="Accident Year", yaxis_title="Loss Ratio (%)", template="plotly_white")
st.plotly_chart(fig, use_container_width=True)
