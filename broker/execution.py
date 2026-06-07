"""Execution cost models: commission and slippage.

Kept separate from the broker so different cost assumptions can be swapped in
without touching fill logic.
"""

from engine.events import FillEvent, OrderStatusEvent

class SimulatedBroker:
    def __init__(self, data_handler, events, commission_rate=0.001, slippage_rate=0.0005,
                 max_participation=1.0):
        self.data_handler = data_handler
        self.events = events
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.max_participation = max_participation   # cap on share of bar volume
        self.pending_orders = []           # orders waiting to (continue to) fill

    def execute_order(self, event):
        """Receive an OrderEvent — just queue it, fill happens next bar."""
        if event.type != "ORDER":
            return
        self.pending_orders.append(event)

    def process_pending_orders(self, market_event):
        """Called on each MarketEvent. Try to (continue to) fill this symbol's
        orders against THIS bar. A fill takes at most a capped share of the
        bar's volume, so a large order fills partially over several bars. The
        unfilled remainder is kept or cancelled per time-in-force."""
        if not self.pending_orders:
            return

        symbol = market_event.symbol
        still_pending = []
        for order in self.pending_orders:
            if order.symbol != symbol:
                still_pending.append(order)        # not this symbol's bar — leave it
                continue

            bar = self.data_handler.get_latest_bar(order.symbol)
            fill_price = self._fill_price(order, bar)
            remaining = order.quantity - order.filled_qty

            if fill_price is None:                 # limit not reached — no fill this bar
                if self._rests(order, bar):
                    still_pending.append(order)
                else:
                    self._cancel(order)            # DAY / IOC / FOK / expired GTD
                continue

            capacity = int(self.max_participation * bar["volume"])
            if order.tif == "FOK" and capacity < remaining:
                self._cancel(order)                # all-or-nothing, can't do all -> kill
                continue

            fill_qty = min(remaining, capacity)
            if fill_qty > 0:
                self._emit_fill(order, bar, fill_price, fill_qty)
                order.filled_qty += fill_qty
                remaining -= fill_qty

            if remaining <= 0:
                self.events.put(OrderStatusEvent(order.order_id, order.symbol, "FILLED"))
            elif self._rests(order, bar):
                still_pending.append(order)        # partially filled -> rest for more
            else:
                self._cancel(order)                # IOC / DAY remainder -> cancel
        self.pending_orders = still_pending

    def _rests(self, order, bar):
        """Whether an order with an unfilled remainder stays on the book."""
        if order.tif == "GTC":
            return True
        if order.tif == "GTD":
            return bar.name <= order.expire_date
        return False                               # DAY, IOC, FOK

    def _cancel(self, order):
        self.events.put(OrderStatusEvent(order.order_id, order.symbol, "CANCELLED"))

    def _emit_fill(self, order, bar, fill_price, qty):
        commission = qty * fill_price * self.commission_rate
        self.events.put(FillEvent(
            symbol=order.symbol,
            timestamp=bar.name,
            quantity=qty,
            direction=order.direction,
            fill_price=fill_price,
            commission=commission,
        ))

    def cancel(self, order_id):
        """Remove a working order from the book and report it cancelled."""
        for order in self.pending_orders:
            if order.order_id == order_id:
                self.pending_orders.remove(order)
                self.events.put(OrderStatusEvent(order_id, order.symbol, "CANCELLED"))
                return

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
