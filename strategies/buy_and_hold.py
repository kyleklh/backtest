"""Buy-and-hold benchmark strategy.

Emits a single BUY SignalEvent on the first bar and never trades again. Serves
as the baseline every active strategy is measured against.
"""

from strategies.base_strategy import BaseStrategy
from engine.events import SignalEvent

class BuyAndHoldStrategy(BaseStrategy):
    def __init__(self, data_handler, events, symbol="AAPL"):
        super().__init__()
        self.data_handler = data_handler
        self.events = events
        self.symbol = symbol
        self.in_position = False

    def calculate_signals(self, event):
        if event.type != "MARKET":
            return
        if not self.in_position:
            bar = self.data_handler.get_latest_bar()
            self.events.put(SignalEvent(self.symbol, bar.name, "BUY"))
            self.in_position = True
