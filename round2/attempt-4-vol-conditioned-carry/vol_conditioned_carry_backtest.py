"""
Attempt 4: FX Volatility/Ambiguity-Regime-Conditioned Broad Carry
====================================================================

Motivation: attempt 3 tested the *plain, unconditional* broad (DM+EM)
carry sort. But the paper that actually motivated re-testing carry in
this audit -- Asano, Cai, Sakemoto (2025), "Global Foreign Exchange
Volatility, Ambiguity, and Currency Carry Trades", SSRN 4993938 -- is not
about plain carry. Its real contribution is conditioning carry exposure
on FX volatility/ambiguity regimes to avoid carry-crash drawdowns. This
attempt implements that conditioning mechanism (not the plain sort) on
top of attempt 3's exact frozen base strategy.

Attempt 3's own robustness deep-dive found two specific weaknesses this
is meant to address:
  1. Subperiod instability: OOS Sharpe was flat/negative in 2019-early
     2021 (incl. COVID) and the entire 0.68 OOS Sharpe came from
     2022-2024.
  2. Fails the strict Newey-West/HAC significance test (p ~ 0.48) even
     though the plain t-test was marginal (p = 0.089).

Hypothesis: scaling down carry exposure during high FX-volatility-
dispersion ("ambiguity") regimes should reduce crash-driven negative
skew and smooth the return profile enough to move HAC significance and
subperiod stability in the right direction.

BASE STRATEGY (unchanged from attempt 3, not re-tuned):
  - Universe: 9 G10 + 16 EM currencies vs USD (25 total).
  - Signal: policy rate differential (foreign - USD), known at prior
    month-end (BIS WS_CBPOL via DBnomics).
  - Quintile sort: long top 5 (highest carry), short bottom 5 (lowest),
    equal-weighted, dollar-neutral, monthly rebalance.
  - 2bps one-way transaction cost per unit of turnover.
  - Split: In-sample 2006-05 to 2018-12; Out-of-sample 2019-01 to
    2025-06 -- identical to attempt 3.

NEW: VOLATILITY/AMBIGUITY CONDITIONING OVERLAY
  - Regime measure R(t): cross-sectional DISPERSION (std across the 25
    currencies) of each currency's trailing 21-trading-day realized
    annualized volatility, computed at each month-end using only data up
    to that month-end (no look-ahead). This is the "ambiguity" proxy --
    high dispersion means currencies disagree about the current vol
    regime, which is closer to what Asano-Cai-Sakemoto measure than raw
    vol level.
  - Threshold: the 67th percentile (top tercile cutoff) of R(t) computed
    ONLY on the in-sample window (2006-05 to 2018-12). This numeric
    value is then FROZEN and applied mechanically, unchanged, to the
    out-of-sample window. No re-estimation, no threshold search on OOS
    data.
  - Rule: exposure multiplier s(t) = 0.0 if R(t) > frozen IS threshold
    (elevated ambiguity regime -- go flat), else s(t) = 1.0 (full carry
    exposure). This is a single, pre-registered design choice, not a
    grid search.
  - Both the strategy's gross return AND its transaction cost scale by
    s(t) each month (reduced position size => proportionally reduced
    trading cost), i.e.:
        conditioned_gross(t) = s(t) * carry_gross(t)
        conditioned_cost(t)  = s(t) * carry_cost(t)
        conditioned_net(t)   = conditioned_gross(t) - conditioned_cost(t)

DATA SUBSTITUTIONS (same as attempt 3, flagged again for this file):
  - Policy-rate-differential proxy for forward discount (not true forward
    points), coarser for EM (capital controls, NDF premia not captured).
  - 25-currency universe (free-data-available subset), smaller than
    academic 40-50 currency samples.
  - Realized vol computed from yfinance daily spot closes (no options
    data / implied vol available for free) -- "ambiguity" here is a
    historical-vol-dispersion proxy, not the model-based ambiguity
    measure in the original paper.

Outputs: results/ CSVs + PNGs, printed summary stats, head-to-head
comparison against attempt 3.
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yfinance as yf
from dbnomics import fetch_series
from scipy import stats
import statsmodels.api as sm
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS = "/private/tmp/claude-501/-Users-trishatjokrosapoetro/ffa35993-cabc-4b2a-8fb1-084a45231434/scratchpad/alpha-papers/round2-macro-fx/attempt-4-vol-conditioned-carry/results"
ATT3_PANEL = "/private/tmp/claude-501/-Users-trishatjokrosapoetro/ffa35993-cabc-4b2a-8fb1-084a45231434/scratchpad/alpha-papers/round2-macro-fx/attempt-3-broad-dm-em-carry/results/monthly_returns_panel.csv"
ATT3_SUMMARY = "/private/tmp/claude-501/-Users-trishatjokrosapoetro/ffa35993-cabc-4b2a-8fb1-084a45231434/scratchpad/alpha-papers/round2-macro-fx/attempt-3-broad-dm-em-carry/results/summary_stats.csv"

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
ccys = list(FX_TICKERS.keys())

IS_START, IS_END = "2006-05-01", "2018-12-31"
OOS_START, OOS_END = "2019-01-01", "2025-06-30"
VOL_LOOKBACK_DAYS = 21
REGIME_TERCILE = 0.67  # top-tercile cutoff, calibrated on IS only


def fetch_fx_daily():
    px = {}
    for ccy, (ticker, conv) in FX_TICKERS.items():
        df = yf.download(ticker, start="2000-01-01", progress=False, auto_adjust=False)
        s = df["Close"][ticker] if isinstance(df["Close"], pd.DataFrame) else df["Close"]
        s = s.dropna()
        if conv == "indirect":
            s = 1.0 / s
        s.index = pd.to_datetime(s.index)
        px[ccy] = s
    fx_daily = pd.DataFrame(px).sort_index().ffill()
    fx_daily.index.name = "date"
    return fx_daily


print("Fetching daily FX spot data (25 currencies) for realized-vol regime measure ...")
fx_daily = fetch_fx_daily()
print(fx_daily.shape, fx_daily.index.min(), fx_daily.index.max())

daily_ret = fx_daily[ccys].pct_change()
realized_vol = daily_ret.rolling(VOL_LOOKBACK_DAYS).std() * np.sqrt(252)

# Month-end snapshot of each currency's trailing realized vol (no look-ahead:
# uses only data up to and including that month-end date).
vol_monthly = realized_vol.resample("ME").last()

# Regime measure R(t): cross-sectional dispersion (std across currencies)
# of month-end trailing realized vol.
regime = vol_monthly.std(axis=1, skipna=True)
regime.name = "vol_dispersion"
regime.to_csv(f"{RESULTS}/regime_measure_monthly.csv")

# ---- Load attempt 3's frozen base-strategy monthly panel (unchanged) ----
panel = pd.read_csv(ATT3_PANEL, index_col=0, parse_dates=True)
panel.index.name = "date"

common_idx = panel.index.intersection(regime.index).sort_values()
panel = panel.loc[common_idx]
regime = regime.loc[common_idx]

is_mask = (panel.index >= IS_START) & (panel.index <= IS_END)

# ---- Calibrate threshold on IS window ONLY, then freeze ----
is_regime_values = regime.loc[is_mask].dropna()
frozen_threshold = is_regime_values.quantile(REGIME_TERCILE)
print(f"\nFrozen IS-calibrated regime threshold (67th pct of vol dispersion, IS only): {frozen_threshold:.6f}")
print("This exact numeric value is applied unchanged to the OOS window below.")

exposure = (regime <= frozen_threshold).astype(float)  # 1.0 = full exposure, 0.0 = flat (elevated ambiguity)
exposure.name = "exposure_multiplier"

panel["exposure"] = exposure
panel["cond_gross"] = panel["exposure"] * panel["carry_gross"]
panel["cond_cost"] = panel["exposure"] * (panel["carry_gross"] - panel["carry_net"])
panel["cond_net"] = panel["cond_gross"] - panel["cond_cost"]

panel.to_csv(f"{RESULTS}/monthly_returns_panel_conditioned.csv")

is_mask = (panel.index >= IS_START) & (panel.index <= IS_END)
oos_mask = (panel.index >= OOS_START) & (panel.index <= OOS_END)

print(f"\nExposure=1 (full carry) fraction of months -- IS: {panel.loc[is_mask,'exposure'].mean():.3f}, "
      f"OOS: {panel.loc[oos_mask,'exposure'].mean():.3f}")


def hac_ttest(r: pd.Series, maxlags=6):
    """Newey-West/HAC t-test on the mean of r being different from 0,
    via OLS of r on a constant with HAC standard errors."""
    r = r.dropna()
    X = np.ones((len(r), 1))
    model = sm.OLS(r.values, X).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    return model.params[0], model.tvalues[0], model.pvalues[0]


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
    _, hac_t, hac_p = hac_ttest(r)
    skew = stats.skew(r)
    kurt = stats.kurtosis(r)

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
    print(f"Skew / Kurtosis:   {skew: .3f} / {kurt: .3f}")
    print(f"Mean monthly ret:  {r.mean(): .5f}   plain t: {tstat: .3f} (p={pval:.4f})   "
          f"HAC t: {hac_t: .3f} (p={hac_p:.4f})")

    return {"label": label, "n_months": n, "cagr": ann_ret, "ann_vol": ann_vol,
            "sharpe": sharpe, "sharpe_ci_lo": ci_lo, "sharpe_ci_hi": ci_hi,
            "max_dd": max_dd, "win_rate": win_rate, "skew": skew, "kurtosis": kurt,
            "mean_monthly_ret": r.mean(), "tstat": tstat, "pvalue": pval,
            "hac_tstat": hac_t, "hac_pvalue": hac_p}


summary = []
summary.append(perf_stats(panel.loc[is_mask, "cond_net"], "VOL-CONDITIONED CARRY (net) - In-Sample"))
summary.append(perf_stats(panel.loc[oos_mask, "cond_net"], "VOL-CONDITIONED CARRY (net) - Out-of-Sample"))
summary.append(perf_stats(panel.loc[is_mask, "carry_net"], "ATTEMPT 3 UNCONDITIONAL CARRY (net) - In-Sample [reference]"))
summary.append(perf_stats(panel.loc[oos_mask, "carry_net"], "ATTEMPT 3 UNCONDITIONAL CARRY (net) - Out-of-Sample [reference]"))

pd.DataFrame(summary).to_csv(f"{RESULTS}/summary_stats.csv", index=False)

# ---- Subperiod stability check on the conditioned strategy (OOS only) ----
oos_panel = panel.loc[oos_mask]
sub_bounds = [("2019-01-01", "2021-02-28"), ("2021-03-01", "2023-04-30"), ("2023-05-01", "2025-06-30")]
sub_rows = []
for start, end in sub_bounds:
    sub = oos_panel.loc[(oos_panel.index >= start) & (oos_panel.index <= end), "cond_net"].dropna()
    sub_uncond = oos_panel.loc[(oos_panel.index >= start) & (oos_panel.index <= end), "carry_net"].dropna()
    if len(sub) < 3:
        continue
    ann_vol = sub.std() * np.sqrt(12)
    sharpe = (sub.mean() * 12) / ann_vol if ann_vol > 0 else np.nan
    ann_vol_u = sub_uncond.std() * np.sqrt(12)
    sharpe_u = (sub_uncond.mean() * 12) / ann_vol_u if ann_vol_u > 0 else np.nan
    sub_rows.append({"period": f"{start} to {end}", "n_months": len(sub),
                      "cond_sharpe": sharpe, "uncond_sharpe_ref": sharpe_u})
sub_df = pd.DataFrame(sub_rows)
sub_df.to_csv(f"{RESULTS}/subperiod_stability.csv", index=False)
print("\nSubperiod stability (conditioned vs. attempt-3 unconditional, OOS only):")
print(sub_df.to_string(index=False))

# ---- Head-to-head comparison table vs attempt 3 ----
att3_summary = pd.read_csv(ATT3_SUMMARY)
att3_is_net = att3_summary[att3_summary["label"] == "BROAD CARRY (net) - In-Sample"].iloc[0]
att3_oos_net = att3_summary[att3_summary["label"] == "BROAD CARRY (net) - Out-of-Sample"].iloc[0]

cond_is = summary[0]
cond_oos = summary[1]

print("\n=== HEAD-TO-HEAD: Attempt 4 (vol-conditioned) vs Attempt 3 (unconditional) ===")
print(f"{'Metric':<20}{'Att3 IS':>12}{'Att4 IS':>12}{'Att3 OOS':>12}{'Att4 OOS':>12}")
print(f"{'Sharpe':<20}{att3_is_net['sharpe']:>12.3f}{cond_is['sharpe']:>12.3f}"
      f"{att3_oos_net['sharpe']:>12.3f}{cond_oos['sharpe']:>12.3f}")
print(f"{'Max DD':<20}{att3_is_net['max_dd']:>12.3f}{cond_is['max_dd']:>12.3f}"
      f"{att3_oos_net['max_dd']:>12.3f}{cond_oos['max_dd']:>12.3f}")

head_to_head = pd.DataFrame({
    "metric": ["sharpe", "max_dd", "skew", "plain_pvalue", "hac_pvalue"],
    "attempt3_IS": [att3_is_net["sharpe"], att3_is_net["max_dd"], np.nan, att3_is_net["pvalue"], np.nan],
    "attempt4_IS": [cond_is["sharpe"], cond_is["max_dd"], cond_is["skew"], cond_is["pvalue"], cond_is["hac_pvalue"]],
    "attempt3_OOS": [att3_oos_net["sharpe"], att3_oos_net["max_dd"], np.nan, att3_oos_net["pvalue"], np.nan],
    "attempt4_OOS": [cond_oos["sharpe"], cond_oos["max_dd"], cond_oos["skew"], cond_oos["pvalue"], cond_oos["hac_pvalue"]],
})
head_to_head.to_csv(f"{RESULTS}/head_to_head_vs_attempt3.csv", index=False)

# ---- Charts ----
fig, ax = plt.subplots(figsize=(11, 6))
cum_cond = (1 + panel["cond_net"]).cumprod()
cum_uncond = (1 + panel["carry_net"]).cumprod()
ax.plot(cum_cond.index, cum_cond.values, label="Vol-conditioned carry (net)", lw=1.8)
ax.plot(cum_uncond.index, cum_uncond.values, label="Attempt 3: unconditional carry (net)", lw=1.4, alpha=0.8)
ax.axvline(pd.Timestamp(OOS_START), color="gray", linestyle="--", lw=1, label="IS/OOS split")
ax.set_title("Vol/Ambiguity-Conditioned Carry vs. Unconditional Carry (Attempt 3)")
ax.set_ylabel("Cumulative growth of $1")
ax.legend()
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(f"{RESULTS}/cumulative_returns_comparison.png", dpi=130)
plt.close(fig)

fig, ax = plt.subplots(figsize=(11, 4))
ax.plot(regime.index, regime.values, color="darkred", lw=1.2, label="Vol dispersion (ambiguity proxy)")
ax.axhline(frozen_threshold, color="black", linestyle="--", lw=1, label="Frozen IS threshold (67th pct)")
ax.axvline(pd.Timestamp(OOS_START), color="gray", linestyle="--", lw=1)
ax.set_title("FX Volatility-Dispersion Regime Measure vs. Frozen IS Threshold")
ax.legend()
fig.tight_layout()
fig.savefig(f"{RESULTS}/regime_measure.png", dpi=130)
plt.close(fig)

print("\nDone. Results written to:", RESULTS)
