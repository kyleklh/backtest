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
        """Called on each MarketEvent. Try to fill pending orders against THIS
        bar. Market orders fill at the open; limit orders fill only if the bar
        reached the limit, otherwise they rest for a future bar (GTC)."""
        if not self.pending_orders:
            return

        still_pending = []
        for order in self.pending_orders:
            bar = self.data_handler.get_latest_bar(order.symbol)
            fill_price = self._fill_price(order, bar)
            if fill_price is None:                 # limit not reached — order rests
                still_pending.append(order)
                continue
            commission = order.quantity * fill_price * self.commission_rate
            self.events.put(FillEvent(
                symbol=order.symbol,
                timestamp=bar.name,
                quantity=order.quantity,
                direction=order.direction,
                fill_price=fill_price,
                commission=commission,
            ))
        self.pending_orders = still_pending        # keep only unfilled limits

    def _fill_price(self, order, bar):
        """Fill price for this order on this bar, or None if a limit order's
        price wasn't reached. Market orders fill at the open with slippage;
        limit orders fill at their limit (or better on a gap) with no slippage."""
        open_ = bar["open"]
        if order.order_type == "LMT":
            limit = order.limit_price
            if order.direction == "BUY":
                if bar["low"] <= limit:            # price dipped to our limit
                    return min(open_, limit)       # gap below limit -> better open fill
                return None
            else:                                  # SELL
                if bar["high"] >= limit:           # price rose to our limit
                    return max(open_, limit)
                return None
        # market order
        if order.direction == "BUY":
            return open_ * (1 + self.slippage_rate)
        return open_ * (1 - self.slippage_rate)
