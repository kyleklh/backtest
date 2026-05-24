"""Portfolio: the risk and accounting hub.

Translates SignalEvents into sized OrderEvents, applies FillEvents to cash and
positions, and reports total equity for the equity curve.
"""

class Portfolio:
    def __init__(self, initial_cap = 100000):
        self.initial_capital = initial_cap
        self.cash = initial_cap
        self.position = 0
        self.equity_curve = []

    def total_return(self):
        if not self.equity_curve:
            return 0.0
        return self.equity_curve[-1][1] / self.initial_capital - 1

    def update(self, bar, signal):
        if signal == "BUY":
            shares= self.cash / bar['close']
            self.position += shares
            self.cash -= shares * bar['close']

        elif signal == "SELL":
            self.cash += self.position * bar['close']
            self.position = 0

        equity = self.cash + self.position * bar['close']

        self.equity_curve.append((bar.name, equity))