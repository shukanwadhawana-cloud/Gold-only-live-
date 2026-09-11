"""Gold-only Voroa paper-runtime entry point.

This entry point is intentionally isolated from account_preflight.py and all
exchange-authenticated execution. Voroa must run only the continuous paper
runtime against public/read-only market data.
"""
import os

# Hard safety gates for the Voroa paper worker. These override any accidental
# live-trading environment values configured on the hosting service.
os.environ["LIVE_TRADING"] = "false"
os.environ["ALLOW_LIVE_ORDERS"] = "false"
os.environ["VOROA_PAPER_ONLY"] = "true"

from paper_runtime import run


if __name__ == "__main__":
    run()
