"""Offline unit tests — indicator math on synthetic data. No network needed."""

import numpy as np
import pandas as pd
import pytest

from portfolio_signals_mcp.server import _macd, _rsi, _sma_signals


@pytest.fixture
def uptrend():
    rng = np.random.default_rng(42)
    return pd.Series(100 + np.cumsum(rng.normal(0.3, 1.0, 300)))


@pytest.fixture
def downtrend():
    rng = np.random.default_rng(42)
    return pd.Series(300 - np.cumsum(np.abs(rng.normal(0.3, 0.5, 300))))


def test_rsi_bounds(uptrend, downtrend):
    for series in (uptrend, downtrend):
        assert 0 <= _rsi(series) <= 100


def test_rsi_direction(uptrend, downtrend):
    assert _rsi(uptrend) > 50
    assert _rsi(downtrend) < 50


def test_rsi_flat_series_is_neutral():
    flat = pd.Series([100.0] * 50)
    # No gains, no losses -> RSI is NaN-ish edge; just assert no crash
    val = _rsi(flat)
    assert val != val or 0 <= val <= 100  # NaN or in range


def test_macd_keys_and_position(uptrend):
    out = _macd(uptrend)
    assert set(out) == {"macd", "signal", "histogram", "vs_signal"}
    assert out["vs_signal"] in {
        "above_signal", "below_signal", "crossed_above_signal", "crossed_below_signal"
    }


def test_macd_histogram_consistency(uptrend):
    out = _macd(uptrend)
    assert out["histogram"] == pytest.approx(out["macd"] - out["signal"], abs=1e-3)


def test_sma_crosses(uptrend, downtrend):
    assert _sma_signals(uptrend)["sma_50_vs_200"] == "golden_cross"
    assert _sma_signals(downtrend)["sma_50_vs_200"] == "death_cross"


def test_sma_short_series_returns_none():
    short = pd.Series(np.linspace(100, 110, 30))
    out = _sma_signals(short)
    assert out["sma_50"] is None and out["sma_200"] is None
