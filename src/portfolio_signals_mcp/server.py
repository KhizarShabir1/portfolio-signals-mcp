"""Portfolio Signals MCP Server.

An MCP server that gives any coding agent (Claude Code, Cursor, etc.)
real-time stock quotes and technical-analysis signals via yfinance.

Tools:
    get_quote             - current price, day change, volume, 52w range
    get_technical_signals - RSI, MACD, SMA 50/200 crossover classifications
    compare_tickers       - side-by-side returns over a period
    weekly_digest         - one-call weekly report for a whole portfolio

Run:
    portfolio-signals-mcp            # stdio (for Claude Code / Cursor)
    portfolio-signals-mcp --http     # streamable HTTP (for remote hosting)
"""

from __future__ import annotations

import argparse
import os

import pandas as pd
import yfinance as yf
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "Portfolio Signals",
    host=os.environ.get("HOST", "0.0.0.0"),
    port=int(os.environ.get("PORT", "8000")),
)


# ---------------------------------------------------------------------------
# Indicator helpers (pure pandas — no TA library needed)
# ---------------------------------------------------------------------------

def _rsi(close: pd.Series, period: int = 14) -> float:
    """Wilder's RSI over the given period."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)


def _macd(close: pd.Series) -> dict:
    """MACD(12, 26, 9): line, signal, histogram, and cross direction."""
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line
    prev, curr = float(hist.iloc[-2]), float(hist.iloc[-1])
    if prev <= 0 < curr:
        position = "crossed_above_signal"
    elif prev >= 0 > curr:
        position = "crossed_below_signal"
    else:
        position = "above_signal" if curr > 0 else "below_signal"
    return {
        "macd": round(float(macd_line.iloc[-1]), 4),
        "signal": round(float(signal_line.iloc[-1]), 4),
        "histogram": round(curr, 4),
        "vs_signal": position,
    }


def _sma_signals(close: pd.Series) -> dict:
    """SMA 50/200 values and golden/death-cross status."""
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    out = {
        "sma_50": round(float(sma50.iloc[-1]), 2) if not pd.isna(sma50.iloc[-1]) else None,
        "sma_200": round(float(sma200.iloc[-1]), 2) if not pd.isna(sma200.iloc[-1]) else None,
        "price_vs_sma50": None,
        "sma_50_vs_200": None,
    }
    price = float(close.iloc[-1])
    if out["sma_50"]:
        out["price_vs_sma50"] = "above" if price > out["sma_50"] else "below"
    if out["sma_50"] and out["sma_200"]:
        out["sma_50_vs_200"] = "golden_cross" if out["sma_50"] > out["sma_200"] else "death_cross"
    return out


def _history(ticker: str, period: str = "1y") -> pd.DataFrame:
    df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
    if df.empty:
        raise ValueError(f"No data found for ticker '{ticker}'. Check the symbol.")
    return df


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_quote(ticker: str) -> dict:
    """Get the current quote for a stock/ETF ticker: price, day change,
    volume, and 52-week range.

    Args:
        ticker: Symbol like 'AAPL', 'MSFT', 'VOO'.
    """
    df = _history(ticker, "1y")
    close = df["Close"]
    price = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    return {
        "ticker": ticker.upper(),
        "price": round(price, 2),
        "day_change_pct": round((price - prev) / prev * 100, 2),
        "volume": int(df["Volume"].iloc[-1]),
        "52w_high": round(float(close.max()), 2),
        "52w_low": round(float(close.min()), 2),
        "pct_off_52w_high": round((price / float(close.max()) - 1) * 100, 2),
        "as_of": str(df.index[-1].date()),
    }


@mcp.tool()
def get_technical_signals(ticker: str) -> dict:
    """Compute technical indicators for a ticker: RSI(14), MACD(12,26,9),
    and SMA 50/200 relationships.

    Returns measurements and standard threshold classifications only —
    interpretation is left to the caller. Classifications used:
    - rsi_zone: 'overbought' if RSI >= 70, 'oversold' if RSI <= 30,
      else 'neutral' (standard Wilder thresholds)
    - macd.vs_signal: MACD line position relative to its 9-period signal
      line, including single-day crossovers
    - moving_averages.sma_50_vs_200: 'golden_cross' if SMA50 > SMA200,
      'death_cross' otherwise (standard definitions)

    Args:
        ticker: Symbol like 'AAPL', 'NVDA'.
    """
    df = _history(ticker, "1y")
    close = df["Close"]
    rsi = _rsi(close)

    if rsi >= 70:
        rsi_zone = "overbought"
    elif rsi <= 30:
        rsi_zone = "oversold"
    else:
        rsi_zone = "neutral"

    return {
        "ticker": ticker.upper(),
        "price": round(float(close.iloc[-1]), 2),
        "rsi_14": rsi,
        "rsi_zone": rsi_zone,
        "rsi_thresholds": {"overbought": 70, "oversold": 30},
        "macd": _macd(close),
        "moving_averages": _sma_signals(close),
        "disclaimer": "Measurements and standard threshold classifications only — not financial advice.",
    }


@mcp.tool()
def compare_tickers(tickers: list[str], period: str = "3mo") -> dict:
    """Compare total returns of multiple tickers over a period.

    Args:
        tickers: List of symbols, e.g. ['AAPL', 'MSFT', 'VOO'].
        period: One of '1mo', '3mo', '6mo', '1y', '2y', '5y'.
    """
    results = []
    for t in tickers:
        try:
            close = _history(t, period)["Close"]
            ret = (float(close.iloc[-1]) / float(close.iloc[0]) - 1) * 100
            results.append({"ticker": t.upper(), "return_pct": round(ret, 2),
                            "start": round(float(close.iloc[0]), 2),
                            "end": round(float(close.iloc[-1]), 2)})
        except Exception as e:  # keep going if one symbol fails
            results.append({"ticker": t.upper(), "error": str(e)})
    ranked = sorted([r for r in results if "return_pct" in r],
                    key=lambda r: r["return_pct"], reverse=True)
    return {"period": period, "results": results,
            "best": ranked[0]["ticker"] if ranked else None,
            "worst": ranked[-1]["ticker"] if ranked else None}


@mcp.tool()
def weekly_digest(tickers: list[str]) -> dict:
    """One-call weekly portfolio report: 1-week and 1-month returns plus
    indicator readings for each holding. Ideal for a recurring
    'weekly portfolio signals' check-in.

    Args:
        tickers: Portfolio symbols, e.g. ['AAPL', 'NVDA', 'VOO'].
    """
    holdings = []
    for t in tickers:
        try:
            df = _history(t, "1y")
            close = df["Close"]
            price = float(close.iloc[-1])
            week_ago = float(close.iloc[-6]) if len(close) > 6 else float(close.iloc[0])
            month_ago = float(close.iloc[-22]) if len(close) > 22 else float(close.iloc[0])
            holdings.append({
                "ticker": t.upper(),
                "price": round(price, 2),
                "1w_return_pct": round((price / week_ago - 1) * 100, 2),
                "1mo_return_pct": round((price / month_ago - 1) * 100, 2),
                "rsi_14": _rsi(close),
                "macd_vs_signal": _macd(close)["vs_signal"],
            })
        except Exception as e:
            holdings.append({"ticker": t.upper(), "error": str(e)})

    ok = [h for h in holdings if "1w_return_pct" in h]
    return {
        "as_of": str(pd.Timestamp.today().date()),
        "holdings": holdings,
        "top_gainer_1w": max(ok, key=lambda h: h["1w_return_pct"])["ticker"] if ok else None,
        "top_loser_1w": min(ok, key=lambda h: h["1w_return_pct"])["ticker"] if ok else None,
        "rsi_outside_30_70": [h["ticker"] for h in ok if h["rsi_14"] >= 70 or h["rsi_14"] <= 30],
        "disclaimer": "Measurements and standard threshold classifications only — not financial advice.",
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Portfolio Signals MCP server")
    parser.add_argument("--http", action="store_true",
                        help="Serve over streamable HTTP instead of stdio")
    args = parser.parse_args()
    mcp.run(transport="streamable-http" if args.http else "stdio")


if __name__ == "__main__":
    main()
