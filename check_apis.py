#!/usr/bin/env python3
"""
Data check: finds out what the free data sources can actually do before we build on them.

It always tests Yahoo Finance (no account or key needed) on Canadian and US stocks:
price history since 2021, currency, company description, news, analyst data, and some
basic sanity checks on the prices. It also tests Alpaca, Finnhub and Twelve Data if you
have put free keys in keys.txt (optional). Keys are never printed.

Optional setup: copy keys_example.txt to a new file named keys.txt, paste keys in, save.
Run:   double-click "Check APIs.bat"   (or: python check_apis.py)
Then copy the printed results back to Claude. They contain no keys.
"""
import os
from datetime import date, timedelta

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = date.today()


def load_env():
    path = next((p for p in (os.path.join(HERE, "keys.txt"), os.path.join(HERE, ".env")) if os.path.exists(p)), None)
    if not path:
        return False
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return True


def call(url, headers=None, params=None):
    """Returns (json_or_None, error_text_or_None). Never includes keys in messages."""
    try:
        r = requests.get(url, headers=headers, params=params, timeout=20)
    except Exception as exc:
        return None, f"network problem ({type(exc).__name__})"
    try:
        data = r.json()
    except Exception:
        return None, f"HTTP {r.status_code}, unreadable reply"
    if r.status_code >= 400:
        msg = data.get("message") or data.get("error") if isinstance(data, dict) else None
        return None, f"HTTP {r.status_code}: {str(msg)[:140] if msg else 'request refused'}"
    if isinstance(data, dict) and data.get("status") == "error":
        return None, f"{str(data.get('message', 'error'))[:140]}"
    return data, None


results = []


def record(name, ok, detail):
    results.append((name, ok, detail))
    print(f"  [{'OK' if ok else 'FAIL'}] {name}: {detail}")


def skip(group, how):
    print(f"\n{group}: SKIPPED (no keys found). {how}")


def check_yahoo():
    print("\nYahoo Finance via yfinance (free, no key)")
    try:
        import yfinance as yf
    except ImportError:
        return record("yfinance library", False, "not installed (run: python -m pip install yfinance)")
    for sym in ("RY.TO", "SHOP.TO", "AAPL"):
        try:
            t = yf.Ticker(sym)
            h = t.history(start="2021-01-04", interval="1d", auto_adjust=True)
        except Exception as exc:
            record(f"{sym} history", False, f"failed ({type(exc).__name__})")
            continue
        if h is None or h.empty:
            record(f"{sym} history", False, "no data returned")
            continue
        bad = int(h[["Open", "High", "Low", "Close"]].isna().any(axis=1).sum())
        h = h.dropna(subset=["Close"])
        moves = h["Close"].pct_change().abs()
        big = int((moves > 0.25).sum())
        gaps = int((h.index.to_series().diff().dt.days > 5).sum())
        record(f"{sym} history since 2021", len(h) > 900,
               f"{len(h)} daily bars, {h.index[0]:%Y-%m-%d} to {h.index[-1]:%Y-%m-%d}, last close {h['Close'].iloc[-1]:.2f}; "
               f"{bad} blank rows, {big} daily moves over 25%, {gaps} gaps over 5 days")
        info = {}
        try:
            info = t.info or {}
        except Exception:
            pass
        summary = info.get("longBusinessSummary")
        record(f"{sym} currency and description", bool(info.get("currency") and summary),
               f"currency {info.get('currency')}, {len(summary or '')} characters of description")
        try:
            news = t.news or []
        except Exception:
            news = []
        try:
            targets = t.analyst_price_targets or {}
        except Exception:
            targets = {}
        record(f"{sym} news and analyst targets", bool(news) or bool(targets),
               f"{len(news)} news items, analyst target mean {targets.get('mean')}")


def check_alpaca():
    kid, sec = os.getenv("ALPACA_KEY_ID"), os.getenv("ALPACA_SECRET_KEY")
    if not (kid and sec):
        return skip("Alpaca", "Sign up at alpaca.markets, create API keys, add ALPACA_KEY_ID and ALPACA_SECRET_KEY.")
    print("\nAlpaca (US stocks)")
    h = {"APCA-API-KEY-ID": kid, "APCA-API-SECRET-KEY": sec}
    base = "https://data.alpaca.markets/v2/stocks/AAPL"
    d, e = call(base + "/quotes/latest", h, {"feed": "iex"})
    if e:
        record("Latest AAPL quote", False, e)
    else:
        q = d.get("quote", {})
        record("Latest AAPL quote", True, f"bid {q.get('bp')}, ask {q.get('ap')}, time {q.get('t')}")
    d, e = call(base + "/bars", h, {"timeframe": "1Day", "start": "2021-01-04", "limit": 10000, "feed": "iex",
                                     "adjustment": "all"})
    if e:
        record("Daily history since 2021", False, e)
    else:
        bars = d.get("bars") or []
        record("Daily history since 2021", bool(bars),
               f"{len(bars)} daily bars, first {bars[0]['t'][:10]}" if bars else "no bars returned")


def check_finnhub():
    key = os.getenv("FINNHUB_API_KEY")
    if not key:
        return skip("Finnhub", "Sign up at finnhub.io and add FINNHUB_API_KEY.")
    print("\nFinnhub (company info, news, analysts)")
    h = {"X-Finnhub-Token": key}
    u = "https://finnhub.io/api/v1"
    d, e = call(u + "/quote", h, {"symbol": "AAPL"})
    record("US quote (AAPL)", bool(d and d.get("c")), e or f"price {d.get('c')}")
    d, e = call(u + "/stock/profile2", h, {"symbol": "AAPL"})
    record("Company profile", bool(d and d.get("name")), e or f"{d.get('name')} | {d.get('finnhubIndustry')}")
    d, e = call(u + "/company-news", h, {"symbol": "AAPL", "from": str(TODAY - timedelta(days=7)), "to": str(TODAY)})
    record("Company news (7 days)", bool(d), e or f"{len(d)} articles")
    d, e = call(u + "/stock/recommendation", h, {"symbol": "AAPL"})
    record("Analyst recommendations", bool(d), e or f"{len(d)} monthly records")
    d, e = call(u + "/quote", h, {"symbol": "RY.TO"})
    record("Canadian quote (RY.TO)", bool(d and d.get("c")), e or (f"price {d.get('c')}" if d.get("c") else "returned no data"))


def check_twelvedata():
    key = os.getenv("TWELVEDATA_API_KEY")
    if not key:
        return skip("Twelve Data", "Sign up at twelvedata.com and add TWELVEDATA_API_KEY.")
    print("\nTwelve Data (Canadian TSX stocks)")
    h = {"Authorization": f"apikey {key}"}
    u = "https://api.twelvedata.com"
    d, e = call(u + "/quote", h, {"symbol": "RY", "exchange": "TSX"})
    record("TSX quote (RY)", bool(d and d.get("close")), e or f"close {d.get('close')} {d.get('currency', '')}, {d.get('datetime')}")
    d, e = call(u + "/time_series", h, {"symbol": "RY", "exchange": "TSX", "interval": "1day",
                                         "start_date": "2021-01-04", "outputsize": 5000})
    if e:
        record("TSX daily history since 2021", False, e)
    else:
        vals = d.get("values") or []
        record("TSX daily history since 2021", bool(vals),
               f"{len(vals)} daily bars, oldest {vals[-1]['datetime']}" if vals else "no bars returned")


def main():
    if not load_env():
        print("No keys.txt found: that is fine, only the Yahoo checks will run (no keys needed).")
    check_yahoo()
    check_alpaca()
    check_finnhub()
    check_twelvedata()
    ok = sum(1 for r in results if r[1])
    print(f"\nSummary: {ok} of {len(results)} checks passed. Copy everything above into your chat with Claude.")
    print("(Your keys are not printed anywhere in this output.)")


if __name__ == "__main__":
    main()
