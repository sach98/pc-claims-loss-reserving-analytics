# Business Requirements Document (BRD)
## P&C Claims Analytics, Loss Reserving & Actuarial Reporting Engine

**Document Control**
- **Author:** Sachin Sharma (Business Analyst)
- **Version:** 1.1
- **Date:** 2026-07-22
- **Status:** Draft. This is a portfolio exercise on a synthetic triangle. It has
  not been reviewed or approved by any firm, and no approver is named because
  none exists.
- **Intended audience (illustrative):** Chief Actuary, Claims Operations Lead,
  Solvency II Reporting Committee

**Traceability**

| Req | Implemented by | Covered by |
|---|---|---|
| BR-01 | `build_loss_triangle()` | `TestTriangleShape` |
| BR-02 | `development_factors()`, `cumulative_factors()` | `TestDevelopmentFactors` |
| BR-03 | `project_reserves()` | `TestReserveDecomposition` |
| BR-04 | `estimate_tail_factor()` | `TestTailEstimation` |
| BR-05 | `mack_standard_error()` | `TestMackAgainstPublishedBenchmark` |
| BR-06 | `INITIAL_EXPECTED_LOSS_RATIO` | `TestBornhuetterFerguson` |

---

## 1. Executive Summary & Business Need
In Property & Casualty (P&C) insurance, accurate claims loss reserving is critical for insurer solvency, capital adequacy under Solvency II, and financial reporting under IFRS 17. Claims incurred today may take multiple years to fully develop and settle. 

Failure to set adequate **Incurred But Not Reported (IBNR)** reserves leads to sudden capital depletion, while over-reserving inefficiently locks up regulatory solvency capital.

This system specifies the requirements for automated **Loss Development Triangles**, **ChainLadder Actuarial Reserving**, and **Ultimate Loss Ratio Reporting** across multiple lines of business (Commercial Property, Private Motor).

---

## 2. Business Requirements & Functional Specifications

### BR-01: Claims Data Aggregation & Triangle Construction
- **Accident Year (AY) Grouping:** Group claims by year of occurrence ($AY \in [2019, 2023]$).
- **Development Year (DY) Tracking:** Track annual development periods ($DY \in [0, 4]$).
- **Metrics Tracked:**
  - `Paid Claims (£)`: Cumulative actual payments disbursed to claimants.
  - `Incurred Claims (£)`: Cumulative paid claims plus case reserves set by handlers.
  - `Earned Premium (£)`: Net earned premium for each accident year cohort.

### BR-02: ChainLadder Development Factor (LDF) Engine
- **Link Ratio Calculation:** For development periods $k \to k+1$, calculate weighted loss development factor:
  $$f_k = \frac{\sum_{i=1}^{n-k} C_{i, k+1}}{\sum_{i=1}^{n-k} C_{i, k}}$$
- **Cumulative Development Factor (CDF):** Product of link ratios from current development stage to tail maturity ($DY_4$):
  $$CDF_j = \prod_{k=j}^{m-1} f_k$$

### BR-03: Ultimate Claims & Reserve Decomposition
- **Projected Ultimate Claims:**
  $$\text{Ultimate Claims}_{AY} = \text{Latest Cumulative Paid Claims}_{AY} \times CDF_{latest}$$
- **Reserve decomposition.** These are three distinct quantities and the engine
  reports them separately. Version 1.0 of this document defined IBNR as ultimate
  minus paid, which is the total unpaid reserve. That definition overstated IBNR
  by the whole case reserve, a factor of 3.15x for Commercial Property AY2020.
  - **Total unpaid (outstanding):** $\text{Ultimate} - \text{Cumulative Paid}$
  - **Case reserves:** $\text{Incurred} - \text{Cumulative Paid}$ (handler-set, on known claims)
  - **IBNR:** $\text{Ultimate} - \text{Incurred}$, equivalently total unpaid less case reserves
- **Ultimate Loss Ratio Metric:**
  $$\text{Loss Ratio}_{AY} = \frac{\text{Ultimate Claims}_{AY}}{\text{Earned Premium}_{AY}}$$

### BR-04: Tail Factor Selection
- **Requirement:** the tail beyond the last observed development year must be
  derived from the data and stated, not assumed to be 1.0.
- **Method:** the ratio of incurred to paid on the oldest accident year at its
  final observed development year. The case reserve still open at that point is
  the handlers' own estimate of what remains to be paid.
- **Result:** Commercial Property 1.013333 (£50,000 still open at DY4).
  Private Motor 1.000000 (fully run off, so no tail is warranted).

### BR-05: Reserve Variability
- **Requirement:** a best-estimate reserve must be accompanied by a measure of
  its uncertainty. A point estimate alone is not a reserving deliverable under
  Solvency II or IFRS 17.
- **Method:** Mack (1993) standard error, with the terminal sigma extrapolated
  by Mack's rule. Reported as a standard error, a coefficient of variation, and
  75th and 95th percentiles on a normal approximation.
- **Validation:** the implementation reproduces the published per-accident-year
  standard errors for the Taylor & Ashe (1983) triangle exactly. See
  `tests/test_reserving.py::TestMackAgainstPublishedBenchmark`.

### BR-06: Bornhuetter-Ferguson A Priori
- **Requirement:** the initial expected loss ratio must be set explicitly per
  line of business and be visible to the reader, since the BF reserve scales
  directly with it.
- **Current setting:** 0.75 for both lines, declared in
  `INITIAL_EXPECTED_LOSS_RATIO` in `src/claims_analysis.py`.
- **Limitation:** in a real engagement this comes from the pricing or business
  plan. It is not derived here, and the BF results should be read as
  conditional on it.

---

## 3. Data Dictionary & Outputs

| Metric Name | Business Definition | Formula | Key Consumer |
|---|---|---|---|
| `latest_paid_claims` | Latest cumulative paid amount | $\max_{DY} \text{Paid}_{AY, DY}$ | Claims Operations |
| `cdf_to_ultimate` | Cumulative multiplier to maturity | $\prod f_k$ | Actuarial Reserving |
| `projected_ultimate_claims` | Estimated final claims cost | $\text{Latest Paid} \times CDF$ | Finance & Solvency II |
| `ibnr_reserve_required` | Unpaid/unreported reserve buffer | $\text{Ultimate} - \text{Latest Paid}$ | Risk Committee |
| `projected_ultimate_loss_ratio` | Claims cost relative to premium | $\text{Ultimate} / \text{Earned Premium}$ | Underwriting |
