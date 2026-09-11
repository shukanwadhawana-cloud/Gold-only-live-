"""Temporary Voroa runtime diagnostic.

This intentionally does not import the trading bot or contact Binance/Telegram.
It only proves whether Voroa's Worker actually executes the configured command.
"""
import platform
import sys
import time

print("=== VOROA RUNTIME TEST STARTED ===", flush=True)
print(f"Python: {sys.version}", flush=True)
print(f"Platform: {platform.platform()}", flush=True)
print("Process will remain alive for 1 hour.", flush=True)

while True:
    print("VOROA RUNTIME TEST: process alive", flush=True)
    time.sleep(60)
