"""Offline tests for tool behaviour: 52-week range, batch error reporting and
the tool schema. Market data is replaced with synthetic frames, so no network
is needed."""

import asyncio

import numpy as np
import pandas as pd
import pytest

from portfolio_signals_mcp import server
from portfolio_signals_mcp.server import (
    TickerNotFoundError,
    _range_52w,
    compare_tickers,
    get_quote,
    mcp,
    weekly_digest,
)


def _bars(n: int = 252, seed: int = 0) -> pd.DataFrame:
    """Synthetic daily bars where intraday highs and lows extend past the closes."""
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0.1, 1.0, n))
    return pd.DataFrame(
        {
            "Close": close,
            "High": close + rng.uniform(0.5, 2.0, n),
            "Low": close - rng.uniform(0.5, 2.0, n),
            "Volume": rng.integers(1_000, 10_000, n),
        },
        index=pd.date_range("2025-01-01", periods=n, freq="B"),
    )


@pytest.fixture
def fake_history(monkeypatch):
    """Serve synthetic bars; 'BAD' behaves like an unknown symbol and 'FLAKY'
    like a network failure."""

    def history(ticker: str, period: str = "1y") -> pd.DataFrame:
        if ticker.upper() == "BAD":
            raise TickerNotFoundError(f"No data found for ticker '{ticker}'. Check the symbol.")
        if ticker.upper() == "FLAKY":
            raise ConnectionError("connection reset")
        return _bars()

    monkeypatch.setattr(server, "_history", history)


def test_52w_range_uses_intraday_high_and_low():
    df = _bars()
    high, low = _range_52w(df)
    assert high == df["High"].max() and low == df["Low"].min()
    # The closes alone would understate the true range.
    assert high > df["Close"].max() and low < df["Close"].min()


def test_get_quote_reports_true_52w_range(fake_history):
    df = _bars()
    out = get_quote("aapl")
    assert out["ticker"] == "AAPL"
    assert out["52w_high"] == round(df["High"].max(), 2)
    assert out["52w_low"] == round(df["Low"].min(), 2)
    assert out["52w_low"] <= out["price"] <= out["52w_high"]
    expected = round((df["Close"].iloc[-1] / df["High"].max() - 1) * 100, 2)
    assert out["pct_off_52w_high"] == expected


def test_compare_tickers_reports_error_type(fake_history):
    out = compare_tickers(["AAPL", "BAD", "FLAKY"], "1mo")
    by_ticker = {r["ticker"]: r for r in out["results"]}
    assert "return_pct" in by_ticker["AAPL"]
    assert by_ticker["BAD"]["error_type"] == "TickerNotFoundError"
    assert by_ticker["FLAKY"]["error_type"] == "ConnectionError"
    assert out["best"] == out["worst"] == "AAPL"


def test_weekly_digest_reports_error_type(fake_history):
    out = weekly_digest(["AAPL", "BAD"])
    errs = [h for h in out["holdings"] if "error" in h]
    assert len(errs) == 1
    assert errs[0] == {
        "ticker": "BAD",
        "error": "No data found for ticker 'BAD'. Check the symbol.",
        "error_type": "TickerNotFoundError",
    }
    assert out["top_gainer_1w"] == "AAPL"


def test_period_values_are_in_the_tool_schema():
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    period = tools["compare_tickers"].inputSchema["properties"]["period"]
    assert period["enum"] == ["1mo", "3mo", "6mo", "1y", "2y", "5y"]
    assert period["default"] == "3mo"
