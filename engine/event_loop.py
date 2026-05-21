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
