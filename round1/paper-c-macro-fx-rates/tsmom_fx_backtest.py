"""
Out-of-sample replication test of the FX time-series-momentum (TSMOM) strategy
described in:

  Pollok, A. & Robik, K. (2026). "End-to-End Parametric Portfolio Policies for
  Cross-Asset Futures Timing: When Do AI Models Beat Simple Rules?"
  arXiv:2607.00475v1 [q-fin.ST], submitted 1 Jul 2026.
  https://arxiv.org/abs/2607.00475

The paper benchmarks learned (transformer / LSTM) allocation policies against
three simple rules -- equal weight (1/N), risk parity, and time-series
momentum (TSMOM) -- across six asset-class "sleeves" of 16 liquid CME futures.
The FX sleeve uses exactly two contracts: 6E (Euro FX) and 6J (Japanese Yen
FX). Table II of the paper reports, for the FX sleeve, out-of-sample
(2011-2024, gross 2bp transaction cost):

    Strategy      Return   Vol    Sharpe  NetSharpe  Sortino  MDD   Calmar  Turnover
    1/N           -0.03    0.07   -0.36   -0.36      -0.57    0.49  -0.05   0.00
    Risk parity   -0.03    0.07   -0.37   -0.37      -0.57    0.50  -0.05   0.00
    TSMOM          0.02    0.07    0.25    0.23        0.35   0.20   0.08   0.03

TSMOM is the paper's "trading signal" (12-month time-series momentum,
Moskowitz-Ooi-Pedersen 2012 style, vol-scaled, unit gross exposure), and it is
the ONLY one of the three simple rules that shows a positive, non-trivial
Sharpe ratio on the FX sleeve. This script replicates that TSMOM signal from
scratch with free data and asks whether it actually holds up.

DATA SUBSTITUTION (explicitly flagged):
  The paper uses Barchart continuous CME futures (6E, 6J). Those are not
  freely available. We substitute free daily SPOT FX data from Yahoo Finance
  via yfinance: EURUSD=X for 6E, and 1/(JPY=X) for 6J (JPY=X on Yahoo is
  quoted USD-per-JPY... actually it is JPY-per-USD, i.e. USDJPY convention;
  we invert it to USD-per-JPY so its return direction matches "long JPY",
  the same convention as 6J and as EURUSD=X). Spot FX omits the roll/carry
  embedded in futures term structure and has no exchange margining, so it is
  a reasonable but NOT identical proxy for the futures contracts the paper
  used. This is a deviation from the paper, stated here explicitly.

  We could not obtain data back to 2000 for EUR (Yahoo's EURUSD=X starts
  2003-12-01), so our in-sample/calibration window is shorter than the
  paper's (2000-2010): ours is 2003-12-01 to 2010-12-31. Our out-of-sample
  window, however, matches the paper's exactly: 2011-01-01 to 2024-12-31.
  We add a second, genuinely fresh holdout window the paper's authors could
  not have seen (2025-01-01 to the present), since the paper was posted to
  arXiv in July 2026.

METHODOLOGY IMPLEMENTED (matches paper's description as closely as free data
allows):
  - Universe (core, matches paper exactly): EUR/USD, JPY/USD (inverted).
  - Universe (extended robustness check, NOT in paper): + GBP, AUD, CAD, CHF
    (standard G10 majors) to see if the FX-sleeve result generalizes beyond
    a 2-asset portfolio.
  - Signal: sign of trailing 252-trading-day (12-month) return, using
    information available at t-1 close only (no lookahead).
  - Position size: vol-scaled -- raw_i,t = signal_i,t / realized_vol_i,t
    (realized_vol from a rolling window of daily returns, annualized),
    then renormalized across the universe each day so gross exposure
    sum(|w_i,t|) = 1 (paper: "TSMOM ... long/short with unit gross
    exposure").
  - Free parameter we calibrate in-sample (paper does not give the exact
    vol-estimation window, only "the standard 12-month signal" for the
    momentum lookback, which we do NOT tune): the realized-vol lookback
    window, chosen from {20, 60, 100} trading days by maximizing in-sample
    net Sharpe on the core (EUR, JPY) universe. Momentum lookback is fixed
    at 252 days throughout, matching the paper, and is never tuned.
  - Benchmarks: 1/N (equal weight, constant target weight => zero turnover
    by construction, matching the paper's Table II definition of turnover
    as change in TARGET weight) and Risk Parity (60-day inverse-volatility
    weights, long-only, matches paper's stated risk-parity spec exactly).
  - Rebalance: daily. Transaction cost: 2bp per unit of turnover
    (turnover_t = 0.5 * sum_i |w_i,t - w_i,t-1|), matching the paper's
    reported "2bp" cost assumption for liquid futures. We also report a
    1/5/10bp sensitivity table.
  - Portfolio return: r_P,t = sum_i w_i,t-1 * r_i,t (yesterday's weight
    applied to today's return, exactly as the paper's Eq. 2).

Run with:  python3 tsmom_fx_backtest.py
Requires:  pandas, numpy, scipy, matplotlib, yfinance
"""

import warnings
warnings.filterwarnings("ignore")

import os
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(HERE, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
CORE_TICKERS = {
    "EUR": ("EURUSD=X", False),   # (ticker, invert?) EURUSD=X already USD-per-EUR
    "JPY": ("JPY=X", True),       # JPY=X is USDJPY (JPY per USD) -> invert to USD-per-JPY
}
EXTENDED_TICKERS = {
    **CORE_TICKERS,
    "GBP": ("GBPUSD=X", False),
    "AUD": ("AUDUSD=X", False),
    "CAD": ("CAD=X", True),       # USDCAD -> invert
    "CHF": ("CHF=X", True),       # USDCHF -> invert
}

MOM_LOOKBACK = 252          # 12-month signal, fixed, NOT tuned (matches paper)
TARGET_VOL = None           # unit-gross-exposure normalization used instead of a vol target
VOL_WINDOW_GRID = [20, 60, 100]   # free parameter, calibrated in-sample only
RISK_PARITY_VOL_WINDOW = 60       # paper states this explicitly
COST_BPS_DEFAULT = 2.0            # paper's baseline cost assumption
COST_BPS_GRID = [1.0, 2.0, 5.0, 10.0]

IN_SAMPLE_START = "2003-12-01"
IN_SAMPLE_END = "2010-12-31"
OOS_START = "2011-01-01"
OOS_END = "2024-12-31"
HOLDOUT_START = "2025-01-01"   # genuinely fresh, post-paper-publication window
HOLDOUT_END = None             # through latest available data

N_BOOTSTRAP = 5000
BLOCK_LEN = 21   # ~1 trading month, for stationary block bootstrap on Sharpe CI

PAPER_FX_OOS = {
    # Table II of Pollok & Robik (2026), FX sleeve, out-of-sample 2011-2024
    "1/N":         dict(Return=-0.03, Vol=0.07, Sharpe=-0.36, NetSharpe=-0.36, Sortino=-0.57, MDD=0.49, Calmar=-0.05, Turnover=0.00),
    "Risk parity": dict(Return=-0.03, Vol=0.07, Sharpe=-0.37, NetSharpe=-0.37, Sortino=-0.57, MDD=0.50, Calmar=-0.05, Turnover=0.00),
    "TSMOM":       dict(Return=0.02,  Vol=0.07, Sharpe=0.25,  NetSharpe=0.23,  Sortino=0.35,  MDD=0.20, Calmar=0.08,  Turnover=0.03),
}


# ----------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------
def fetch_prices(ticker_map, start="1999-01-01"):
    frames = {}
    for name, (ticker, invert) in ticker_map.items():
        df = yf.download(ticker, start=start, progress=False, auto_adjust=True)
        if df.empty:
            raise RuntimeError(f"No data returned for {ticker}")
        s = df["Close"]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        s.name = name
        if invert:
            s = 1.0 / s
        frames[name] = s
    prices = pd.concat(frames.values(), axis=1)
    prices.columns = list(frames.keys())
    prices = prices.dropna(how="any").sort_index()
    return prices


# ----------------------------------------------------------------------
# Signal / weight construction
# ----------------------------------------------------------------------
def compute_returns(prices):
    return prices.pct_change()


def compute_tsmom_weights(prices, rets, vol_window, mom_lookback=MOM_LOOKBACK):
    """Vol-scaled 12M TSMOM, renormalized daily to unit gross exposure.
    All inputs into day t's weight use only information available at t-1.
    """
    mom = prices.pct_change(mom_lookback).shift(1)          # info at t-1
    signal = np.sign(mom)
    vol = rets.rolling(vol_window).std().shift(1) * np.sqrt(252)  # info at t-1
    raw = signal / vol
    raw = raw.replace([np.inf, -np.inf], np.nan)
    gross = raw.abs().sum(axis=1)
    weights = raw.div(gross.replace(0, np.nan), axis=0)
    weights = weights.fillna(0.0)
    return weights


def compute_equal_weights(prices):
    n = prices.shape[1]
    w = pd.DataFrame(1.0 / n, index=prices.index, columns=prices.columns)
    # mask days before we have any data (shouldn't occur post-dropna, but safe)
    return w


def compute_risk_parity_weights(rets, vol_window=RISK_PARITY_VOL_WINDOW):
    vol = rets.rolling(vol_window).std().shift(1) * np.sqrt(252)
    inv_vol = 1.0 / vol
    inv_vol = inv_vol.replace([np.inf, -np.inf], np.nan)
    weights = inv_vol.div(inv_vol.sum(axis=1), axis=0)
    weights = weights.fillna(0.0)
    return weights


# ----------------------------------------------------------------------
# Backtest engine
# ----------------------------------------------------------------------
def run_backtest(weights, rets, cost_bps=COST_BPS_DEFAULT):
    """weights: target weights indexed by day t (decided using info at t-1).
    Portfolio return for day t uses weights.shift(1) applied to rets at t
    (i.e., the weight decided at t-1 close, held into t), matching the
    paper's R_P,t = sum_i w_i,t-1 * R_i,t.
    """
    w_lag = weights.shift(1).fillna(0.0)
    gross_ret = (w_lag * rets).sum(axis=1)

    turnover = 0.5 * (weights - weights.shift(1)).abs().sum(axis=1)
    turnover = turnover.fillna(0.0)
    cost = cost_bps * 1e-4 * turnover
    net_ret = gross_ret - cost

    out = pd.DataFrame({
        "gross_ret": gross_ret,
        "net_ret": net_ret,
        "turnover": turnover,
    })
    return out


# ----------------------------------------------------------------------
# Metrics
# ----------------------------------------------------------------------
def max_drawdown(cum_returns):
    running_max = cum_returns.cummax()
    dd = cum_returns / running_max - 1.0
    return -dd.min()


def annualized_metrics(daily_ret, turnover=None):
    daily_ret = daily_ret.dropna()
    n = len(daily_ret)
    if n == 0:
        return {}
    ann_ret = daily_ret.mean() * 252
    ann_vol = daily_ret.std(ddof=1) * np.sqrt(252)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else np.nan

    downside = daily_ret[daily_ret < 0]
    down_dev = downside.std(ddof=1) * np.sqrt(252) if len(downside) > 1 else np.nan
    sortino = ann_ret / down_dev if down_dev and down_dev > 0 else np.nan

    cum = (1 + daily_ret).cumprod()
    mdd = max_drawdown(cum)
    calmar = ann_ret / mdd if mdd > 0 else np.nan

    cagr = cum.iloc[-1] ** (252.0 / n) - 1.0

    win_rate = (daily_ret > 0).mean()

    tstat, pval = stats.ttest_1samp(daily_ret.values, 0.0)

    m = dict(
        N_days=n, Return=ann_ret, Vol=ann_vol, Sharpe=sharpe, Sortino=sortino,
        MDD=mdd, Calmar=calmar, CAGR=cagr, WinRate=win_rate,
        t_stat=tstat, p_value=pval,
    )
    if turnover is not None:
        m["Turnover"] = turnover.reindex(daily_ret.index).mean()
    return m


def block_bootstrap_sharpe_ci(daily_ret, n_boot=N_BOOTSTRAP, block_len=BLOCK_LEN, seed=42):
    rng = np.random.default_rng(seed)
    r = daily_ret.dropna().values
    n = len(r)
    if n < block_len * 2:
        return (np.nan, np.nan)
    n_blocks = int(np.ceil(n / block_len))
    sharpes = np.empty(n_boot)
    max_start = n - block_len
    for b in range(n_boot):
        starts = rng.integers(0, max_start + 1, size=n_blocks)
        sample = np.concatenate([r[s:s + block_len] for s in starts])[:n]
        mu = sample.mean() * 252
        sd = sample.std(ddof=1) * np.sqrt(252)
        sharpes[b] = mu / sd if sd > 0 else np.nan
    lo, hi = np.nanpercentile(sharpes, [2.5, 97.5])
    return lo, hi


def evaluate_strategy(name, weights, rets, start, end, cost_bps=COST_BPS_DEFAULT):
    bt = run_backtest(weights, rets, cost_bps=cost_bps)
    bt = bt.loc[start:end]
    gross_m = annualized_metrics(bt["gross_ret"], bt["turnover"])
    net_m = annualized_metrics(bt["net_ret"], bt["turnover"])
    ci_lo, ci_hi = block_bootstrap_sharpe_ci(bt["net_ret"])
    row = {
        "Strategy": name,
        "Return": net_m.get("Return", np.nan),
        "Vol": net_m.get("Vol", np.nan),
        "Sharpe_gross": gross_m.get("Sharpe", np.nan),
        "Sharpe_net": net_m.get("Sharpe", np.nan),
        "Sharpe_net_CI_lo": ci_lo,
        "Sharpe_net_CI_hi": ci_hi,
        "Sortino_net": net_m.get("Sortino", np.nan),
        "MDD_net": net_m.get("MDD", np.nan),
        "Calmar_net": net_m.get("Calmar", np.nan),
        "CAGR_net": net_m.get("CAGR", np.nan),
        "WinRate_net": net_m.get("WinRate", np.nan),
        "Turnover": net_m.get("Turnover", np.nan),
        "t_stat_net": net_m.get("t_stat", np.nan),
        "p_value_net": net_m.get("p_value", np.nan),
        "N_days": net_m.get("N_days", np.nan),
    }
    return row, bt


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    print("=" * 78)
    print("Fetching data (yfinance)...")
    core_prices = fetch_prices(CORE_TICKERS)
    ext_prices = fetch_prices(EXTENDED_TICKERS)
    print(f"Core (EUR, JPY) universe: {core_prices.index.min().date()} -> {core_prices.index.max().date()}, {len(core_prices)} days")
    print(f"Extended (6 G10 majors) universe: {ext_prices.index.min().date()} -> {ext_prices.index.max().date()}, {len(ext_prices)} days")

    core_rets = compute_returns(core_prices)
    ext_rets = compute_returns(ext_prices)

    # ---- Step 1: in-sample calibration of the ONE free parameter (vol_window)
    print("\n" + "=" * 78)
    print(f"IN-SAMPLE CALIBRATION of realized-vol lookback window, {IN_SAMPLE_START} to {IN_SAMPLE_END}")
    print("(momentum lookback fixed at 252d per paper; NOT tuned)")
    calib_results = []
    for vw in VOL_WINDOW_GRID:
        w = compute_tsmom_weights(core_prices, core_rets, vw)
        bt = run_backtest(w, core_rets, cost_bps=COST_BPS_DEFAULT)
        bt_is = bt.loc[IN_SAMPLE_START:IN_SAMPLE_END]
        m = annualized_metrics(bt_is["net_ret"])
        calib_results.append((vw, m.get("Sharpe", np.nan)))
        print(f"  vol_window={vw:4d}d  in-sample net Sharpe = {m.get('Sharpe', np.nan):.3f}")
    best_vw = max(calib_results, key=lambda x: (x[1] if not np.isnan(x[1]) else -999))[0]
    print(f"  -> Selected vol_window = {best_vw} (max in-sample net Sharpe), LOCKED for all out-of-sample tests.")

    # ---- Step 2: build weights for all strategies using the locked parameter
    strategies_core = {
        "1/N": compute_equal_weights(core_prices),
        "Risk parity": compute_risk_parity_weights(core_rets),
        "TSMOM": compute_tsmom_weights(core_prices, core_rets, best_vw),
    }
    strategies_ext = {
        "1/N (ext G10)": compute_equal_weights(ext_prices),
        "Risk parity (ext G10)": compute_risk_parity_weights(ext_rets),
        "TSMOM (ext G10)": compute_tsmom_weights(ext_prices, ext_rets, best_vw),
    }

    periods = {
        "IN-SAMPLE (calibration)": (IN_SAMPLE_START, IN_SAMPLE_END),
        "OUT-OF-SAMPLE (matches paper 2011-2024)": (OOS_START, OOS_END),
        "POST-PAPER HOLDOUT (2025-present, never seen by authors)": (HOLDOUT_START, HOLDOUT_END or core_prices.index.max().strftime("%Y-%m-%d")),
    }

    all_rows = []
    bt_series = {}  # for plotting
    for period_name, (start, end) in periods.items():
        print("\n" + "=" * 78)
        print(f"{period_name}: {start} to {end}")
        print("-" * 78)
        for name, w in strategies_core.items():
            row, bt = evaluate_strategy(name, w, core_rets, start, end)
            row["Period"] = period_name
            row["Universe"] = "Core (EUR, JPY) - matches paper"
            all_rows.append(row)
            bt_series[(period_name, name)] = bt
            print(f"  [core] {name:14s}  NetSharpe={row['Sharpe_net']:6.3f}  GrossSharpe={row['Sharpe_gross']:6.3f}  "
                  f"Return={row['Return']:6.3f}  MDD={row['MDD_net']:5.3f}  Turnover={row['Turnover']:5.3f}  "
                  f"t={row['t_stat_net']:5.2f}  p={row['p_value_net']:.3f}  95%CI Sharpe=[{row['Sharpe_net_CI_lo']:.2f},{row['Sharpe_net_CI_hi']:.2f}]")
        for name, w in strategies_ext.items():
            row, bt = evaluate_strategy(name, w, ext_rets, start, end)
            row["Period"] = period_name
            row["Universe"] = "Extended G10 (EUR,JPY,GBP,AUD,CAD,CHF) - robustness, NOT in paper"
            all_rows.append(row)
            bt_series[(period_name, name)] = bt
            print(f"  [ext ] {name:22s}  NetSharpe={row['Sharpe_net']:6.3f}  GrossSharpe={row['Sharpe_gross']:6.3f}  "
                  f"Return={row['Return']:6.3f}  MDD={row['MDD_net']:5.3f}  Turnover={row['Turnover']:5.3f}  "
                  f"t={row['t_stat_net']:5.2f}  p={row['p_value_net']:.3f}  95%CI Sharpe=[{row['Sharpe_net_CI_lo']:.2f},{row['Sharpe_net_CI_hi']:.2f}]")

    results_df = pd.DataFrame(all_rows)
    results_path = os.path.join(RESULTS_DIR, "backtest_results.csv")
    results_df.to_csv(results_path, index=False)
    print(f"\nSaved full results table -> {results_path}")

    # ---- Step 3: transaction cost sensitivity (core universe, TSMOM, OOS period)
    print("\n" + "=" * 78)
    print("TRANSACTION COST SENSITIVITY (core universe, TSMOM, out-of-sample 2011-2024)")
    cost_rows = []
    for cbps in COST_BPS_GRID:
        row, _ = evaluate_strategy("TSMOM", strategies_core["TSMOM"], core_rets, OOS_START, OOS_END, cost_bps=cbps)
        cost_rows.append({"cost_bps": cbps, "NetSharpe": row["Sharpe_net"], "Return": row["Return"]})
        print(f"  cost={cbps:5.1f}bp  NetSharpe={row['Sharpe_net']:.3f}  Return={row['Return']:.4f}")
    cost_df = pd.DataFrame(cost_rows)
    cost_path = os.path.join(RESULTS_DIR, "cost_sensitivity.csv")
    cost_df.to_csv(cost_path, index=False)

    # ---- Step 4: comparison vs paper's reported OOS FX-sleeve numbers
    print("\n" + "=" * 78)
    print("REPLICATION CHECK vs paper's Table II (FX sleeve, OOS 2011-2024, futures data)")
    print("-" * 78)
    comp_rows = []
    oos_core = results_df[(results_df["Period"] == "OUT-OF-SAMPLE (matches paper 2011-2024)") &
                           (results_df["Universe"] == "Core (EUR, JPY) - matches paper")]
    for name, paper_vals in PAPER_FX_OOS.items():
        mine = oos_core[oos_core["Strategy"] == name]
        if mine.empty:
            continue
        mine = mine.iloc[0]
        comp_rows.append({
            "Strategy": name,
            "Paper_NetSharpe": paper_vals["NetSharpe"],
            "Mine_NetSharpe(spotFX)": round(mine["Sharpe_net"], 3),
            "Paper_Turnover": paper_vals["Turnover"],
            "Mine_Turnover": round(mine["Turnover"], 3),
            "Paper_MDD": paper_vals["MDD"],
            "Mine_MDD": round(mine["MDD_net"], 3),
        })
        print(f"  {name:14s}  paper NetSharpe={paper_vals['NetSharpe']:6.2f}   spot-FX replication NetSharpe={mine['Sharpe_net']:6.2f}")
    comp_df = pd.DataFrame(comp_rows)
    comp_path = os.path.join(RESULTS_DIR, "paper_vs_replication.csv")
    comp_df.to_csv(comp_path, index=False)
    print(f"Saved -> {comp_path}")

    # ---- Step 5: plots
    make_plots(bt_series, core_prices)

    print("\nDone.")
    return results_df, comp_df


def make_plots(bt_series, core_prices):
    # Equity curves: core universe, OOS period + holdout, TSMOM vs 1/N vs Risk parity
    fig, axes = plt.subplots(2, 1, figsize=(10, 9), sharex=False)

    ax = axes[0]
    for name in ["1/N", "Risk parity", "TSMOM"]:
        bt = bt_series[("OUT-OF-SAMPLE (matches paper 2011-2024)", name)]
        cum = (1 + bt["net_ret"]).cumprod()
        ax.plot(cum.index, cum.values, label=name, linewidth=1.4)
    ax.set_title("Core FX universe (EUR, JPY spot proxy) -- Out-of-Sample 2011-2024\nGrowth of $1, net of 2bp transaction costs")
    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_ylabel("Growth of $1")

    ax2 = axes[1]
    for name in ["1/N", "Risk parity", "TSMOM"]:
        bt = bt_series[("OUT-OF-SAMPLE (matches paper 2011-2024)", name)]
        cum = (1 + bt["net_ret"]).cumprod()
        dd = cum / cum.cummax() - 1
        ax2.plot(dd.index, dd.values, label=name, linewidth=1.2)
    ax2.set_title("Drawdown, out-of-sample 2011-2024 (net of costs)")
    ax2.legend()
    ax2.grid(alpha=0.3)
    ax2.set_ylabel("Drawdown")

    fig.tight_layout()
    fig.savefig(os.path.join(RESULTS_DIR, "equity_and_drawdown_oos.png"), dpi=140)
    plt.close(fig)

    # Holdout period plot
    fig2, ax3 = plt.subplots(figsize=(10, 5))
    for name in ["1/N", "Risk parity", "TSMOM"]:
        bt = bt_series[("POST-PAPER HOLDOUT (2025-present, never seen by authors)", name)]
        cum = (1 + bt["net_ret"]).cumprod()
        ax3.plot(cum.index, cum.values, label=name, linewidth=1.4)
    ax3.set_title("Core FX universe -- Post-paper holdout (2025-present)\nGrowth of $1, net of 2bp costs")
    ax3.legend()
    ax3.grid(alpha=0.3)
    fig2.tight_layout()
    fig2.savefig(os.path.join(RESULTS_DIR, "equity_holdout.png"), dpi=140)
    plt.close(fig2)

    # Extended G10 OOS equity curve
    fig3, ax4 = plt.subplots(figsize=(10, 5))
    for name in ["1/N (ext G10)", "Risk parity (ext G10)", "TSMOM (ext G10)"]:
        bt = bt_series[("OUT-OF-SAMPLE (matches paper 2011-2024)", name)]
        cum = (1 + bt["net_ret"]).cumprod()
        ax4.plot(cum.index, cum.values, label=name, linewidth=1.4)
    ax4.set_title("Extended G10 FX universe (robustness check, not in paper)\nOut-of-sample 2011-2024, growth of $1 net of 2bp costs")
    ax4.legend()
    ax4.grid(alpha=0.3)
    fig3.tight_layout()
    fig3.savefig(os.path.join(RESULTS_DIR, "equity_extended_universe_oos.png"), dpi=140)
    plt.close(fig3)

    print(f"Saved plots -> {RESULTS_DIR}/equity_and_drawdown_oos.png, equity_holdout.png, equity_extended_universe_oos.png")


if __name__ == "__main__":
    main()
