# quantbot/utils.py
"""
Utility helpers for fetching market data and basic trading math.

Behavior:
 - If MODE == "ALPACA" and ALPACA keys exist in environment, attempt to fetch bars from Alpaca (more stable).
 - If Alpaca fetch fails (or MODE != ALPACA), fall back to yfinance with retries.
 - Functions always return a pandas DataFrame with columns ['Open','Close'] (may be empty).
 - Lightweight debug prints are emitted on failures to help trace issues.

Also provides:
 - Position sizing helpers (allocation % and risk % / stop-loss based)
 - Price quantization helper (useful for limit orders)
 - Basic P&L helpers
"""

import os
import time
from typing import Optional
import pandas as pd
from dotenv import load_dotenv
from decimal import Decimal, ROUND_HALF_UP   # <-- add this line


# Environment / config
MODE = os.getenv("MODE", "SIM").upper()
ALPACA_KEY = os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")


def _fetch_latest_ohlc_yf(
    ticker: str,
    period: str = "30d",
    interval: str = "1d",
    retries: int = 3,
    pause: float = 1.0,
) -> pd.DataFrame:
    """Fetch OHLC using yfinance with retries. Returns DataFrame or empty DF."""
    try:
        import yfinance as yf
    except Exception as e:
        print(f"[utils/_fetch_latest_ohlc_yf] yfinance import error: {e}")
        return pd.DataFrame(columns=["Open", "Close"])

    last_exc: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            df = yf.download(
                ticker, period=period, interval=interval, progress=False, auto_adjust=True
            )
            if df is None:
                last_exc = ValueError("yfinance returned None")
                raise last_exc
            # Normalise multiindex columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if "Open" in df.columns and "Close" in df.columns:
                df2 = df[["Open", "Close"]].dropna()
                if not df2.empty:
                    return df2
                last_exc = ValueError("Dataframe empty after dropna")
            else:
                last_exc = ValueError(f"Missing Open/Close. Columns: {list(df.columns)}")
        except Exception as e:
            last_exc = e
        time.sleep(pause)

    print(
        f"[utils/_fetch_latest_ohlc_yf] FAILED for {ticker} after {retries} retries. Last error: {repr(last_exc)}"
    )
    return pd.DataFrame(columns=["Open", "Close"])


def _fetch_latest_ohlc_alpaca(ticker: str, limit: int = 200) -> pd.DataFrame:
    """
    Fetch OHLC using Alpaca REST (barset). Returns DataFrame or empty DF.
    NOTE: this uses alpaca_trade_api and expects ALPACA_KEY/SECRET to be set.
    """
    try:
        from alpaca_trade_api import REST
    except Exception as e:
        print(f"[utils/_fetch_latest_ohlc_alpaca] alpaca_trade_api not installed or import failed: {e}")
        return pd.DataFrame(columns=["Open", "Close"])

    try:
        api = REST(ALPACA_KEY, ALPACA_SECRET, ALPACA_BASE_URL, api_version="v2")
        # Using get_barset for compatibility across client versions
        barset = api.get_barset(ticker, "day", limit=limit)
        # barset may be dict-like or BarSet object depending on version
        bars = barset.get(ticker) if isinstance(barset, dict) else barset[ticker]
        if not bars:
            return pd.DataFrame(columns=["Open", "Close"])
        rows = []
        for b in bars:
            o = getattr(b, "o", getattr(b, "open", None))
            c = getattr(b, "c", getattr(b, "close", None))
            t = getattr(b, "t", getattr(b, "time", None))
            rows.append({"t": t, "Open": float(o), "Close": float(c)})
        df = pd.DataFrame(rows).set_index("t")
        df.index = pd.to_datetime(df.index)
        return df[["Open", "Close"]]
    except Exception as e:
        print(f"[utils/_fetch_latest_ohlc_alpaca] error: {repr(e)}")
        return pd.DataFrame(columns=["Open", "Close"])


def fetch_latest_ohlc(ticker: str, period: str = "30d", interval: str = "1d") -> pd.DataFrame:
    """
    Unified fetch:
      - If MODE == 'ALPACA' and keys exist -> try Alpaca first (fast, stable).
      - If Alpaca fails or MODE != ALPACA, fall back to yfinance.
    Always returns a DataFrame with columns ['Open','Close'] (possibly empty).
    """
    ticker = ticker.strip().upper()
    # prefer alpaca when configured
    if MODE == "ALPACA" and ALPACA_KEY and ALPACA_SECRET:
        df = _fetch_latest_ohlc_alpaca(ticker, limit=200)
        if df is not None and not df.empty:
            return df
        # fallback to yfinance if alpaca gave nothing
        print(f"[utils/fetch_latest_ohlc] Alpaca returned no data for {ticker}, falling back to yfinance.")

    # default: use yfinance
    return _fetch_latest_ohlc_yf(ticker, period=period, interval=interval)


def get_latest_price(ticker: str) -> Optional[float]:
    """
    Return the latest available price (best-effort):
      - Try Alpaca latest trade/last_quote if MODE==ALPACA and keys present
      - Otherwise use yfinance .history with period='1d'
      - Returns float price or None if unavailable
    """
    ticker = ticker.strip().upper()

    # try alpaca first if available
    if MODE == "ALPACA" and ALPACA_KEY and ALPACA_SECRET:
        try:
            from alpaca_trade_api import REST

            api = REST(ALPACA_KEY, ALPACA_SECRET, ALPACA_BASE_URL, api_version="v2")
            # prefer get_latest_trade (newer wrapper)
            try:
                lt = api.get_latest_trade(ticker)
                price = getattr(lt, "price", getattr(lt, "p", None))
                if price is not None:
                    return float(price)
            except Exception:
                # try older method
                try:
                    last = api.get_last_trade(ticker)
                    price = getattr(last, "price", None)
                    if price is not None:
                        return float(price)
                except Exception:
                    pass
        except Exception:
            pass

    # fallback to yfinance
    try:
        import yfinance as yf

        df = yf.download(ticker, period="2d", interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        # normalize columns if MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if "Close" in df.columns:
            last_close = df["Close"].dropna().iloc[-1]
            return float(last_close)
    except Exception:
        return None

    return None


# ---------------------------
# Position sizing & risk helpers
# ---------------------------

def compute_position_size_equity_pct(equity: float, price: float, alloc_pct: float) -> int:
    """
    Compute position size based on allocation percentage of total equity.
    Example: equity=100000, alloc_pct=0.1, price=250 -> uses 10% of 100k = 10k / 250 = 40 shares.
    """
    try:
        equity = float(equity)
        price = float(price)
        alloc_pct = float(alloc_pct)
    except Exception:
        return 0

    if equity <= 0 or price <= 0 or alloc_pct <= 0:
        return 0
    alloc = equity * alloc_pct
    qty = int(alloc // price)
    return max(qty, 0)


def compute_position_size_risk_based(equity: float, entry_price: float, stop_price: float, risk_pct: float) -> int:
    """
    Compute position size based on risk per trade (% of equity).
    qty = (equity * risk_pct) / (entry_price - stop_price)
    Example: equity=100000, risk_pct=0.01, entry=250, stop=245 -> risk=1000 / 5 = 200 shares.
    """
    try:
        equity = float(equity)
        entry_price = float(entry_price)
        stop_price = float(stop_price)
        risk_pct = float(risk_pct)
    except Exception:
        return 0

    if equity <= 0 or entry_price <= 0 or risk_pct <= 0:
        return 0
    risk_amount = equity * risk_pct
    risk_per_share = abs(entry_price - stop_price)
    if risk_per_share <= 0:
        return 0
    qty = int(risk_amount // risk_per_share)
    return max(qty, 0)


def compute_sizing(equity: float, price: float, alloc_pct: float = 0.1, risk_pct: Optional[float] = None, stop_price: Optional[float] = None) -> int:
    """
    Unified function: choose between allocation-based or risk-based sizing.
    If stop_price and risk_pct provided, uses risk-based sizing.
    Otherwise, defaults to allocation-based sizing.
    """
    if stop_price is not None and risk_pct:
        return compute_position_size_risk_based(equity, price, stop_price, risk_pct)
    return compute_position_size_equity_pct(equity, price, alloc_pct)


# ---------------------------
# Price / P&L helpers
# ---------------------------

def quantize_price(price: float, decimals: int = 2) -> float:
    """
    Round price safely to nearest tick (e.g., 2 decimals for USD).
    Returns a float rounded to `decimals`.
    """
    try:
        d = Decimal(str(price))
        q = Decimal(1).scaleb(-decimals)
        return float(d.quantize(q, rounding=ROUND_HALF_UP))
    except Exception:
        try:
            return round(float(price), decimals)
        except Exception:
            return float(price)


def compute_unrealized_pnl(qty: int, avg_price: float, current_price: float) -> float:
    """
    Compute unrealized profit/loss for open position.
    """
    try:
        return float(qty) * (float(current_price) - float(avg_price))
    except Exception:
        return 0.0


def compute_realized_pnl(entry_price: float, exit_price: float, qty: int, fees: float = 0.0) -> float:
    """
    Compute realized P&L for a closed trade.
    """
    try:
        gross = (float(exit_price) - float(entry_price)) * int(qty)
        return gross - float(fees)
    except Exception:
        return 0.0


def percent_change(new: float, old: float) -> float:
    """
    Compute % change safely between two values.
    """
    try:
        if float(old) == 0:
            return 0.0
        return ((float(new) - float(old)) / float(old)) * 100.0
    except Exception:
        return 0.0

