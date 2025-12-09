import os
from typing import Any, Dict, Optional

import httpx
from fastmcp import FastMCP

# This is the FastMCP server object FastMCP Cloud will expose
mcp = FastMCP(name="CoinGlass Proxy")

# --- Basic config -----------------------------------------------------------

BASE_URL = "https://open-api-v4.coinglass.com"
API_KEY_ENV = "COINGLASS_API_KEY"

# On the Hobbyist plan, short intervals like 1m, 5m, 15m, 30m, 1h are NOT allowed
# whenever an endpoint uses an "interval" parameter.
HOBBYIST_DISALLOWED_INTERVALS = {"1m", "3m", "5m", "15m", "30m", "1h"}


def _get_api_key() -> str:
    """Read the API key from the environment (FastMCP Variables & Secrets)."""
    key = os.getenv(API_KEY_ENV)
    if not key:
        raise RuntimeError(
            f"{API_KEY_ENV} is not set. "
            "Add it as a secret environment variable in FastMCP Cloud."
        )
    return key


def _validate_interval(interval: Optional[str]) -> None:
    """Enforce Hobbyist plan rules for any endpoint that has an 'interval'."""
    if not interval:
        return
    if interval in HOBBYIST_DISALLOWED_INTERVALS:
        raise ValueError(
            "This CoinGlass account is on the Hobbyist plan, so 'interval' must be "
            ">= 4h. Values like 1m, 5m, 15m, 30m, 1h are not allowed."
        )


async def _coinglass_get(
    path: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not path.startswith("/"):
        path = "/" + path

    url = BASE_URL + path
    headers = {
        "Accept": "application/json",
        "CG-API-KEY": _get_api_key(),   # ← changed here
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers, params=params)

    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"HTTP error from CoinGlass: {e.response.status_code} {e.response.text}"
        ) from e

    data = resp.json()

    if isinstance(data, dict) and "code" in data and data.get("code") not in (0, "0"):
        raise RuntimeError(
            f"CoinGlass API error: code={data.get('code')} msg={data.get('msg')}"
        )

    return data


# ---------------------------------------------------------------------------
# 1) Generic tool: can call ANY CoinGlass GET endpoint
# ---------------------------------------------------------------------------

@mcp.tool()
async def coinglass_raw_get(
    path: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Low-level access to CoinGlass GET endpoints.

    Args:
        path:
            The endpoint path starting with "/api/...".
            Examples:
              - "/api/index/fear-greed-history"
              - "/api/etf/bitcoin/flow-history"
              - "/api/futures/open-interest/history"

        params:
            Optional query parameters as a JSON object
            (e.g. {"symbol": "BTC", "interval": "4h"}).

    Notes:
      - On the Hobbyist plan, if you pass an "interval" parameter it must be
        >= 4h. This function blocks 1m/5m/15m/30m/1h and similar disallowed
        values.
    """
    params = params or {}
    interval = params.get("interval")
    if isinstance(interval, str):
        _validate_interval(interval)

    return await _coinglass_get(path, params=params)


# ---------------------------------------------------------------------------
# 2) Convenience tools (the ones you already saw in FastMCP)
#    These just call specific popular endpoints.
# ---------------------------------------------------------------------------

@mcp.tool()
async def futures_open_interest_exchange_list(symbol: str = "BTCUSDT") -> Dict[str, Any]:
    """
    Get futures open interest across exchanges for a single symbol.

    This wraps the CoinGlass endpoint:
      /api/futures/open-interest/exchange-list

    Args:
        symbol: Trading symbol, e.g. "BTCUSDT".
    """
    params = {"symbol": symbol}
    return await _coinglass_get("/api/futures/open-interest/exchange-list", params)


@mcp.tool()
async def funding_rate_exchange_list(symbol: str = "BTCUSDT") -> Dict[str, Any]:
    """
    Get accumulated funding rate by exchange for a single symbol.

    This wraps (Hobbyist-safe) CoinGlass funding-rate exchange list endpoint.
    """
    params = {"symbol": symbol}
    # If you prefer the accumulated endpoint, you can change the path below:
    # "/api/futures/funding-rate/accumulated-exchange-list"
    return await _coinglass_get(
        "/api/futures/funding-rate/accumulated-exchange-list", params
    )


@mcp.tool()
async def btc_etf_flows_history(interval: str = "1d") -> Dict[str, Any]:
    """
    Get Bitcoin ETF flow history (all BTC ETFs combined).

    This wraps:
      /api/etf/bitcoin/flow-history

    Args:
        interval:
            Time interval for the data. For Hobbyist, use safe values like
            "1d", "3d", "1w". (No 1m/5m/15m/30m/1h.)
    """
    _validate_interval(interval)
    params = {"interval": interval}
    return await _coinglass_get("/api/etf/bitcoin/flow-history", params)
