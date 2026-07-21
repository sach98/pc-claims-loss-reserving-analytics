#!/usr/bin/env python3
"""
P&C Claims Analytics & Actuarial Reserving Engine
--------------------------------------------------
Performs:
1. Loss Development Triangle Construction (Paid & Incurred Claims).
2. ChainLadder Loss Development Factors (LDF) & Link Ratio Calculations.
3. Bornhuetter-Ferguson (BF) Reserving Method (combining IELR & CDF).
4. Ultimate Claims Projections & IBNR Reserving comparison.
5. Loss Ratio Analysis (Paid Loss Ratio, Incurred Loss Ratio, Ultimate Loss Ratio).
6. Visualizations & Executive Reporting Summaries.

Author: Sachin Sharma (Senior Business Analyst & Insurance Analytics Specialist)
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def load_data(filepath):
    """Load claims dataset."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Dataset not found at {filepath}")
    return pd.read_csv(filepath)

def build_loss_triangle(df, line_of_business, metric='paid_claims'):
    """Build Loss Development Triangle for a given Line of Business and metric."""
    lob_df = df[df['line_of_business'] == line_of_business]
    triangle = lob_df.pivot(index='accident_year', columns='development_year', values=metric)
    return triangle

def calculate_chainladder_factors(triangle):
    """
    Calculate ChainLadder Link Ratios (Loss Development Factors - LDF).
    LDF_{i, i+1} = sum(Claims_{ay, i+1}) / sum(Claims_{ay, i}) for available accident years.
    """
    ldfs = []
    dev_years = triangle.columns
    for i in range(len(dev_years) - 1):
        dev_curr = dev_years[i]
        dev_next = dev_years[i+1]
        
        valid = triangle[[dev_curr, dev_next]].dropna()
        ldf = valid[dev_next].sum() / valid[dev_curr].sum()
        ldfs.append(ldf)
    
    # Cumulative LDFs (from dev year to tail)
    cdf = [1.0] * len(dev_years)
    cdf[-1] = 1.0
    for i in range(len(dev_years) - 2, -1, -1):
        cdf[i] = cdf[i+1] * ldfs[i]
        
    return ldfs, cdf

def project_ultimate_and_ibnr(triangle, cdf, premium_map, initial_expected_loss_ratio=0.75):
    """
    Project Ultimate Claims & IBNR using both ChainLadder and Bornhuetter-Ferguson (BF) methods.
    """
    results = []
    
    for ay in triangle.index:
        row = triangle.loc[ay].dropna()
        latest_dev = row.index[-1]
        latest_value = row.iloc[-1]
        
        c_factor = cdf[latest_dev]
        premium = premium_map.get(ay, np.nan)
        
        # 1. ChainLadder Projection
        cl_ultimate = latest_value * c_factor
        cl_ibnr = cl_ultimate - latest_value
        cl_loss_ratio = (cl_ultimate / premium) if premium else np.nan
        
        # 2. Bornhuetter-Ferguson (BF) Projection
        # Expected Initial Ultimate Loss = Premium * IELR
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
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    for idx, lob in enumerate(lobs):
        print(f"\n==========================================")
        print(f"Processing Line of Business: {lob}")
        print(f"==========================================")
        
        paid_triangle = build_loss_triangle(df, lob, metric='paid_claims')
        ldfs, cdfs = calculate_chainladder_factors(paid_triangle)
        
        lob_df = df[df['line_of_business'] == lob]
        premium_map = lob_df.groupby('accident_year')['earned_premium'].first().to_dict()
        
        reserving_summary = project_ultimate_and_ibnr(paid_triangle, cdfs, premium_map, initial_expected_loss_ratio=0.75)
        reserving_summary['line_of_business'] = lob
        all_summaries.append(reserving_summary)
        
        print("\n--- ChainLadder vs Bornhuetter-Ferguson Reserving Summary ---")
        print(reserving_summary[['accident_year', 'latest_paid_claims', 'cl_ultimate_claims', 'cl_ibnr_reserve', 'bf_ultimate_claims', 'bf_ibnr_reserve']])
        
        # Plot Loss Ratio Comparison Trend
        ax = axes[idx]
        ax.plot(reserving_summary['accident_year'], reserving_summary['cl_loss_ratio'] * 100, marker='o', linewidth=2, label='ChainLadder Loss Ratio (%)')
        ax.plot(reserving_summary['accident_year'], reserving_summary['bf_loss_ratio'] * 100, marker='s', linewidth=2, linestyle='--', label='Bornhuetter-Ferguson Loss Ratio (%)')
        ax.set_title(f'{lob}: Actuarial Reserving Loss Ratios')
        ax.set_xlabel('Accident Year')
        ax.set_ylabel('Loss Ratio (%)')
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.legend()
        
    combined_summary = pd.concat(all_summaries, ignore_index=True)
    summary_path = os.path.join(output_dir, 'reserving_summary.csv')
    combined_summary.to_csv(summary_path, index=False)
    print(f"\n[SUCCESS] Reserving Summary exported to {summary_path}")
    
    chart_path = os.path.join(output_dir, 'loss_ratios_by_lob.png')
    plt.tight_layout()
    plt.savefig(chart_path, dpi=300)
    plt.close()
    print(f"[SUCCESS] Loss Ratio Chart exported to {chart_path}")

if __name__ == '__main__':
    main()
