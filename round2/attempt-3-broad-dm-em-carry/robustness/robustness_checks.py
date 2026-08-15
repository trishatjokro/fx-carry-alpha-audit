"""
Robustness deep-dive on Attempt 3: Broad (DM+EM) FX Carry, quintile sort.

This is DIAGNOSTIC ONLY on the already-frozen strategy from
../broad_carry_backtest.py. No parameters of the signal are changed here.

Checks performed:
  1. OOS-extension feasibility (policy-rate data frontier check)
  2. Cost sensitivity: 0.5x / 1x / 2x / 3x the original 2bps one-way cost
  3. Probabilistic Sharpe Ratio (Bailey & Lopez de Prado) + skew/kurtosis +
     a stationary (Politis-Romano) block bootstrap CI on OOS Sharpe
  4. Subperiod stability: OOS split into yearly and 3-block sub-windows
  5. Factor exposure: regress carry_net on the dollar factor (bm_net) and
     on SPY monthly excess returns
  6. (narrative only, see README) literature Sharpe comparison
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats
import statsmodels.api as sm
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = "/private/tmp/claude-501/-Users-trishatjokrosapoetro/ffa35993-cabc-4b2a-8fb1-084a45231434/scratchpad/alpha-papers/round2-macro-fx/attempt-3-broad-dm-em-carry"
RESULTS = f"{BASE}/results"
OUT = f"{BASE}/robustness/results"

IS_START, IS_END = "2006-05-01", "2018-12-31"
OOS_START, OOS_END = "2019-01-01", "2025-06-30"

panel = pd.read_csv(f"{RESULTS}/monthly_returns_panel.csv", index_col=0, parse_dates=True)
is_mask = (panel.index >= IS_START) & (panel.index <= IS_END)
oos_mask = (panel.index >= OOS_START) & (panel.index <= OOS_END)

# ---------------------------------------------------------------------
# Check 2: cost sensitivity
# ---------------------------------------------------------------------
rows = []
for mult in [0.0, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0]:
    cost_bps = 2.0 * mult
    cost = panel["turnover"] * (cost_bps / 10000.0) * 2
    net = panel["carry_gross"] - cost
    for label, mask in [("IS", is_mask), ("OOS", oos_mask)]:
        r = net[mask].dropna()
        ann_vol = r.std() * np.sqrt(12)
        sharpe = (r.mean() * 12) / ann_vol if ann_vol > 0 else np.nan
        t, p = stats.ttest_1samp(r, 0.0)
        rows.append({"cost_bps_oneway": cost_bps, "mult_of_original": mult,
                      "period": label, "sharpe": sharpe, "mean_monthly": r.mean(),
                      "tstat": t, "pvalue": p})
cost_sens = pd.DataFrame(rows)
cost_sens.to_csv(f"{OUT}/cost_sensitivity.csv", index=False)
print("=== Check 2: Cost sensitivity ===")
print(cost_sens.to_string(index=False))

# ---------------------------------------------------------------------
# Check 3: PSR, skew/kurtosis, stationary bootstrap
# ---------------------------------------------------------------------
def stationary_bootstrap_sharpe_ci(r, avg_block=6, n_boot=5000, seed=42, ann=12):
    rng = np.random.default_rng(seed)
    n = len(r)
    p = 1.0 / avg_block
    r_arr = r.values
    sharpes = []
    for _ in range(n_boot):
        idx = []
        while len(idx) < n:
            start = rng.integers(0, n)
            blen = rng.geometric(p)
            idx.extend([(start + k) % n for k in range(blen)])
        idx = idx[:n]
        samp = r_arr[idx]
        sv = samp.std()
        sh = (samp.mean() * ann) / (sv * np.sqrt(ann)) if sv > 0 else np.nan
        sharpes.append(sh)
    sharpes = np.array([s for s in sharpes if not np.isnan(s)])
    return np.percentile(sharpes, [2.5, 97.5]), sharpes


def psr(r, sr_benchmark=0.0):
    n = len(r)
    sr_period = r.mean() / r.std()
    skew = stats.skew(r, bias=False)
    kurt = stats.kurtosis(r, fisher=False, bias=False)  # normal = 3
    denom = np.sqrt(max(1 - skew * sr_period + (kurt - 1) / 4 * sr_period ** 2, 1e-9))
    z = (sr_period - sr_benchmark) * np.sqrt(n - 1) / denom
    p = stats.norm.cdf(z)
    return p, skew, kurt, sr_period


rows3 = []
for label, mask in [("IS", is_mask), ("OOS", oos_mask)]:
    r = panel.loc[mask, "carry_net"].dropna()
    psr_val, skew, kurt, sr_period = psr(r, 0.0)
    (ci_lo, ci_hi), boot_dist = stationary_bootstrap_sharpe_ci(r)
    iid_rng = np.random.default_rng(7)
    iid_boot = []
    for _ in range(5000):
        samp = iid_rng.choice(r.values, size=len(r), replace=True)
        sv = samp.std()
        if sv > 0:
            iid_boot.append((samp.mean() * 12) / (sv * np.sqrt(12)))
    iid_boot = np.array(iid_boot)
    iid_ci = np.percentile(iid_boot, [2.5, 97.5])
    rows3.append({
        "period": label, "n_months": len(r), "monthly_skew": skew, "monthly_kurtosis": kurt,
        "PSR_vs_0": psr_val, "ann_sharpe": (r.mean() * 12) / (r.std() * np.sqrt(12)),
        "iid_bootstrap_CI_lo": iid_ci[0], "iid_bootstrap_CI_hi": iid_ci[1],
        "stationary_block_bootstrap_CI_lo": ci_lo, "stationary_block_bootstrap_CI_hi": ci_hi,
    })
psr_df = pd.DataFrame(rows3)
psr_df.to_csv(f"{OUT}/psr_and_bootstrap.csv", index=False)
print("\n=== Check 3: PSR / skew-kurtosis / stationary bootstrap ===")
print(psr_df.to_string(index=False))

# ---------------------------------------------------------------------
# Check 4: subperiod stability
# ---------------------------------------------------------------------
oos = panel.loc[oos_mask, "carry_net"].dropna()
rows4 = []
for yr, grp in oos.groupby(oos.index.year):
    ann_vol = grp.std() * np.sqrt(12)
    sh = (grp.mean() * 12) / ann_vol if ann_vol > 0 else np.nan
    rows4.append({"window": str(yr), "n_months": len(grp), "sharpe": sh, "mean_monthly": grp.mean()})

n = len(oos)
edges = [0, n // 3, 2 * n // 3, n]
labels3 = [f"block1_{oos.index[edges[0]].date()}_{oos.index[edges[1]-1].date()}",
           f"block2_{oos.index[edges[1]].date()}_{oos.index[edges[2]-1].date()}",
           f"block3_{oos.index[edges[2]].date()}_{oos.index[edges[3]-1].date()}"]
for lab, a, b in zip(labels3, edges[:-1], edges[1:]):
    grp = oos.iloc[a:b]
    ann_vol = grp.std() * np.sqrt(12)
    sh = (grp.mean() * 12) / ann_vol if ann_vol > 0 else np.nan
    rows4.append({"window": lab, "n_months": len(grp), "sharpe": sh, "mean_monthly": grp.mean()})

subperiod_df = pd.DataFrame(rows4)
subperiod_df.to_csv(f"{OUT}/subperiod_stability.csv", index=False)
print("\n=== Check 4: Subperiod stability (OOS) ===")
print(subperiod_df.to_string(index=False))

# ---------------------------------------------------------------------
# Check 5: factor exposure (dollar factor + SPY)
# ---------------------------------------------------------------------
print("\nFetching SPY monthly returns for factor regression ...")
spy = yf.download("SPY", start="2005-01-01", progress=False, auto_adjust=True)
spy_close = spy["Close"]["SPY"] if isinstance(spy["Close"], pd.DataFrame) else spy["Close"]
spy_m = spy_close.resample("ME").last().pct_change()
spy_m.index.name = "date"

rows5 = []
for label, mask in [("IS", is_mask), ("OOS", oos_mask)]:
    y = panel.loc[mask, "carry_net"]
    dollar = panel.loc[mask, "bm_net"]
    spy_aligned = spy_m.reindex(y.index)
    df = pd.DataFrame({"y": y, "dollar": dollar, "spy": spy_aligned}).dropna()
    X = sm.add_constant(df[["dollar", "spy"]])
    model = sm.OLS(df["y"], X).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
    rows5.append({
        "period": label, "n_obs": len(df),
        "alpha_monthly": model.params["const"], "alpha_tstat": model.tvalues["const"], "alpha_pvalue": model.pvalues["const"],
        "beta_dollar": model.params["dollar"], "beta_dollar_tstat": model.tvalues["dollar"], "beta_dollar_pvalue": model.pvalues["dollar"],
        "beta_spy": model.params["spy"], "beta_spy_tstat": model.tvalues["spy"], "beta_spy_pvalue": model.pvalues["spy"],
        "r_squared": model.rsquared,
    })
factor_df = pd.DataFrame(rows5)
factor_df.to_csv(f"{OUT}/factor_regression.csv", index=False)
print("\n=== Check 5: Factor exposure regression (HAC/Newey-West SE, 6 lags) ===")
print(factor_df.to_string(index=False))

# Chart: subperiod sharpe bars
fig, ax = plt.subplots(figsize=(9, 4.5))
ax.bar(subperiod_df["window"], subperiod_df["sharpe"], color="steelblue")
ax.axhline(0, color="black", lw=0.8)
ax.set_title("OOS Sharpe by Subperiod (Broad DM+EM Carry, net)")
ax.set_ylabel("Annualized Sharpe")
plt.xticks(rotation=45, ha="right")
fig.tight_layout()
fig.savefig(f"{OUT}/subperiod_sharpe.png", dpi=130)
plt.close(fig)

# Chart: cost sensitivity
fig, ax = plt.subplots(figsize=(8, 4.5))
for label in ["IS", "OOS"]:
    sub = cost_sens[cost_sens["period"] == label]
    ax.plot(sub["cost_bps_oneway"], sub["sharpe"], marker="o", label=label)
ax.axhline(0, color="black", lw=0.8)
ax.set_xlabel("One-way transaction cost (bps)")
ax.set_ylabel("Annualized Sharpe (net)")
ax.set_title("Cost Sensitivity: Broad DM+EM Carry")
ax.legend()
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(f"{OUT}/cost_sensitivity.png", dpi=130)
plt.close(fig)

print("\nDone. Robustness outputs written to:", OUT)
