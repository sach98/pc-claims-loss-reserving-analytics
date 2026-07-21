#!/usr/bin/env python3
"""
P&C Claims Analytics & Actuarial Reserving Engine
--------------------------------------------------
Reporting layer. All reserving arithmetic lives in src/reserving.py, which is
validated against the published Taylor & Ashe (1983) Mack benchmark in the
test suite.

Author: Sachin Sharma
"""

import os

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns

from src.reserving import (
    build_loss_triangle,
    estimate_tail_factor,
    project_reserves,
)

# A priori loss ratio for the Bornhuetter-Ferguson projection, per line of
# business. In a real engagement this comes from the pricing plan or the
# business plan, not from the reserving analyst. It is set explicitly here so
# the assumption is visible and can be sensitivity-tested, rather than being a
# single hidden default applied to every line.
INITIAL_EXPECTED_LOSS_RATIO = {
    'Commercial Property': 0.75,
    'Private Motor': 0.75,
}

AS_AT_DATE = '2026-07-22'
SOURCE_NOTE = (
    'Source: synthetic illustrative triangle (data/pc_claims_dataset.csv) | '
    f'as at {AS_AT_DATE} | chain ladder with data-derived paid tail | '
    'Mack (1993) standard errors'
)


def load_data(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Dataset not found at {filepath}")
    return pd.read_csv(filepath)


def money(value):
    return f"£{value:,.0f}"


def build_markdown_table(summary, line_of_business):
    """Generate the README reserving table straight from the results frame."""
    lob = summary[summary['line_of_business'] == line_of_business]
    header = (
        "| Accident Year | Latest Paid | Case Reserves | CDF to Ultimate | Ultimate "
        "| Total Unpaid | IBNR | Mack SE | 75th %ile | CL Loss Ratio |"
    )
    rows = [header, "|---|---|---|---|---|---|---|---|---|---|"]
    for _, row in lob.iterrows():
        rows.append(
            f"| **{int(row['accident_year'])}** "
            f"| {money(row['latest_paid_claims'])} "
            f"| {money(row['case_reserves'])} "
            f"| {row['cdf_to_ultimate']:.4f} "
            f"| {money(row['cl_ultimate_claims'])} "
            f"| {money(row['cl_total_unpaid_reserve'])} "
            f"| {money(row['cl_ibnr_reserve'])} "
            f"| {money(row['cl_reserve_standard_error'])} "
            f"| {money(row['cl_reserve_75th_percentile'])} "
            f"| {row['cl_loss_ratio'] * 100:.1f}% |"
        )
    totals = lob[['cl_total_unpaid_reserve', 'cl_ibnr_reserve', 'case_reserves']].sum()
    rows.append(
        f"| **Total** | | {money(totals['case_reserves'])} | | | "
        f"{money(totals['cl_total_unpaid_reserve'])} | {money(totals['cl_ibnr_reserve'])} | | | |"
    )
    return "\n".join(rows)


def plot_triangle(triangle, output_path):
    plt.figure(figsize=(8, 5))
    ax = sns.heatmap(
        triangle / 1e6, annot=True, fmt='.2f', cmap='Blues',
        cbar_kws={'label': 'Cumulative paid claims (£m)'},
    )
    ax.set_title('Commercial Property: cumulative paid loss development triangle (£m)')
    ax.set_xlabel('Development year')
    ax.set_ylabel('Accident year')
    plt.figtext(0.5, 0.005, SOURCE_NOTE, ha='center', fontsize=7, color='#444444')
    plt.tight_layout(rect=[0, 0.04, 1, 1])
    plt.savefig(output_path, dpi=300)
    plt.close()


def plot_loss_ratios(summary, lobs, output_path):
    """
    Chain ladder against Bornhuetter-Ferguson, on a shared y-axis so the two
    panels are actually comparable, with integer accident years.
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), sharey=True)

    for idx, lob in enumerate(lobs):
        data = summary[summary['line_of_business'] == lob]
        ax = axes[idx]
        years = data['accident_year'].astype(int)
        cl = data['cl_loss_ratio'] * 100
        bf = data['bf_loss_ratio'] * 100

        ax.plot(years, cl, marker='o', linewidth=2, label='Chain ladder', color='#1f77b4')
        ax.plot(years, bf, marker='s', linewidth=2, linestyle='--',
                label='Bornhuetter-Ferguson', color='#ff7f0e')

        # Annotate the widest divergence between the two methods, which is the
        # actual finding and previously went unmarked.
        gaps = (cl.values - bf.values)
        worst = int(abs(gaps).argmax())
        worst_year = int(years.iloc[worst])
        ax.annotate(
            f'{abs(gaps[worst]):.1f} pt gap\n(least mature year)',
            xy=(worst_year, (cl.iloc[worst] + bf.iloc[worst]) / 2),
            xytext=(-95, 0), textcoords='offset points',
            fontsize=8, va='center',
            arrowprops=dict(arrowstyle='->', color='#666666', lw=1),
            bbox=dict(boxstyle='round,pad=0.3', fc='#fffbe6', ec='#cccccc'),
        )

        deterioration = cl.iloc[-1] - cl.iloc[0]
        ax.set_title(f'{lob}: ultimate loss ratio worsens {deterioration:+.1f} pts '
                     f'({int(years.iloc[0])} to {int(years.iloc[-1])})', fontsize=10)
        ax.set_xlabel('Accident year')
        ax.xaxis.set_major_locator(mticker.FixedLocator(years.tolist()))
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.legend(fontsize=8)

    axes[0].set_ylabel('Projected ultimate loss ratio (%)')
    plt.figtext(0.5, 0.01, SOURCE_NOTE, ha='center', fontsize=7, color='#444444')
    plt.tight_layout(rect=[0, 0.05, 1, 1])
    plt.savefig(output_path, dpi=300)
    plt.close()


def plot_reserve_decomposition(summary, lobs, output_path):
    """
    Case reserves against IBNR, stacked. This is the chart that makes the
    distinction visible: the previous version of this repo reported the whole
    stack under the label IBNR.
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), sharey=True)

    for idx, lob in enumerate(lobs):
        data = summary[summary['line_of_business'] == lob]
        ax = axes[idx]
        years = data['accident_year'].astype(int)
        case = data['case_reserves'] / 1e6
        ibnr = data['cl_ibnr_reserve'] / 1e6

        ax.bar(years, case, label='Case reserves (known claims)', color='#4c72b0')
        ax.bar(years, ibnr, bottom=case, label='IBNR (ultimate less incurred)', color='#dd8452')

        for year, c, i in zip(years, case, ibnr):
            if c + i > 0.02:
                ax.text(year, c + i + 0.06, f'{c + i:.2f}', ha='center', fontsize=8)

        total_unpaid = data['cl_total_unpaid_reserve'].sum() / 1e6
        total_ibnr = data['cl_ibnr_reserve'].sum() / 1e6
        ax.set_title(f'{lob}: £{total_unpaid:.2f}m unpaid, of which £{total_ibnr:.2f}m IBNR',
                     fontsize=10)
        ax.set_xlabel('Accident year')
        ax.xaxis.set_major_locator(mticker.FixedLocator(years.tolist()))
        ax.grid(True, axis='y', linestyle='--', alpha=0.6)
        ax.legend(fontsize=8)

    axes[0].set_ylabel('Reserve (£m)')
    plt.figtext(0.5, 0.01, SOURCE_NOTE, ha='center', fontsize=7, color='#444444')
    plt.tight_layout(rect=[0, 0.05, 1, 1])
    plt.savefig(output_path, dpi=300)
    plt.close()


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, 'data', 'pc_claims_dataset.csv')
    output_dir = os.path.join(base_dir, 'outputs')
    os.makedirs(output_dir, exist_ok=True)

    print("Loading P&C Claims Dataset...")
    df = load_data(data_path)
    lobs = list(df['line_of_business'].unique())

    summaries = []
    for lob in lobs:
        paid = build_loss_triangle(df, lob, 'paid_claims')
        incurred = build_loss_triangle(df, lob, 'incurred_claims')
        premium = (df[df['line_of_business'] == lob]
                   .groupby('accident_year')['earned_premium'].first().to_dict())
        tail = estimate_tail_factor(paid, incurred)
        ielr = INITIAL_EXPECTED_LOSS_RATIO[lob]

        result = project_reserves(paid, incurred, premium, ielr, tail_factor=tail)
        result['line_of_business'] = lob
        result['tail_factor'] = tail
        result['initial_expected_loss_ratio'] = ielr
        summaries.append(result)

        print(f"\n--- {lob} ---")
        print(f"Derived paid tail factor : {tail:.6f}"
              f"{' (fully run off, no tail warranted)' if tail == 1.0 else ''}")
        print(f"Total unpaid reserve     : {money(result['cl_total_unpaid_reserve'].sum())}")
        print(f"  of which case reserves : {money(result['case_reserves'].sum())}")
        print(f"  of which IBNR          : {money(result['cl_ibnr_reserve'].sum())}")
        print(f"Ultimate loss ratio      : {result['cl_loss_ratio'].iloc[0] * 100:.1f}% "
              f"({int(result['accident_year'].iloc[0])}) to "
              f"{result['cl_loss_ratio'].iloc[-1] * 100:.1f}% "
              f"({int(result['accident_year'].iloc[-1])})")

    summary = pd.concat(summaries, ignore_index=True)
    summary_path = os.path.join(output_dir, 'reserving_summary.csv')
    summary.to_csv(summary_path, index=False)
    print(f"\n[SUCCESS] Saved reserving summary to {summary_path}")

    table_path = os.path.join(output_dir, 'reserving_table.md')
    with open(table_path, 'w') as handle:
        handle.write(build_markdown_table(summary, 'Commercial Property') + "\n")
    print(f"[SUCCESS] Saved README reserving table to {table_path}")

    plot_triangle(
        build_loss_triangle(df, 'Commercial Property', 'paid_claims'),
        os.path.join(output_dir, 'claims_triangle_heatmap.png'),
    )
    plot_loss_ratios(summary, lobs, os.path.join(output_dir, 'loss_ratios_by_lob.png'))
    plot_reserve_decomposition(
        summary, lobs, os.path.join(output_dir, 'reserve_decomposition.png')
    )
    print("[SUCCESS] Saved triangle, loss ratio and reserve decomposition charts")


if __name__ == '__main__':
    main()
