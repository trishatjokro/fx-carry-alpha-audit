# Attempt 2: Combined FX Carry + Value + Momentum Blend — G10

## Paper / effect

Naive equal-weighted combination of three well-documented, largely
uncorrelated FX return predictors: carry (interest rate differential),
value (long-horizon PPP/real-exchange-rate reversion), and momentum
(12-1 month spot momentum). The literature's consistent claim is that this
kind of blend is more robust (higher Sharpe, shallower drawdowns) than any
single style alone, because the styles are roughly uncorrelated and tend
to perform in different macro regimes.

- Asness, C., Moskowitz, T., Pedersen, L. H. (2013). "Value and Momentum
  Everywhere." *Journal of Finance*, 68(3), 929–985.
- Menkhoff, L., Sarno, L., Schmeling, M., Schrimpf, A. (2012). "Currency
  Momentum Strategies." *Journal of Financial Economics*, 106(3), 660–684.
- Menkhoff, L., Sarno, L., Schmeling, M., Schrimpf, A. (2017). "Currency
  Value." *Review of Financial Studies* (working paper widely available;
  also summarized in JFE-adjacent working papers).
- Motivating recent evidence that this remains an actively re-tested
  combination, not a one-off: Chernov, Dahlquist, Lochstoer (2024) SSRN
  4802331; Quantpedia's 200-year replication of combined FX
  carry+value+momentum (2024), based on Joseph Chen's long-run dataset,
  reporting a materially higher Sharpe and shallower drawdowns for the
  naive equal-weight 3-style blend vs. any single style.

Freely readable: yes (SSRN/arXiv-adjacent preprints and widely
disseminated working-paper versions of the above).

## Why this is a genuinely different attempt, not a re-tuning of Attempt 1

Attempt 1 (carry alone, G10) came back statistically insignificant in both
IS and OOS. Per the task's anti-p-hacking rule, we did **not** then tweak
attempt 1's leg count, cost assumption, or rebalance rule until OOS looked
better. Instead we tested a different, independently documented effect —
adding two more, largely uncorrelated signals — with combination weights
fixed at equal-weight-of-cross-sectional-rank (the standard, non-optimized
way this is done in the literature, e.g. AQR). No blend-weight search was
performed.

## Methodology

- **Universe**: same 9 G10 currencies vs USD as Attempt 1.
- **Three signals**, each known as of prior month-end t-1:
  1. **Carry**: policy rate differential (foreign − US).
  2. **Value**: −(5-year change in BIS Real Effective Exchange Rate,
     broad, 64-economy index) — i.e., currencies whose real exchange rate
     has depreciated most over 5 years are "cheap" (long candidate).
  3. **Momentum**: 12-1 month spot return (spot(t-1)/spot(t-13) − 1,
     skipping the most recent month per standard convention).
- Each month, currencies are cross-sectionally **ranked** (not z-scored)
  separately on each signal; composite score = simple average of the 3
  ranks. Currencies missing any of the 3 signals that month are dropped
  from the cross-section.
- **Portfolio**: long top 3 / short bottom 3 by composite score,
  equal-weighted, dollar-neutral, monthly rebalance.
- Same transaction cost (2 bps one-way per unit turnover) and return-proxy
  conventions as Attempt 1.
- **In-sample**: 2007-06 → 2018-12 (139 months; starts a year later than
  Attempt 1 because momentum needs a 13-month spot history on top of
  AUD's 2006-05 start). **Out-of-sample**: 2019-01 → 2025-05 (77 months;
  REER data availability ends 2025-05).
- **Benchmarks**: (a) equal-weight long-only basket (same as Attempt 1),
  and (b) Attempt 1's carry-only tercile strategy, recomputed on this
  attempt's exact dates/universe, as the required single-signal baseline.

## Data sources & substitutions (flagged)

- FX spot & policy rates: same as Attempt 1 (yfinance, DBnomics
  `BIS/WS_CBPOL`).
- Value signal: DBnomics dataset `BIS/WS_EER`, series `M.R.B.<country>`
  (Real Effective Exchange Rate, Broad, monthly). This is a trade-weighted
  real effective rate, not a bilateral real-USD rate or a structural PPP
  fair-value estimate — the standard free-data proxy for "cheap/expensive
  vs. own history," consistent with the value literature above.
- Same G10-only, free-data caveats as Attempt 1.

## Results

| Metric | IS (net) | OOS (net) |
|---|---|---|
| Period | 2007-06 to 2018-12 | 2019-01 to 2025-05 |
| N months | 139 | 77 |
| CAGR | -0.40% | 0.18% |
| Ann. Vol | 3.94% | 2.62% |
| Ann. Sharpe | -0.08 | 0.08 |
| Sharpe 95% bootstrap CI | [-0.48, 0.36] | [-0.62, 0.56] |
| Max Drawdown | -10.7% | -4.5% |
| Win rate | 50.4% | 59.7% |
| Mean monthly return | -0.027% | 0.018% |
| t-stat vs 0 | -0.28 | 0.21 |
| p-value | 0.78 | 0.84 |
| Avg monthly turnover | 18.8% | 21.9% |

Baseline (carry-only, same dates/universe): IS Sharpe -0.01, OOS Sharpe
0.22. Benchmark (EW long-only basket): IS Sharpe -0.08, OOS Sharpe -0.04.

Charts: `results/cumulative_returns.png` (shows blend vs carry-only
baseline vs EW benchmark), `results/turnover.png`. Raw panel:
`results/monthly_returns_panel.csv`. Full stats:
`results/summary_stats.csv`.

## Verdict: **DOES NOT HOLD UP**

The 3-signal equal-weight blend is *negative* Sharpe in-sample (-0.08) and
only marginally positive out-of-sample (0.08), with neither period close
to statistical significance (p = 0.78 IS, p = 0.84 OOS). It also
underperforms the simple carry-only baseline out-of-sample (baseline
Sharpe 0.22 vs. blend 0.08 over the same dates/universe). This
contradicts the literature's usual finding that combining carry+value+
momentum improves on any single style — most likely because (a) our
G10-only universe has limited cross-sectional dispersion for all three
signals, (b) the naive REER-based value proxy is a coarse stand-in for
the value signals used in the source papers, and (c) momentum, in
particular, is known to work far better across a large multi-asset-class
universe (Asness-Moskowitz-Pedersen 2013's headline result) than within
9 G10 FX pairs alone. We report this honestly as a genuine miss, not
something to fix by re-weighting the blend until OOS improves.

## Caveats

- Value proxy (BIS REER 5-year reversal) is coarser than the value
  measures in the cited papers.
- Momentum is computed on the same G10-only universe, historically a weak
  place to find currency momentum (which tends to be more of a
  cross-sectional, broad-universe effect).
- Equal rank-weighting across 3 signals is a strong, non-tuned assumption;
  it is possible (but untested here, to avoid p-hacking) that other
  weighting schemes would perform differently — we deliberately did not
  search this space.
- Small sample size (139 / 77 months) limits statistical power.

## Reproduction

```
cd attempt-2-carry-value-momentum-blend
python3 cvm_blend_backtest.py
```
Requires: `yfinance`, `dbnomics`, `pandas`, `numpy`, `scipy`,
`matplotlib`. Internet access required.
