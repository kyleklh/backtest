"""Historical data handler for the event-driven engine.

Owns one OHLCV dataframe per symbol and replays them in lockstep, advancing a
single cursor that represents simulated "now". On each step it pushes a
MarketEvent onto the shared queue to announce that a new bar is available.

All symbols are aligned to a shared timeline (the intersection of their dates),
so a single cursor indexes the same calendar bar across every symbol. Other
components never touch the dataframes directly — they read the current bar (and
any trailing history) through this handler, passing the symbol they want.
Because every read is taken relative to the cursor, future rows are physically
unreachable, which structurally prevents lookahead bias.

DESIGN NOTE — the shared-timeline (intersection) approach is correct-by-
construction (it never fabricates a price) but lossy: when symbols trade on
different calendars (e.g. US equities + crypto, or mismatched holidays), it
silently drops any bar a symbol lacks. That's fine for same-calendar equities,
where the intersection drops essentially nothing. A FUTURE redesign for true
mixed-frequency/mixed-calendar data would drop the single shared grid and give
each symbol its own event stream — every symbol emits a MarketEvent only when
it actually has a bar, and the loop merges those time-ordered streams. More
general, but the cursor stops being a single integer, so it's a bigger change.
"""


from engine.events import MarketEvent

class DataHandler:
    def __init__(self, data, symbols, events):
        # data: dict[symbol -> df]; symbols: list of symbols to replay
        self.symbols = symbols
        self.events = events

        # shared timeline = dates every symbol has in common, sorted
        common = data[symbols[0]].index
        for s in symbols[1:]:
            common = common.intersection(data[s].index)
        self.timeline = common.sort_values()

        # reindex each symbol onto the shared timeline so one cursor position
        # maps to the same calendar date in every symbol's dataframe
        self.data = {s: data[s].reindex(self.timeline) for s in symbols}

        self.cursor = -1            # index into timeline; -1 = nothing revealed yet
        self.continue_backtest = True

    def update_bars(self):
        """Advance one bar. Push a MarketEvent, or stop if data's exhausted."""
        self.cursor += 1
        if self.cursor >= len(self.timeline):
            self.continue_backtest = False
            return
        self.events.put(MarketEvent())

    def get_latest_bar(self, symbol):
        """The current bar (a pandas row) for one symbol."""
        return self.data[symbol].iloc[self.cursor]

    def get_latest_bar_value(self, symbol, field):
        """One field (e.g. 'close') from a symbol's current bar."""
        return self.data[symbol].iloc[self.cursor][field]

    def get_latest_bars(self, symbol, n=1):
        """The last n bars of one symbol up to the cursor — for strategies
        needing history (like the MA crossover). Never returns future rows."""
        start = max(0, self.cursor - n + 1)
        return self.data[symbol].iloc[start:self.cursor + 1]
