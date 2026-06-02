"""Portfolio: accounting and risk hub.

Sits at two points in the event chain. On a SignalEvent it sizes the trade and
emits an OrderEvent — but touches no money yet, because the real fill price and
commission aren't known until the broker responds. On the resulting FillEvent
it applies the actual trade to cash and the position for that symbol. On every
MarketEvent it marks the whole book to market and records a point on the equity
curve.

Cash is a single shared pool; positions and average cost are tracked per
symbol. Sizing uses an equal split: each BUY targets initial_capital / N (N =
number of symbols), capped by available cash so it can never overdraw.

The split between on_signal (intention) and on_fill (reality) is deliberate:
costs and slippage live in the gap between the order and the fill, so the
portfolio simply trusts the fill price and commission the broker reports.
"""

from dataclasses import dataclass

from engine.events import OrderEvent


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
    def __init__(self, data_handler, events, symbols, initial_capital = 100000,
                 commission_rate = 0.001, slippage_rate = 0.0005):
        self.data_handler = data_handler
        self.events = events
        self.symbols = symbols
        self.num_symbols = len(symbols)
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

    def on_signal(self, event):
        """SignalEvent -> size the trade -> push an OrderEvent."""
        symbol = event.symbol
        price = self.data_handler.get_latest_bar_value(symbol, 'close')
        if event.direction == 'BUY':
            all_in_price = price * (1 + self.slippage_rate) * (1 + self.commission_rate)
            # equal split of CURRENT equity (compounding, like zipline/backtrader);
            # capped by cash on hand so it can never overdraw
            budget = min(self.current_equity() / self.num_symbols, self.cash)
            quantity = int(budget / all_in_price)   # whole shares, leftover stays as cash
        elif event.direction == 'SELL':
            quantity = self.position[symbol]         # sell entire position
        else:
            return

        if quantity > 0:
            self.events.put(OrderEvent(symbol, "MKT", quantity, event.direction))

    def on_fill(self, event):
        """FillEvent -> apply the actual trade to cash, position, and realized PnL."""
        s = event.symbol
        if event.direction == "BUY":
            new_cost = self.avg_cost[s] * self.position[s] + event.quantity * event.fill_price + event.commission
            self.position[s] += event.quantity
            self.avg_cost[s] = new_cost / self.position[s]
            self.cash -= event.quantity * event.fill_price + event.commission
        elif event.direction == "SELL":
            proceeds = event.quantity * event.fill_price - event.commission
            cost_basis = event.quantity * self.avg_cost[s]
            trade_pnl = proceeds - cost_basis
            self.realized_pnl += trade_pnl
            self.trades.append(Trade(
                symbol=s,
                shares=event.quantity,
                entry_price=self.avg_cost[s],   # avg cost still set; reset happens below
                exit_price=event.fill_price,
                pnl=trade_pnl,
                exit_date=event.timestamp,
            ))
            self.position[s] -= event.quantity
            self.cash += proceeds
            if abs(self.position[s]) < 1e-9:     # flat -> reset cost basis
                self.position[s] = 0
                self.avg_cost[s] = 0.0

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
