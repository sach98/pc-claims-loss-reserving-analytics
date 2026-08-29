"""Differential test of the reserving engine against an independent implementation.

This is NOT a second oracle. `chainladder` implements the same published formulae
on the same data, so agreement demonstrates that two separately written programs
compute the arithmetic the same way. It does not validate chain ladder, Mack or
Bornhuetter-Ferguson as methods, and it says nothing about whether their
assumptions hold on this data. The external oracle in this repository remains the
published Taylor and Ashe figures in tests/test_reserving.py.

What it is worth: an implementation error that both a hand calculation and the
package would catch is a different class of bug from one only a second
implementation catches, and this covers the second class.

The package is optional, and this file skips loudly without it. See
requirements-crosscheck.txt for why it cannot go in requirements.txt: it needs
numpy 2, and this repository pins numpy 1.26.4 so matplotlib 3.6.2 can render the
committed charts, which do not survive the upgrade.
"""

from __future__ import annotations

import os
import unittest

import pandas as pd

from src.reserving import (
    build_loss_triangle,
    cumulative_factors,
    development_factors,
    mack_standard_error,
)
from tests.test_reserving import PUBLISHED_MACK_SE, taylor_ashe_triangle

try:
    import chainladder as cl
    import numpy as np
    HAVE_CHAINLADDER = True
except ImportError:  # pragma: no cover - exercised by not installing it
    HAVE_CHAINLADDER = False

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "pc_claims_dataset.csv")

LINES = ("Commercial Property", "Private Motor")

# chainladder's DEFAULT sigma_interpolation is 'log-linear'. Mack (1993) uses a
# different rule for the final development period's sigma, and the package
# implements it under the name 'mack'. This is a convention choice rather than a
# correctness question, and the size of it is measured in
# test_the_default_sigma_convention_is_what_differs below.
MACK_SIGMA = "mack"

skip_without_package = unittest.skipUnless(
    HAVE_CHAINLADDER,
    "chainladder is not installed. This check is optional: "
    "pip install -r requirements-crosscheck.txt in a separate environment.",
)


def _to_chainladder(df: pd.DataFrame, line_of_business: str):
    """Load one line of business into a chainladder Triangle."""
    sub = df[df["line_of_business"] == line_of_business].copy()
    sub["origin"] = sub["accident_year"].astype(str)
    # chainladder wants a valuation period, not a development offset.
    sub["valuation"] = (sub["accident_year"] + sub["development_year"]).astype(str)
    return cl.Triangle(sub, origin="origin", development="valuation",
                       columns=["paid_claims"], cumulative=True)


def _fitted(triangle):
    return cl.Development(average="volume", n_periods=-1,
                          sigma_interpolation=MACK_SIGMA).fit_transform(triangle)


@skip_without_package
class CrossCheckOnThisRepositorysTriangles(unittest.TestCase):
    """Both lines of business, every quantity the engine publishes."""

    @classmethod
    def setUpClass(cls):
        cls.df = pd.read_csv(DATA_PATH)

    def test_development_factors_agree(self):
        for lob in LINES:
            with self.subTest(line_of_business=lob):
                mine = build_loss_triangle(self.df, lob, metric="paid_claims")
                ours = [development_factors(mine)[k] for k in sorted(development_factors(mine))]
                theirs = [float(x) for x in np.array(_fitted(_to_chainladder(self.df, lob)).ldf_).flatten()]
                self.assertEqual(len(ours), len(theirs))
                for i, (a, b) in enumerate(zip(ours, theirs)):
                    self.assertAlmostEqual(a, b, places=10, msg=f"age-to-age factor {i}")

    def test_ultimates_agree(self):
        for lob in LINES:
            with self.subTest(line_of_business=lob):
                tri = build_loss_triangle(self.df, lob, metric="paid_claims")
                factors = development_factors(tri)
                cdfs = cumulative_factors(factors, list(tri.columns), tail_factor=1.0)
                ours = []
                for ay in tri.index:
                    row = tri.loc[ay].dropna()
                    ours.append(row.iloc[-1] * cdfs[row.index[-1]])
                fitted = _fitted(_to_chainladder(self.df, lob))
                theirs = [float(x) for x in np.array(cl.Chainladder().fit(fitted).ultimate_).flatten()]
                for ay, a, b in zip(tri.index, ours, theirs):
                    self.assertAlmostEqual(a, b, places=6, msg=f"ultimate for {ay}")

    def test_mack_standard_errors_agree(self):
        for lob in LINES:
            with self.subTest(line_of_business=lob):
                tri = build_loss_triangle(self.df, lob, metric="paid_claims")
                ours = [mack_standard_error(tri, tail_factor=1.0)[k]
                        for k in sorted(mack_standard_error(tri, tail_factor=1.0))]
                summary = cl.MackChainladder().fit(
                    _fitted(_to_chainladder(self.df, lob))
                ).summary_.to_frame(origin_as_datetime=False)
                theirs = list(summary["Mack Std Err"].fillna(0.0).values)
                for ay, a, b in zip(tri.index, ours, theirs):
                    self.assertAlmostEqual(a, b, places=6, msg=f"Mack SE for {ay}")


@skip_without_package
class CrossCheckOnThePublishedBenchmark(unittest.TestCase):
    """Three-way: this engine, the package, and the figures Mack published."""

    def test_all_three_agree_on_taylor_and_ashe(self):
        tri = taylor_ashe_triangle()
        ours = mack_standard_error(tri, tail_factor=1.0)
        summary = cl.MackChainladder().fit(
            _fitted(cl.load_sample("genins"))
        ).summary_.to_frame(origin_as_datetime=False)
        theirs = list(summary["Mack Std Err"].fillna(0.0).values)

        for i, ay in enumerate(sorted(ours)):
            with self.subTest(accident_year=ay):
                published = PUBLISHED_MACK_SE[ay]
                self.assertAlmostEqual(ours[ay], published, delta=1.0)
                self.assertAlmostEqual(theirs[i], published, delta=1.0)
                self.assertAlmostEqual(ours[ay], theirs[i], delta=1.0)

    def test_the_default_sigma_convention_is_what_differs(self):
        """Names the disagreement instead of hiding it behind a setting.

        Left on its default 'log-linear' interpolation the package misses the
        published figures by roughly 3,700 at the widest, about 4.9% on the
        second accident year. That is not an error in the package: it is a
        different rule for extrapolating the final development period's sigma.
        Pinning the size of it here means a future version changing its default
        shows up as a failure with an explanation attached, rather than as a
        mysterious drift.
        """
        default_fit = cl.Development(average="volume", n_periods=-1,
                                     sigma_interpolation="log-linear")
        summary = cl.MackChainladder().fit(
            default_fit.fit_transform(cl.load_sample("genins"))
        ).summary_.to_frame(origin_as_datetime=False)
        theirs = list(summary["Mack Std Err"].fillna(0.0).values)
        worst = max(abs(theirs[i] - PUBLISHED_MACK_SE[ay])
                    for i, ay in enumerate(sorted(PUBLISHED_MACK_SE)))
        self.assertGreater(worst, 1000.0,
                           "the default convention no longer differs; update the README note")
        self.assertLess(worst, 10000.0,
                        "the default convention now differs by more than documented")


if __name__ == "__main__":
    unittest.main()
