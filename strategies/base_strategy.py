"""Strategy interface.

A strategy consumes MarketEvents and produces SignalEvents. It never touches
cash, positions, or orders directly — that is the Portfolio's job.

Subclasses implement: calculate_signals(event)
"""

from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def calculate_signals(self, event):
        """
        Called by the event loop on every MarketEvent. Reads the latest bar(s)
        from the DataHandler and pushes SignalEvents onto the queue.
        """
        pass