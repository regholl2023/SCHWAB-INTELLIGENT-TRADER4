

import os
from datetime import datetime, timezone
import time
import traceback

import numpy as np
import pandas as pd

# -------------------------
# Config (load from config.py or .env)
# -------------------------
try:
    from quantbot.config import (
        TICKER, SHORT, LONG, ALLOC_PCT, SLIPPAGE_PCT,
        COMMISSION, POLL_INTERVAL_SECONDS, MODE, INITIAL_CAPITAL
    )
except Exception:
    # fallback defaults if config not present
    TICKER = os.getenv("TICKER", "AAPL")
    SHORT = int(os.getenv("SHORT", 50))
    LONG = int(os.getenv("LONG", 200))
    ALLOC_PCT = float(os.getenv("ALLOC_PCT", 0.10))
    SLIPPAGE_PCT = float(os.getenv("SLIPPAGE_PCT", 0.0005))
    COMMISSION = float(os.getenv("COMMISSION", 1.0))
    POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", 30))
    MODE = os.getenv("MODE", "SIM").upper()
    # IMPORTANT: define INITIAL_CAPITAL fallback so code never references undefined name
    INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", 100000.0))

# Broker wrapper (must exist at quantbot.broker.Broker)
from quantbot.broker import Broker

# try yfinance for price fetching
try:
    import yfinance as yf
    HAVE_YF = True
except Exception:
    HAVE_YF = False


class Runner:
    def __init__(self, ticker=None, short=SHORT, long=LONG, alloc_pct=ALLOC_PCT,
                 slippage_pct=SLIPPAGE_PCT, commission=COMMISSION):
        self.ticker = (ticker or TICKER).upper()
        self.short = int(short)
        self.long = int(long)
        self.alloc_pct = float(alloc_pct)
        self.slippage_pct = float(slippage_pct)
        self.commission = float(commission)
        self.broker = Broker()
        self.history = pd.DataFrame(columns=['Close'])
        # keep enough days: long + some buffer
        self._max_history = max(self.long * 2, 365)
        self.last_signal = "HOLD"
        self._last_price = np.nan

        # warm up history with a small fetch
        try:
            self._warmup_history()
        except Exception:
            # keep empty history; step() will try to fetch
            pass

    # ---------------------
    # Price fetching helpers
    # ---------------------
    def _warmup_history(self):
        """Fetch initial history (yfinance preferred)."""
        df = self._fetch_ohlc(days=max(self.long + 10, 60))
        if not df.empty and 'Close' in df.columns:
            self.history = df[['Close']].copy().tail(self._max_history)

    def _fetch_ohlc(self, days=60):
        """Return DataFrame indexed by date with Close column. Uses yfinance if available."""
        if HAVE_YF:
            try:
                df = yf.download(self.ticker, period=f"{days}d", interval="1d",
                                 progress=False, auto_adjust=True)
                if df is None or df.empty:
                    return pd.DataFrame()
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                df.index = pd.to_datetime(df.index)
                df.index.name = "Date"
                return df[['Close']].copy()
            except Exception:
                return pd.DataFrame()
        else:
            return pd.DataFrame()

    def _get_latest_price(self):
        """Return the most recent trade price (float) or np.nan if not available."""
        # try yfinance quick tick
        if HAVE_YF:
            try:
                ser = yf.Ticker(self.ticker).history(period="2d", interval="1d", auto_adjust=True)
                if ser is not None and not ser.empty and 'Close' in ser.columns:
                    val = ser['Close'].dropna().iloc[-1]
                    return float(val)
            except Exception:
                pass

        # fallback: try broker positions / account
        try:
            pos = self.broker.get_position(self.ticker)
            if pos and pos[0] > 0:
                return float(pos[1]) if pos[1] else np.nan
        except Exception:
            pass

        return np.nan

    # ---------------------
    # Indicators & signals
    # ---------------------
    def _compute_indicators(self):
        """Compute SMA and EMA on self.history and return latest sma_short, ema_long."""
        if self.history.empty or len(self.history) < min(self.short, self.long):
            return np.nan, np.nan
        closes = self.history['Close'].astype(float)
        sma_short = closes.rolling(self.short).mean().iloc[-1] if len(closes) >= self.short else np.nan
        ema_long = closes.ewm(span=self.long, adjust=False).mean().iloc[-1] if len(closes) >= 2 else np.nan
        return float(sma_short) if not pd.isna(sma_short) else np.nan, float(ema_long) if not pd.isna(ema_long) else np.nan

    def _decide_signal(self, sma, ema):
        """Return 'BUY' / 'SELL' / 'HOLD' based on crossover + previous signal stored in self.last_signal."""
        if pd.isna(sma) or pd.isna(ema):
            return "HOLD"

        prev_sma, prev_ema = np.nan, np.nan
        if len(self.history) >= max(self.short, self.long) + 1:
            closes = self.history['Close'].astype(float)
            prev_sma = closes[:-1].rolling(self.short).mean().iloc[-1] if len(closes[:-1]) >= self.short else np.nan
            prev_ema = closes[:-1].ewm(span=self.long, adjust=False).mean().iloc[-1] if len(closes[:-1]) >= 2 else np.nan

        if (not pd.isna(prev_sma) and not pd.isna(prev_ema)
                and prev_sma <= prev_ema and sma > ema):
            return "BUY"
        if (not pd.isna(prev_sma) and not pd.isna(prev_ema)
                and prev_sma >= prev_ema and sma < ema):
            return "SELL"

        if sma > ema:
            return "BUY"
        if sma < ema:
            return "SELL"
        return "HOLD"

    # ---------------------
    # Trading helpers
    # ---------------------
    def _position_size_by_alloc(self, price, alloc_pct=None):
        """Compute integer number of shares to buy using alloc_pct of equity at 'price'."""
        alloc_pct = self.alloc_pct if alloc_pct is None else float(alloc_pct)
        try:
            equity = float(self.broker.account_value({self.ticker: price} if not pd.isna(price) else {}))
        except Exception:
            equity = float(INITIAL_CAPITAL)

        budget = equity * alloc_pct
        if price is None or price == 0 or pd.isna(price):
            return 0
        effective_price = float(price) * (1 + self.slippage_pct)
        qty = int((budget - self.commission) // effective_price)
        return max(0, qty)

    def _execute_trade(self, side, price, qty):
        """Place an order via broker."""
        if qty <= 0:
            raise RuntimeError("Computed qty <= 0; skipping order")
        side_up = side.upper()
        try:
            # If Alpaca broker implementation accepts 'type' kwarg, it'll use market orders.
            return self.broker.place_order(self.ticker, side_up, price, qty, type="market")
        except TypeError:
            # In case SIM broker signature doesn't accept 'type'
            return self.broker.place_order(self.ticker, side_up, price, qty, fees=self.commission)
        except Exception:
            raise

    # ---------------------
    # Public API
    # ---------------------
    def step(self):
        """Run one step: fetch price, compute indicators, maybe trade. Return status dict."""
        ts = datetime.now(timezone.utc).isoformat()
        price = np.nan

        try:
            latest = self._get_latest_price()
            price = float(latest) if not pd.isna(latest) else np.nan
        except Exception:
            price = np.nan

        try:
            if not pd.isna(price):
                row = pd.DataFrame({'Close': [price]}, index=[pd.Timestamp.now()])
                self.history = pd.concat([self.history, row]).drop_duplicates(keep='last').sort_index()
                if len(self.history) > self._max_history:
                    self.history = self.history.tail(self._max_history)
            else:
                fetched = self._fetch_ohlc(days=max(self.long + 5, 60))
                if not fetched.empty:
                    self.history = pd.concat([self.history, fetched[['Close']]]).sort_index().drop_duplicates(keep='last')
                    if len(self.history) > self._max_history:
                        self.history = self.history.tail(self._max_history)
                if not self.history.empty:
                    price = float(self.history['Close'].dropna().iloc[-1])
        except Exception:
            traceback.print_exc()

        self._last_price = price

        sma, ema = self._compute_indicators()
        signal = self._decide_signal(sma, ema)

        info = {'ts': ts, 'signal': signal, 'price': price, 'equity': None}
        try:
            if signal != self.last_signal and signal in ("BUY", "SELL"):
                qty = self._position_size_by_alloc(price)
                if qty > 0:
                    try:
                        order = self._execute_trade(signal, price, qty)
                        print(f"[Runner] Executed {signal} {qty} {self.ticker} @ {price:.2f}")
                    except Exception as e:
                        print(f"[Runner] Order failed: {e}")
                else:
                    print("[Runner] Qty computed as 0, skipping order.")
                self.last_signal = signal
            else:
                if self.last_signal == "HOLD" and signal != "HOLD":
                    self.last_signal = signal
        except Exception as e:
            print("[Runner] Exception while attempting trade:", e)
            traceback.print_exc()

        try:
            equity = float(self.broker.account_value({self.ticker: price} if not pd.isna(price) else {}))
        except Exception:
            try:
                equity = float(getattr(self.broker._impl, 'cash', INITIAL_CAPITAL))
            except Exception:
                equity = float(INITIAL_CAPITAL)

        info['equity'] = equity
        info['price'] = price

        return info

    def close(self):
        try:
            self.broker.close()
        except Exception:
            pass


# convenience test when run as script
if __name__ == "__main__":
    r = Runner()
    print("Runner initialized for", r.ticker, "- MODE:", MODE)
    st = r.step()
    print("Step result:", st)

