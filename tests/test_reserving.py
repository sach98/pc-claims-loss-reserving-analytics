"""
Behavioural tests for the reserving engine.

The headline test is TestMackAgainstPublishedBenchmark: the Mack (1993)
standard-error implementation is validated against the Taylor & Ashe (1983)
triangle, for which the per-accident-year standard errors are published. That
is an external oracle, not a self-consistency check.
"""

import os
import unittest

import pandas as pd

from src.reserving import (
    build_loss_triangle,
    cumulative_factors,
    development_factors,
    estimate_tail_factor,
    mack_standard_error,
    project_reserves,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'pc_claims_dataset.csv')

# Taylor & Ashe (1983) cumulative paid triangle, as used in Mack (1993).
TAYLOR_ASHE = [
    [357848, 1124788, 1735330, 2218270, 2745596, 3319994, 3466336, 3606286, 3833515, 3901463],
    [352118, 1236139, 2170033, 3353322, 3799067, 4120063, 4647867, 4914039, 5339085, None],
    [290507, 1292306, 2218525, 3235179, 3985995, 4132918, 4628910, 4909315, None, None],
    [310608, 1418858, 2195047, 3757447, 4029929, 4381982, 4588268, None, None, None],
    [443160, 1136350, 2128333, 2897821, 3402672, 3873311, None, None, None, None],
    [396132, 1333217, 2180715, 2985752, 3691712, None, None, None, None, None],
    [440832, 1288463, 2419861, 3483130, None, None, None, None, None, None],
    [359480, 1421128, 2864498, None, None, None, None, None, None, None],
    [376686, 1363294, None, None, None, None, None, None, None, None],
    [344014, None, None, None, None, None, None, None, None, None],
]

# Published Mack standard errors for the triangle above.
PUBLISHED_MACK_SE = {
    1: 0, 2: 75535, 3: 121699, 4: 133549, 5: 261406,
    6: 411010, 7: 558317, 8: 875328, 9: 971258, 10: 1363155,
}
PUBLISHED_TOTAL_RESERVE = 18680856


def taylor_ashe_triangle():
    tri = pd.DataFrame(TAYLOR_ASHE, index=range(1, 11), columns=range(0, 10)).astype(float)
    tri.index.name = 'accident_year'
    tri.columns.name = 'development_year'
    return tri


class TestMackAgainstPublishedBenchmark(unittest.TestCase):
    """External validation. If this fails, the variability model is wrong."""

    def setUp(self):
        self.tri = taylor_ashe_triangle()

    def test_total_reserve_matches_published(self):
        factors = development_factors(self.tri)
        cdfs = cumulative_factors(factors, list(self.tri.columns), 1.0)
        total = 0.0
        for ay in self.tri.index:
            row = self.tri.loc[ay].dropna()
            latest = row.iloc[-1]
            total += latest * cdfs[row.index[-1]] - latest
        self.assertAlmostEqual(total, PUBLISHED_TOTAL_RESERVE, delta=1.0)

    def test_per_year_standard_errors_match_published(self):
        errors = mack_standard_error(self.tri, tail_factor=1.0)
        for ay, expected in PUBLISHED_MACK_SE.items():
            self.assertAlmostEqual(
                errors[ay], expected, delta=1.0,
                msg=f"Mack SE for accident year {ay} does not match the published value",
            )


class TestDevelopmentFactors(unittest.TestCase):

    def setUp(self):
        self.df = pd.read_csv(DATA_PATH)
        self.paid = build_loss_triangle(self.df, 'Commercial Property', 'paid_claims')

    def test_f0_against_hand_calculation(self):
        factors = development_factors(self.paid)
        # (2,300,000+2,550,000+2,800,000+3,050,000) / (1,250,000+1,400,000+1,550,000+1,700,000)
        self.assertAlmostEqual(factors[0], 10700000 / 5900000, places=10)
        self.assertAlmostEqual(factors[0], 1.8135593220, places=9)

    def test_terminal_factor_uses_single_pair(self):
        factors = development_factors(self.paid)
        self.assertAlmostEqual(factors[3], 3750000 / 3550000, places=10)

    def test_paid_factors_are_at_least_one(self):
        # Cumulative paid claims cannot decrease.
        for dev, factor in development_factors(self.paid).items():
            self.assertGreaterEqual(factor, 1.0, msg=f"development year {dev}")

    def test_cdf_is_product_of_remaining_factors(self):
        factors = development_factors(self.paid)
        cdfs = cumulative_factors(factors, list(self.paid.columns), 1.0)
        self.assertAlmostEqual(cdfs[0], factors[0] * factors[1] * factors[2] * factors[3], places=10)
        self.assertAlmostEqual(cdfs[4], 1.0, places=10)

    def test_tail_factor_multiplies_every_cdf(self):
        factors = development_factors(self.paid)
        plain = cumulative_factors(factors, list(self.paid.columns), 1.0)
        tailed = cumulative_factors(factors, list(self.paid.columns), 1.05)
        for dev in plain:
            self.assertAlmostEqual(tailed[dev], plain[dev] * 1.05, places=9)


class TestTailEstimation(unittest.TestCase):

    def setUp(self):
        self.df = pd.read_csv(DATA_PATH)

    def test_commercial_property_tail_derived_from_open_case_reserves(self):
        paid = build_loss_triangle(self.df, 'Commercial Property', 'paid_claims')
        inc = build_loss_triangle(self.df, 'Commercial Property', 'incurred_claims')
        # AY2019 at DY4: paid 3,750,000 against incurred 3,800,000.
        self.assertAlmostEqual(estimate_tail_factor(paid, inc), 3800000 / 3750000, places=9)

    def test_fully_run_off_line_gets_unit_tail(self):
        paid = build_loss_triangle(self.df, 'Private Motor', 'paid_claims')
        inc = build_loss_triangle(self.df, 'Private Motor', 'incurred_claims')
        # AY2019 at DY4 is fully settled, so no tail is warranted.
        self.assertAlmostEqual(estimate_tail_factor(paid, inc), 1.0, places=9)


class TestReserveDecomposition(unittest.TestCase):
    """
    The defect this repo previously shipped: total unpaid reserve was published
    under the name IBNR, which overstates IBNR by the whole case reserve.
    """

    def setUp(self):
        self.df = pd.read_csv(DATA_PATH)
        self.paid = build_loss_triangle(self.df, 'Commercial Property', 'paid_claims')
        self.inc = build_loss_triangle(self.df, 'Commercial Property', 'incurred_claims')
        premium = (self.df[self.df.line_of_business == 'Commercial Property']
                   .groupby('accident_year')['earned_premium'].first().to_dict())
        self.premium = premium
        self.result = project_reserves(self.paid, self.inc, premium, 0.75, tail_factor=1.0)

    def row(self, ay):
        return self.result[self.result.accident_year == ay].iloc[0]

    def test_unpaid_equals_case_plus_ibnr(self):
        for _, row in self.result.iterrows():
            self.assertAlmostEqual(
                row['cl_total_unpaid_reserve'],
                row['case_reserves'] + row['cl_ibnr_reserve'],
                delta=0.02,
                msg=f"decomposition does not close for AY{row['accident_year']}",
            )

    def test_ibnr_is_not_total_unpaid(self):
        row = self.row(2020)
        self.assertAlmostEqual(row['cl_total_unpaid_reserve'], 219718, delta=1)
        self.assertAlmostEqual(row['cl_ibnr_reserve'], 69718, delta=1)
        self.assertGreater(row['cl_total_unpaid_reserve'] / row['cl_ibnr_reserve'], 3.0)

    def test_case_reserves_match_incurred_minus_paid(self):
        row = self.row(2022)
        self.assertAlmostEqual(row['case_reserves'], 3700000 - 3050000, delta=0.01)

    def test_oldest_year_is_fully_developed_without_tail(self):
        row = self.row(2019)
        self.assertAlmostEqual(row['cdf_to_ultimate'], 1.0, places=6)
        self.assertAlmostEqual(row['cl_total_unpaid_reserve'], 0.0, delta=0.01)

    def test_percentiles_exceed_best_estimate(self):
        for _, row in self.result.iterrows():
            if row['cl_total_unpaid_reserve'] > 0:
                self.assertGreater(row['cl_reserve_75th_percentile'], row['cl_total_unpaid_reserve'])
                self.assertGreater(row['cl_reserve_95th_percentile'], row['cl_reserve_75th_percentile'])

    def test_tail_increases_every_reserve(self):
        tailed = project_reserves(self.paid, self.inc, self.premium, 0.75, tail_factor=1.02)
        for ay in self.result['accident_year']:
            base = self.row(ay)['cl_total_unpaid_reserve']
            with_tail = tailed[tailed.accident_year == ay].iloc[0]['cl_total_unpaid_reserve']
            self.assertGreater(with_tail, base, msg=f"AY{ay}")


class TestBornhuetterFerguson(unittest.TestCase):

    def setUp(self):
        self.df = pd.read_csv(DATA_PATH)
        self.paid = build_loss_triangle(self.df, 'Commercial Property', 'paid_claims')
        self.inc = build_loss_triangle(self.df, 'Commercial Property', 'incurred_claims')
        self.premium = (self.df[self.df.line_of_business == 'Commercial Property']
                        .groupby('accident_year')['earned_premium'].first().to_dict())

    def test_bf_uses_percent_unreported(self):
        result = project_reserves(self.paid, self.inc, self.premium, 0.75, tail_factor=1.0)
        row = result[result.accident_year == 2023].iloc[0]
        expected = self.premium[2023] * 0.75 * (1.0 - 1.0 / row['cdf_to_ultimate'])
        self.assertAlmostEqual(row['bf_total_unpaid_reserve'], expected, delta=1.0)

    def test_bf_converges_to_paid_when_fully_developed(self):
        result = project_reserves(self.paid, self.inc, self.premium, 0.75, tail_factor=1.0)
        row = result[result.accident_year == 2019].iloc[0]
        self.assertAlmostEqual(row['bf_total_unpaid_reserve'], 0.0, delta=0.01)

    def test_higher_a_priori_raises_bf_reserve(self):
        low = project_reserves(self.paid, self.inc, self.premium, 0.60, tail_factor=1.0)
        high = project_reserves(self.paid, self.inc, self.premium, 0.90, tail_factor=1.0)
        low_row = low[low.accident_year == 2023].iloc[0]
        high_row = high[high.accident_year == 2023].iloc[0]
        self.assertGreater(high_row['bf_total_unpaid_reserve'], low_row['bf_total_unpaid_reserve'])


class TestTriangleShape(unittest.TestCase):

    def test_triangle_axes(self):
        df = pd.read_csv(DATA_PATH)
        tri = build_loss_triangle(df, 'Commercial Property', 'paid_claims')
        self.assertEqual(tri.index.name, 'accident_year')
        self.assertEqual(tri.columns.name, 'development_year')

    def test_non_zero_based_development_years_do_not_crash(self):
        """
        Regression guard. The previous implementation indexed a positional list
        with a development-year label, so a 1-based triangle raised IndexError.
        """
        df = pd.read_csv(DATA_PATH).copy()
        df['development_year'] = df['development_year'] + 1
        paid = build_loss_triangle(df, 'Commercial Property', 'paid_claims')
        inc = build_loss_triangle(df, 'Commercial Property', 'incurred_claims')
        premium = (df[df.line_of_business == 'Commercial Property']
                   .groupby('accident_year')['earned_premium'].first().to_dict())
        result = project_reserves(paid, inc, premium, 0.75, tail_factor=1.0)
        self.assertEqual(len(result), 5)


if __name__ == '__main__':
    unittest.main()
