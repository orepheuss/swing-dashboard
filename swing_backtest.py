#!/usr/bin/env python3
"""
Backtest of the swing score model.

For every trading day in the history of each stock, this scores the stock using
ONLY data available up to that day, then simulates the trade the model would
have proposed (enter next open, stop and target from the model, exit after
--hold days if neither is hit) and groups the results by verdict.

If the model works, results should improve as the verdict gets better:
"STRONG CANDIDATE" should show a higher average R and win rate than
"WATCHLIST", and both should beat "PASS". If they don't, the model needs tuning.

Setup:  needs swing_scanner.py in the same folder (and yfinance, pandas, numpy)
Run:    python swing_backtest.py
        python swing_backtest.py --years 3 --hold 15
        python swing_backtest.py --tickers AAPL MSFT NVDA --csv signals.csv
"""
import argparse

import numpy as np
import pandas as pd

import swing_scanner as sc

DEFAULT_TICKERS = (
    "AAPL MSFT NVDA AMZN GOOGL META AVGO TSLA COST NFLX AMD PEP ADBE CSCO TMUS "
    "LIN QCOM INTU AMAT TXN AMGN ISRG BKNG HON CMCSA PANW VRTX ADP MU GILD"
).split()


def precompute(df):
    """Indicator columns for every day, matching swing_scanner.indicators()."""
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    prev = c.shift()
    tr = pd.concat([h - l, (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    return pd.DataFrame({
        "price": c,
        "sma20": c.rolling(20).mean(),
        "sma50": c.rolling(50).mean(),
        "sma200": c.rolling(200).mean(),
        "rsi": rsi.fillna(100),
        "atr": tr.rolling(14).mean(),
        "avg_vol": v.shift(1).rolling(20).mean(),
        "today_vol": v,
        "low10": l.rolling(10).min(),
        "high60": h.rolling(60).max(),
    })


def simulate(o, h, l, c, i, entry_idx, stop, target, hold):
    """Walk forward from the entry day. Stop is checked first (conservative)."""
    entry = o[entry_idx]
    risk = entry - stop
    if risk <= 0 or entry >= target:
        return None
    for j in range(entry_idx, entry_idx + hold):
        if o[j] <= stop:                      # gapped through the stop
            return (o[j] - entry) / risk, "stop", j
        if l[j] <= stop:
            return -1.0, "stop", j
        if o[j] >= target:                    # gapped through the target
            return (o[j] - entry) / risk, "target", j
        if h[j] >= target:
            return (target - entry) / risk, "target", j
    return (c[entry_idx + hold - 1] - entry) / risk, "time", entry_idx + hold - 1


def backtest_ticker(tk, df, hold=15):
    df = sc.clean(df)
    ind = precompute(df).dropna()
    o, h, l, c = (df[k].to_numpy(float) for k in ("Open", "High", "Low", "Close"))
    pos = {d: n for n, d in enumerate(df.index)}
    rows = []
    for d, row in ind.iterrows():
        i = pos[d]
        entry_idx = i + 1
        if entry_idx + hold > len(df):        # outcome not known yet
            continue
        res = sc.score(row.to_dict(), None)   # earnings history is not available
        out = simulate(o, h, l, c, i, entry_idx, res["stop"], res["target"], hold)
        if out is None:
            continue
        r_mult, how, exit_idx = out
        rows.append({
            "ticker": tk, "date": d, "score": res["total"], "verdict": res["verdict"],
            "R": r_mult, "exit": how, "ret_pct": (r_mult * (o[entry_idx] - res["stop"])) / o[entry_idx] * 100,
            "exit_idx": exit_idx, "entry_idx": entry_idx,
        })
    return rows


def summarise(results):
    order = ["STRONG CANDIDATE", "WATCHLIST", "PASS", "PASS (hard flag)"]
    lines = []
    for name, grp in [("ALL SIGNALS", results)] + [(v, results[results.verdict == v]) for v in order]:
        if grp.empty:
            continue
        lines.append({
            "Verdict": name, "Trades": len(grp),
            "Win rate": f"{(grp.R > 0).mean() * 100:.0f}%",
            "Avg R": f"{grp.R.mean():+.2f}",
            "Median R": f"{grp.R.median():+.2f}",
            "Avg return": f"{grp.ret_pct.mean():+.2f}%",
            "Hit target": f"{(grp.exit == 'target').mean() * 100:.0f}%",
            "Hit stop": f"{(grp.exit == 'stop').mean() * 100:.0f}%",
        })
    return pd.DataFrame(lines)


def independent_trades(results):
    """Strong signals only, one open trade per stock at a time (no overlap)."""
    keep = []
    for tk, grp in results[results.verdict == "STRONG CANDIDATE"].groupby("ticker"):
        free_from = -1
        for _, r in grp.sort_values("entry_idx").iterrows():
            if r.entry_idx > free_from:
                keep.append(r)
                free_from = r.exit_idx
    return pd.DataFrame(keep)


def main():
    ap = argparse.ArgumentParser(description="Backtest the swing score model on historical data.")
    ap.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS)
    ap.add_argument("--years", type=int, default=3, help="years of signals to test (default 3)")
    ap.add_argument("--hold", type=int, default=15, help="max trading days to hold (default 15)")
    ap.add_argument("--csv", help="save every signal to this CSV file")
    a = ap.parse_args()

    import yfinance as yf
    all_rows = []
    for tk in a.tickers:
        try:
            df = yf.Ticker(tk).history(period=f"{a.years + 1}y", interval="1d", auto_adjust=True)
            if len(df) < 300:
                print(f"{tk}: not enough data, skipped")
                continue
            rows = backtest_ticker(tk, df, a.hold)
            all_rows += rows
            print(f"{tk}: {len(rows)} signals")
        except Exception as exc:
            print(f"{tk}: failed ({exc})")

    if not all_rows:
        print("No results.")
        return
    results = pd.DataFrame(all_rows)
    if a.csv:
        results.drop(columns=["exit_idx", "entry_idx"]).to_csv(a.csv, index=False)

    pd.set_option("display.width", 200)
    print(f"\nBacktest: {results.ticker.nunique()} stocks, hold up to {a.hold} days\n")
    print(summarise(results).to_string(index=False))

    ind = independent_trades(results)
    if not ind.empty:
        print(f"\nStrong candidates with no overlapping trades per stock: {len(ind)} trades, "
              f"win rate {(ind.R > 0).mean() * 100:.0f}%, avg R {ind.R.mean():+.2f}")

    print("\nHow to read this: R = profit as a multiple of the amount risked (1R = hit the stop).")
    print("The model is only useful if Avg R and win rate rise from PASS to WATCHLIST to STRONG CANDIDATE.")
    print("Caveats: today's big stocks are survivors (flatters results); earnings dates are not")
    print("modelled; no commissions or slippage; overlapping signals on nearby days are correlated.")


if __name__ == "__main__":
    main()
