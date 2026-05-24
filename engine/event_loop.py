"""The central event loop that drives a backtest.

Pulls bars from the data handler, then drains the event queue, routing each
event to the right component, until no events remain — then repeats for the
next bar.

Routing:
    MarketEvent -> Strategy.calculate_signals + Portfolio.update_market
    SignalEvent -> Portfolio.on_signal
    OrderEvent  -> Broker.execute_order
    FillEvent   -> Portfolio.on_fill
"""


class EventLoop:
    def __init__(self, data, strategy, portfolio, broker, event_queue):
        self.data = data
        self.strategy = strategy
        self.portfolio = portfolio
        # self.broker = broker
        # self.event_queue = event_queue

    def run(self):
        for _, bar in self.data.iterrows():
            signal = self.strategy.on_bar(bar)
            self.portfolio.update(bar, signal)

