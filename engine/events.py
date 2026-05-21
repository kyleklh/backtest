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
