# Swing Dashboard

A free stock-screening dashboard for swing traders, built in Python with Streamlit.
Type a ticker and it pulls daily price data, draws a candlestick chart with moving
averages, and scores the setup out of 100 with a suggested stop, target and position size.

Canadian TSX stocks work too: add `.TO` to the ticker (for example `SHOP.TO`, `RY.TO`).

> **Educational tool, not financial advice.** In a 3-year backtest on 30 large Nasdaq
> stocks, the current score showed **no reliable edge** (strong candidates won 35% of
> trades versus 48% for all days). Treat the page as a chart and checklist tool, not a
> buy signal. See "Roadmap" for what is being done about that.

## What is in this repository

| File | What it does |
|---|---|
| `swing_live.py` | The website (Streamlit app). This is the file you deploy. |
| `swing_scanner.py` | The scoring model, also usable from the command line. |
| `swing_backtest.py` | Tests whether the score predicted results historically. |
| `rs_ranker.py` | Ranks stocks by strength versus the Nasdaq-100 (QQQ) and backtests the idea. |
| `check_apis.py` | Checks what the free data sources return on your computer. |
| `launch.py` and `*.bat` files | One-click launchers for Windows. |
| `requirements.txt` | The Python libraries the app needs. |
| `keys_example.txt` | Template for optional API keys. Copy to `keys.txt`. Never upload `keys.txt`. |
| `DEPLOY.md` | Step-by-step guide to publishing the site with a shareable link. |

## How the score works

Six checks add up to 100 points: trend (25), entry location (20), liquidity and
volatility (20), reward to risk (15), volume confirmation (10) and event risk (10).
75 or more is a "strong candidate", 55 to 74 is "watchlist", below 55 is a pass, and
any hard flag (downtrend, reward-to-risk under 1.5, earnings within 3 days, bad stop)
forces a pass. The stop sits half an ATR below the 10-day low and the target is the
60-day high, kept between 2 and 4 ATR above the price.

## Run it on your own computer

1. Install Python from python.org (tick "Add python.exe to PATH" on Windows).
2. Download this repository (green **Code** button, then **Download ZIP**) and unzip it.
3. Double-click `Start Swing Dashboard.bat`. It installs what it needs and opens the site.

Or from a terminal in the folder:

```
python -m pip install -r requirements.txt
python -m streamlit run swing_live.py
```

Other tools (run from the same folder):

```
python swing_scanner.py SHOP.TO RY.TO AAPL     # score and rank several stocks
python swing_backtest.py                       # backtest the score
python rs_ranker.py                            # strongest stocks versus QQQ
python rs_ranker.py --backtest                 # does that ranking work?
python check_apis.py                           # test the data sources
```

## Publish it with a shareable link

See `DEPLOY.md`. It uses Streamlit Community Cloud, which is free and publishes
directly from this repository.

## Data

Prices come from Yahoo Finance through the unofficial `yfinance` library. It is free
and covers TSX (`.TO`) and US stocks, but it is not an official feed. It can be
briefly delayed, occasionally return blank or wrong rows, and may rate-limit shared
servers. Confirm any price on your broker before trading.

## Roadmap

- Backtest five models side by side, using data from 2021 onward and walk-forward
  testing: RSI + Bollinger Bands mean reversion, volume-weighted momentum, Elastic Net,
  XGBoost and an ensemble that combines them.
- Include realistic trading costs. On Wealthsimple, US stocks bought from a CAD account
  carry a 1.5% currency conversion fee each way, so TSX stocks are the main focus.
- Ticker page additions: short company description, publicly reported partners
  (from news), headlines with sentiment, analyst targets, and a simple pass/fail.

## Disclaimer

This software is provided as is, for education. Nothing here is investment advice.
Past performance does not predict future results, and you can lose money trading.
