"""Event type definitions for the event-driven backtester.

Every interaction in the engine is expressed as an Event placed onto a queue
and consumed by the central event loop.

Define here:
- EventType / Direction / OrderType enums
- MarketEvent  -> new bar of data is available
- SignalEvent  -> a strategy's directional view on a symbol
- OrderEvent   -> instruction sent to the broker
- FillEvent    -> result of an executed order
"""

class Event:
    """base class (loop treat everything uniformly as an Event)"""
    pass

class MarketEvent(Event):
    """A new bar has arrived. Carries no data - readers pull the current
    bar from the DataHandler"""
    def __init__(self):
        self.type = 'MARKET'

class SignalEvent(Event):
    """Strategy's decision. Says WHAT and WHICH WAY — not how many shares."""
    def __init__(self, symbol, timestamp, direction):
        self.type = 'SIGNAL'
        self.symbol = symbol
        self.timestamp = timestamp
        self.direction = direction  # 'LONG' or 'EXIT'

class OrderEvent(Event):
    """Portfolio's sized order, ready for the broker."""
    def __init__(self, symbol, order_type, quantity, direction):
        self.type = 'ORDER'
        self.symbol = symbol
        self.order_type = order_type  # "MKT" for now (market order)
        self.quantity = quantity      # number of share
        self.direction = direction    # 'BUY' or 'SELL'


class FillEvent(Event):
    """Broker's confirmation: what actually filled, and what it cost."""
    def __init__(self, symbol, timestamp, quantity, direction, fill_price, commission):
        self.type = 'FILL'
        self.symbol = symbol
        self.timestamp = timestamp
        self.quantity = quantity
        self.direction = direction  # 'BUY' or 'SELL'
        self.fill_price = fill_price # price the broker gives us
        self.commission = commission # cost of trade
