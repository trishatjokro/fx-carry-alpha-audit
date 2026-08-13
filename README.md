# FX Carry Alpha Audit

Independent replication of FX carry-trade alpha claims, tested with **free data**, a **frozen
in-sample/out-of-sample split** (no tuning against OOS results), **realistic transaction costs**, and
**statistical significance testing** — including robustness checks (cost sensitivity, distribution-aware
significance, factor decomposition, subperiod stability) on the most promising result, not just a
single headline number.

## TL;DR

Three attempts, one genuinely promising result — but even the best one falls short of a clean
"holds up" verdict once tested rigorously enough.

| Round | Strategy | In-sample Sharpe | Out-of-sample Sharpe | Verdict |
|---|---|---|---|---|
| 1 | TSMOM on FX futures (Pollok & Robik 2026, [arXiv:2607.00475](https://arxiv.org/abs/2607.00475)) | — | 0.12, p=0.65; **-0.71** on fresh 2025-26 holdout | DOES NOT HOLD UP |
| 2 | G10 FX carry, tercile sort | 0.14, p=0.62 | 0.23, p=0.56 | DOES NOT HOLD UP |
| 2 | Carry+Value+Momentum blend, G10 | -0.08, p=0.78 | 0.08, p=0.84 | DOES NOT HOLD UP |
| 2 | **Broad DM+EM carry, quintile sort, 25 currencies** | 0.25, p=0.37 | **0.68, p=0.089** | **PARTIALLY HOLDS UP** |

## The strongest candidate: broad DM+EM carry

Based on the effect documented in:
- Lustig, H., Verdelhan, A. (2007). "The Cross Section of Foreign Currency Risk Premia and
  Consumption Growth Risk." *American Economic Review*, 97(1), 89–117.
- Menkhoff, L., Sarno, L., Schmeling, M., Schrimpf, A. (2012). "Carry Trades and Global Foreign
  Exchange Volatility." *Journal of Finance*, 67(2), 681–718.
- Asano, T., Cai, X., Sakemoto, R. (2025). "Global Foreign Exchange Volatility, Ambiguity, and
  Currency Carry Trades." *Journal of Banking & Finance*, 178 (SSRN preprint 4993938) — the recent
  paper that motivated re-testing this now.

**What's genuinely encouraging:**
- Out-of-sample Sharpe (0.68) exceeds in-sample (0.25) — the opposite of the "looks good in-sample,
  collapses out-of-sample" pattern typical of overfitting. Parameters were frozen before the OOS
  window was ever examined.
- Nearly cost-insensitive: Sharpe only drifts from 0.68 to 0.66 even at 5x the baseline cost
  assumption (10bps one-way) — genuinely different from round 1's FX momentum paper, which died
  above 8bps.
- Probabilistic Sharpe Ratio (accounting for the negative skew/fat tails carry trades are known to
  have) = 0.934 — 93% probability the true Sharpe is positive.
- Low factor exposure (R² 0.06–0.20) to a dollar-factor basket and to SPY — not disguised beta to a
  more mundane risk factor.
- Drawdowns land exactly on known carry-crash events (COVID March 2020, the August 2024 JPY-carry
  unwind) — the textbook risk signature of a genuine carry premium.

**What holds it back from a clean "HOLDS UP":**
- Under Newey-West/HAC standard errors (the most conservative, appropriate estimator for
  autocorrelated returns), the alpha is **insignificant** in both periods (p≈0.48) — the strictest
  test in the whole exercise kills the signal.
- Subperiod instability: the OOS window is not uniformly strong. The first ~26 months (2019–early
  2021, including COVID) were flat-to-negative (Sharpe ≈ -0.05); the entire result is concentrated
  in 2022–2024, the well-documented Fed/BOJ carry-divergence period. Economically coherent, but
  undercuts a "stable throughout" reading.
- Plain two-sided significance (p=0.089) doesn't clear the conventional 5% threshold.

**Verdict: PARTIALLY HOLDS UP.** The most literature-consistent, mechanism-sound, cost-robust result
across everything tested (12 attempts across equities, crypto/vol, and macro/FX domains) — but by the
most rigorous statistical standard, still short of a demonstrated edge.

## Layout

```
round1/paper-c-macro-fx-rates/                        TSMOM replication (round 1)
round2/attempt-1-fx-carry-tercile/                     G10 carry, tercile sort
round2/attempt-2-carry-value-momentum-blend/           Combined signal, G10
round2/attempt-3-broad-dm-em-carry/                    Broad 25ccy carry (strongest result)
round2/attempt-3-broad-dm-em-carry/robustness/         Deep-dive robustness checks
round2/SUMMARY.md                                       Cross-attempt summary
```

Each attempt folder contains: paper citation(s), exact methodology as implemented (with data-proxy
substitutions flagged), data sources/date ranges, full IS vs OOS results table, a VERDICT line,
caveats, and reproduction steps.

## Data sources

- FX spot: [yfinance](https://github.com/ranaroussi/yfinance) (free, no key)
- Policy rates (carry signal, forward-discount proxy): [DBnomics](https://db.nomics.world/) `BIS/WS_CBPOL`
  (free REST API, no key) — used instead of FRED directly, which has proven unreliable/rate-limited
- No forward-rate or NDF data was available for free; policy-rate differentials were used as a proxy
  for the forward discount, flagged explicitly in each attempt's README

## Caveats that apply across the board

- Small number of independent attempts — a spot-check of the literature, not a systematic survey.
- 25-currency universe is smaller than academic full samples (Lustig-Verdelhan/Menkhoff et al. use
  40–50 currencies, some only accessible via non-deliverable forwards unavailable for free).
- Uniform transaction-cost assumption across DM and EM legs likely flatters EM-leg returns somewhat,
  since EM FX trades wider than 2bps in practice.
- Sample is ~19 years; two major carry-unwind events (2020, 2024) dominate the tail risk profile — a
  longer sample would give a cleaner read.
- "Partially holds up" means: directionally consistent with 20 years of published literature,
  economically sensible, cost-robust — but not statistically proven at conventional significance on
  this sample. It is evidence in favor of the effect being real, not proof.

## Reproduction

Each attempt folder is independently runnable:

```
cd round2/attempt-3-broad-dm-em-carry
python3 broad_carry_backtest.py
```

Requires: `yfinance`, `dbnomics`, `pandas`, `numpy`, `scipy`, `matplotlib`, `statsmodels`. Internet
access required (fetches free FX and policy-rate data at runtime).
