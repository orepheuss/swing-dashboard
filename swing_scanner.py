#!/usr/bin/env python3
"""
Swing trade scanner.

Pulls daily price/volume data from Yahoo Finance (via the yfinance library),
calculates the indicators, and scores each stock out of 100 using the same
model as the Swing trade scorecard page.

Setup (once):   pip install yfinance pandas numpy
Examples:       python swing_scanner.py AAPL
                python swing_scanner.py AAPL MSFT NVDA SHOP.TO --account 10000 --risk 1
                python swing_scanner.py AAPL --support 205 --target 230

Educational tool, not financial advice. Yahoo data is free but unofficial and
can be delayed or occasionally wrong: confirm on your broker's chart.
"""
import argparse
import sys
from datetime import date, datetime

import numpy as np
import pandas as pd


# --------------------------------------------------------------------- data
def fetch(ticker):
    """Return (daily OHLCV DataFrame, days until next earnings or None)."""
    import yfinance as yf

    t = yf.Ticker(ticker)
    df = t.history(period="1y", interval="1d", auto_adjust=True)
    earn_days = None
    try:
        cal = t.calendar
        dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
        if dates:
            today = date.today()
            clean = [d.date() if isinstance(d, datetime) else d for d in dates]
            future = [d for d in clean if d >= today]
            if future:
                earn_days = (min(future) - today).days
    except Exception:
        pass  # earnings date is optional
    return df, earn_days


# --------------------------------------------------------------- indicators
def clean(df):
    """Drop rows with missing prices (Yahoo sometimes returns an empty latest bar)."""
    df = df.dropna(subset=["Open", "High", "Low", "Close"]).copy()
    df["Volume"] = df["Volume"].fillna(0)
    return df


def indicators(df):
    df = clean(df)
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    prev = c.shift()
    tr = pd.concat([h - l, (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    return {
        "price": float(c.iloc[-1]),
        "sma20": float(c.rolling(20).mean().iloc[-1]),
        "sma50": float(c.rolling(50).mean().iloc[-1]),
        "sma200": float(c.rolling(200).mean().iloc[-1]),
        "rsi": float(rsi.fillna(100).iloc[-1]),
        "atr": float(tr.rolling(14).mean().iloc[-1]),
        "avg_vol": float(v.iloc[-21:-1].mean()),  # 20 sessions before the latest
        "today_vol": float(v.iloc[-1]),
        "low10": float(l.iloc[-10:].min()),
        "high60": float(h.iloc[-60:].max()),
    }


# ------------------------------------------------------------------ scoring
def score(ind, earn_days, support=None, target=None):
    bad = [k for k, x in ind.items() if x != x or x in (float("inf"), float("-inf"))]
    if bad or ind["atr"] <= 0 or ind["price"] <= 0:
        raise ValueError("incomplete price data from Yahoo (" + ", ".join(bad or ["atr"]) + "); try again shortly")
    p, atr = ind["price"], ind["atr"]
    est = []
    if support is None:
        support = ind["low10"]
        est.append("support = lowest low of last 10 sessions")
    if target is None:
        # Aim for the 60-day high, but keep the move realistic for a 1-3 week swing:
        # at least 2 ATR above price (so stocks at their highs are not penalised)
        # and at most 4 ATR (so a stock far below its high does not get a fantasy target).
        room = ind["high60"] - p
        target = p + min(max(room, 2 * atr), 4 * atr)
        est.append("target = 60-day high, limited to between 2 and 4 ATR above price")

    factors, flags = [], []

    # Trend (25)
    pts, weak = 0, []
    for ok, w, msg in [
        (p > ind["sma50"], 8, "price below 50-day"),
        (ind["sma20"] > ind["sma50"], 6, "20-day below 50-day"),
        (ind["sma50"] > ind["sma200"], 6, "50-day below 200-day"),
        (p > ind["sma200"], 5, "price below 200-day"),
    ]:
        pts += w if ok else 0
        if not ok:
            weak.append(msg)
    factors.append(("Trend", pts, 25, "; ".join(weak) or "all four trend checks pass"))
    if p < ind["sma200"] and ind["sma50"] < ind["sma200"]:
        flags.append("Confirmed downtrend (price and 50-day under the 200-day)")

    # Entry location (20)
    pts, notes = 0, []
    dist = abs(p - ind["sma20"]) / atr
    if dist <= 1:
        pts += 10
        notes.append(f"within {dist:.1f} ATR of the 20-day")
    elif dist <= 2:
        pts += 5
        notes.append(f"{dist:.1f} ATR from the 20-day (a bit stretched)")
    else:
        notes.append(f"{dist:.1f} ATR from the 20-day (chasing)")
    rsi = ind["rsi"]
    if 40 <= rsi <= 60:
        pts += 10
        notes.append(f"RSI {rsi:.0f} in pullback zone")
    elif 30 <= rsi < 40 or 60 < rsi <= 70:
        pts += 5
        notes.append(f"RSI {rsi:.0f} borderline")
    else:
        notes.append(f"RSI {rsi:.0f} {'overbought' if rsi > 70 else 'weak'}")
    factors.append(("Entry location", pts, 20, "; ".join(notes)))

    # Liquidity and volatility (20)
    pts, notes = 0, []
    av = ind["avg_vol"]
    if av >= 1e6:
        pts += 10
        notes.append(f"liquid ({av / 1e6:.1f}M/day)")
    elif av >= 5e5:
        pts += 6
        notes.append("adequate volume")
    elif av >= 2e5:
        pts += 3
        notes.append("thin volume")
    else:
        notes.append("illiquid")
    atr_pct = atr / p * 100
    if 1.5 <= atr_pct <= 5:
        pts += 10
        notes.append(f"ATR {atr_pct:.1f}% of price")
    elif 1 <= atr_pct < 1.5 or 5 < atr_pct <= 7:
        pts += 5
        notes.append(f"ATR {atr_pct:.1f}% ({'sluggish' if atr_pct < 1.5 else 'jumpy'})")
    else:
        notes.append(f"ATR {atr_pct:.1f}% ({'too quiet' if atr_pct < 1 else 'too volatile'})")
    factors.append(("Liquidity/volatility", pts, 20, "; ".join(notes)))

    # Volume confirmation (10)
    rv = ind["today_vol"] / av if av else 0
    pts = 10 if rv >= 1.2 else 6 if rv >= 1 else 3 if rv >= 0.7 else 0
    factors.append(("Volume confirmation", pts, 10, f"latest volume {rv:.1f}x average"))

    # Reward to risk (15)
    stop = support - 0.5 * atr
    risk, reward = p - stop, target - p
    rr = reward / risk if risk > 0 else float("nan")
    if risk <= 0:
        pts, note = 0, "stop is not below price"
        flags.append("Stop at or above entry price")
    elif reward <= 0:
        pts, note = 0, "target is not above price"
        flags.append("Target at or below entry price")
    else:
        pts = 15 if rr >= 3 else 12 if rr >= 2 else 6 if rr >= 1.5 else 0
        note = f"risk {risk:.2f} to make {reward:.2f} = {rr:.2f}:1"
        if rr < 1.5:
            flags.append("Reward-to-risk under 1.5:1")
    factors.append(("Reward to risk", pts, 15, note))

    # Event risk (10)
    if earn_days is None or earn_days > 14:
        pts, note = 10, "no earnings in the next 14 days" if earn_days is None else f"earnings in {earn_days} days"
    elif earn_days >= 8:
        pts, note = 6, f"earnings in {earn_days} days: plan an early exit"
    elif earn_days >= 4:
        pts, note = 2, f"earnings in {earn_days} days: gap risk"
    else:
        pts, note = 0, f"earnings in {earn_days} days"
        flags.append("Earnings within 3 days")
    factors.append(("Event risk", pts, 10, note))

    total = sum(f[1] for f in factors)
    if flags:
        verdict = "PASS (hard flag)"
    elif total >= 75:
        verdict = "STRONG CANDIDATE"
    elif total >= 55:
        verdict = "WATCHLIST"
    else:
        verdict = "PASS"
    return dict(total=total, verdict=verdict, factors=factors, flags=flags, estimates=est,
                entry=p, stop=stop, target=target, risk=risk, rr=rr)


def size_position(res, account, risk_pct):
    if not res["risk"] > 0:  # also catches NaN
        return 0
    return int(account * risk_pct / 100 // res["risk"])


# ------------------------------------------------------------------- output
def report(ticker, ind, res, account, risk_pct):
    shares = size_position(res, account, risk_pct)
    line = "=" * 64
    print(f"\n{line}\n{ticker}   ${res['entry']:.2f}   score {res['total']}/100   {res['verdict']}\n{line}")
    for name, pts, mx, note in res["factors"]:
        print(f"  {name:<22}{pts:>3}/{mx:<3} {note}")
    for f in res["flags"]:
        print(f"  !! {f}")
    print(f"  Plan: entry {res['entry']:.2f} | stop {res['stop']:.2f} | target {res['target']:.2f}"
          f" | {shares} shares (${shares * res['entry']:,.0f}) | max loss ${shares * res['risk']:,.0f}")
    if shares * res["entry"] > account:
        print("  Note: position cost exceeds your account size; reduce size or skip.")
    for e in res["estimates"]:
        print(f"  (auto) {e}")


def short_flags(flags):
    names = {"Confirmed": "downtrend", "Reward": "low R:R", "Earnings": "earnings soon",
             "Stop": "stop above entry", "Target": "target below entry"}
    return ", ".join(names.get(f.split()[0], f) for f in flags)


def main():
    ap = argparse.ArgumentParser(description="Score stocks for swing trading using live Yahoo Finance data.")
    ap.add_argument("tickers", nargs="+", help="e.g. AAPL MSFT SHOP.TO")
    ap.add_argument("--account", type=float, default=10000, help="account size in $ (default 10000)")
    ap.add_argument("--risk", type=float, default=1.0, help="percent of account risked per trade (default 1)")
    ap.add_argument("--support", type=float, help="your own support level (single ticker only)")
    ap.add_argument("--target", type=float, help="your own target price (single ticker only)")
    args = ap.parse_args()

    rows = []
    for tk in [t.upper() for t in args.tickers]:
        try:
            df, earn = fetch(tk)
            if len(df) < 200:
                print(f"{tk}: only {len(df)} days of data (need 200). Skipping.")
                continue
            one = len(args.tickers) == 1
            ind = indicators(df)
            res = score(ind, earn, args.support if one else None, args.target if one else None)
            report(tk, ind, res, args.account, args.risk)
            rows.append((tk, res["total"], res["verdict"], res["rr"], short_flags(res["flags"])))
        except Exception as exc:
            print(f"{tk}: failed ({exc})")

    if len(rows) > 1:
        order = {"STRONG CANDIDATE": 0, "WATCHLIST": 1, "PASS": 2, "PASS (hard flag)": 3}
        print("\nRanking (best verdict first, then score)")
        for tk, total, verdict, rr, why in sorted(rows, key=lambda r: (order[r[2]], -r[1])):
            rr_txt = f"{rr:.2f}" if rr == rr else "n/a"
            print(f"  {tk:<10}{total:>4}  {verdict:<18} R:R {rr_txt:<6} {why}")
    print("\nEducational tool, not financial advice. Confirm on the chart before trading.")


if __name__ == "__main__":
    sys.exit(main())
