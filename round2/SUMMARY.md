# Round 2 (Macro/FX/Rates) — Overview of Replication Attempts

Goal: find a macro/FX/rates trading signal from the recent literature that
survives an honest, non-p-hacked out-of-sample test, after three prior
replication attempts in other domains (including a TSMOM-on-FX paper)
failed to hold up out-of-sample.

**Rule followed throughout**: for each attempt, methodology (universe,
signal definition, portfolio construction, costs, IS/OOS split) was fixed
*before* any out-of-sample number was computed or examined. When an
attempt failed, we moved to a genuinely different paper/effect rather than
re-tuning the same strategy's parameters until OOS looked better.

## Attempts

| # | Folder | Effect tested | Universe | OOS Sharpe | OOS t-stat (p) | Verdict |
|---|---|---|---|---|---|---|
| 1 | `attempt-1-fx-carry-tercile/` | FX carry (interest rate differential), tercile sort | 9 G10 currencies | 0.23 | 0.59 (p=0.56) | **DOES NOT HOLD UP** |
| 2 | `attempt-2-carry-value-momentum-blend/` | Carry+Value+Momentum blend (equal-weight ranks) | 9 G10 currencies | 0.08 | 0.21 (p=0.84) | **DOES NOT HOLD UP** |
| 3 | `attempt-3-broad-dm-em-carry/` | FX carry, broad DM+EM cross-section, quintile sort | 9 G10 + 16 EM = 25 currencies | 0.68 | 1.72–1.79 (p≈0.07–0.09) | **PARTIALLY HOLDS UP** |

## Which one (if any) holds up

**Attempt 3 (broad DM+EM carry)** is the closest to a genuine finding, but
we are deliberately not calling it a clean "HOLDS UP" because it does not
clear the conventional 5% significance threshold (p ≈ 0.07–0.09, both
plain and Newey-West t-tests) and its in-sample Sharpe (0.25, t=0.90,
p=0.37) is itself not significant. What makes it the most credible of the
three, in order of importance:

1. **OOS was not weaker than IS** — OOS Sharpe (0.68) exceeds IS Sharpe
   (0.25). Overfit/data-mined strategies almost always show the opposite
   pattern (great IS, decaying OOS); since the strategy design was frozen
   before the OOS window was touched, this pattern could not have been
   engineered.
2. **Economically sensible tail behavior**: the OOS return series is
   negatively skewed, and its two worst months are March 2020 (COVID
   crash) and August 2024 (the well-documented JPY-carry-unwind episode)
   — exactly the systemic events genuine carry trades are known to be hurt
   by. A spurious or buggy result would be less likely to line up with
   known real-world carry-crash dates.
3. **Not driven by one outlier month**: excluding the single best OOS
   month, Sharpe only falls from 0.68 to 0.59 (t from 1.72 to 1.50).
4. **Directionally consistent with the literature's own claim**: carry
   premia are documented to be concentrated in the broad DM+EM
   cross-section (Lustig-Verdelhan 2007; Menkhoff et al. 2012), and indeed
   the G10-only version of the identical signal (Attempt 1) failed while
   the broad-cross-section version (Attempt 3) came closest to working —
   consistent with, not contradicting, the academic literature's own
   caveat about where carry premia live.

That said, honestly: p ≈ 0.08 and a bootstrap Sharpe CI that still
touches zero in-sample means this is **suggestive, not proven**. A
practitioner should treat it as "worth monitoring / consistent with prior
literature" rather than "statistically demonstrated alpha."

## Why the other two failed

- **Attempt 1 (G10 carry alone)**: correct sign, modest positive Sharpe in
  both periods (0.14 IS / 0.23 OOS), beat a negative passive benchmark in
  both periods, but never came close to statistical significance
  (p > 0.5 throughout). Consistent with Hsu, Taylor, Wang, Li (2024,
  JIMF) — an actual paper in the literature — which finds that carry
  strategies that look good in one period frequently fail an honest OOS
  test, especially in the low-dispersion G10 subset.
- **Attempt 2 (Carry+Value+Momentum blend, G10)**: the literature's claim
  that blending styles beats any single style did **not** replicate here
  — the blend was Sharpe-negative in-sample (-0.08) and only marginally
  positive OOS (0.08), underperforming even the plain carry-only baseline
  OOS (0.22). Most likely explanation: our free-data value proxy (BIS REER
  5-year reversal) and momentum, both computed on a small 9-currency G10
  universe, are much weaker versions of the signals used in the source
  papers, which typically rely on larger cross-sections and/or richer
  value measures.

## Data sources used (free, no API key)

- FX spot: `yfinance` (Yahoo Finance), monthly closes.
- Policy rates and Real Effective Exchange Rates: `dbnomics` Python
  package, dataset `BIS/WS_CBPOL` (central bank policy rates) and
  `BIS/WS_EER` (Real Effective Exchange Rate, broad, monthly) — DBnomics
  mirrors BIS data reliably without hitting FRED directly.

## Honest limitations across all three attempts

- Policy rates are used as a proxy for forward-implied interest
  differentials; none of the attempts have access to free historical FX
  forward quotes.
- All backtests are limited to ~19 years of monthly data (2006–2025),
  giving modest statistical power (78 OOS months) and only two major
  systemic carry-unwind episodes (2020, 2024) in the tail.
- Transaction costs (2bps one-way) are a simplifying, uniform assumption;
  real EM execution costs are higher than G10.
- No results here should be read as investment advice; this is a research
  replication exercise using free data and out-of-sample discipline, not
  a production trading strategy.

## Reproduction

Each `attempt-N-*/` folder contains a self-contained Python script that
pulls fresh data from yfinance and DBnomics and reproduces its results
folder from scratch:

```
cd attempt-1-fx-carry-tercile && python3 fx_carry_backtest.py
cd attempt-2-carry-value-momentum-blend && python3 cvm_blend_backtest.py
cd attempt-3-broad-dm-em-carry && python3 broad_carry_backtest.py
```

Requires: `yfinance`, `dbnomics`, `pandas`, `numpy`, `scipy`,
`statsmodels`, `matplotlib`. Internet access required (no local data
caching between runs by design, to keep results honest/reproducible).
