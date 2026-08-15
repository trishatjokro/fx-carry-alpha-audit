"""
Attempt 2: Combined FX Carry + Value + Momentum Signal Blend (G10)
====================================================================

Effect being tested: a naive equal-weighted combination of three
well-documented, largely uncorrelated FX return predictors -- carry
(interest rate differential), value (long-horizon PPP/real-exchange-rate
reversion), and momentum (12-1 month spot momentum). The literature
consistently finds that combining these three "styles" produces a more
robust, higher-Sharpe, lower-drawdown strategy than any single one alone,
because the styles are roughly uncorrelated and tend to do well in
different macro regimes (e.g. value/carry outperform momentum around
turning points, momentum outperforms in trending regimes).

Primary literature basis:
  - Asness, Moskowitz, Pedersen (2013), "Value and Momentum Everywhere",
    Journal of Finance 68(3): 929-985 -- documents FX value and momentum
    and their low correlation / diversification benefit, across countries
    and asset classes.
  - Menkhoff, Sarno, Schmeling, Schrimpf (2012 JF; carry) and (2012 JFE,
    "Currency Momentum Strategies") and Menkhoff, Sarno, Schmeling,
    Schrimpf (2017 JFE, "Currency Value") -- the three underlying single-
    signal FX anomalies used here.
  - Recent (2024-2025) re-examinations of multi-style currency portfolios
    used to motivate that this is an actively re-tested class of effects,
    not a one-off fitted result: Chernov, Dahlquist, Lochstoer (2024),
    "Reassessing Sources of Risk Premiums in Currency Markets" (SSRN
    4802331); Quantpedia's 2024 200-year replication of combined FX carry+
    value+momentum ("FX Carry + Value + Momentum Strategies over Their
    200+ Year History", based on Joseph Chen's long-run dataset) reports
    that a naive equal-weighted 3-style blend has historically had a
    materially higher Sharpe ratio and shallower drawdowns than any single
    style alone -- exactly the design tested here.

WHY THIS IS A DIFFERENT ATTEMPT, NOT A RE-TUNING OF ATTEMPT 1:
  Attempt 1 tested carry alone and found a positive-but-statistically-
  insignificant effect (Sharpe ~0.14 IS, ~0.23 OOS, p>0.5 in both). Rather
  than tweaking attempt 1's carry parameters until OOS looks better (which
  the task explicitly forbids), this attempt tests a genuinely different,
  independently-documented effect: adding two more return predictors
  (value, momentum) that the literature says are largely uncorrelated with
  carry. The combination weights are fixed at equal-weight-of-ranks (the
  standard, non-optimized way this is done in the academic and practitioner
  literature, e.g. AQR) -- we do NOT search over blend weights.

DATA SUBSTITUTIONS FROM THE ORIGINAL PAPERS (flagged explicitly):
  - Same carry proxy as attempt 1 (BIS central bank policy rate
    differential vs USD, not actual forward points).
  - Value signal proxied by BIS Real Effective Exchange Rate, Broad
    (64-economy) index (monthly), via DBnomics dataset BIS/WS_EER,
    M.R.B.<country>. This is a trade-weighted real effective rate, not a
    bilateral real USD exchange rate or true PPP fair value from a
    structural model -- it is the standard, freely available proxy for
    "how rich/cheap is this currency in real terms relative to its own
    history", consistent with Menkhoff et al. (2017) and AQR's approach.
  - Momentum computed from the same free yfinance spot series as attempt 1
    (G10 vs USD only, not the full 40+ currency cross-section academic
    papers typically use).
  - G10-only universe (9 currencies) again -- historically a *harder* test
    than the broader academic cross-section because there is less
    dispersion/idiosyncratic variation to exploit.

METHODOLOGY (fixed ex ante, before any OOS numbers were examined):
  - Universe: EUR, GBP, AUD, NZD, JPY, CAD, CHF, SEK, NOK vs USD (same as
    attempt 1).
  - Three signals, each known as of prior month-end t-1 (no look-ahead):
      1. Carry:    rate_i(t-1) - rate_US(t-1)                 [higher = better]
      2. Value:    -( REER_i(t-1) / REER_i(t-1, 60m ago) - 1 )  [higher = cheaper = better]
      3. Momentum: spot_i(t-1) / spot_i(t-13) - 1  (12-1 month, skip most
                    recent month per standard momentum convention)  [higher = better]
  - Each month, currencies are cross-sectionally RANKED (1=worst..9=best)
    separately on each of the 3 signals; a currency's composite score is
    the simple average of its 3 ranks (equal-weighted combination -- the
    standard "naive diversification" approach, not optimized). Currencies
    missing any of the 3 signals in a given month are dropped from that
    month's cross-section.
  - Portfolio: long top 3 by composite score, short bottom 3, equal-
    weighted within each leg, dollar-neutral, monthly rebalance.
  - Same monthly return proxy, transaction cost (2bps one-way per unit
    turnover), and cost treatment as attempt 1.
  - Split (fixed before looking at OOS results, same convention as
    attempt 1): In-sample 2007-06 -> 2018-12 (starts one year later than
    attempt 1 because momentum needs a 13-month spot history and AUD data
    only starts 2006-05); Out-of-sample 2019-01 -> 2025-05 (REER data ends
    2025-05).
  - Benchmarks: (a) equal-weight long-only basket of all 9 currencies
    (passive, same as attempt 1), and (b) attempt 1's carry-only tercile
    strategy, recomputed on the identical dates/universe as this attempt's
    OOS window, as the "single-signal baseline" per task instructions.

Outputs: results/ CSVs and PNG charts, printed summary stats.
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yfinance as yf
from dbnomics import fetch_series
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS = "/private/tmp/claude-501/-Users-trishatjokrosapoetro/ffa35993-cabc-4b2a-8fb1-084a45231434/scratchpad/alpha-papers/round2-macro-fx/attempt-2-carry-value-momentum-blend/results"

FX_TICKERS = {
    "EUR": ("EURUSD=X", "direct"),
    "GBP": ("GBPUSD=X", "direct"),
    "AUD": ("AUDUSD=X", "direct"),
    "NZD": ("NZDUSD=X", "direct"),
    "JPY": ("USDJPY=X", "indirect"),
    "CAD": ("USDCAD=X", "indirect"),
    "CHF": ("USDCHF=X", "indirect"),
    "SEK": ("USDSEK=X", "indirect"),
    "NOK": ("USDNOK=X", "indirect"),
}

BIS_CODES = {
    "USD": "US", "EUR": "XM", "GBP": "GB", "AUD": "AU", "NZD": "NZ",
    "JPY": "JP", "CAD": "CA", "CHF": "CH", "SEK": "SE", "NOK": "NO",
}

IS_START, IS_END = "2007-06-01", "2018-12-31"
OOS_START, OOS_END = "2019-01-01", "2025-05-31"
N_LONG = 3
N_SHORT = 3
COST_BPS_ONEWAY = 2.0
MOM_LOOKBACK = 12   # months, 12-1 convention (skip most recent month)
VALUE_LOOKBACK = 60  # months, 5-year REER reversal

ccys = list(FX_TICKERS.keys())


def fetch_fx_monthly():
    px = {}
    for ccy, (ticker, conv) in FX_TICKERS.items():
        df = yf.download(ticker, start="2000-01-01", progress=False, auto_adjust=False)
        s = df["Close"][ticker] if isinstance(df["Close"], pd.DataFrame) else df["Close"]
        s = s.dropna()
        if conv == "indirect":
            s = 1.0 / s
        s.index = pd.to_datetime(s.index)
        px[ccy] = s.resample("ME").last()
    fx = pd.DataFrame(px)
    fx.index.name = "date"
    return fx


def fetch_rates_monthly():
    rates = {}
    for ccy, code in BIS_CODES.items():
        df = fetch_series(f"BIS/WS_CBPOL/M.{code}")
        s = df.set_index("period")["value"].sort_index()
        s.index = pd.to_datetime(s.index)
        rates[ccy] = s.resample("ME").last().ffill()
    r = pd.DataFrame(rates)
    r.index.name = "date"
    return r


def fetch_reer_monthly():
    reer = {}
    for ccy, code in BIS_CODES.items():
        df = fetch_series(f"BIS/WS_EER/M.R.B.{code}")
        s = df.set_index("period")["value"].sort_index()
        s.index = pd.to_datetime(s.index)
        reer[ccy] = s.resample("ME").last().ffill()
    r = pd.DataFrame(reer)
    r.index.name = "date"
    return r


print("Fetching FX spot data from yfinance ...")
fx = fetch_fx_monthly()
print("Fetching policy rate data from DBnomics (BIS WS_CBPOL) ...")
rates = fetch_rates_monthly()
print("Fetching REER data from DBnomics (BIS WS_EER) ...")
reer = fetch_reer_monthly()

fx.to_csv(f"{RESULTS}/raw_fx_monthly.csv")
rates.to_csv(f"{RESULTS}/raw_policy_rates_monthly.csv")
reer.to_csv(f"{RESULTS}/raw_reer_monthly.csv")

common_idx = fx.index.intersection(rates.index).intersection(reer.index).sort_values()
fx, rates, reer = fx.loc[common_idx], rates.loc[common_idx], reer.loc[common_idx]

spot_ret = fx[ccys].pct_change()

# --- Signal 1: Carry ---
carry_diff = rates[ccys].sub(rates["USD"], axis=0)
carry_signal = carry_diff.shift(1)
carry_accrual = carry_diff.shift(1) / 100.0 / 12.0

# --- Signal 2: Value (5yr REER reversal) ---
reer_chg_5y = reer[ccys].pct_change(VALUE_LOOKBACK)
value_signal = (-reer_chg_5y).shift(1)

# --- Signal 3: Momentum (12-1 month spot) ---
mom_raw = fx[ccys].pct_change(MOM_LOOKBACK)  # t / t-12 - 1, uses spot up to t
momentum_signal = mom_raw.shift(1)  # known at t-1, i.e. uses spot(t-1)/spot(t-13)-1

# cross-sectional rank (1=worst,...,9=best) per date, per signal
def xs_rank(df):
    return df.rank(axis=1, method="average")

rank_carry = xs_rank(carry_signal)
rank_value = xs_rank(value_signal)
rank_mom = xs_rank(momentum_signal)

composite = pd.DataFrame(index=carry_signal.index, columns=ccys, dtype=float)
for dt in composite.index:
    row = pd.DataFrame({"c": rank_carry.loc[dt], "v": rank_value.loc[dt], "m": rank_mom.loc[dt]})
    complete = row.dropna()
    if len(complete) > 0:
        composite.loc[dt, complete.index] = complete.mean(axis=1)

records = []
prev_long, prev_short = set(), set()
prev_long_c, prev_short_c = set(), set()  # single-signal (carry-only) baseline legs

for i, dt in enumerate(composite.index):
    comp = composite.loc[dt].dropna()
    if len(comp) < (N_LONG + N_SHORT):
        continue
    ranked = comp.sort_values(ascending=False)
    longs = set(ranked.index[:N_LONG])
    shorts = set(ranked.index[-N_SHORT:])

    if dt not in spot_ret.index:
        continue
    ret_t = spot_ret.loc[dt]
    carry_t = carry_accrual.loc[dt]
    if ret_t[list(longs)].isna().any() or ret_t[list(shorts)].isna().any():
        continue

    long_leg_ret = (ret_t[list(longs)] + carry_t[list(longs)]).mean()
    short_leg_ret = (ret_t[list(shorts)] + carry_t[list(shorts)]).mean()
    blend_gross = 0.5 * long_leg_ret - 0.5 * short_leg_ret

    chg_long = len(longs.symmetric_difference(prev_long))
    chg_short = len(shorts.symmetric_difference(prev_short))
    turnover = (chg_long + chg_short) / (2 * (N_LONG + N_SHORT))
    cost = turnover * (COST_BPS_ONEWAY / 10000.0) * 2
    blend_net = blend_gross - cost

    # single-signal carry-only baseline recomputed on this attempt's exact
    # dates/universe (task-required baseline for a blended signal)
    csig = carry_signal.loc[dt].dropna()
    if len(csig) >= (N_LONG + N_SHORT):
        cranked = csig.sort_values(ascending=False)
        clongs, cshorts = set(cranked.index[:N_LONG]), set(cranked.index[-N_SHORT:])
        cl_ret = (ret_t[list(clongs)] + carry_t[list(clongs)]).mean()
        cs_ret = (ret_t[list(cshorts)] + carry_t[list(cshorts)]).mean()
        carry_only_gross = 0.5 * cl_ret - 0.5 * cs_ret
        cchg_l = len(clongs.symmetric_difference(prev_long_c))
        cchg_s = len(cshorts.symmetric_difference(prev_short_c))
        cturn = (cchg_l + cchg_s) / (2 * (N_LONG + N_SHORT))
        carry_only_net = carry_only_gross - cturn * (COST_BPS_ONEWAY / 10000.0) * 2
        prev_long_c, prev_short_c = clongs, cshorts
    else:
        carry_only_net = np.nan

    bm_gross = ret_t[ccys].mean()
    bm_cost = (COST_BPS_ONEWAY / 10000.0) if i == 0 else 0.0
    bm_net = bm_gross - bm_cost

    records.append({
        "date": dt, "longs": ",".join(sorted(longs)), "shorts": ",".join(sorted(shorts)),
        "blend_gross": blend_gross, "blend_net": blend_net, "turnover": turnover,
        "carry_only_net": carry_only_net, "bm_net": bm_net,
    })
    prev_long, prev_short = longs, shorts

panel = pd.DataFrame(records).set_index("date")
panel.to_csv(f"{RESULTS}/monthly_returns_panel.csv")
print(f"Built {len(panel)} months: {panel.index.min()} to {panel.index.max()}")


def perf_stats(returns: pd.Series, label: str):
    r = returns.dropna()
    n = len(r)
    ann_ret = (1 + r).prod() ** (12 / n) - 1
    ann_vol = r.std() * np.sqrt(12)
    sharpe = (r.mean() * 12) / ann_vol if ann_vol > 0 else np.nan
    cum = (1 + r).cumprod()
    dd = cum / cum.cummax() - 1
    max_dd = dd.min()
    win_rate = (r > 0).mean()
    tstat, pval = stats.ttest_1samp(r, 0.0)

    rng = np.random.default_rng(42)
    block, n_boot = 6, 5000
    sharpes = []
    r_arr = r.values
    nblocks = int(np.ceil(n / block))
    for _ in range(n_boot):
        idx = []
        for _b in range(nblocks):
            start = rng.integers(0, max(n - block, 1))
            idx.extend(range(start, min(start + block, n)))
        idx = idx[:n]
        samp = r_arr[idx]
        sv = samp.std()
        sh = (samp.mean() * 12) / (sv * np.sqrt(12)) if sv > 0 else np.nan
        sharpes.append(sh)
    sharpes = np.array([s for s in sharpes if not np.isnan(s)])
    ci_lo, ci_hi = np.percentile(sharpes, [2.5, 97.5])

    print(f"\n--- {label} (n={n} months, {r.index.min().date()} to {r.index.max().date()}) ---")
    print(f"CAGR:              {ann_ret: .4f}")
    print(f"Ann. Vol:          {ann_vol: .4f}")
    print(f"Ann. Sharpe:       {sharpe: .4f}   (95% bootstrap CI: [{ci_lo:.3f}, {ci_hi:.3f}])")
    print(f"Max Drawdown:      {max_dd: .4f}")
    print(f"Win rate (months): {win_rate: .4f}")
    print(f"Mean monthly ret:  {r.mean(): .5f}   t-stat: {tstat: .3f}   p-value: {pval: .4f}")

    return {"label": label, "n_months": n, "cagr": ann_ret, "ann_vol": ann_vol,
            "sharpe": sharpe, "sharpe_ci_lo": ci_lo, "sharpe_ci_hi": ci_hi,
            "max_dd": max_dd, "win_rate": win_rate, "mean_monthly_ret": r.mean(),
            "tstat": tstat, "pvalue": pval}


is_mask = (panel.index >= IS_START) & (panel.index <= IS_END)
oos_mask = (panel.index >= OOS_START) & (panel.index <= OOS_END)

summary = []
summary.append(perf_stats(panel.loc[is_mask, "blend_net"], "BLEND (net) - In-Sample"))
summary.append(perf_stats(panel.loc[oos_mask, "blend_net"], "BLEND (net) - Out-of-Sample"))
summary.append(perf_stats(panel.loc[is_mask, "blend_gross"], "BLEND (gross) - In-Sample"))
summary.append(perf_stats(panel.loc[oos_mask, "blend_gross"], "BLEND (gross) - Out-of-Sample"))
summary.append(perf_stats(panel.loc[is_mask, "carry_only_net"], "BASELINE: Carry-only (net) - In-Sample"))
summary.append(perf_stats(panel.loc[oos_mask, "carry_only_net"], "BASELINE: Carry-only (net) - Out-of-Sample"))
summary.append(perf_stats(panel.loc[is_mask, "bm_net"], "BENCHMARK: EW basket (net) - In-Sample"))
summary.append(perf_stats(panel.loc[oos_mask, "bm_net"], "BENCHMARK: EW basket (net) - Out-of-Sample"))

print(f"\nAvg monthly turnover (blend, IS): {panel.loc[is_mask,'turnover'].mean():.3f}")
print(f"Avg monthly turnover (blend, OOS): {panel.loc[oos_mask,'turnover'].mean():.3f}")

pd.DataFrame(summary).to_csv(f"{RESULTS}/summary_stats.csv", index=False)

fig, ax = plt.subplots(figsize=(11, 6))
cum_blend = (1 + panel["blend_net"]).cumprod()
cum_carry = (1 + panel["carry_only_net"].fillna(0)).cumprod()
cum_bm = (1 + panel["bm_net"]).cumprod()
ax.plot(cum_blend.index, cum_blend.values, label="Carry+Value+Momentum blend (net)", lw=1.8)
ax.plot(cum_carry.index, cum_carry.values, label="Baseline: Carry-only (net)", lw=1.3, alpha=0.85)
ax.plot(cum_bm.index, cum_bm.values, label="Benchmark: EW long-only basket (net)", lw=1.2, alpha=0.7)
ax.axvline(pd.Timestamp(OOS_START), color="gray", linestyle="--", lw=1, label="IS/OOS split")
ax.set_title("FX Carry+Value+Momentum Blend vs Carry-only Baseline vs EW Benchmark (G10)")
ax.set_ylabel("Cumulative growth of $1")
ax.legend()
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(f"{RESULTS}/cumulative_returns.png", dpi=130)
plt.close(fig)

fig, ax = plt.subplots(figsize=(11, 4))
ax.bar(panel.index, panel["turnover"], width=20, color="steelblue")
ax.axvline(pd.Timestamp(OOS_START), color="gray", linestyle="--", lw=1)
ax.set_title("Monthly Turnover (fraction of legs changed) - Blend Strategy")
fig.tight_layout()
fig.savefig(f"{RESULTS}/turnover.png", dpi=130)
plt.close(fig)

print("\nDone. Results written to:", RESULTS)
