"""
Attempt 1: FX Carry Trade (cross-sectional interest-rate-differential sort)
============================================================================

Effect being tested: the FX carry trade / forward-premium anomaly. Currencies
with higher (short-term) interest rates tend to subsequently outperform
currencies with lower interest rates, violating uncovered interest parity
(UIP). This is one of the most extensively replicated findings in
international finance.

Primary literature basis:
  - Menkhoff, Sarno, Schmeling, Schrimpf (2012), "Carry Trades and Global
    Foreign Exchange Volatility", Journal of Finance 67(2): 681-718.
    -> defines the standard methodology used here: sort currencies each
       period into terciles/quintiles by forward discount (interest rate
       differential), go long the high-rate tercile, short the low-rate
       tercile, equal-weighted, monthly rebalance.
  - Recent re-examinations (2024-2025), used to motivate that this is an
    actively re-tested effect, not a one-off fitted result:
      * Chernov, Dahlquist, Lochstoer (2024), "Reassessing Sources of Risk
        Premiums in Currency Markets", SSRN 4802331.
      * Hsu, Taylor, Wang, Li (2024), "The Out-of-Sample Performance of
        Carry Trades", Journal of International Money and Finance 143,
        also SSRN 3661395 -- IMPORTANT: this paper is actually a *skeptical*
        re-test, finding that carry strategies picked as "best" in-sample
        largely fail to repeat out-of-sample once data-snooping is
        corrected for. We take this as a warning, not a reason to tune our
        design until it "works" -- we instead fix the standard, un-tuned
        Menkhoff et al. design below BEFORE looking at any out-of-sample
        numbers.

DATA SUBSTITUTIONS FROM THE ORIGINAL PAPERS (flagged explicitly):
  - Menkhoff et al. use actual forward exchange rates (1-month forwards)
    from Barclays/Reuters to compute the forward discount and to fund
    trades at prevailing forward points. We do not have free access to
    historical FX forward quotes. Instead we approximate the forward
    discount / carry return using the interest-rate differential between
    each country's central bank policy rate and the US Fed funds rate
    (source: BIS, via DBnomics, dataset BIS/WS_CBPOL). This is a standard
    academic proxy (covered interest parity implies forward discount ~=
    interest differential) but is coarser than actual money-market/
    forward-implied rates and updates only at central bank meeting
    frequency, not continuously.
  - Universe is G10 only (9 currencies vs USD), not Menkhoff et al.'s full
    cross-section of ~40-50 developed + emerging currencies. G10-only carry
    has historically been *weaker* than the full cross-section (less
    dispersion in rates), which is a conservative (harder-to-pass) choice,
    not one that flatters the result.
  - Spot FX from Yahoo Finance (yfinance), which is free but has a shorter
    and occasionally gappy history than institutional data vendors.

METHODOLOGY (fixed ex ante, before any OOS numbers were examined):
  - Universe: EUR, GBP, AUD, NZD, JPY, CAD, CHF, SEK, NOK, all vs USD.
  - Signal: policy-rate differential (foreign - US), known as of the prior
    month-end (no look-ahead: signal uses rate observed at the end of month
    t-1, applied to return realized over month t).
  - Portfolio: standard Menkhoff-style tercile sort. With 9 currencies,
    tercile = top 3 (go long, highest carry) and bottom 3 (go short, most
    negative carry / funding currencies), equal-weighted within each leg,
    dollar-neutral long-short, rebalanced monthly.
  - Monthly currency excess return proxy: (r_foreign - r_US)/12 + spot
    return over the month (spot quoted as USD per unit of foreign
    currency). This is the standard uncovered-return decomposition used
    when forward data are unavailable.
  - Transaction costs: 2 bps one-way per unit of notional turned over,
    charged on every rebalance leg change (conservative for G10 majors,
    which typically trade 0.5-2 bps one-way).
  - Split (fixed before looking at OOS results):
      In-sample (IS):      2006-05 -> 2018-12
      Out-of-sample (OOS): 2019-01 -> 2025-06 (BIS policy-rate data ends
                            2025-06 as of the pull date; this is a genuine
                            data availability limit, not a chosen cutoff to
                            exclude inconvenient recent months)
  - No free parameters are tuned on the IS window and then re-tuned; the
    tercile-sort/monthly-rebalance/2bps-cost design is fixed by literature
    convention. The IS window is used only to report descriptive stats
    prior to the single, frozen OOS evaluation.
  - Benchmark: equal-weight, monthly-rebalanced, long-only basket of all 9
    currencies vs USD (passive USD-diversification exposure, no carry
    signal), same cost treatment.

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

RESULTS = "/private/tmp/claude-501/-Users-trishatjokrosapoetro/ffa35993-cabc-4b2a-8fb1-084a45231434/scratchpad/alpha-papers/round2-macro-fx/attempt-1-fx-carry-tercile/results"

# ----------------------------------------------------------------------
# 1. Universe & tickers
# ----------------------------------------------------------------------
# currency -> (yfinance ticker, quote_convention) ; 'direct' = USD per unit
# foreign ccy (ticker already gives that); 'indirect' = foreign units per
# USD (must invert to get USD per foreign ccy)
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
    "USD": "US",
    "EUR": "XM",
    "GBP": "GB",
    "AUD": "AU",
    "NZD": "NZ",
    "JPY": "JP",
    "CAD": "CA",
    "CHF": "CH",
    "SEK": "SE",
    "NOK": "NO",
}

IS_START, IS_END = "2006-05-01", "2018-12-31"
OOS_START, OOS_END = "2019-01-01", "2025-06-30"
N_LONG = 3
N_SHORT = 3
COST_BPS_ONEWAY = 2.0  # one-way transaction cost in bps of notional

# ----------------------------------------------------------------------
# 2. Fetch FX spot data, build month-end USD-per-foreign-currency prices
# ----------------------------------------------------------------------
def fetch_fx_monthly():
    px = {}
    for ccy, (ticker, conv) in FX_TICKERS.items():
        df = yf.download(ticker, start="2000-01-01", progress=False, auto_adjust=False)
        s = df["Close"][ticker] if isinstance(df["Close"], pd.DataFrame) else df["Close"]
        s = s.dropna()
        if conv == "indirect":
            s = 1.0 / s
        s.index = pd.to_datetime(s.index)
        m = s.resample("ME").last()
        px[ccy] = m
    fx = pd.DataFrame(px)
    fx.index.name = "date"
    return fx


def fetch_rates_monthly():
    rates = {}
    for ccy, code in BIS_CODES.items():
        df = fetch_series(f"BIS/WS_CBPOL/M.{code}")
        s = df.set_index("period")["value"].sort_index()
        s.index = pd.to_datetime(s.index)
        s = s.resample("ME").last().ffill()
        rates[ccy] = s
    r = pd.DataFrame(rates)
    r.index.name = "date"
    return r


print("Fetching FX spot data from yfinance ...")
fx = fetch_fx_monthly()
print(fx.shape, fx.index.min(), fx.index.max())

print("Fetching policy rate data from DBnomics (BIS WS_CBPOL) ...")
rates = fetch_rates_monthly()
print(rates.shape, rates.index.min(), rates.index.max())

fx.to_csv(f"{RESULTS}/raw_fx_monthly.csv")
rates.to_csv(f"{RESULTS}/raw_policy_rates_monthly.csv")

# ----------------------------------------------------------------------
# 3. Align, compute signal (rate differential, known at prior month-end)
#    and spot returns
# ----------------------------------------------------------------------
common_idx = fx.index.intersection(rates.index).sort_values()
fx = fx.loc[common_idx]
rates = rates.loc[common_idx]

ccys = list(FX_TICKERS.keys())
spot_ret = fx[ccys].pct_change()

diff = rates[ccys].sub(rates["USD"], axis=0)  # foreign - US, in percentage points
signal = diff.shift(1)  # known at prior month-end -> used to trade current month

carry_accrual = diff.shift(1) / 100.0 / 12.0  # monthly carry accrual from rate diff (as decimal)

# Full sample date range actually usable (need both fx return and prior signal)
valid_start = max(spot_ret.dropna(how="all").index.min(), signal.dropna(how="all").index.min())
dates = common_idx[(common_idx >= valid_start)]

results_rows = []
prev_long, prev_short = set(), set()
turnover_series = {}

records = []
for i, dt in enumerate(dates):
    if dt not in signal.index or dt not in spot_ret.index:
        continue
    sig = signal.loc[dt].dropna()
    if len(sig) < (N_LONG + N_SHORT):
        continue
    ranked = sig.sort_values(ascending=False)
    longs = set(ranked.index[:N_LONG])
    shorts = set(ranked.index[-N_SHORT:])

    ret_t = spot_ret.loc[dt]
    carry_t = carry_accrual.loc[dt]

    if ret_t[list(longs)].isna().any() or ret_t[list(shorts)].isna().any():
        continue

    long_leg_ret = (ret_t[list(longs)] + carry_t[list(longs)]).mean()
    short_leg_ret = (ret_t[list(shorts)] + carry_t[list(shorts)]).mean()
    strat_ret_gross = 0.5 * long_leg_ret - 0.5 * short_leg_ret

    # turnover: fraction of legs changed this month (0 to 1 per leg, both legs)
    chg_long = len(longs.symmetric_difference(prev_long))
    chg_short = len(shorts.symmetric_difference(prev_short))
    turnover = (chg_long + chg_short) / (2 * (N_LONG + N_SHORT))  # normalized 0..1
    cost = turnover * (COST_BPS_ONEWAY / 10000.0) * 2  # both legs rebalanced, one-way cost each side
    strat_ret_net = strat_ret_gross - cost

    # equal-weight passive benchmark (all 9 currencies, long only)
    bm_ret_gross = ret_t[ccys].mean()
    bm_signal_now = set(ccys)  # static universe, negligible turnover after first month
    bm_turnover = 0.0 if i > 0 else 1.0
    bm_cost = bm_turnover * (COST_BPS_ONEWAY / 10000.0)
    bm_ret_net = bm_ret_gross - bm_cost

    records.append({
        "date": dt, "longs": ",".join(sorted(longs)), "shorts": ",".join(sorted(shorts)),
        "carry_gross": strat_ret_gross, "carry_net": strat_ret_net, "turnover": turnover,
        "bm_gross": bm_ret_gross, "bm_net": bm_ret_net,
    })
    prev_long, prev_short = longs, shorts

panel = pd.DataFrame(records).set_index("date")
panel.to_csv(f"{RESULTS}/monthly_returns_panel.csv")
print(f"Built {len(panel)} months of returns: {panel.index.min()} to {panel.index.max()}")

# ----------------------------------------------------------------------
# 4. Stats helpers
# ----------------------------------------------------------------------
def perf_stats(returns: pd.Series, label: str):
    r = returns.dropna()
    n = len(r)
    ann_ret = (1 + r).prod() ** (12 / n) - 1
    ann_vol = r.std() * np.sqrt(12)
    sharpe = (r.mean() * 12) / ann_vol if ann_vol > 0 else np.nan
    cum = (1 + r).cumprod()
    running_max = cum.cummax()
    dd = cum / running_max - 1
    max_dd = dd.min()
    win_rate = (r > 0).mean()
    tstat, pval = stats.ttest_1samp(r, 0.0)

    # block bootstrap CI on annualized Sharpe (block size ~6 months to
    # capture serial correlation in monthly FX carry returns)
    rng = np.random.default_rng(42)
    block = 6
    n_boot = 5000
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

    return {
        "label": label, "n_months": n, "cagr": ann_ret, "ann_vol": ann_vol,
        "sharpe": sharpe, "sharpe_ci_lo": ci_lo, "sharpe_ci_hi": ci_hi,
        "max_dd": max_dd, "win_rate": win_rate, "mean_monthly_ret": r.mean(),
        "tstat": tstat, "pvalue": pval,
    }


def avg_turnover(t: pd.Series):
    return t.mean()


# ----------------------------------------------------------------------
# 5. Split IS / OOS and compute stats
# ----------------------------------------------------------------------
is_mask = (panel.index >= IS_START) & (panel.index <= IS_END)
oos_mask = (panel.index >= OOS_START) & (panel.index <= OOS_END)

summary = []
summary.append(perf_stats(panel.loc[is_mask, "carry_net"], "CARRY (net) - In-Sample"))
summary.append(perf_stats(panel.loc[oos_mask, "carry_net"], "CARRY (net) - Out-of-Sample"))
summary.append(perf_stats(panel.loc[is_mask, "carry_gross"], "CARRY (gross, no costs) - In-Sample"))
summary.append(perf_stats(panel.loc[oos_mask, "carry_gross"], "CARRY (gross, no costs) - Out-of-Sample"))
summary.append(perf_stats(panel.loc[is_mask, "bm_net"], "BENCHMARK equal-weight basket (net) - In-Sample"))
summary.append(perf_stats(panel.loc[oos_mask, "bm_net"], "BENCHMARK equal-weight basket (net) - Out-of-Sample"))

print(f"\nAvg monthly turnover (carry strategy, IS): {avg_turnover(panel.loc[is_mask,'turnover']):.3f}")
print(f"Avg monthly turnover (carry strategy, OOS): {avg_turnover(panel.loc[oos_mask,'turnover']):.3f}")

summ_df = pd.DataFrame(summary)
summ_df.to_csv(f"{RESULTS}/summary_stats.csv", index=False)

# ----------------------------------------------------------------------
# 6. Charts
# ----------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(11, 6))
cum_carry = (1 + panel["carry_net"]).cumprod()
cum_bm = (1 + panel["bm_net"]).cumprod()
ax.plot(cum_carry.index, cum_carry.values, label="FX Carry (tercile L/S, net of costs)", lw=1.8)
ax.plot(cum_bm.index, cum_bm.values, label="Benchmark: EW long-only basket (net)", lw=1.4, alpha=0.8)
ax.axvline(pd.Timestamp(OOS_START), color="gray", linestyle="--", lw=1, label="IS/OOS split")
ax.set_title("FX Carry (Menkhoff-style tercile sort, G10) vs Equal-Weight Benchmark")
ax.set_ylabel("Cumulative growth of $1")
ax.legend()
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(f"{RESULTS}/cumulative_returns.png", dpi=130)
plt.close(fig)

fig, ax = plt.subplots(figsize=(11, 4))
ax.bar(panel.index, panel["turnover"], width=20, color="steelblue")
ax.axvline(pd.Timestamp(OOS_START), color="gray", linestyle="--", lw=1)
ax.set_title("Monthly Turnover (fraction of legs changed)")
fig.tight_layout()
fig.savefig(f"{RESULTS}/turnover.png", dpi=130)
plt.close(fig)

print("\nDone. Results written to:", RESULTS)
