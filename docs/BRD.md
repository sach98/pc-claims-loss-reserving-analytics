# Business Requirements Document (BRD)
## P&C Claims Analytics, Loss Reserving & Actuarial Reporting Engine

**Document Control**
- **Author:** Sachin Sharma (Lead Business Analyst & Insurance Analytics Specialist)
- **Status:** Approved / Baseline
- **Target Audience:** Chief Actuary, Claims Operations Lead, Solvency II Reporting Committee

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

### BR-03: Ultimate Claims & IBNR Reserve Calculation
- **Projected Ultimate Claims:**
  $$\text{Ultimate Claims}_{AY} = \text{Latest Cumulative Paid Claims}_{AY} \times CDF_{latest}$$
- **Required IBNR Reserve:**
  $$\text{IBNR Reserve}_{AY} = \text{Ultimate Claims}_{AY} - \text{Latest Cumulative Paid Claims}_{AY}$$
- **Ultimate Loss Ratio Metric:**
  $$\text{Loss Ratio}_{AY} = \frac{\text{Ultimate Claims}_{AY}}{\text{Earned Premium}_{AY}}$$

---

## 3. Data Dictionary & Outputs

| Metric Name | Business Definition | Formula | Key Consumer |
|---|---|---|---|
| `latest_paid_claims` | Latest cumulative paid amount | $\max_{DY} \text{Paid}_{AY, DY}$ | Claims Operations |
| `cdf_to_ultimate` | Cumulative multiplier to maturity | $\prod f_k$ | Actuarial Reserving |
| `projected_ultimate_claims` | Estimated final claims cost | $\text{Latest Paid} \times CDF$ | Finance & Solvency II |
| `ibnr_reserve_required` | Unpaid/unreported reserve buffer | $\text{Ultimate} - \text{Latest Paid}$ | Risk Committee |
| `projected_ultimate_loss_ratio` | Claims cost relative to premium | $\text{Ultimate} / \text{Earned Premium}$ | Underwriting |
