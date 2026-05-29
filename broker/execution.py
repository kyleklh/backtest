"""Execution cost models: commission and slippage.

Kept separate from the broker so different cost assumptions can be swapped in
without touching fill logic.
"""

from engine.events import FillEvent

class SimulatedBroker:
    def __init__(self, data_handler, events, commission_rate = 0.001, slippage_rate = 0.0005):
        self.data_handler = data_handler
        self.events = events
        self.commission_rate = commission_rate          # 0.1% of trade value
        self.slippage_rate = slippage_rate              # 0.05% of price per share


    def execute_order(self, event):
        """OrderEvent -> apply slippage + commission -> push a FillEvent."""
        if event.type != 'ORDER':
            return
        
        bar = self.data_handler.get_latest_bar()
        price = bar["close"]

        #slippage: price moves against us (worse price than you saw)
        if event.direction == 'BUY':
            fill_price = price * (1 + self.slippage_rate)
        elif event.direction == 'SELL':
            fill_price = price * (1 - self.slippage_rate)
        else:
            return
        
        commission = event.quantity * fill_price * self.commission_rate  # % of trade value

        # push the FillEvent
        fill = FillEvent(
            symbol=event.symbol,
            timestamp=bar.name,
            quantity=event.quantity,
            direction=event.direction,
            fill_price=fill_price,
            commission=commission,
        )
        self.events.put(fill)