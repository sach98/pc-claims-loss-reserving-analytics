#!/usr/bin/env python3
"""
Actuarial reserving primitives: development factors, tail selection, reserve
decomposition and Mack (1993) reserve variability.

Kept separate from the reporting script so the arithmetic can be tested
against hand-computed oracles without touching matplotlib.

RESERVE TERMINOLOGY
-------------------
These are three different numbers and this module keeps them distinct,
because an earlier version of this repo reported the first one under the
name of the third:

    Total unpaid (outstanding) = Ultimate - Cumulative Paid
    Case reserves              = Incurred - Cumulative Paid   (handler-set, known claims)
    IBNR                       = Ultimate - Incurred          (= Total unpaid - Case reserves)

IBNR is the pure "incurred but not reported" provision. Reporting total
unpaid as IBNR overstates the IBNR provision by the whole case reserve,
which on this dataset is a factor of 3.15x for Commercial Property AY2020.
"""

import numpy as np
import pandas as pd


def build_loss_triangle(df, line_of_business, metric='paid_claims'):
    """Cumulative development triangle for one line of business."""
    lob_df = df[df['line_of_business'] == line_of_business]
    return lob_df.pivot(index='accident_year', columns='development_year', values=metric)


def development_factors(triangle):
    """
    Volume-weighted age-to-age factors.

    f_k = sum_i C_{i,k+1} / sum_i C_{i,k}, over accident years i where both
    C_{i,k} and C_{i,k+1} are observed.
    """
    dev_years = list(triangle.columns)
    factors = {}
    for i in range(len(dev_years) - 1):
        curr, nxt = dev_years[i], dev_years[i + 1]
        valid = triangle[[curr, nxt]].dropna()
        factors[curr] = valid[nxt].sum() / valid[curr].sum()
    return factors


def cumulative_factors(factors, dev_years, tail_factor=1.0):
    """
    CDF from each development year to ultimate, including the tail.

    Keyed by development year rather than list position. The previous
    implementation indexed a positional list with a development-year label,
    which silently worked only because this triangle happens to start at 0.
    """
    cdfs = {}
    running = tail_factor
    for dev in reversed(dev_years):
        cdfs[dev] = running
        # CDF for the previous development year picks up that year's own
        # age-to-age factor, i.e. CDF_{j-1} = f_{j-1} * CDF_j.
        if dev - 1 in factors:
            running = running * factors[dev - 1]
    return {dev: cdfs[dev] for dev in dev_years}


def estimate_tail_factor(paid_triangle, incurred_triangle):
    """
    Derive a paid tail factor from the oldest, most developed accident year
    instead of assuming 1.0.

    At the last observed development year the case reserve (incurred minus
    paid) is the handlers' own estimate of what is still to be paid on known
    claims. The ratio incurred/paid at that point is therefore a defensible
    first-order tail on the paid triangle.

    Returns 1.0 when the oldest year is fully run off (case reserve zero),
    which is the correct answer rather than an assumption.
    """
    oldest = paid_triangle.index[0]
    paid_row = paid_triangle.loc[oldest].dropna()
    incurred_row = incurred_triangle.loc[oldest].dropna()
    last_dev = paid_row.index[-1]
    if last_dev not in incurred_row.index:
        return 1.0
    paid, incurred = paid_row.loc[last_dev], incurred_row.loc[last_dev]
    if paid <= 0:
        return 1.0
    return max(1.0, incurred / paid)


def mack_sigma_squared(triangle):
    """
    Mack (1993) process variance parameters sigma_k^2.

    The final sigma has no degrees of freedom on a square triangle, so it is
    extrapolated by Mack's standard rule:
        sigma_n^2 = min(sigma_{n-1}^2, sigma_{n-2}^2, sigma_{n-1}^4 / sigma_{n-2}^2)
    """
    dev_years = list(triangle.columns)
    factors = development_factors(triangle)
    sigmas = {}

    for i in range(len(dev_years) - 1):
        curr, nxt = dev_years[i], dev_years[i + 1]
        valid = triangle[[curr, nxt]].dropna()
        n_pairs = len(valid)
        if n_pairs <= 1:
            sigmas[curr] = None  # filled by extrapolation below
            continue
        f_k = factors[curr]
        residuals = valid[curr] * (valid[nxt] / valid[curr] - f_k) ** 2
        sigmas[curr] = residuals.sum() / (n_pairs - 1)

    keys = [d for d in dev_years[:-1]]
    for idx, key in enumerate(keys):
        if sigmas[key] is None:
            if idx >= 2 and sigmas[keys[idx - 1]] and sigmas[keys[idx - 2]]:
                s1, s2 = sigmas[keys[idx - 1]], sigmas[keys[idx - 2]]
                sigmas[key] = min(s1, s2, s1 ** 2 / s2)
            elif idx >= 1 and sigmas[keys[idx - 1]]:
                sigmas[key] = sigmas[keys[idx - 1]]
            else:
                sigmas[key] = 0.0
    return sigmas


def mack_standard_error(triangle, tail_factor=1.0):
    """
    Mack (1993) standard error of the chain-ladder reserve, per accident year.

    mse(R_i) = C_i,ult^2 * sum_k (sigma_k^2 / f_k^2)
                            * (1 / C_i,k_hat + 1 / sum_j C_j,k)

    The tail factor is applied to the ultimate but carries no estimated
    variance of its own, so this understates total uncertainty. That is
    stated rather than hidden.
    """
    dev_years = list(triangle.columns)
    factors = development_factors(triangle)
    sigmas = mack_sigma_squared(triangle)
    cdfs = cumulative_factors(factors, dev_years, tail_factor)

    errors = {}
    for ay in triangle.index:
        row = triangle.loc[ay].dropna()
        latest_dev = row.index[-1]
        latest = row.iloc[-1]
        ultimate = latest * cdfs[latest_dev]

        # Project the accident year forward to build C_i,k_hat at each future k.
        projected = {latest_dev: latest}
        value = latest
        for dev in dev_years:
            if dev >= latest_dev and dev in factors:
                value = value * factors[dev]
                projected[dev + 1] = value

        total = 0.0
        for dev in dev_years[:-1]:
            if dev < latest_dev:
                continue
            f_k = factors.get(dev)
            sigma2 = sigmas.get(dev)
            if not f_k or sigma2 is None:
                continue
            c_ik = projected.get(dev)
            if not c_ik:
                continue
            column_sum = triangle[[dev, dev + 1]].dropna()[dev].sum()
            if column_sum <= 0:
                continue
            total += (sigma2 / f_k ** 2) * (1.0 / c_ik + 1.0 / column_sum)

        errors[ay] = float(np.sqrt(ultimate ** 2 * total))
    return errors


def project_reserves(paid_triangle, incurred_triangle, premium_map,
                     initial_expected_loss_ratio=0.75, tail_factor=1.0):
    """
    Chain-ladder and Bornhuetter-Ferguson projection with a full reserve
    decomposition into case reserves and IBNR.
    """
    dev_years = list(paid_triangle.columns)
    factors = development_factors(paid_triangle)
    cdfs = cumulative_factors(factors, dev_years, tail_factor)
    std_errors = mack_standard_error(paid_triangle, tail_factor)

    rows = []
    for ay in paid_triangle.index:
        paid_row = paid_triangle.loc[ay].dropna()
        latest_dev = paid_row.index[-1]
        latest_paid = paid_row.iloc[-1]

        incurred_row = incurred_triangle.loc[ay].dropna()
        latest_incurred = (incurred_row.loc[latest_dev]
                           if latest_dev in incurred_row.index else np.nan)
        case_reserves = latest_incurred - latest_paid

        cdf = cdfs[latest_dev]
        premium = premium_map.get(ay, np.nan)

        cl_ultimate = latest_paid * cdf
        cl_total_unpaid = cl_ultimate - latest_paid
        cl_ibnr = cl_ultimate - latest_incurred

        expected_ultimate = premium * initial_expected_loss_ratio
        percent_unreported = 1.0 - (1.0 / cdf)
        bf_total_unpaid = expected_ultimate * percent_unreported
        bf_ultimate = latest_paid + bf_total_unpaid
        bf_ibnr = bf_ultimate - latest_incurred

        se = std_errors[ay]
        rows.append({
            'accident_year': ay,
            'latest_dev_year': latest_dev,
            'latest_paid_claims': latest_paid,
            'latest_incurred_claims': latest_incurred,
            'case_reserves': case_reserves,
            # Stored at full precision, not rounded. This is the factor a
            # reviewer recomputes the ultimate from, so a rounded value here
            # would make the published table fail to reconcile against itself.
            'cdf_to_ultimate': cdf,
            'cl_ultimate_claims': round(cl_ultimate, 2),
            'cl_total_unpaid_reserve': round(cl_total_unpaid, 2),
            'cl_ibnr_reserve': round(cl_ibnr, 2),
            'cl_reserve_standard_error': round(se, 2),
            'cl_reserve_cv_pct': (round(100.0 * se / cl_total_unpaid, 2)
                                  if cl_total_unpaid > 0 else 0.0),
            'cl_reserve_75th_percentile': round(cl_total_unpaid + 0.6745 * se, 2),
            'cl_reserve_95th_percentile': round(cl_total_unpaid + 1.6449 * se, 2),
            'bf_ultimate_claims': round(bf_ultimate, 2),
            'bf_total_unpaid_reserve': round(bf_total_unpaid, 2),
            'bf_ibnr_reserve': round(bf_ibnr, 2),
            'cl_loss_ratio': round(cl_ultimate / premium, 4) if premium else np.nan,
            'bf_loss_ratio': round(bf_ultimate / premium, 4) if premium else np.nan,
            'earned_premium': premium,
        })

    return pd.DataFrame(rows)
