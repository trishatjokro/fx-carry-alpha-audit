"""
Attempt 3: Broad (DM+EM) Cross-Sectional FX Carry, Quintile Sort
====================================================================

Effect being tested: same underlying carry/UIP-violation effect as
attempt 1, but the literature is explicit that the carry premium is
concentrated in, and strongest for, the broad cross-section of currencies
(including high-yielding emerging markets) rather than the G10 alone,
which has much less interest-rate dispersion. This is a genuinely
different, independently-motivated test -- NOT a re-tuning of attempt 1's
parameters on the same universe. Attempt 1 (G10-only carry) was found
statistically insignificant both in-sample and out-of-sample; rather than
tweak leg count / cost assumptions / rebalance frequency on the *same*
G10 universe until OOS looks better (forbidden by design), this attempt
tests the literature's actual claim at the universe on which it was
originally documented: developed + emerging market currencies together.

Primary literature basis:
  - Lustig, Verdelhan (2007), "The Cross Section of Foreign Currency Risk
    Premia and Consumption Growth Risk", American Economic Review 97(1):
    89-117 -- documents that sorting a broad currency cross-section into
    interest-rate portfolios produces a large, priced return spread; this
    is the paper that established using EM+DM currency portfolios sorted
    by interest rate.
  - Menkhoff, Sarno, Schmeling, Schrimpf (2012), "Carry Trades and Global
    Foreign Exchange Volatility", Journal of Finance 67(2): 681-718 --
    same quintile-portfolio-sort methodology used here, applied to a
    broad (~40+ currency) cross-section.
  - Recent (2025) re-examination used to motivate this is an actively
    re-tested effect: Asano, Cai, Sakemoto (2025), "Global Foreign
    Exchange Volatility, Ambiguity, and Currency Carry Trades", SSRN
    4993938 -- re-tests carry portfolios (incl. EM) conditioning on global
    FX volatility/ambiguity regimes.

DATA SUBSTITUTIONS FROM THE ORIGINAL PAPERS (flagged explicitly):
  - Same policy-rate-differential proxy for forward discount as attempts
    1-2 (BIS central bank policy rates via DBnomics, not actual forward
    points / money-market rates). This proxy is coarser for EM currencies,
    where policy rates can diverge more from realized short-term funding
    costs (capital controls, non-deliverable forward premia, sovereign
    risk) than for G10 currencies -- flagged as a real limitation, not
    swept under the rug.
  - Universe: 9 G10 + 16 EM currencies vs USD = 25 total, chosen purely by
    free-data availability (yfinance spot history from ~2003-2006, BIS
    policy rate coverage). This is smaller than Lustig-Verdelhan's or
    Menkhoff et al.'s full samples (40-50 currencies, some with non-
    deliverable-forward-only markets we cannot access for free) but is
    the largest broad cross-section obtainable from free data sources.
    EM set: MXN, ZAR, BRL, INR, TRY, PLN, HUF, CZK, ILS, KRW, IDR, THB,
    PHP, CLP, COP, RON.
  - No transaction-cost differentiation between DM and EM legs, even
    though EM FX genuinely trades wider (this likely *overstates* net
    EM-leg returns and is flagged as an optimistic simplification, not
    hidden).

METHODOLOGY (fixed ex ante, mirroring attempt 1's design exactly except
for universe size and the resulting quintile -- not tuned to make OOS
look better):
  - Signal: policy-rate differential (foreign - US), known at prior
    month-end (no look-ahead), identical construction to attempt 1.
  - Portfolio: quintile sort (standard for N ~20-30 currencies in this
    literature, vs. tercile used for the N=9 G10-only case in attempt 1).
    With 25 currencies, quintile = top 5 (long, highest carry) and bottom
    5 (short, most negative carry), equal-weighted, dollar-neutral,
    monthly rebalance.
  - Same monthly return proxy ((rate diff)/12 + spot return) and 2bps
    one-way transaction cost per unit of turnover as attempts 1-2.
  - Split (same convention as attempt 1, fixed before looking at OOS
    results): In-sample 2006-05 -> 2018-12; Out-of-sample 2019-01 ->
    2025-06.
  - Benchmark: equal-weight long-only basket of all 25 currencies
    (passive), plus attempt 1's G10-only carry as a secondary reference
    line (not a re-tuning target).

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

RESULTS = "/private/tmp/claude-501/-Users-trishatjokrosapoetro/ffa35993-cabc-4b2a-8fb1-084a45231434/scratchpad/alpha-papers/round2-macro-fx/attempt-3-broad-dm-em-carry/results"

DM_TICKERS = {
    "EUR": ("EURUSD=X", "direct"), "GBP": ("GBPUSD=X", "direct"),
    "AUD": ("AUDUSD=X", "direct"), "NZD": ("NZDUSD=X", "direct"),
    "JPY": ("USDJPY=X", "indirect"), "CAD": ("USDCAD=X", "indirect"),
    "CHF": ("USDCHF=X", "indirect"), "SEK": ("USDSEK=X", "indirect"),
    "NOK": ("USDNOK=X", "indirect"),
}
EM_TICKERS = {
    "MXN": ("USDMXN=X", "indirect"), "ZAR": ("USDZAR=X", "indirect"),
    "BRL": ("USDBRL=X", "indirect"), "INR": ("USDINR=X", "indirect"),
    "TRY": ("USDTRY=X", "indirect"), "PLN": ("USDPLN=X", "indirect"),
    "HUF": ("USDHUF=X", "indirect"), "CZK": ("USDCZK=X", "indirect"),
    "ILS": ("USDILS=X", "indirect"), "KRW": ("USDKRW=X", "indirect"),
    "IDR": ("USDIDR=X", "indirect"), "THB": ("USDTHB=X", "indirect"),
    "PHP": ("USDPHP=X", "indirect"), "CLP": ("USDCLP=X", "indirect"),
    "COP": ("USDCOP=X", "indirect"), "RON": ("USDRON=X", "indirect"),
}
FX_TICKERS = {**DM_TICKERS, **EM_TICKERS}

BIS_CODES = {
    "USD": "US", "EUR": "XM", "GBP": "GB", "AUD": "AU", "NZD": "NZ",
    "JPY": "JP", "CAD": "CA", "CHF": "CH", "SEK": "SE", "NOK": "NO",
    "MXN": "MX", "ZAR": "ZA", "BRL": "BR", "INR": "IN", "TRY": "TR",
    "PLN": "PL", "HUF": "HU", "CZK": "CZ", "ILS": "IL", "KRW": "KR",
    "IDR": "ID", "THB": "TH", "PHP": "PH", "CLP": "CL", "COP": "CO",
    "RON": "RO",
}

IS_START, IS_END = "2006-05-01", "2018-12-31"
OOS_START, OOS_END = "2019-01-01", "2025-06-30"
N_LONG = 5
N_SHORT = 5
COST_BPS_ONEWAY = 2.0

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


print("Fetching FX spot data (25 currencies) from yfinance ...")
fx = fetch_fx_monthly()
print(fx.shape, fx.index.min(), fx.index.max())
print("Fetching policy rate data from DBnomics (BIS WS_CBPOL) ...")
rates = fetch_rates_monthly()
print(rates.shape, rates.index.min(), rates.index.max())

fx.to_csv(f"{RESULTS}/raw_fx_monthly.csv")
rates.to_csv(f"{RESULTS}/raw_policy_rates_monthly.csv")

common_idx = fx.index.intersection(rates.index).sort_values()
fx, rates = fx.loc[common_idx], rates.loc[common_idx]

spot_ret = fx[ccys].pct_change()
diff = rates[ccys].sub(rates["USD"], axis=0)
signal = diff.shift(1)
carry_accrual = diff.shift(1) / 100.0 / 12.0

records = []
prev_long, prev_short = set(), set()

for i, dt in enumerate(common_idx):
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
    strat_gross = 0.5 * long_leg_ret - 0.5 * short_leg_ret

    chg_long = len(longs.symmetric_difference(prev_long))
    chg_short = len(shorts.symmetric_difference(prev_short))
    turnover = (chg_long + chg_short) / (2 * (N_LONG + N_SHORT))
    cost = turnover * (COST_BPS_ONEWAY / 10000.0) * 2
    strat_net = strat_gross - cost

    bm_gross = ret_t[ccys].mean()
    bm_cost = (COST_BPS_ONEWAY / 10000.0) if i == 0 else 0.0
    bm_net = bm_gross - bm_cost

    records.append({
        "date": dt, "longs": ",".join(sorted(longs)), "shorts": ",".join(sorted(shorts)),
        "carry_gross": strat_gross, "carry_net": strat_net, "turnover": turnover,
        "bm_gross": bm_gross, "bm_net": bm_net,
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
summary.append(perf_stats(panel.loc[is_mask, "carry_net"], "BROAD CARRY (net) - In-Sample"))
summary.append(perf_stats(panel.loc[oos_mask, "carry_net"], "BROAD CARRY (net) - Out-of-Sample"))
summary.append(perf_stats(panel.loc[is_mask, "carry_gross"], "BROAD CARRY (gross) - In-Sample"))
summary.append(perf_stats(panel.loc[oos_mask, "carry_gross"], "BROAD CARRY (gross) - Out-of-Sample"))
summary.append(perf_stats(panel.loc[is_mask, "bm_net"], "BENCHMARK: EW basket 25ccy (net) - In-Sample"))
summary.append(perf_stats(panel.loc[oos_mask, "bm_net"], "BENCHMARK: EW basket 25ccy (net) - Out-of-Sample"))

print(f"\nAvg monthly turnover (broad carry, IS): {panel.loc[is_mask,'turnover'].mean():.3f}")
print(f"Avg monthly turnover (broad carry, OOS): {panel.loc[oos_mask,'turnover'].mean():.3f}")

pd.DataFrame(summary).to_csv(f"{RESULTS}/summary_stats.csv", index=False)

fig, ax = plt.subplots(figsize=(11, 6))
cum_carry = (1 + panel["carry_net"]).cumprod()
cum_bm = (1 + panel["bm_net"]).cumprod()
ax.plot(cum_carry.index, cum_carry.values, label="Broad DM+EM Carry (quintile L/S, net)", lw=1.8)
ax.plot(cum_bm.index, cum_bm.values, label="Benchmark: EW long-only basket, 25ccy (net)", lw=1.4, alpha=0.8)
ax.axvline(pd.Timestamp(OOS_START), color="gray", linestyle="--", lw=1, label="IS/OOS split")
ax.set_title("Broad (DM+EM) FX Carry Quintile Sort vs Equal-Weight Benchmark")
ax.set_ylabel("Cumulative growth of $1")
ax.legend()
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(f"{RESULTS}/cumulative_returns.png", dpi=130)
plt.close(fig)

fig, ax = plt.subplots(figsize=(11, 4))
ax.bar(panel.index, panel["turnover"], width=20, color="steelblue")
ax.axvline(pd.Timestamp(OOS_START), color="gray", linestyle="--", lw=1)
ax.set_title("Monthly Turnover (fraction of legs changed) - Broad Carry")
fig.tight_layout()
fig.savefig(f"{RESULTS}/turnover.png", dpi=130)
plt.close(fig)

print("\nDone. Results written to:", RESULTS)
