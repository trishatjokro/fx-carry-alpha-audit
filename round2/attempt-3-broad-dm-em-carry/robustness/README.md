# Robustness deep-dive: Broad (DM+EM) FX Carry, quintile sort

Diagnostic-only follow-up on `../broad_carry_backtest.py` (Attempt 3, the strongest of the 9
round-2 candidates, originally verdict "PARTIALLY HOLDS UP": OOS Sharpe 0.68, p=0.089, IS 0.25).
**No signal parameters were changed** — this only stress-tests the already-frozen strategy.
Code: `robustness_checks.py`. Outputs: `results/`.

## 1. Can the OOS window be extended to today?

**No, not meaningfully.** The signal's rate data (BIS `WS_CBPOL` via DBnomics) has a genuine
reporting lag: as of this check, the freshest monthly observation is **2025-06** (matching an
alternate free source, IMF IFS `FPOLM_PA`, which offers exactly one more month, 2025-07). FX spot
data (yfinance) is current through 2026-08, but the rate leg — the actual carry signal — is not.
The original OOS window (through 2025-06-30) was already pushed to the real data frontier; there
is no untested "extra" free data being left on the table. This is a genuine limitation of free
policy-rate sources, not a choice that could bias the original test.

## 2. Cost sensitivity

| Cost (one-way) | OOS Sharpe | OOS p-value |
|---|---|---|
| 0 bps | 0.680 | 0.087 |
| 1 bp (0.5x) | 0.678 | 0.088 |
| 2 bps (1x, original) | 0.675 | 0.089 |
| 4 bps (2x) | 0.671 | 0.091 |
| 6 bps (3x) | 0.666 | 0.094 |
| 10 bps (5x) | 0.656 | 0.098 |

**Essentially cost-insensitive.** Monthly turnover is low (~3-4%, since a rate-differential rank
changes slowly month to month), so even a 5x cost shock barely moves the Sharpe. This is a real
point in the strategy's favor and a sharp contrast with round 1's FX momentum paper, which died
above ~8bps — that strategy's edge *was* the trading cost.

## 3. PSR, skew/kurtosis, stationary bootstrap

| Period | Skew | Kurtosis | PSR (P[true Sharpe>0]) | iid boot 95% CI | Stationary block boot 95% CI |
|---|---|---|---|---|---|
| IS | -0.61 | 4.91 | 0.810 | [-0.29, 0.84] | [-0.19, 0.78] |
| OOS | -1.22 | 6.51 | **0.934** | [-0.10, 1.69] | [-0.10, 1.64] |

Both periods are meaningfully negatively skewed and fat-tailed — the crash-risk signature carry
trades are supposed to have (confirmed, not just eyeballed off two bad months as in the original
README). The Probabilistic Sharpe Ratio, which explicitly penalizes for that skew/kurtosis rather
than assuming a normal Sharpe estimator, puts **93.4% probability that the true OOS Sharpe exceeds
zero** — more favorable than the plain two-sided t-test suggests, because PSR is a one-directional
"is it positive" question (closer to a one-sided test; the original two-sided p=0.089 corresponds
to a one-sided p≈0.044, which *does* clear 5% if you treat "carry premium is positive" as an
ex-ante directional hypothesis, which the 40+ years of carry literature supports). The
stationary (random block-length) bootstrap CI is nearly identical to the original fixed-block
bootstrap — confirms the original CI wasn't understating uncertainty from autocorrelation.

## 4. Subperiod stability — the important new caveat

| Window | Sharpe |
|---|---|
| 2019 | 0.89 |
| 2020 (COVID) | **-0.81** |
| 2021 | 0.26 |
| 2022 | 1.18 |
| 2023 | 2.38 |
| 2024 | 0.98 |
| 2025 (partial) | 0.49 |
| Block 1 (2019-01→2021-02) | **-0.05** |
| Block 2 (2021-03→2023-04) | 1.24 |
| Block 3 (2023-05→2025-06) | 1.07 |

**This is the one check that meaningfully tempers the upgrade.** The OOS result is not evenly
distributed — the first third of the OOS window (spanning COVID) is flat-to-negative, and the
entire positive result comes from 2021 onward, concentrated hardest in 2022-2024. That maps
cleanly onto a real, well-documented macro event (the Fed-vs-BOJ rate divergence and "yen carry
trade" period that dominated financial press through the August 2024 unwind we already flagged as
a crash month) — so the concentration has an economic explanation rather than looking like noise.
But it does mean the original README's "OOS at least as strong as IS throughout" framing slightly
overstates uniformity; a live trader holding this strategy through 2019-2021 would have seen ~2
flat-to-losing years before it worked.

## 5. Factor exposure (dollar factor + SPY, HAC/Newey-West SEs, 6 lags)

| Period | Monthly alpha (t, p) | β to dollar factor (t, p) | β to SPY (t, p) | R² |
|---|---|---|---|---|
| IS | 0.068% (t=0.73, p=0.47) | 0.150 (t=2.20, **p=0.028**) | 0.073 (t=1.53, p=0.13) | 0.20 |
| OOS | 0.108% (t=0.71, p=0.48) | -0.086 (t=-1.08, p=0.28) | 0.075 (t=1.95, p=0.051) | 0.06 |

Low R² in both periods (0.20 IS, 0.06 OOS) means this is **not** repackaged dollar-factor or
equity-market beta — it's largely orthogonal to both, which is a genuine point of reassurance
against the "disguised known factor" concern. But note the HAC-adjusted alpha itself is *not*
significant in either period (t≈0.7) — weaker than the plain t-test, because Newey-West standard
errors properly account for the same autocorrelation/fat-tails already visible in check 3. This
is the most sobering number in the whole robustness pass: once you use a conservative, serial-
correlation-robust estimator and control for the two obvious factor exposures, the standalone
alpha is comfortably inside noise.

## 6. Literature Sharpe comparison (narrative, from general knowledge of the literature —
not re-verified against the primary sources in this pass)

Menkhoff, Sarno, Schmeling & Schrimpf (2012) report the classic HML_FX carry portfolio (broad
cross-section, 1983-2009) earning a Sharpe in roughly the 0.8-0.9 range pre-costs. Subsequent
literature and BIS commentary widely document carry performance decaying through the 2010s as
DM policy rates converged near zero, then reviving sharply in 2022-2024 amid the Fed/BOJ
divergence. Our numbers fit this arc well: IS Sharpe 0.25 (2006-2018, spanning the GFC and the
low-rate decade) sits below the historical pre-GFC estimate, consistent with a genuinely weak
carry regime; OOS Sharpe 0.68 (2019-2025) sits much closer to the historical range and is
concentrated exactly where the financial press and BIS reporting say carry did well. This
consistency with known market history is reassuring against a data/implementation bug — a bug
would have no reason to line up with the real-world carry cycle.

## Updated verdict

**Confidence has gone up, but not enough to call a clean "HOLDS UP."**

What improved: cost-robustness is a real, previously-untested point in its favor (this is not a
turnover-fragile strategy like round 1's momentum paper); PSR properly accounting for skew/
kurtosis gives 93%+ confidence the true OOS Sharpe is positive; it is not disguised dollar or
equity beta; and the OOS gains land in exactly the period independent, non-strategy-specific
financial history says carry should have worked.

What holds it back: conventional two-sided significance is still not cleared (p=0.089); the HAC-
robust regression alpha, which is the most methodologically conservative estimate in this whole
exercise, is squarely insignificant (p≈0.48); and subperiod analysis shows real instability — the
first ~26 months of OOS were flat/negative, so this is not a strategy that would have looked good
continuously.

**Final call: PARTIALLY HOLDS UP — the strongest and most literature-consistent result in either
round of this project, worth further live-tracking, but still short of a demonstrated,
statistically robust edge.** A one-sided/PSR reading is more favorable than the original two-sided
framing and is defensible given the directional theory behind carry, but this report keeps the
more conservative two-sided verdict as the headline to avoid inflating a marginal result.

## Reproduction

```
cd attempt-3-broad-dm-em-carry/robustness
python3 robustness_checks.py
```
Requires the parent attempt's `results/monthly_returns_panel.csv` to already exist (run
`../broad_carry_backtest.py` first if not). Additional dependency: `statsmodels`.
