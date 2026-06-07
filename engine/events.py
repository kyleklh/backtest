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
    """A new bar has arrived for one symbol. Carries which symbol and when;
    price data is pulled from the DataHandler at the cursor."""
    def __init__(self, symbol, timestamp):
        self.type = 'MARKET'
        self.symbol = symbol
        self.timestamp = timestamp

class SignalEvent(Event):
    """Strategy's decision: the target STANCE for a symbol, not a trade. The
    portfolio + sizer translate this into orders. Says what, not how many."""
    def __init__(self, symbol, timestamp, direction):
        self.type = 'SIGNAL'
        self.symbol = symbol
        self.timestamp = timestamp
        self.direction = direction  # 'LONG', 'SHORT', or 'EXIT' (flat)

class OrderEvent(Event):
    """Portfolio's sized order, ready for the broker."""
    def __init__(self, symbol, order_type, quantity, direction, limit_price=None,
                 order_id=None, tif="GTC", expire_date=None):
        self.type = 'ORDER'
        self.symbol = symbol
        self.order_type = order_type    # "MKT" (market) or "LMT" (limit)
        self.quantity = quantity        # number of shares
        self.direction = direction      # 'BUY' or 'SELL'
        self.limit_price = limit_price  # required for "LMT"; ignored for "MKT"
        self.order_id = order_id        # set by the portfolio; lets the order be cancelled
        self.tif = tif                  # time-in-force: "GTC" | "DAY" | "GTD"
        self.expire_date = expire_date  # only for "GTD"


class CancelEvent(Event):
    """Request to cancel a still-working order by id."""
    def __init__(self, order_id):
        self.type = 'CANCEL'
        self.order_id = order_id


class OrderStatusEvent(Event):
    """Broker's report on an order's lifecycle, so the portfolio can keep its
    set of open orders accurate."""
    def __init__(self, order_id, symbol, status):
        self.type = 'STATUS'
        self.order_id = order_id
        self.symbol = symbol
        self.status = status            # 'FILLED' | 'CANCELLED' | 'REJECTED'


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
