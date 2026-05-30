"""Execution cost models: commission and slippage.

Kept separate from the broker so different cost assumptions can be swapped in
without touching fill logic.
"""

from engine.events import FillEvent

class SimulatedBroker:
    def __init__(self, data_handler, events, commission_rate=0.001, slippage_rate=0.0005):
        self.data_handler = data_handler
        self.events = events
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.pending_orders = []           # NEW: orders waiting for the next bar

    def execute_order(self, event):
        """Receive an OrderEvent — just queue it, fill happens next bar."""
        if event.type != "ORDER":
            return
        self.pending_orders.append(event)

    def process_pending_orders(self, market_event):
        """Called on each MarketEvent. Fill any pending orders at THIS bar's open."""
        if not self.pending_orders:
            return
        bar = self.data_handler.get_latest_bar()
        price = bar["open"]                # the new bar's OPEN, not close

        for order in self.pending_orders:
            if order.direction == "BUY":
                fill_price = price * (1 + self.slippage_rate)
            else:
                fill_price = price * (1 - self.slippage_rate)
            commission = order.quantity * fill_price * self.commission_rate
            self.events.put(FillEvent(
                symbol=order.symbol,
                timestamp=bar.name,
                quantity=order.quantity,
                direction=order.direction,
                fill_price=fill_price,
                commission=commission,
            ))
        self.pending_orders = []           # clear after filling
