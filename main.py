"""Gold-only Voroa entry point.

Runs the continuous paper-validation runtime. No Binance authentication,
Telegram, or real order placement is used in this mode.
"""
from paper_runtime import run


if __name__ == "__main__":
    run()
