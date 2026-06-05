"""Position sizing — decides HOW MANY shares a full position is.

Separated from the Portfolio (which only accounts) and the Strategy (which only
signals intent). A sizer answers one question: given a symbol, its price, and
the current portfolio state, how large should a full position be? Swap the
policy here without touching signal logic or accounting.
"""


class EqualWeightSizer:
    """Equal split of current equity across the universe: each full position
    targets `current_equity / N`, in whole shares, with a cost buffer so the
    fill (slippage + commission) can't overdraw the budget."""

    def __init__(self, num_symbols):
        self.num_symbols = num_symbols

    def size(self, symbol, price, portfolio):
        all_in = price * (1 + portfolio.slippage_rate) * (1 + portfolio.commission_rate)
        budget = portfolio.current_equity() / self.num_symbols
        return int(budget / all_in)
