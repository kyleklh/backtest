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

import queue

class EventLoop:
    def __init__(self, data, strategy, portfolio, broker, events):
        self.data_handler = data
        self.strategy = strategy
        self.portfolio = portfolio
        self.broker = broker
        self.events = events

    def run(self):
        while self.data_handler.continue_backtest:
            # OUTER: advance time - pushes one MarketEvent
            self.data_handler.update_bars()

            # INNER: drain every event this bar triggered
            while True:
                try:
                    event = self.events.get(False) # non-blocking get
                except queue.Empty:
                    break
                else:
                    self._route(event)
            
            if self.data_handler.continue_backtest:
                self.portfolio.update_market(None)



    def _route(self, event):
        """Route an event to the right component."""
        if event.type == 'MARKET':
            self.broker.process_pending_orders(event)   # NEW: fill any pending orders first
            self.strategy.calculate_signals(event)
        elif event.type == 'SIGNAL':
            self.portfolio.on_signal(event)
        elif event.type == 'ORDER':
            self.broker.execute_order(event)
        elif event.type == 'FILL':
            self.portfolio.on_fill(event)

