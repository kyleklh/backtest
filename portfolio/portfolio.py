"""Portfolio: accounting and risk hub.

Sits at two points in the event chain. On a SignalEvent it sizes the trade and
emits an OrderEvent — but touches no money yet, because the real fill price and
commission aren't known until the broker responds. On the resulting FillEvent
it applies the actual trade to cash and the position for that symbol. On every
MarketEvent it marks the whole book to market and records a point on the equity
curve.

Cash is a single shared pool; positions and average cost are tracked per
symbol and may be long (positive) or short (negative). Signals express a target
stance ('LONG', 'SHORT', 'EXIT'); a PositionSizer decides how many shares a full
position is; the portfolio emits the delta order(s) to move from the current
position to the target. A reversal goes through flat as two orders, so every
fill is cleanly either opening (re-average) or closing (realize PnL).

The split between on_signal (intention) and on_fill (reality) is deliberate:
costs and slippage live in the gap between the order and the fill, so the
portfolio simply trusts the fill price and commission the broker reports.
"""

from dataclasses import dataclass

from engine.events import OrderEvent, CancelEvent


@dataclass
class Trade:
    """One closed round-trip: shares of `symbol` bought at `entry_price` (the
    average cost when sold) and sold at `exit_price`, realizing `pnl`."""
    symbol: str
    shares: float
    entry_price: float
    exit_price: float
    pnl: float
    exit_date: object


class Portfolio:
    def __init__(self, data_handler, events, symbols, sizer=None, initial_capital = 100000,
                 commission_rate = 0.001, slippage_rate = 0.0005):
        self.data_handler = data_handler
        self.events = events
        self.symbols = symbols
        self.num_symbols = len(symbols)
        self.sizer = sizer           # PositionSizer; required for on_signal, not on_fill
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.position = {s: 0 for s in symbols}    # shares held per symbol
        self.avg_cost = {s: 0.0 for s in symbols}  # avg price paid per share, per symbol
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.equity_curve = []
        self.realized_pnl = 0.0      # cumulative profit/loss from closed trades
        self.trades = []             # list of Trade records, one per closing sell
        self.bars_total = 0          # bars marked
        self.bars_invested = 0       # bars where at least one position was held
        self._next_id = 0            # monotonic order-id counter
        self.open_orders = {s: set() for s in symbols}   # working order ids per symbol

    def on_signal(self, event):
        """SignalEvent -> translate the target stance into a target position,
        then emit the delta order(s) to reach it."""
        symbol = event.symbol
        stance = event.direction                 # 'LONG' | 'SHORT' | 'EXIT'
        if stance == "EXIT":
            target = 0
        elif stance in ("LONG", "SHORT"):
            price = self.data_handler.get_latest_bar_value(symbol, 'close')
            full = self.sizer.size(symbol, price, self)
            target = full if stance == "LONG" else -full
        else:
            return
        # supersede any still-working orders for this symbol before issuing new ones
        for oid in list(self.open_orders[symbol]):
            self.events.put(CancelEvent(oid))
        self._move_to_target(symbol, target)

    def on_status(self, event):
        """OrderStatusEvent -> drop closed orders from the working set."""
        if event.status in ("FILLED", "CANCELLED", "REJECTED"):
            self.open_orders[event.symbol].discard(event.order_id)

    def _move_to_target(self, symbol, target):
        """Emit order(s) to move from the current position to `target`. A sign
        reversal (long<->short) is split into close-to-flat then open, so each
        resulting fill is purely opening or purely closing."""
        current = self.position[symbol]
        if target == current:
            return
        if current != 0 and target != 0 and (current > 0) != (target > 0):
            self._emit_order(symbol, -current)          # close to flat
            self._emit_order(symbol, target)            # open the new side
        else:
            self._emit_order(symbol, target - current)  # single delta

    def _emit_order(self, symbol, delta, order_type="MKT", limit_price=None, tif="GTC"):
        """Queue an order for a signed share delta (+buy / -sell), tagged with a
        fresh id and recorded as a working order so it can be cancelled later."""
        if delta == 0:
            return
        self._next_id += 1
        self.open_orders[symbol].add(self._next_id)
        direction = "BUY" if delta > 0 else "SELL"
        self.events.put(OrderEvent(symbol, order_type, abs(delta), direction,
                                   limit_price=limit_price, order_id=self._next_id, tif=tif))

    def on_fill(self, event):
        """FillEvent -> apply the trade to cash, position, and realized PnL.

        Handles long and short symmetrically. A fill either OPENS/adds (same
        direction as the position, or from flat) — re-averaging the entry basis
        — or CLOSES (opposite direction) — realizing PnL. Reversals were already
        split into two fills upstream, so a fill never crosses through zero."""
        s = event.symbol
        qty = event.quantity
        price = event.fill_price
        comm = event.commission
        pos = self.position[s]
        signed = qty if event.direction == "BUY" else -qty
        new_pos = pos + signed

        opening = (pos == 0) or ((pos > 0) == (signed > 0))
        if opening:
            # fold commission into the entry basis: a long pays more per share,
            # a short receives less per share
            if signed > 0:
                basis = abs(pos) * self.avg_cost[s] + qty * price + comm
            else:
                basis = abs(pos) * self.avg_cost[s] + qty * price - comm
            self.avg_cost[s] = basis / abs(new_pos)
        else:
            # closing: long profits when price rises, short when price falls;
            # the closing commission reduces the realized PnL either way
            if pos > 0:
                trade_pnl = qty * (price - self.avg_cost[s]) - comm
            else:
                trade_pnl = qty * (self.avg_cost[s] - price) - comm
            self.realized_pnl += trade_pnl
            self.trades.append(Trade(
                symbol=s,
                shares=qty,
                entry_price=self.avg_cost[s],
                exit_price=price,
                pnl=trade_pnl,
                exit_date=event.timestamp,
            ))
            if abs(new_pos) < 1e-9:              # flat -> reset cost basis
                new_pos = 0
                self.avg_cost[s] = 0.0

        self.position[s] = new_pos
        self.cash -= signed * price + comm

    def current_equity(self):
        """Total mark-to-market value: cash + every holding at its latest close."""
        equity = self.cash
        for s in self.symbols:
            equity += self.position[s] * self.data_handler.get_latest_bar_value(s, 'close')
        return equity

    def update_market(self, event):
        """MarketEvent -> mark the whole book to market and record equity."""
        date = self.data_handler.get_latest_bar(self.symbols[0]).name
        self.equity_curve.append((date, self.current_equity()))
        self.bars_total += 1
        if any(self.position[s] != 0 for s in self.symbols):
            self.bars_invested += 1

    def total_return(self):
        if not self.equity_curve:
            return 0.0
        return self.equity_curve[-1][1] / self.initial_capital - 1

    def num_trades(self):
        return len(self.trades)

    def win_rate(self):
        if not self.trades:
            return None
        return sum(1 for t in self.trades if t.pnl > 0) / len(self.trades)

    def time_in_market(self):
        """Fraction of bars during which at least one position was held."""
        if self.bars_total == 0:
            return 0.0
        return self.bars_invested / self.bars_total

    def unrealized_pnl(self):
        total = 0.0
        for s in self.symbols:
            price = self.data_handler.get_latest_bar_value(s, 'close')
            total += self.position[s] * (price - self.avg_cost[s])
        return total
