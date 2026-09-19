"""Gold-only Voroa entry point.

The continuous paper worker is only imported when this file is executed as a
process. Vercel imports this module as a Python function, so keeping the worker
import lazy prevents optional runtime dependencies or the worker loop from
being loaded in the serverless environment.

Vercel is NOT the Gold worker runtime; it only exposes a read-only health app.
"""
import os

# Hard safety gates for the Voroa paper worker. These override any accidental
# live-trading environment values configured on the hosting service.
os.environ["LIVE_TRADING"] = "false"
os.environ["ALLOW_LIVE_ORDERS"] = "false"
os.environ["VOROA_PAPER_ONLY"] = "true"


def app(environ, start_response):
    """Read-only deployment health endpoint; never starts the trading loop."""
    body = b"gold-only-live paper worker: deployment healthy; worker not running on Vercel\n"
    start_response(
        "200 OK",
        [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


if __name__ == "__main__":
    from paper_runtime import run
    run()
