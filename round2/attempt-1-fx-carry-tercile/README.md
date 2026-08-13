# Attempt 1: FX Carry Trade — G10 Tercile Sort

## Paper / effect

Classic FX carry trade (forward-premium anomaly / UIP violation), tested with
the standard Menkhoff-style methodology:

- Menkhoff, L., Sarno, L., Schmeling, M., Schrimpf, A. (2012). "Carry Trades
  and Global Foreign Exchange Volatility." *Journal of Finance*, 67(2),
  681–718.
- Motivating recent (2024) re-examinations, cited to show this remains an
  actively re-tested effect, not a single stale finding:
  - Chernov, M., Dahlquist, M., Lochstoer, L. A. (2024). "Reassessing
    Sources of Risk Premiums in Currency Markets." SSRN 4802331.
  - Hsu, P.-H., Taylor, M. P., Wang, Z., Li, Y. (2024). "The Out-of-Sample
    Performance of Carry Trades." *Journal of International Money and
    Finance*, 143. Also SSRN 3661395. **Note**: this paper is itself
    skeptical — it finds that carry strategies chosen as "best" in-sample
    largely fail to repeat OOS once data-snooping bias is corrected for.
    We used this as a caution, not as license to keep tuning our design.

Freely readable: yes (SSRN preprints / working papers linked above; the
Menkhoff et al. JF 2012 methodology is widely summarized in freely
available working-paper versions).

## Methodology

- **Universe**: 9 G10 currencies vs USD — EUR, GBP, AUD, NZD, JPY, CAD,
  CHF, SEK, NOK.
- **Signal**: month-end central bank policy rate differential (foreign −
  US), known as of the *prior* month-end (no look-ahead).
- **Portfolio**: standard tercile sort. Long top 3 (highest carry), short
  bottom 3 (lowest/most negative carry), equal-weighted within each leg,
  dollar-neutral, monthly rebalance.
- **Monthly return proxy**: (rate differential)/12 + spot return (USD per
  foreign currency unit) — the standard decomposition used when actual
  forward rates are unavailable.
- **Transaction costs**: 2 bps one-way per unit of turnover, both legs.
- **In-sample**: 2006-06 → 2018-12 (151 months). **Out-of-sample**:
  2019-01 → 2025-06 (78 months), fixed *before* any OOS number was
  examined.
- **Benchmark**: equal-weight, monthly-rebalanced, long-only basket of all
  9 currencies vs USD.

## Data sources & substitutions (flagged)

- FX spot: yfinance (`EURUSD=X`, `GBPUSD=X`, `AUDUSD=X`, `NZDUSD=X`,
  `USDJPY=X`, `USDCAD=X`, `USDCHF=X`, `USDSEK=X`, `USDNOK=X`).
- Policy rates: DBnomics, dataset `BIS/WS_CBPOL` (BIS central bank policy
  rates), monthly, end of period. **Substitution**: used in place of
  actual 1-month forward points / money-market rates (not freely
  available historically); this is a standard academic proxy via covered
  interest parity but is coarser and updates only at meeting frequency.
- Universe is G10-only, smaller than Menkhoff et al.'s ~40-50 currency
  cross-section — a conservative (harder-to-pass), not flattering, choice.
- AUDUSD=X on Yahoo only starts 2006-05, which sets the earliest usable
  date for the whole universe.

## Results

| Metric | IS (net) | OOS (net) |
|---|---|---|
| Period | 2006-06 to 2018-12 | 2019-01 to 2025-06 |
| N months | 151 | 78 |
| CAGR | 0.51% | 0.63% |
| Ann. Vol | 4.21% | 2.92% |
| Ann. Sharpe | 0.14 | 0.23 |
| Sharpe 95% bootstrap CI | [-0.48, 0.83] | [-0.41, 0.95] |
| Max Drawdown | -15.9% | -5.6% |
| Win rate | 55.0% | 56.4% |
| Mean monthly return | 0.050% | 0.056% |
| t-stat vs 0 | 0.50 | 0.59 |
| p-value | 0.62 | 0.56 |
| Avg monthly turnover | 2.3% | 4.3% |

Gross-of-cost numbers are nearly identical (costs are small given low
turnover — see `results/summary_stats.csv`).

Benchmark (equal-weight long-only basket, net): IS Sharpe -0.04, OOS
Sharpe -0.02 — both negative, so the carry strategy beats the passive
benchmark in both periods, but the carry strategy's own returns are not
statistically distinguishable from zero in either period.

Charts: `results/cumulative_returns.png`, `results/turnover.png`.
Raw panel: `results/monthly_returns_panel.csv`. Full stats:
`results/summary_stats.csv`.

## Verdict: **DOES NOT HOLD UP** (statistically)

The G10-only carry signal has the correct sign and modestly positive
Sharpe in both IS (0.14) and OOS (0.23) periods, and it beats a negative
passive benchmark in both — but neither period's mean return is
statistically distinguishable from zero (t-stats 0.50 and 0.59; bootstrap
Sharpe CIs both comfortably straddle 0). This is consistent with Hsu et
al. (2024)'s finding that G10-only carry premia have weakened/become
noisy in recent decades. We do not consider this a genuine, demonstrated
edge — it is directionally suggestive but not evidence of a real,
tradeable effect at this universe size and sample.

## Caveats

- Policy-rate proxy for forward discount, not true forward points.
- G10-only universe → limited cross-sectional dispersion in rates,
  historically the weakest place to find carry premia (see Attempt 3 for
  the broader-cross-section version of this same effect).
- No allowance for regime shifts in central bank meeting frequency change
  over the sample.
- Small sample (151 / 78 months) limits statistical power.

## Reproduction

```
cd attempt-1-fx-carry-tercile
python3 fx_carry_backtest.py
```
Requires: `yfinance`, `dbnomics`, `pandas`, `numpy`, `scipy`,
`matplotlib`. Internet access required (pulls fresh data from Yahoo
Finance and DBnomics on each run).
