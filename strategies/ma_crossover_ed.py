"""Moving-average crossover strategy (event-driven variant).

Reacts to MarketEvents: on each new bar it reads the trailing price window
from the DataHandler, computes a short and long moving average, and detects
when their relationship flips. A short-above-long crossover emits a BUY
SignalEvent; a short-below-long crossover emits a SELL. It only acts on the
moment of the cross, not the standing relationship, and never holds more than
one position at a time.

Unlike the Option A version, this strategy holds no price buffer of its own
and returns nothing — it asks the DataHandler for history (which can never
expose future bars) and pushes SignalEvents onto the shared queue.
"""

from strategies.base_strategy import BaseStrategy
from engine.events import SignalEvent

class MACrossoverStrategy(BaseStrategy):
    def __init__(self, data_handler, events, symbol="AAPL", short_window = 20, long_window = 50):
        super().__init__()
        self.data_handler = data_handler
        self.events = events
        self.symbol = symbol
        self.short_window = short_window
        self.long_window = long_window
        self.in_position = False
        self.prev_short_above = None

    def calculate_signals(self, event):
        if event.type != "MARKET":
            return

        bars = self.data_handler.get_latest_bars(self.long_window)
        if len(bars) < self.long_window:           # not enough history yet
            return

        closes = bars["close"]
        short_ma = closes[-self.short_window:].mean()    # last short_window closes
        long_ma  = closes.mean()           # all long_window closes
        short_above = short_ma > long_ma

        timestamp = bars.index[-1]
        if self.prev_short_above is not None:
            if short_above and not self.prev_short_above and not self.in_position:
                self.events.put(SignalEvent(self.symbol, timestamp, "BUY"))   # entering
                self.in_position = True
            elif not short_above and self.prev_short_above and self.in_position:
                self.events.put(SignalEvent(self.symbol, timestamp, "SELL"))   # exiting
                self.in_position = False

        self.prev_short_above = short_above