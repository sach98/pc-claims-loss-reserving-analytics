#!/usr/bin/env python3
"""
P&C Claims Analytics & Actuarial Reserving Engine
--------------------------------------------------
Author: Sachin Sharma (Senior Business Analyst & Insurance Analytics Specialist)
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

def load_data(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Dataset not found at {filepath}")
    return pd.read_csv(filepath)

def build_loss_triangle(df, line_of_business, metric='paid_claims'):
    lob_df = df[df['line_of_business'] == line_of_business]
    triangle = lob_df.pivot(index='accident_year', columns='development_year', values=metric)
    return triangle

def calculate_chainladder_factors(triangle):
    ldfs = []
    dev_years = triangle.columns
    for i in range(len(dev_years) - 1):
        dev_curr = dev_years[i]
        dev_next = dev_years[i+1]
        valid = triangle[[dev_curr, dev_next]].dropna()
        ldf = valid[dev_next].sum() / valid[dev_curr].sum()
        ldfs.append(ldf)
    
    cdf = [1.0] * len(dev_years)
    cdf[-1] = 1.0
    for i in range(len(dev_years) - 2, -1, -1):
        cdf[i] = cdf[i+1] * ldfs[i]
        
    return ldfs, cdf

def project_ultimate_and_ibnr(triangle, cdf, premium_map, initial_expected_loss_ratio=0.75):
    results = []
    for ay in triangle.index:
        row = triangle.loc[ay].dropna()
        latest_dev = row.index[-1]
        latest_value = row.iloc[-1]
        
        c_factor = cdf[latest_dev]
        premium = premium_map.get(ay, np.nan)
        
        cl_ultimate = latest_value * c_factor
        cl_ibnr = cl_ultimate - latest_value
        cl_loss_ratio = (cl_ultimate / premium) if premium else np.nan
        
        expected_ultimate = premium * initial_expected_loss_ratio
        percent_unreported = 1.0 - (1.0 / c_factor)
        bf_ibnr = expected_ultimate * percent_unreported
        bf_ultimate = latest_value + bf_ibnr
        bf_loss_ratio = (bf_ultimate / premium) if premium else np.nan
        
        results.append({
            'accident_year': ay,
            'latest_dev_year': latest_dev,
            'latest_paid_claims': latest_value,
            'cdf_to_ultimate': round(c_factor, 4),
            'cl_ultimate_claims': round(cl_ultimate, 2),
            'cl_ibnr_reserve': round(cl_ibnr, 2),
            'cl_loss_ratio': round(cl_loss_ratio, 4),
            'bf_ibnr_reserve': round(bf_ibnr, 2),
            'bf_ultimate_claims': round(bf_ultimate, 2),
            'bf_loss_ratio': round(bf_loss_ratio, 4),
            'earned_premium': premium
        })
        
    return pd.DataFrame(results)

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, 'data', 'pc_claims_dataset.csv')
    output_dir = os.path.join(base_dir, 'outputs')
    os.makedirs(output_dir, exist_ok=True)
    
    print("Loading P&C Claims Dataset...")
    df = load_data(data_path)
    
    lobs = df['line_of_business'].unique()
    all_summaries = []
    
    # 1. Plot Heatmap of Loss Development Triangle
    comm_prop_triangle = build_loss_triangle(df, 'Commercial Property', 'paid_claims')
    plt.figure(figsize=(8, 5))
    sns.heatmap(comm_prop_triangle / 1e6, annot=True, fmt='.2f', cmap='Blues', cbar_kws={'label': 'Paid Claims (£ Millions)'})
    plt.title('Commercial Property: Loss Development Triangle (£M)')
    plt.xlabel('Development Year')
    plt.ylabel('Accident Year')
    plt.tight_layout()
    heatmap_path = os.path.join(output_dir, 'claims_triangle_heatmap.png')
    plt.savefig(heatmap_path, dpi=300)
    plt.close()
    print(f"[SUCCESS] Saved Loss Triangle Heatmap to {heatmap_path}")
    
    # 2. Plot Loss Ratio Trends
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for idx, lob in enumerate(lobs):
        paid_triangle = build_loss_triangle(df, lob, metric='paid_claims')
        ldfs, cdfs = calculate_chainladder_factors(paid_triangle)
        lob_df = df[df['line_of_business'] == lob]
        premium_map = lob_df.groupby('accident_year')['earned_premium'].first().to_dict()
        
        reserving_summary = project_ultimate_and_ibnr(paid_triangle, cdfs, premium_map, initial_expected_loss_ratio=0.75)
        reserving_summary['line_of_business'] = lob
        all_summaries.append(reserving_summary)
        
        ax = axes[idx]
        ax.plot(reserving_summary['accident_year'], reserving_summary['cl_loss_ratio'] * 100, marker='o', linewidth=2, label='ChainLadder Loss Ratio (%)', color='#1f77b4')
        ax.plot(reserving_summary['accident_year'], reserving_summary['bf_loss_ratio'] * 100, marker='s', linewidth=2, linestyle='--', label='Bornhuetter-Ferguson Loss Ratio (%)', color='#ff7f0e')
        ax.set_title(f'{lob}: Actuarial Reserving Loss Ratios')
        ax.set_xlabel('Accident Year')
        ax.set_ylabel('Loss Ratio (%)')
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.legend()
        
    combined_summary = pd.concat(all_summaries, ignore_index=True)
    summary_path = os.path.join(output_dir, 'reserving_summary.csv')
    combined_summary.to_csv(summary_path, index=False)
    
    chart_path = os.path.join(output_dir, 'loss_ratios_by_lob.png')
    plt.tight_layout()
    plt.savefig(chart_path, dpi=300)
    plt.close()
    print(f"[SUCCESS] Saved Loss Ratio Chart to {chart_path}")

if __name__ == '__main__':
    main()
