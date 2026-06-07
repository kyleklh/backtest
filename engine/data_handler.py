"""Historical data handler for the event-driven engine.

Owns one OHLCV dataframe per symbol and replays them along a shared **union**
timeline — every date on which *any* symbol traded. A single cursor walks that
timeline; on each step the handler emits a MarketEvent only for the symbols that
actually printed a bar on that date. Symbols on mismatched calendars therefore
lose no data, and no fabricated bar is ever tradeable.

Two kinds of read are deliberately separated:

- TRADING reads (`get_latest_bar`, `get_latest_bars`, `get_latest_bar_value`)
  return a symbol's *real* bars only. They're called for a symbol on its own
  MarketEvent, so the current bar is always a genuine, just-printed bar — and
  trailing history skips the days the symbol didn't trade.
- VALUATION reads (`get_value`) return the last-known (forward-filled) price, so
  the book can be marked to market on a date even for a symbol that didn't print
  that day. Forward-filling is fine for valuation; it is never used to trade.

Because every read is taken relative to the cursor, future rows are physically
unreachable, which structurally prevents lookahead bias.
"""


from engine.events import MarketEvent

class DataHandler:
    def __init__(self, data, symbols, events):
        # data: dict[symbol -> df]; symbols: list of symbols to replay
        self.symbols = symbols
        self.events = events

        # shared timeline = union of every symbol's dates (any symbol trading)
        timeline = data[symbols[0]].index
        for s in symbols[1:]:
            timeline = timeline.union(data[s].index)
        self.timeline = timeline.sort_values()

        # raw view: reindex onto the timeline, NaN where a symbol didn't trade.
        # valued view: forward-filled, for marking positions to market on gaps.
        self.data = {s: data[s].reindex(self.timeline) for s in symbols}
        self.valued = {s: self.data[s].ffill() for s in symbols}

        self.cursor = -1            # index into timeline; -1 = nothing revealed yet
        self.continue_backtest = True

    def update_bars(self):
        """Advance one date. Emit a MarketEvent for each symbol that has a real
        bar on this date, or stop if the timeline is exhausted."""
        self.cursor += 1
        if self.cursor >= len(self.timeline):
            self.continue_backtest = False
            return
        date = self.timeline[self.cursor]
        for s in self.symbols:
            if not self._is_missing(s):
                self.events.put(MarketEvent(s, date))

    def _is_missing(self, symbol):
        """True if `symbol` has no real bar at the cursor (didn't trade that date)."""
        return bool(self.data[symbol].iloc[self.cursor].isna().any())

    def current_date(self):
        """The current timeline date (independent of any one symbol)."""
        return self.timeline[self.cursor]

    # --- trading reads: a symbol's real bars only -------------------------------
    def get_latest_bar(self, symbol):
        """The symbol's current bar (a pandas row)."""
        return self.data[symbol].iloc[self.cursor]

    def get_latest_bar_value(self, symbol, field):
        """One field (e.g. 'close') from a symbol's current bar."""
        return self.data[symbol].iloc[self.cursor][field]

    def get_latest_bars(self, symbol, n=1):
        """The last n *real* bars of one symbol up to the cursor (days the symbol
        didn't trade are skipped). Never returns future rows."""
        history = self.data[symbol].iloc[:self.cursor + 1].dropna()
        return history.iloc[-n:]

    # --- valuation read: last-known price, forward-filled -----------------------
    def get_value(self, symbol, field="close"):
        """Last-known value for marking to market, even on a date the symbol
        didn't trade. NaN only before the symbol's first-ever bar."""
        return self.valued[symbol].iloc[self.cursor][field]
