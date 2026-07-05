"""End-to-end tests — spawn the real MCP server over stdio and call every
tool through the protocol, exactly as Claude Code would.

Needs internet (Yahoo Finance). Run with: pytest tests/test_mcp_e2e.py -v
Skip in offline CI with: pytest -m "not network"
"""

import json
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark = [pytest.mark.network, pytest.mark.anyio]

# Spawn the server with the same interpreter running pytest, so tests work
# regardless of whether the venv's bin/ is on PATH.
SERVER = StdioServerParameters(
    command=sys.executable, args=["-m", "portfolio_signals_mcp.server"]
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def _call(tool: str, args: dict) -> dict:
    async with stdio_client(SERVER) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool(tool, args)
            assert not res.isError, res.content[0].text
            return json.loads(res.content[0].text)


async def test_tools_discoverable():
    async with stdio_client(SERVER) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            names = {t.name for t in (await s.list_tools()).tools}
    assert names == {"get_quote", "get_technical_signals", "compare_tickers", "weekly_digest"}


async def test_get_quote():
    out = await _call("get_quote", {"ticker": "AAPL"})
    assert out["ticker"] == "AAPL"
    assert out["price"] > 0
    assert out["52w_low"] <= out["price"] <= out["52w_high"] * 1.01


async def test_get_technical_signals():
    out = await _call("get_technical_signals", {"ticker": "MSFT"})
    assert 0 <= out["rsi_14"] <= 100
    assert out["rsi_zone"] in {"overbought", "oversold", "neutral"}
    assert out["macd"]["vs_signal"] in {
        "above_signal", "below_signal", "crossed_above_signal", "crossed_below_signal"
    }
    # Server must not editorialize — no narrative or directional-adjective fields
    assert "summary" not in out
    flat = json.dumps(out).lower()
    assert "bullish" not in flat and "bearish" not in flat


async def test_compare_tickers():
    out = await _call("compare_tickers", {"tickers": ["AAPL", "VOO"], "period": "1mo"})
    assert len(out["results"]) == 2
    assert out["best"] in {"AAPL", "VOO"}


async def test_weekly_digest():
    out = await _call("weekly_digest", {"tickers": ["AAPL", "NVDA", "VOO"]})
    assert len(out["holdings"]) == 3
    assert out["top_gainer_1w"] in {"AAPL", "NVDA", "VOO"}


async def test_bad_ticker_degrades_gracefully():
    out = await _call("weekly_digest", {"tickers": ["AAPL", "NOTREAL123"]})
    errs = [h for h in out["holdings"] if "error" in h]
    oks = [h for h in out["holdings"] if "1w_return_pct" in h]
    assert len(errs) == 1 and len(oks) == 1


async def test_invalid_ticker_returns_tool_error():
    async with stdio_client(SERVER) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool("get_quote", {"ticker": "NOTREAL123"})
    assert res.isError  # protocol-level error, not a crash
