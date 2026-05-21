"""Simulated broker.

Consumes OrderEvents and produces FillEvents, applying slippage and commission.
Market orders fill at the latest price; limit orders fill only if the price
crosses the limit.
"""
