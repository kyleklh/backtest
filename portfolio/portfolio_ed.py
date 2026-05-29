"""Portfolio: accounting and risk hub (event-driven variant).

Sits at two points in the event chain. On a SignalEvent it sizes the trade and
emits an OrderEvent — but touches no money yet, because the real fill price and
commission aren't known until the broker responds. On the resulting FillEvent
it applies the actual trade to cash and position. On every MarketEvent it marks
the book to market and records a point on the equity curve.

The split between on_signal (intention) and on_fill (reality) is deliberate:
costs and slippage live in the gap between the order and the fill, so the
portfolio simply trusts the fill price and commission the broker reports.
"""

from engine.events import OrderEvent

class Portfolio:
    def __init__(self, data_handler, events, initial_capital = 100000):
        self.data_handler = data_handler
        self.events = events
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.position = 0
        self.equity_curve = []

    def on_signal(self, event):
        """SignalEvent -> size the trade -> push an OrderEvent."""
        price = self.data_handler.get_latest_bar_value('close')
        if event.direction == 'BUY':
            quantity = self.cash / price         # all cash / price
        elif event.direction == 'SELL':
            quantity = self.position              # sell entire position
        else: 
            return
        
        if quantity > 0:
            self.events.put(OrderEvent(event.symbol, "MKT", quantity, event.direction))

    def on_fill(self, event):
        """FillEvent -> apply the actual trade to cash and position."""
        if event.direction == "BUY":
            self.position += event.quantity
            self.cash -= event.quantity * event.fill_price + event.commission
        elif event.direction == "SELL":
            self.position -= event.quantity
            self.cash += event.quantity * event.fill_price - event.commission

    def update_market(self, event):
        """MarketEvent -> mark-to-market and record equity."""
        bar = self.data_handler.get_latest_bar()
        price = bar["close"]
        equity = self.cash + self.position * price
        self.equity_curve.append((bar.name, equity))

    def total_return(self):
        if not self.equity_curve:
            return 0.0
        return self.equity_curve[-1][1] / self.initial_capital - 1
