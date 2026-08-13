# Replication test: FX time-series momentum (TSMOM) from Pollok & Robik (2026)

## Paper

**"End-to-End Parametric Portfolio Policies for Cross-Asset Futures Timing: When Do AI Models Beat Simple Rules?"**
Austin Pollok (USC) & Kevin Robik (Critical Technologies, LLC)
arXiv:2607.00475v1 [q-fin.ST], submitted 1 Jul 2026
https://arxiv.org/abs/2607.00475

**Claimed alpha (summary):** The paper trains end-to-end neural allocation policies (a transformer and an LSTM) on the 16 most liquid CME futures across six asset classes, and benchmarks them against three simple rules — equal weight (1/N), risk parity, and 12-month time-series momentum (TSMOM). The paper's main finding is that the learned policies beat the simple rules in some sleeves but not others, and it is explicit that **"time-series momentum is hardest to beat in rates and currencies."** For the FX sleeve specifically (2 contracts: Euro FX and Japanese Yen FX futures), TSMOM is the only one of the three simple rules with a positive out-of-sample Sharpe ratio (0.25 gross / 0.23 net of costs, 2011–2024), while 1/N and risk parity are both negative (~-0.36). We treat **TSMOM on the FX sleeve** as the concrete, replicable "trading signal" and test whether it holds up out of sample with free data.

## What we replicated, and how

### Signal (exactly as specified in the paper, Sections II–III)
- **Momentum lookback:** trailing 252-trading-day (12-month) return, fixed, never tuned (`sign(P_{t-1}/P_{t-253} - 1)`).
- **Position sizing:** vol-scaled score `raw_i,t = signal_i,t / realized_vol_i,t`, then renormalized across the universe each day so gross exposure `sum(|w_i,t|) = 1` ("unit gross exposure," per the paper's Section III).
- **Realized-vol lookback window:** the paper does not state this number explicitly (only "the standard 12-month signal" for the momentum part). We treat it as the one free parameter and calibrate it in-sample from `{20, 60, 100}` trading days by maximizing in-sample net Sharpe, then lock it for all out-of-sample tests (see `tsmom_fx_backtest.py`, selected value printed at runtime: **20 days**).
- **Benchmarks:** 1/N (equal weight, constant target weight ⇒ zero turnover by construction, matching the paper's own turnover definition) and risk parity (60-day inverse-volatility weights, long-only) — both specified explicitly in the paper.
- **Rebalance:** daily. **Transaction cost:** 2bp per unit of turnover (`turnover_t = 0.5·Σ|w_i,t − w_i,t-1|`), the paper's stated baseline; we also report a 1/2/5/10bp sensitivity table.
- **Portfolio return:** `r_P,t = Σ w_i,t-1 · r_i,t` (yesterday's weight applied to today's return — the paper's Eq. 2).

### Deviations from the paper (explicitly flagged)
1. **Instrument substitution.** The paper uses Barchart continuous CME futures (6E Euro FX, 6J Japanese Yen FX). Free equivalents are not available, so we substitute **daily spot FX from Yahoo Finance** (`yfinance`): `EURUSD=X` for 6E, and `1/(JPY=X)` for 6J (Yahoo's `JPY=X` is quoted USD-per-JPY... actually JPY-per-USD; we invert it to USD-per-JPY so it moves in the same direction as "long JPY," matching 6J and matching `EURUSD=X`'s convention). Spot FX has no futures roll/term-structure carry embedded and no exchange margining — it is a reasonable but **not identical** proxy for the futures the paper used.
2. **Shorter in-sample window.** The paper's models train on 2000–2010. Yahoo's `EURUSD=X` only goes back to 2003-12-01, so our in-sample/calibration window is **2003-12-01 to 2010-12-31** (about 7 years vs. the paper's 10). Our out-of-sample window matches the paper's exactly: **2011-01-01 to 2024-12-31**.
3. **Extra genuinely-fresh holdout.** Since the paper posted to arXiv in July 2026, we add a **2025-01-01 to 2026-08-10** holdout window that literally could not have been seen by the authors or leaked into their design choices. This is the strongest out-of-sample test in this report.
4. **Extended universe (robustness check, not in the paper).** We also run the identical signal on a 6-currency G10 basket (EUR, JPY, GBP, AUD, CAD, CHF) to see whether the paper's 2-asset result generalizes. This is our addition, not a paper claim.
5. No DBnomics data was used: the replicated signal is purely price-based (spot FX from yfinance), so no macro/rates series were needed.

## Data sources and date ranges
- **Source:** Yahoo Finance via `yfinance` (`EURUSD=X`, `JPY=X`, `GBPUSD=X`, `AUDUSD=X`, `CAD=X`, `CHF=X`).
- **In-sample (calibration):** 2003-12-01 to 2010-12-31.
- **Out-of-sample (matches paper):** 2011-01-01 to 2024-12-31.
- **Post-paper holdout (fresh, unseen by authors):** 2025-01-01 to 2026-08-10 (latest available at run time).

## Results

All figures are annualized; Sharpe/Sortino/Calmar use net-of-cost returns unless labeled "gross." Full numbers in `results/backtest_results.csv`.

### Core universe (EUR, JPY) — matches the paper's exact FX sleeve

| Period | Strategy | Return | Vol | Sharpe (gross) | Sharpe (net, 2bp) | 95% CI (net Sharpe, block bootstrap) | MDD | Turnover | Win rate | t-stat | p-value |
|---|---|---|---|---|---|---|---|---|---|---|---|
| In-sample 2003.12–2010 | 1/N | 3.9% | 9.4% | 0.42 | 0.42 | [-0.29, 1.08] | 14.4% | 0.00 | 50.2% | 1.13 | 0.258 |
| In-sample 2003.12–2010 | Risk parity | 3.8% | 9.3% | 0.41 | 0.41 | [-0.28, 1.09] | 14.5% | 0.005 | 48.5% | 1.10 | 0.270 |
| In-sample 2003.12–2010 | **TSMOM** | 0.04% | 12.9% | 0.02 | **0.00** | [-0.51, 0.44] | 18.9% | 0.035 | 43.6% | 0.01 | 0.994 |
| OOS 2011–2024 (matches paper) | 1/N | -2.7% | 7.1% | -0.39 | -0.39 | [-0.85, 0.11] | 40.5% | 0.00 | 47.9% | -1.47 | 0.142 |
| OOS 2011–2024 (matches paper) | Risk parity | -2.8% | 6.9% | -0.40 | -0.41 | [-0.88, 0.10] | 41.4% | 0.004 | 48.0% | -1.55 | 0.122 |
| OOS 2011–2024 (matches paper) | **TSMOM** | 0.7% | 6.1% | 0.16 | **0.12** | [-0.43, 0.64] | 25.0% | 0.045 | 51.5% | 0.45 | 0.652 |
| Holdout 2025–2026 (unseen) | 1/N | 3.2% | 7.4% | 0.43 | 0.43 | [-0.98, 1.54] | 8.1% | 0.00 | 47.3% | 0.56 | 0.579 |
| Holdout 2025–2026 (unseen) | Risk parity | 3.9% | 7.4% | 0.53 | 0.53 | [-0.90, 1.63] | 7.5% | 0.004 | 48.1% | 0.68 | 0.497 |
| Holdout 2025–2026 (unseen) | **TSMOM** | -4.4% | 6.2% | -0.68 | **-0.71** | [-2.24, 0.81] | 8.5% | 0.038 | 48.8% | -0.91 | 0.361 |

### Paper's own reported numbers (FX sleeve, futures data, OOS 2011–2024) vs. our spot-FX replication

| Strategy | Paper NetSharpe (futures) | Our NetSharpe (spot FX) | Paper turnover | Our turnover | Paper MDD | Our MDD |
|---|---|---|---|---|---|---|
| 1/N | -0.36 | -0.39 | 0.00 | 0.00 | 0.49 | 0.40 |
| Risk parity | -0.37 | -0.41 | 0.00 | 0.004 | 0.50 | 0.41 |
| **TSMOM** | **0.23** | **0.12** | 0.03 | 0.045 | 0.20 | 0.25 |

Directionally, the naive-benchmark numbers replicate closely (both around -0.4 Sharpe, similar MDD), which is a good sign the free-data substitution is reasonable. **TSMOM replicates the correct sign and correct ranking (TSMOM > 1/N, TSMOM > risk parity) but at roughly half the paper's reported magnitude**, and — critically — with a t-stat of 0.45 (p=0.65) and a bootstrapped 95% Sharpe CI of [-0.43, 0.64] that comfortably contains zero.

### Extended G10 universe (EUR, JPY, GBP, AUD, CAD, CHF) — our robustness addition, not in the paper

| Period | Strategy | Sharpe (net) | t-stat | p-value |
|---|---|---|---|---|
| OOS 2011–2024 | 1/N | -0.28 | -1.07 | 0.284 |
| OOS 2011–2024 | Risk parity | -0.31 | -1.20 | 0.232 |
| OOS 2011–2024 | **TSMOM** | **-0.16** | -0.62 | 0.535 |
| Holdout 2025–2026 | **TSMOM** | **-0.38** | -0.48 | 0.630 |

When the same signal is applied to a broader, more standard G10 basket rather than the paper's narrow 2-asset (EUR, JPY) sleeve, the TSMOM Sharpe **turns negative** in both the matched out-of-sample window and the fresh holdout. The paper's positive FX result does not generalize beyond its specific 2-instrument universe.

### Transaction-cost sensitivity (core universe, TSMOM, OOS 2011–2024)

| Cost (bp, one-way) | Net Sharpe |
|---|---|
| 1 | 0.14 |
| 2 (paper's baseline) | 0.12 |
| 5 | 0.06 |
| 10 | -0.03 |

The already-weak, statistically insignificant edge disappears entirely once costs exceed ~8bp one-way — plausible for a strategy trading only spot-liquid G10 pairs, but this shows the result has very little margin for error.

Charts: `results/equity_and_drawdown_oos.png`, `results/equity_holdout.png`, `results/equity_extended_universe_oos.png`.

## VERDICT: **DOES NOT HOLD UP** out-of-sample after costs (with one caveat: the paper's own narrow claim partially replicates directionally, but not statistically)

The signal's sign and ranking (TSMOM beats naive long-only benchmarks) does replicate in the paper's exact 2-currency universe over the paper's exact out-of-sample window, which is a mild positive sign that the underlying mechanism (rather than a data-mining artifact) is being captured. However: (1) the out-of-sample Sharpe we measure (0.12) is roughly half what the paper reports and is **not statistically distinguishable from zero** (t=0.45, p=0.65, 95% CI spans -0.43 to 0.64); (2) it **fails outright** — flips to negative Sharpe — on a genuinely fresh 2025–2026 holdout the paper's authors never saw; (3) it **fails outright** on a broader, more standard G10 currency universe instead of the paper's narrow 2-asset sleeve; and (4) it is not robust to transaction costs above ~8bp. A trader relying on this specific paper's FX TSMOM claim as free-standing alpha, rather than as one input the paper itself describes as merely "hard to beat" relative to a demanding null (naive diversification), would not have made money net of costs going forward.

## Caveats / limitations
- Spot FX is a proxy for CME futures; roll yield/carry embedded in the futures term structure is absent here, which could account for some of the Sharpe gap versus the paper.
- The FX sleeve in both the paper and this replication is thin (2 instruments), so all Sharpe estimates have wide confidence intervals — this is a low-power test by construction, which is itself part of why the paper's authors correct for multiple testing (Bonferroni across seven universes) and note only the equity-index result survives that correction; **the FX/TSMOM Sharpe was never claimed by the paper's own authors to be significant after correction**.
- We calibrated one free parameter (realized-vol window) in-sample; the paper does not specify this parameter, so our choice is a best-effort reconstruction, not a literal replication of an undisclosed implementation detail.
- Daily returns are not fully independent (autocorrelation, especially post-cost), so the simple t-test / block-bootstrap should be read as indicative rather than exact; we used a 21-day block bootstrap specifically to mitigate (not eliminate) this.
- 2026-dated market data reflects this environment's live data feed as of the run date; treat the 2025–2026 holdout as illustrative rather than a long, statistically powerful sample (~19 months).

## Reproduce
```bash
cd paper-c-macro-fx-rates
pip3 install yfinance pandas numpy scipy matplotlib
python3 tsmom_fx_backtest.py
```
Outputs land in `results/`: `backtest_results.csv` (full metrics table), `cost_sensitivity.csv`, `paper_vs_replication.csv`, and three PNG charts (OOS equity/drawdown, holdout equity, extended-universe equity).
