"""Buy-and-hold benchmark strategy.

Goes long each symbol on its first bar and never trades again. Useful as a
baseline to compare more active strategies against.
"""

from strategies.base_strategy import BaseStrategy

class BuyAndHoldStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.in_position = False

    def on_bar(self, bar):
        if not self.in_position:
            self.in_position = True
            print(f"BUY signal at {bar.name} price: {bar['close']}")
            return "BUY"
            
        else:
            # print(f"HOLD signal at {bar.name} price: {bar['close']}")
            return None
            