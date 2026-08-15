# Attempt 3: Broad (DM+EM) Cross-Sectional FX Carry — Quintile Sort

## Paper / effect

Same underlying carry/UIP-violation effect as Attempt 1, but tested on the
universe where the literature actually documents it most strongly: a
broad developed + emerging market currency cross-section, not G10 alone.

- Lustig, H., Verdelhan, A. (2007). "The Cross Section of Foreign Currency
  Risk Premia and Consumption Growth Risk." *American Economic Review*,
  97(1), 89–117. Establishes sorting a broad (DM+EM) currency
  cross-section into interest-rate portfolios.
- Menkhoff, L., Sarno, L., Schmeling, M., Schrimpf, A. (2012). "Carry
  Trades and Global Foreign Exchange Volatility." *Journal of Finance*,
  67(2), 681–718. Same quintile-sort methodology used here, applied to a
  broad cross-section.
- Motivating recent (2025) re-examination: Asano, T., Cai, X., Sakemoto,
  R. (2025). "Global Foreign Exchange Volatility, Ambiguity, and Currency
  Carry Trades." SSRN 4993938 — re-tests carry portfolios (including EM)
  conditioning on global FX volatility/ambiguity regimes.

Freely readable: yes (SSRN preprints linked above).

## Why this is a genuinely different attempt, not a re-tuning of Attempt 1

Attempt 1 tested carry on G10 only and came back statistically
insignificant. Rather than adjust attempt 1's parameters on the *same*
universe until OOS looked better (forbidden), this attempt tests the
literature's actual original claim on the universe it was documented on:
the broad cross-section including emerging markets, which have much
larger interest-rate dispersion. The signal construction, monthly
rebalance, and cost assumptions are otherwise identical to Attempt 1 — only
the universe size changed (9 → 25 currencies), which mechanically changes
tercile (N=9) to quintile (N=25) sort per literature convention for larger
cross-sections. No other parameter was tuned, and this was decided before
looking at any OOS numbers.

## Methodology

- **Universe**: 9 G10 (EUR, GBP, AUD, NZD, JPY, CAD, CHF, SEK, NOK) + 16 EM
  currencies vs USD — MXN, ZAR, BRL, INR, TRY, PLN, HUF, CZK, ILS, KRW,
  IDR, THB, PHP, CLP, COP, RON. 25 currencies total.
- **Signal**: policy rate differential (foreign − US), known at prior
  month-end (identical construction to Attempt 1).
- **Portfolio**: quintile sort — long top 5 (highest carry), short bottom
  5 (lowest/most negative carry), equal-weighted, dollar-neutral, monthly
  rebalance.
- Same return proxy ((rate diff)/12 + spot return) and 2 bps one-way
  transaction cost per unit turnover as Attempt 1.
- **In-sample**: 2006-05 → 2018-12 (152 months). **Out-of-sample**:
  2019-01 → 2025-06 (78 months) — identical split convention to Attempt 1,
  fixed before looking at OOS results.
- **Benchmark**: equal-weight, monthly-rebalanced, long-only basket of all
  25 currencies vs USD.

## Data sources & substitutions (flagged)

- FX spot: yfinance, 16 additional EM tickers (`USDMXN=X`, `USDZAR=X`,
  `USDBRL=X`, `USDINR=X`, `USDTRY=X`, `USDPLN=X`, `USDHUF=X`, `USDCZK=X`,
  `USDILS=X`, `USDKRW=X`, `USDIDR=X`, `USDTHB=X`, `USDPHP=X`, `USDCLP=X`,
  `USDCOP=X`, `USDRON=X`), all available from ~2003-2005 onward.
- Policy rates: DBnomics `BIS/WS_CBPOL`, same proxy caveat as Attempt 1 —
  **more acute for EM**, where policy rates can diverge further from
  realized short-term funding costs (capital controls, NDF premia,
  sovereign risk) than for G10. This is a real limitation, flagged, not
  hidden.
- 25-currency universe is smaller than Lustig-Verdelhan's or Menkhoff et
  al.'s full samples (40-50 currencies, some accessible only via
  non-deliverable forwards we cannot get for free).
- No differentiation of transaction costs between DM and EM legs, even
  though EM FX genuinely trades wider than 2bps in practice — this likely
  *overstates* net EM-leg returns somewhat; flagged as an optimistic
  simplification.

## Results

| Metric | IS (net) | OOS (net) |
|---|---|---|
| Period | 2006-05 to 2018-12 | 2019-01 to 2025-06 |
| N months | 152 | 78 |
| CAGR | 1.09% | 2.68% |
| Ann. Vol | 4.72% | 4.04% |
| Ann. Sharpe | 0.25 | 0.68 |
| Sharpe 95% bootstrap CI | [-0.28, 0.85] | [-0.10, 1.65] |
| Max Drawdown | -10.5% | -7.0% |
| Win rate | 55.3% | 65.4% |
| Mean monthly return | 0.100% | 0.227% |
| t-stat vs 0 (plain) | 0.90 | 1.72 |
| p-value (plain) | 0.37 | 0.089 |
| t-stat vs 0 (Newey-West, 6 lags) | 1.02 | 1.79 |
| p-value (Newey-West) | 0.31 | 0.074 |
| Avg monthly turnover | 3.2% | 4.0% |

Benchmark (equal-weight long-only basket, 25ccy, net): IS Sharpe -0.16,
OOS Sharpe -0.25 — negative in both periods.

**Robustness checks performed on the OOS window before finalizing the
verdict** (diagnostic only — no parameters were changed as a result):
- OOS return distribution is negatively skewed (skew -1.22) with the two
  worst months being March 2020 (-4.76%, COVID crash) and August 2024
  (-2.41%, the well-known JPY-carry-unwind episode). This is exactly the
  crash-risk signature the carry literature associates with genuine carry
  trades — a real strategy should occasionally get hurt by exactly these
  events, and this one does, which is reassuring rather than a red flag.
- Excluding the single best OOS month (May 2023, +2.71%), OOS Sharpe falls
  from 0.68 to 0.59 and the t-stat falls from 1.72 to 1.50 (p rises to
  0.14) — so the result is not manufactured by one freak month, though it
  is not overwhelmingly strong either.

Charts: `results/cumulative_returns.png`, `results/turnover.png`. Raw
panel: `results/monthly_returns_panel.csv`. Full stats:
`results/summary_stats.csv`.

## Verdict: **PARTIALLY HOLDS UP**

This is the strongest of the three attempts and the only one where the
out-of-sample period is *not weaker* than in-sample — OOS Sharpe (0.68) is
actually higher than IS Sharpe (0.25), which argues against the "IS looks
good, OOS collapses" pattern typical of overfitting (since the strategy
design was frozen before OOS was examined, this pattern could not have
been engineered). The OOS mean return is marginally significant at the
10% level (t = 1.72–1.79, p ≈ 0.07–0.09) but does **not** clear the
conventional 5% significance threshold, and the bootstrap 95% CI on
Sharpe still includes zero in-sample (though it excludes most of the
negative range out-of-sample: [-0.10, 1.65]). The strategy also shows the
economically sensible crash-risk profile (negative skew, hurt by known
carry-unwind events) that genuine carry trades are expected to exhibit,
which is a good sign it is not an artifact/bug.

Given the pre-registered rule not to inflate marginal results, we call
this **partially** holds up: directionally consistent with the literature,
economically sensible, OOS at least as strong as IS, but short of
conventional statistical significance and therefore not a fully
"demonstrated" edge on this sample.

## Caveats

- Marginal statistical significance (p ≈ 0.07–0.09, not < 0.05).
- EM policy-rate proxy is coarser than G10 (capital controls, NDF premia
  not captured).
- 25-currency universe, smaller than academic full samples.
- Uniform 2bps cost assumption likely flatters EM legs, which trade wider
  in practice — a more realistic EM cost assumption would lower net
  returns somewhat.
- Sample still limited to ~19 years of data; two major carry-unwind events
  (2020, 2024) dominate the tail — a longer sample would give a cleaner
  read on tail risk.

## Reproduction

```
cd attempt-3-broad-dm-em-carry
python3 broad_carry_backtest.py
```
Requires: `yfinance`, `dbnomics`, `pandas`, `numpy`, `scipy`,
`matplotlib`, `statsmodels` (for the Newey-West robustness check, run
separately — see script comments). Internet access required.
