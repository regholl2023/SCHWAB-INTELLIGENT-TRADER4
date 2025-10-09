# quantbot/strategy.py
import pandas as pd

class SMAEMAStrategy:
    def __init__(self, short=50, long=200, alloc_pct=0.1):
        self.short = short
        self.long = long
        self.alloc_pct = alloc_pct
        self.history = pd.DataFrame()

    def update_history(self, ohlc_df):
        # ohlc_df is a DataFrame with Date index and 'Open','Close' columns appended each poll
        self.history = ohlc_df.copy()
        # compute indicators
        self.history[f"SMA_{self.short}"] = self.history['Close'].rolling(self.short, min_periods=1).mean()
        self.history[f"SMA_{self.long}"] = self.history['Close'].rolling(self.long, min_periods=1).mean()
        self.history[f"EMA_{self.short}"] = self.history['Close'].ewm(span=self.short, adjust=False).mean()
        self.history[f"EMA_{self.long}"] = self.history['Close'].ewm(span=self.long, adjust=False).mean()

    def latest_signal(self):
        # returns 'BUY', 'SELL', or 'HOLD' based on SMA crossover on latest row
        if self.history.empty:
            return 'HOLD', None
        last = self.history.iloc[-1]
        sma_short = last[f"SMA_{self.short}"]
        sma_long = last[f"SMA_{self.long}"]
        prev = self.history.iloc[-2] if len(self.history) > 1 else None

        # simple logic: crossover detection
        if prev is not None:
            prev_short = prev[f"SMA_{self.short}"]
            prev_long = prev[f"SMA_{self.long}"]
            # buy if short crossed above long
            if prev_short <= prev_long and sma_short > sma_long:
                return 'BUY', self.alloc_pct
            # sell if short crossed below long
            if prev_short >= prev_long and sma_short < sma_long:
                return 'SELL', None
        return 'HOLD', None

