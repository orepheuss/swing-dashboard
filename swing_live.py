"""
Live swing trade dashboard.

Shows a candlestick chart with the 20/50/200-day averages, your entry, stop and
target lines, and the 100-point swing score. Data is re-pulled from Yahoo
Finance automatically at the interval you choose.

Easiest way to start: double-click "Start Swing Dashboard.bat" (Windows),
or run launch.py. Needs swing_scanner.py in the same folder.
Manual start: python -m streamlit run swing_live.py
"""
from datetime import date, datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

import swing_scanner as sc

st.set_page_config(page_title="Swing dashboard", layout="wide")

REFRESH = {"1 minute": 60, "5 minutes": 300, "Off": None}

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Settings")
    ticker = st.text_input("Ticker", "AAPL", help="Canadian TSX stocks end in .TO, for example SHOP.TO or RY.TO").strip().upper()
    refresh_label = st.selectbox("Refresh data every", list(REFRESH), index=0)
    account = st.number_input("Account size ($)", min_value=100.0, value=10000.0, step=500.0)
    risk_pct = st.number_input("Risk per trade (%)", min_value=0.1, max_value=5.0, value=1.0, step=0.1)
    manual = st.checkbox("Use my own support and target")
    support = target = None
    if manual:
        support = st.number_input("Support level ($)", min_value=0.01, value=100.0, step=0.5)
        target = st.number_input("Target price ($)", min_value=0.01, value=120.0, step=0.5)
    st.caption("Educational tool, not financial advice.")


# --------------------------------------------------------------------- data
@st.cache_data(ttl=60, show_spinner=False)
def get_history(tk):
    """One year of daily bars. Cached for 60 seconds so many visitors share one Yahoo request."""
    return yf.Ticker(tk).history(period="1y", interval="1d", auto_adjust=True)


@st.cache_data(ttl=3600, show_spinner=False)
def earnings_days(tk):
    """Days until next earnings, or None. Cached for an hour (it rarely changes)."""
    try:
        cal = yf.Ticker(tk).calendar
        dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
        if dates:
            today = date.today()
            clean = [d.date() if isinstance(d, datetime) else d for d in dates]
            future = [d for d in clean if d >= today]
            if future:
                return (min(future) - today).days
    except Exception:
        pass
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def company_info(tk):
    """Name, sector, size and 52-week range. Cached for an hour; may be empty."""
    try:
        info = yf.Ticker(tk).info
        keys = ("longName", "sector", "marketCap", "fiftyTwoWeekHigh", "fiftyTwoWeekLow")
        return {k: info.get(k) for k in keys}
    except Exception:
        return {}


def fmt_cap(x):
    if not x:
        return None
    for div, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if x >= div:
            return f"${x / div:.1f}{suffix}"
    return f"${x:,.0f}"


def build_chart(df, res, tk):
    close = df["Close"]
    view = df.tail(130)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.78, 0.22], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(x=view.index, open=view["Open"], high=view["High"], low=view["Low"],
                                 close=view["Close"], name=tk), row=1, col=1)
    for n, colour in [(20, "#2a9d8f"), (50, "#e9a23b"), (200, "#8a6fd1")]:
        ma = close.rolling(n).mean().tail(130)
        fig.add_trace(go.Scatter(x=view.index, y=ma, mode="lines", name=f"{n}-day",
                                 line=dict(width=1.5, color=colour)), row=1, col=1)
    for label, y, colour in [("Target", res["target"], "#2a9d8f"), ("Entry", res["entry"], "#888888"),
                             ("Stop", res["stop"], "#d1495b")]:
        fig.add_hline(y=y, line=dict(color=colour, width=1, dash="dash"), row=1, col=1,
                      annotation_text=f"{label} {y:.2f}", annotation_position="right")
    fig.add_trace(go.Bar(x=view.index, y=view["Volume"], name="Volume", marker_color="#9aa5a0"), row=2, col=1)
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    fig.update_layout(height=640, margin=dict(l=10, r=70, t=10, b=10), xaxis_rangeslider_visible=False,
                      legend=dict(orientation="h", y=1.02, x=0))
    return fig


# ---------------------------------------------------------------- live view
@st.fragment(run_every=REFRESH[refresh_label])
def live_view():
    info = company_info(ticker)
    st.title(f"{info.get('longName') or ticker} ({ticker})")
    bits = [info.get("sector"), fmt_cap(info.get("marketCap")) and f"market cap {fmt_cap(info.get('marketCap'))}"]
    if info.get("fiftyTwoWeekLow") and info.get("fiftyTwoWeekHigh"):
        bits.append(f"52-week range ${info['fiftyTwoWeekLow']:.2f} to ${info['fiftyTwoWeekHigh']:.2f}")
    bits = [b for b in bits if b]
    if bits:
        st.caption(" | ".join(bits))
    st.warning(
        "Model status: a 3-year backtest on 30 large Nasdaq stocks found no reliable edge in these scores "
        "(strong candidates won 35% of trades versus 48% for all days). Use this as a chart and checklist "
        "tool, not as a buy signal."
    )
    try:
        df = get_history(ticker)
    except Exception as exc:
        st.error(f"Could not fetch data ({type(exc).__name__}). Yahoo may be limiting requests; wait a minute and refresh.")
        return
    if df is not None:
        df = sc.clean(df)
    if df is None or len(df) < 200:
        st.warning("Not enough history (need 200 days). Check the ticker; Canadian stocks need .TO, e.g. SHOP.TO.")
        return

    try:
        ind = sc.indicators(df)
        res = sc.score(ind, earnings_days(ticker), support, target)
    except ValueError as exc:
        st.warning(f"Could not score {ticker}: {exc}")
        return
    shares = sc.size_position(res, account, risk_pct)

    banner = f"Model verdict: {res['verdict']} (score {res['total']}/100)"
    if res["verdict"] == "STRONG CANDIDATE":
        st.success(banner)
    elif res["verdict"] == "WATCHLIST":
        st.warning(banner)
    else:
        st.error(banner)
    for flag in res["flags"]:
        st.error(f"Hard flag: {flag}")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Last price", f"${ind['price']:.2f}")
    c2.metric("Reward : risk", f"{res['rr']:.2f} : 1" if res["rr"] == res["rr"] else "n/a")
    c3.metric("Shares", f"{shares:,}")
    c4.metric("Position cost", f"${shares * res['entry']:,.0f}")
    c5.metric("Max loss", f"${shares * res['risk']:,.0f}" if res["risk"] > 0 else "n/a")
    if shares * res["entry"] > account:
        st.info("Position cost exceeds your account size. Reduce size or skip this trade.")

    st.plotly_chart(build_chart(df, res, ticker), width="stretch")

    table = pd.DataFrame(res["factors"], columns=["Factor", "Points", "Max", "Why"])
    st.dataframe(table, hide_index=True, width="stretch")
    for note in res["estimates"]:
        st.caption(f"Auto-estimated: {note}. Tick the sidebar box to enter your own levels.")

    every = REFRESH[refresh_label]
    st.caption(
        f"Latest bar: {df.index[-1]:%Y-%m-%d} | Pulled at {datetime.now():%H:%M:%S} | "
        + (f"refreshing every {every} s" if every else "auto-refresh is off")
        + " | Yahoo data can be delayed up to 15 minutes depending on the exchange."
    )


live_view()
