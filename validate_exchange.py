"""Read-only Binance Gold discovery.

GitHub Actions runners can be blocked by Binance's regional/IP eligibility
policy. Treat HTTP 451 as an environmental limitation, not a code failure.
"""
import ccxt


def main():
    ex = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "swap"}})
    try:
        markets = ex.load_markets()
    except ccxt.ExchangeNotAvailable as exc:
        message = str(exc)
        if " 451 " in message or "restricted location" in message.lower():
            print("BINANCE_PUBLIC_API_RESTRICTED=TRUE")
            print("GitHub Actions runner is blocked by Binance's regional/IP eligibility policy.")
            print("This does NOT prove your personal Binance account is ineligible.")
            print("Account preflight must run from an eligible environment/account connection.")
            return
        raise

    matches = []
    for m in markets.values():
        market_id = str(m.get("id", "")).upper()
        if market_id == "XAUUSDT" or ("XAU" in market_id and m.get("quote") == "USDT"):
            matches.append({k: m.get(k) for k in ("id", "symbol", "type", "contract", "swap", "active", "limits", "precision")})

    print("Binance Gold markets:")
    for item in matches:
        print(item)
    if not matches:
        raise SystemExit("XAUUSDT was not exposed by this Binance market-data endpoint.")


if __name__ == "__main__":
    main()
