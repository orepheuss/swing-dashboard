#!/usr/bin/env python3
"""
Relative-strength ranker and backtest.

IDEA: stocks that have beaten the market over the last 3 to 6 months tend, on
average, to keep beating it for a while (momentum). This script
  1. ranks a list of stocks by how much they beat QQQ (the Nasdaq-100 fund), and
  2. with --backtest, checks whether the top-ranked stocks actually did better
     over the following weeks than the average stock, using only information
     that was available on each date.

Run:   python rs_ranker.py                   current ranking (top 15)
       python rs_ranker.py --backtest        test whether the ranking worked
       python rs_ranker.py --top 10 --csv ranking.csv
       python rs_ranker.py --tickers AAPL MSFT SHOP.TO

Needs: yfinance, pandas, numpy (already installed if the dashboard works).
Educational tool, not financial advice.
"""
import argparse

import numpy as np
import pandas as pd

BENCH = "QQQ"

# Large, liquid Nasdaq stocks. Approximate and editable: index membership changes,
# and any ticker Yahoo cannot find is skipped automatically.
UNIVERSE = """
AAPL MSFT NVDA AMZN GOOGL META AVGO TSLA COST NFLX AMD PEP ADBE CSCO TMUS LIN QCOM INTU
AMAT TXN AMGN ISRG BKNG HON CMCSA PANW VRTX ADP MU GILD ADI LRCX KLAC SBUX MDLZ REGN MELI
CDNS SNPS CRWD ABNB ORLY MAR PYPL CSX FTNT MRVL ADSK WDAY DASH NXPI ROP CHTR PCAR MNST
AEP CPRT PAYX KDP ROST FAST ODFL EA CTAS EXC XEL IDXX KHC GEHC DDOG TEAM ZS ON LULU CSGP
BKR TTD CCEP BIIB CDW GFS ASML ARM PLTR APP AXON TTWO
""".split()


# --------------------------------------------------------------------- data
def load(tickers, years):
    import yfinance as yf

    names = sorted(set(tickers + [BENCH]))
    raw = yf.download(names, period=f"{years}y", interval="1d", auto_adjust=True,
                      progress=False, threads=True)
    close = raw["Close"].dropna(axis=1, how="all")
    frames = {k: raw[k][close.columns] for k in ("Open", "High", "Low", "Close", "Volume")}
    ok = frames["Close"][BENCH].notna()
    return {k: v[ok] for k, v in frames.items()}


def features(f):
    """Relative-strength scores for every stock on every day (no look-ahead)."""
    c_all = f["Close"]
    bench = c_all[BENCH]
    c = c_all.drop(columns=[BENCH])
    ex3 = (c / c.shift(63) - 1).sub(bench / bench.shift(63) - 1, axis=0)    # ~3 months vs QQQ
    ex6 = (c / c.shift(126) - 1).sub(bench / bench.shift(126) - 1, axis=0)  # ~6 months vs QQQ
    raw = (ex3.rank(axis=1, pct=True) + ex6.rank(axis=1, pct=True)) / 2     # 0 = weakest, 1 = strongest
    trend_ok = c > c.rolling(50).mean()                                      # only stocks above 50-day
    return {"c": c, "bench": bench, "ex3": ex3, "ex6": ex6, "raw": raw, "comp": raw.where(trend_ok)}


# ------------------------------------------------------------- current list
def current(f, top_n):
    ft = features(f)
    c = ft["c"]
    cols = c.columns
    h, l = f["High"][cols], f["Low"][cols]
    pc = c.shift()
    tr = np.maximum(h - l, np.maximum((h - pc).abs(), (l - pc).abs()))
    atr = tr.rolling(14).mean().iloc[-1]
    sma20 = c.rolling(20).mean().iloc[-1]
    price = c.iloc[-1]
    table = pd.DataFrame({
        "Price": price,
        "3m %": (price / c.iloc[-64] - 1) * 100,
        "6m %": (price / c.iloc[-127] - 1) * 100,
        "6m vs QQQ %": ft["ex6"].iloc[-1] * 100,
        "From 52w high %": (price / c.rolling(252, min_periods=120).max().iloc[-1] - 1) * 100,
        "ATR %": atr / price * 100,
        "Pullback (ATR)": (price - sma20) / atr,
        "RS score": ft["comp"].iloc[-1] * 100,
        "Avg volume": f["Volume"][cols].rolling(20).mean().iloc[-1],
    })
    table = table[(table["RS score"].notna()) & (table["Avg volume"] >= 5e5)]
    return table.sort_values("RS score", ascending=False).head(top_n).drop(columns=["Avg volume"])


# ----------------------------------------------------------------- backtest
def backtest(f, top_n, hold):
    ft = features(f)
    c = ft["c"]
    o = f["Open"][c.columns]
    rows = []
    for i in range(130, len(c) - hold, hold):  # non-overlapping periods
        comp = ft["comp"].iloc[i].dropna()
        raw = ft["raw"].iloc[i].dropna()
        if len(comp) < top_n or len(raw) < top_n * 3:
            continue
        fwd = c.iloc[i + hold] / o.iloc[i + 1] - 1  # buy next open, sell `hold` days later
        fwd = fwd.dropna()
        pick = comp.nlargest(top_n).index.intersection(fwd.index)
        worst = raw.nsmallest(top_n).index.intersection(fwd.index)
        allv = raw.index.intersection(fwd.index)
        if len(pick) and len(worst) and len(allv):
            rows.append({"date": c.index[i], "top": fwd[pick].mean() * 100,
                         "universe": fwd[allv].mean() * 100, "bottom": fwd[worst].mean() * 100})
    return pd.DataFrame(rows)


def print_backtest(res, top_n, hold):
    n = len(res)
    if n < 5:
        print("Not enough periods to judge. Try --years 6 or a smaller --hold.")
        return
    diff = res["top"] - res["universe"]
    t = diff.mean() / (diff.std() / np.sqrt(n)) if diff.std() > 0 else float("nan")
    print(f"\nBacktest: {n} separate {hold}-day periods ({res.date.iloc[0]:%Y-%m} to {res.date.iloc[-1]:%Y-%m}), "
          f"top {top_n} stocks per period\n")
    print(f"  Average return per period, strongest {top_n}:   {res['top'].mean():+.2f}%")
    print(f"  Average return per period, all stocks:        {res['universe'].mean():+.2f}%")
    print(f"  Average return per period, weakest {top_n}:     {res['bottom'].mean():+.2f}%")
    print(f"\n  Strongest minus all stocks: {diff.mean():+.2f}% per period "
          f"(beat the average in {(diff > 0).mean() * 100:.0f}% of periods, t-stat {t:.2f})")
    print(f"  Worst period for the strongest group: {res['top'].min():+.1f}%\n")
    if t > 2 and diff.mean() > 0:
        print("  Reading: the ranking showed a statistically meaningful edge in this test.")
    elif diff.mean() > 0:
        print("  Reading: positive, but not strong enough to rule out luck (t-stat under 2).")
    else:
        print("  Reading: no edge found. The strongest stocks did not beat the average.")
    print("\nCaveats: the stock list is today's large Nasdaq companies, which flatters results")
    print("(losers that dropped out are missing); no commissions or slippage; one market period.")


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Rank stocks by relative strength and test the idea.")
    ap.add_argument("--tickers", nargs="+", default=UNIVERSE)
    ap.add_argument("--top", type=int, default=15, help="how many stocks to show / pick")
    ap.add_argument("--backtest", action="store_true", help="test whether the ranking worked historically")
    ap.add_argument("--hold", type=int, default=15, help="holding period in trading days (backtest)")
    ap.add_argument("--years", type=int, default=5, help="years of history to download")
    ap.add_argument("--csv", help="save the current ranking to this file")
    a = ap.parse_args()

    print(f"Downloading {len(a.tickers)} stocks plus {BENCH}... (about a minute)")
    f = load([t.upper() for t in a.tickers], a.years)
    got = len(f["Close"].columns) - 1
    print(f"Got data for {got} stocks.")

    if a.backtest:
        print_backtest(backtest(f, min(a.top, 10), a.hold), min(a.top, 10), a.hold)
        return

    table = current(f, a.top)
    last = f["Close"].index[-1]
    print(f"\nStrongest stocks vs {BENCH} as of {last:%Y-%m-%d} (above 50-day average, ranked by 3m and 6m strength)\n")
    pd.set_option("display.width", 200)
    print(table.round(1).to_string())
    print("\nHow to read: 'Pullback (ATR)' near 0 to 1 means the stock is close to its 20-day average (a more")
    print("sensible entry than chasing). Large values mean it has run far above it. These are the market's")
    print("current leaders, not predictions. Check each on the dashboard and the chart before acting.")
    if a.csv:
        table.round(2).to_csv(a.csv)
        print(f"Saved to {a.csv}")


if __name__ == "__main__":
    main()
