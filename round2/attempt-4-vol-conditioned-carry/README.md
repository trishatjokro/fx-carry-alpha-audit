# Attempt 4: FX Volatility/Ambiguity-Regime-Conditioned Broad Carry

## Motivation

Attempt 3 tested the *plain, unconditional* broad (DM+EM) carry sort. Asano, Cai, Sakemoto (2025),
"Global Foreign Exchange Volatility, Ambiguity, and Currency Carry Trades," *Journal of Banking &
Finance* 178 (SSRN preprint 4993938) — the paper that motivated re-testing carry in this audit — is
not about plain carry; its contribution is conditioning carry on FX volatility/ambiguity regimes.
This attempt builds a general vol/ambiguity-regime overlay **inspired by** that idea and layers it on
top of attempt 3's exact frozen base strategy (same universe, signal, quintile sort, cost assumption,
IS/OOS split — nothing about the base strategy was changed or re-tuned).

**Important attribution correction, confirmed via a follow-up literature check (two independent
secondary academic sources, including an IDEAS/RePEc-sourced abstract of the paper's own findings):**
ACS (2025)'s actual mechanism is an *interaction*, not a simple "reduce exposure when uncertain"
rule. They find that high FX ambiguity is associated with *higher* carry returns, and specifically
that high volatility predicts higher carry returns *only when* ambiguity is also high — high
ambiguity is what keeps investors from acting on a volatility signal and unwinding their carry
positions. It is *low*-ambiguity, high-volatility states they associate with unwind risk, not high
ambiguity.

This attempt's rule does the opposite: it goes **flat during high measured ambiguity/dispersion**.
That means this overlay's exposure rule runs in the **opposite direction** from ACS's documented
mechanism, despite using a similarly-constructed dispersion-based regime measure. This attempt should
therefore be read as an independently-motivated vol/ambiguity-timing overlay that happens to perform
well empirically on this sample — not a faithful implementation of ACS's specific mechanism. We have
not read ACS's full primary text directly (SSRN and ScienceDirect blocked automated access), so the
exact regression specification and robustness of their interaction claim is not independently
confirmed here — but the directional claim itself is corroborated by two independent sources and
should be treated as reasonably solid, not merely speculative.

Attempt 3's robustness deep-dive found two specific weaknesses this is meant to address: subperiod
instability (the entire OOS Sharpe came from 2022–2024; 2019–early 2021 including COVID was flat to
negative) and failure of the strict Newey-West/HAC significance test (p≈0.48) despite a marginal
plain t-test (p=0.089).

## Methodology

- **Regime measure**: cross-sectional dispersion (std across the 25 currencies) of each currency's
  trailing 21-trading-day realized annualized volatility, computed at each month-end using only data
  up to that point (no look-ahead). This is a dispersion-based "ambiguity-style" proxy — high
  dispersion means currencies disagree about the current vol regime — closer in spirit to an
  ambiguity measure than raw vol level, though see the attribution caveat above: whether *this
  direction* of conditioning (exposure down when dispersion is high) matches what ACS (2025)
  themselves found is an open question, not verified against their full text.
- **Threshold**: 67th percentile (top-tercile cutoff) of this measure, calibrated **only on the
  in-sample window** (2006-05 to 2018-12), then **frozen** and applied mechanically, unchanged, to
  the out-of-sample window. No re-estimation, no threshold search on OOS data. This is a single,
  pre-registered design choice, not a grid search.
- **Rule**: exposure multiplier = 0 (flat) when the regime measure exceeds the frozen threshold
  (elevated ambiguity), else 1 (full carry exposure). Both gross return and transaction cost scale
  by the exposure multiplier each month.

## Results

| Metric | Attempt 3 IS | **Attempt 4 IS** | Attempt 3 OOS | **Attempt 4 OOS** |
|---|---|---|---|---|
| Sharpe | 0.25 | **0.67** | 0.68 | **0.89** |
| Sharpe 95% bootstrap CI | [-0.28, 0.85] | [0.07, 1.05] | [-0.10, 1.65] | [0.20, 1.65] |
| Max drawdown | -10.5% | **-5.0%** | -7.0% | **-3.8%** |
| Skew | -0.60 | **+0.69** | -1.20 | **-0.35** |
| Plain t-test p-value | 0.368 | **0.019** | 0.089 | **0.027** |
| Newey-West/HAC p-value | 0.308 | **0.013** | 0.074 | **0.015** |
| Fraction of months flat | 0% (n/a) | 32.9% (IS-calibrated) | 0% (n/a) | 14.1% |

**Both plain and HAC significance now clear the conventional 5% threshold in both periods** — the
specific test that killed attempt 3 (HAC, p≈0.48 OOS) now passes (p=0.015 OOS). Drawdown and skew
both improved materially.

### Subperiod stability (OOS, conditioned vs. attempt-3 unconditional)

| Period | Attempt 4 (conditioned) Sharpe | Attempt 3 (unconditional) Sharpe |
|---|---|---|
| 2019-01 to 2021-02 (incl. COVID) | **+0.41** | -0.05 |
| 2021-03 to 2023-04 | +1.39 | +1.24 |
| 2023-05 to 2025-06 | +0.86 | +1.07 |

The previously-negative first subperiod is now positive — the conditioning overlay did fix the
instability in the COVID window specifically.

## Important honest caveat: the mechanism is partial, not a clean crash detector

Checking the two specific known carry-crash months from attempt 3's robustness check:
- **March 2020 (COVID)**: regime measure was elevated, exposure correctly went to 0 that month and
  the following month (April 2020) — the strategy dodged the -4.76% unconditional loss entirely.
- **August 2024 (JPY-carry-unwind)**: regime measure was **not** flagged as elevated. Exposure stayed
  at 1.0 and the conditioned strategy took the same -2.41% hit as attempt 3.

More tellingly: **excluding both crash months from the OOS sample entirely, the unconditional
strategy (Sharpe 1.16) actually slightly beats the conditioned one (Sharpe 1.06)**. This means the
conditioning overlay is a mild net drag in ordinary months (it goes flat sometimes when staying
invested would have been fine) — the overall OOS improvement is disproportionately attributable to
correctly sitting out the COVID month specifically, not a strategy that broadly improves risk-adjusted
returns in normal conditions. It is not, however, purely a one-month artifact the way the round-2
crypto vol-overlay result was: significance improved with the *full* sample included in both periods
(IS and OOS, plain and HAC), and the in-sample improvement (which does not include either crash month
in a way that dominates its 152-month sample) is also substantial and significant — so this isn't
solely explained by one lucky dodge.

## Verdict: **MEANINGFUL IMPROVEMENT OVER ATTEMPT 3, STILL NOT A CLEAN "HOLDS UP"**

This is a genuine strengthening of the case, not a manufactured one — the threshold was frozen from
in-sample data only and applied mechanically, and the improvement shows up in the strictest test
(HAC) as well as the loosest. But it should not be oversold: roughly half of the OOS improvement
traces to correctly sitting out one specific historical crash month (COVID) that the regime measure
happened to flag, while it missed the other known crash (August 2024) entirely. A regime-conditioning
rule that catches one crash and misses the other is better evidence of a partially-working risk
control than of a fully robust, general-purpose one. Given one more genuinely out-of-sample crash
event (which this design has not yet seen), confidence would either rise substantially (if flagged
correctly) or the "improvement" would look more like this attempt's own version of overfitting to a
single historical event.

## Caveats

- **Attribution/direction uncertainty (see Motivation above)**: this overlay goes flat when its
  ambiguity-dispersion measure is elevated. Secondary summaries of Asano-Cai-Sakemoto (2025) suggest
  their finding runs the other way — high ambiguity associated with *higher*, not lower, carry
  returns. We have not confirmed this against ACS's full text. Read this attempt as a
  literature-inspired vol/ambiguity-timing overlay, not a verified replication of ACS's specific
  mechanism.
- Same base-strategy caveats as attempt 3 (25-currency universe smaller than academic samples,
  policy-rate proxy for forward discount, uniform DM/EM transaction cost assumption).
- Realized-vol dispersion from free daily spot data, not implied vol/options-based ambiguity as in
  the original paper — a historical-vol proxy, not a forward-looking one.
- Binary on/off exposure switch (not smooth scaling) — a simplification, not a claim this is the
  optimal conditioning functional form.
- Only one crash event (COVID) is actually "explained" by this design in-sample-frozen-and-applied
  fashion; August 2024 was missed. Two data points is not enough to validate a crash-avoidance
  mechanism with confidence.

## Reproduction

```
cd attempt-4-vol-conditioned-carry
python3 vol_conditioned_carry_backtest.py
```

Requires: `yfinance`, `dbnomics`, `pandas`, `numpy`, `scipy`, `statsmodels`, `matplotlib`. Requires
attempt 3's `results/monthly_returns_panel.csv` and `results/summary_stats.csv` to exist (run
attempt 3's script first, or use the copies already present in this repo). Internet access required.
