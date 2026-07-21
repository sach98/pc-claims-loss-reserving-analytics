# P&C Claims Analytics & Actuarial Reserving Engine

A production-grade Python analytics engine and business analysis specification for Property & Casualty (P&C) claims reserving, loss development triangles, ChainLadder actuarial projections, and Loss Ratio monitoring across multiple lines of business (Commercial Property, Private Motor).

---

## 📊 Business Problem & Executive Summary

In P&C insurance, claims incurred in a given policy year often take multiple years to settle completely. Finance, Risk, and Actuarial teams require reliable estimates of **Ultimate Claims** and **Incurred But Not Reported (IBNR)** reserves to maintain Solvency II capital adequacy and IFRS 17 compliance.

This project delivers:
- **Loss Development Triangles:** Paid and Incurred claims development matrices across 5 accident years (2019–2023) and 5 development periods.
- **ChainLadder Reserving:** Automated calculation of Loss Development Factors (LDF), Cumulative Development Factors (CDF), and IBNR reserve estimates.
- **Loss Ratio Trend Analysis:** Projected Ultimate Loss Ratio ($\text{Ultimate Claims} / \text{Earned Premium}$) tracking underwriting profitability across Commercial Property and Private Motor portfolios.
- **Formal BA Artefacts:** Complete **[Business Requirements Document (BRD)](docs/BRD.md)** detailing data governance, formulas, and reporting specs.

---

## 📈 Key Results at a Glance

### 1. Commercial Property Reserving Summary

| Accident Year | Latest Paid (£) | CDF to Ultimate | Projected Ultimate (£) | Required IBNR Reserve (£) | Ultimate Loss Ratio (%) |
|---|---|---|---|---|---|
| **2019** | £3,750,000 | 1.0000 | £3,750,000 | £0 | 75.0% |
| **2020** | £3,900,000 | 1.0563 | £4,119,570 | £219,570 | 78.5% |
| **2021** | £3,800,000 | 1.2014 | £4,565,320 | £765,320 | 83.0% |
| **2022** | £3,050,000 | 1.6254 | £4,957,470 | £1,907,470 | 85.5% |
| **2023** | £1,850,000 | 2.9478 | £5,453,430 | £3,603,430 | 89.4% |

### 2. Loss Ratio Comparison

![Loss Ratio Trends](outputs/loss_ratios_by_lob.png)

- **Commercial Property:** Loss ratio escalated from **75.0% in 2019 to 89.4% in 2023**, driven by inflation in commercial repair costs and property claim severity.
- **Private Motor:** Stable claims development with loss ratios ranging between **67.7% and 74.2%**, benefiting from shorter settlement tails.

---

## 🛠️ Methodological Architecture

```
Raw Claims Feed (Accident & Dev Years)
              │
              ▼
   Loss Development Triangle
 (Paid & Incurred Matrices)
              │
              ▼
 ChainLadder Development Engine
  (LDF & Link Ratio Calculation)
              │
              ▼
Ultimate Claims & IBNR Projection
(Ultimate = Paid × CDF; IBNR = Ultimate - Paid)
              │
              ▼
  Executive Reporting Output
(Loss Ratios, CSV Summaries & Charts)
```

---

## 🚀 How to Run

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sach98/pc-claims-loss-reserving-analytics.git
   cd pc-claims-loss-reserving-analytics
   ```

2. **Execute the Python Engine:**
   ```bash
   python3 src/claims_analysis.py
   ```
   *Generates `outputs/reserving_summary.csv` and `outputs/loss_ratios_by_lob.png`.*

3. **Explore Jupyter Walkthrough:**
   ```bash
   jupyter notebook notebooks/pc_claims_reserving_walkthrough.ipynb
   ```

---

## 📜 Business Analysis Artifacts
- **[docs/BRD.md](docs/BRD.md)** — Comprehensive Business Requirements Document, Data Dictionary, and Actuarial Formulas.
