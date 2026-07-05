# Portfolio Signals MCP

[![PyPI](https://img.shields.io/pypi/v/portfolio-signals-mcp)](https://pypi.org/project/portfolio-signals-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/portfolio-signals-mcp)](https://pypi.org/project/portfolio-signals-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An MCP server that gives any AI coding agent (Claude Code, Cursor, Claude Desktop, etc.) real-time stock quotes and **computed** technical-analysis signals — RSI, MACD crossovers, golden/death crosses, and whole-portfolio weekly digests. Indicators are calculated in code, not by the LLM, so the numbers are right.

Data source: Yahoo Finance via [yfinance](https://github.com/ranaroussi/yfinance) — free, no API key required.

mcp-name: io.github.KhizarShabir1/portfolio-signals

## Tools

| Tool | What it does |
|---|---|
| `get_quote(ticker)` | Price, day change, volume, 52-week range |
| `get_technical_signals(ticker)` | RSI(14) with overbought/oversold zone, MACD(12,26,9) vs signal line, SMA 50/200 golden/death cross |
| `compare_tickers(tickers, period)` | Ranked total returns over 1mo–5y |
| `weekly_digest(tickers)` | Whole-portfolio report: 1w/1mo returns, RSI, MACD position, tickers outside RSI 30–70 |

**Design principle:** tools return measurements and standard threshold classifications (RSI 70/30 zones, golden/death cross, MACD vs signal line) — never directional opinions or narrative summaries. Interpretation is the agent's job; determinism is the server's.

## Quick start

No install needed if you have [uv](https://docs.astral.sh/uv/):

```bash
uvx portfolio-signals-mcp
```

### Claude Code

```bash
claude mcp add portfolio-signals -- uvx portfolio-signals-mcp
```

Then ask Claude things like:

- *"What's the RSI and MACD on NVDA right now?"*
- *"Compare AAPL, MSFT and VOO over 6 months."*
- *"Give me a weekly digest for my portfolio: AAPL, NVDA, VOO, TSLA."*

### Cursor

Settings → Tools & MCP → Add a Custom MCP Server:

```json
{
  "mcpServers": {
    "portfolio-signals": {
      "command": "uvx",
      "args": ["portfolio-signals-mcp"]
    }
  }
}
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "portfolio-signals": {
      "command": "uvx",
      "args": ["portfolio-signals-mcp"]
    }
  }
}
```

## From source

```bash
git clone https://github.com/KhizarShabir1/portfolio-signals-mcp
cd portfolio-signals-mcp
pip install -e .
portfolio-signals-mcp           # stdio
portfolio-signals-mcp --http    # streamable HTTP on :8000 (PORT env to change)
```

## Disclaimer

Informational only — not financial advice. Market data comes from Yahoo Finance and is subject to Yahoo's terms of use.

## License

MIT © [Khizar Shabir](https://github.com/KhizarShabir1)
