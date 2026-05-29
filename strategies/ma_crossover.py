"""
MA Crossover Strategy

A simple moving average crossover strategy. Generates a buy signal when the short-term moving average crosses above the long-term moving average, and a sell
signal when the short-term moving average crosses below the long-term moving average.
"""

from collections import deque
from strategies.base_strategy import BaseStrategy

class MACrossoverStrategy(BaseStrategy):
    def __init__(self, short_window = 20, long_window = 50):
        super().__init__()
        self.short_window = short_window
        self.long_window = long_window
        self.prices = deque(maxlen=long_window)
        self.in_position = False
        self.prev_short_above = None


    def on_bar(self, bar):
        self.prices.append(bar['close'])

        # 1. not enough data to form long MA --> no signal
        if len(self.prices) < self.long_window:
            return None
        
        # 2.  compute the two moving averages
        prices = list(self.prices)
        short_ma = sum(prices[-self.short_window:]) / self.short_window
        long_ma = sum(prices) / self.long_window

        # 3. current relationship
        short_above = short_ma > long_ma

        # 4. detect crossover vs last bar, emit only on a flip
        signal = None
        if self.prev_short_above is not None:
            if short_above and not self.prev_short_above and not self.in_position:
                signal = "BUY"
                self.in_position = True
            elif not short_above and self.prev_short_above and self.in_position:
                signal = "SELL"
                self.in_position = False

        self.prev_short_above = short_above
        return signal


