"""Strategy interface.

A strategy consumes MarketEvents and produces SignalEvents. It never touches
cash, positions, or orders directly — that is the Portfolio's job.

Subclasses implement: calculate_signals(event)
"""

from abc import ABC, abstractmethod
from typing import Optional

class BaseStrategy(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def on_bar(self, bar) -> Optional[str]:
        """
        Called by the event loop on every new market bar.
        """
        pass