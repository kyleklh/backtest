"""Historical data handler for the event-driven engine.

Owns the full OHLCV dataframe and replays it one bar at a time, advancing a
cursor that represents simulated "now". On each step it pushes a MarketEvent
onto the shared queue to announce that a new bar is available.

Other components never touch the dataframe directly — they read the current
bar (and any trailing history they need) through this handler. Because every
read is taken relative to the cursor, future rows are physically unreachable,
which structurally prevents lookahead bias.
"""


from engine.events import MarketEvent

class DataHandler:
    def __init__(self, df, symbol, events):
        self.df = df                # full OHLCV df
        self.symbol = symbol
        self.events = events        # shared event queue
        self.cursor = -1            # index of the latest revealed bar; -1 = nothing yet
        self.continue_backtest = True    # flag to signal when we've reached the end of the data

    def update_bars(self):
        """Advance one bar. Push a MarketEvent, or stop if data's exhausted."""
        self.cursor += 1
        if self.cursor >= len(self.df):
            self.continue_backtest = False
            return
        self.events.put(MarketEvent())

    def get_latest_bar(self):
        """The current bar (a pandas row). Components read price from this."""
        return self.df.iloc[self.cursor]
    
    def get_latest_bar_value(self, field):
        """One field (e.g. 'close') from the current bar."""
        return self.df.iloc[self.cursor][field]
    
    def get_latest_bars(self, n=1):
        """The last n bars up to the cursor — for strategies needing history
        (like the MA crossover). Never returns future rows."""
        start = max(0, self.cursor - n + 1)
        return self.df.iloc[start:self.cursor + 1]
