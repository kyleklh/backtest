"""Strategy interface.

A strategy consumes MarketEvents and produces SignalEvents. It never touches
cash, positions, or orders directly — that is the Portfolio's job.

Subclasses implement: calculate_signals(event)
"""
