import os
from typing import Any, Dict, Optional

import httpx
from fastmcp import FastMCP

# Name that will show up in ChatGPT
mcp = FastMCP(name="CoinGlass Proxy")


BASE_URL = "https://open-api-v4.coinglass.com"
API_KEY_ENV = "COINGLASS_API_KEY"


def _get_api_key() -> str:
    """Read API key from environment; fail clearly if missing."""
    key = os.getenv(API_KEY_ENV)
    if not key:
        raise RuntimeError(
            "COINGLASS_API_KEY is not set. "
            "Add it as an environment variable in FastMCP Cloud."
        )
    return key


async def _coinglass_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Helper to call CoinGlass REST API and return JSON.
    """
    headers = {"CG-API-KEY": _get_api_key()}
    url = BASE_URL + path

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()

    # CoinGlass uses "code" == "0" for success
    if isinstance(data, dict) and data.get("code") not in (None, 0, "0"):
        raise RuntimeError(f"CoinGlass error {data.get('code')}: {data.get('msg')}")

    return data


@mcp.tool(annotations={"readOnlyHint": True})
async def futures_open_interest_exchange_list(symbol: str = "BTC") -> Dict[str, Any]:
    """
    Get futures open interest across exchanges for a coin.

    Args:
        symbol: Token symbol, e.g. "BTC", "ETH", "SOL".

    Returns:
        Raw JSON from CoinGlass /api/futures/open-interest/exchange-list.
    """
    return await _coinglass_get(
        "/api/futures/open-interest/exchange-list",
        params={"symbol": symbol.upper()},
    )


@mcp.tool(annotations={"readOnlyHint": True})
async def funding_rate_exchange_list(symbol: str = "BTC") -> Dict[str, Any]:
    """
    Get current funding rates across futures exchanges for a coin.

    Args:
        symbol: Token symbol, e.g. "BTC", "ETH", "SOL".

    Returns:
        Raw JSON from CoinGlass /api/futures/funding-rate/exchange-list.
    """
    return await _coinglass_get(
        "/api/futures/funding-rate/exchange-list",
        params={"symbol": symbol.upper()},
    )


@mcp.tool(annotations={"readOnlyHint": True})
async def btc_etf_flows_history(limit: int = 30) -> Dict[str, Any]:
    """
    Get recent Bitcoin ETF flows history.

    Args:
        limit: How many days of history to fetch (CoinGlass max depends on your plan).

    Returns:
        Raw JSON from CoinGlass /api/etf/btc/flows/history.
    """
    return await _coinglass_get(
        "/api/etf/btc/flows/history",
        params={"limit": limit},
    )


if __name__ == "__main__":
    # For local dev; FastMCP Cloud overrides this when running in HTTP mode.
    mcp.run()
