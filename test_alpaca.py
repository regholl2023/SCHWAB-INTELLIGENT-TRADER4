# test_alpaca.py
"""
Sanitized connection test for Alpaca Paper API.

- Ensures base URL doesn't contain '/v2' (the client appends it).
- Prints the final base URL used by the alpaca client.
- Fetches basic account info, positions and recent orders.

Usage:
  1) Put your keys into a .env file in the same folder:
       ALPACA_KEY=...
       ALPACA_SECRET=...
       ALPACA_BASE_URL=https://paper-api.alpaca.markets
  2) Run:
       python test_alpaca.py
"""

import os
from dotenv import load_dotenv
import sys
import traceback

load_dotenv()

ALPACA_KEY = os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

if not ALPACA_KEY or not ALPACA_SECRET:
    print("ERROR: Alpaca API keys not found in environment.")
    print("Create a .env with ALPACA_KEY and ALPACA_SECRET (and optionally ALPACA_BASE_URL).")
    sys.exit(1)

try:
    import alpaca_trade_api as tradeapi
except Exception:
    print("ERROR: Could not import alpaca_trade_api. Install with:")
    print("    pip install alpaca-trade-api")
    sys.exit(1)


def sanitize_base_url(u: str) -> str:
    if not u:
        return u
    u = u.strip()
    # remove trailing slash
    u = u.rstrip('/')
    # remove an accidental trailing '/v2' (case-insensitive)
    if u.lower().endswith('/v2'):
        u = u[:-3].rstrip('/')
    return u

def main():
    try:
        base = sanitize_base_url(ALPACA_BASE_URL)
        print("Raw ALPACA_BASE_URL from .env:", ALPACA_BASE_URL)
        print("Sanitized base URL (used):", base)
        # create API client (alpaca_trade_api will add /v2 internally)
        api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, base, api_version='v2')

        # Basic account info
        account = api.get_account()
        print("\n=== Account Info ===")
        print(f"Account ID    : {account.id}")
        print(f"Status        : {account.status}")
        print(f"Cash Balance  : {account.cash}")
        print(f"Buying Power  : {getattr(account, 'buying_power', 'N/A')}")
        print()

        # Positions (if any)
        try:
            positions = api.list_positions()
            print("=== Positions ===")
            if not positions:
                print("No open positions.")
            else:
                for p in positions:
                    print(f"{p.symbol:6}  qty={p.qty:>6}  avg_entry={p.avg_entry_price:>10}  market_value={p.market_value:>10}")
            print()
        except Exception:
            print("Could not fetch positions or none exist.")

        # Recent orders
        try:
            orders = api.list_orders(status='all', limit=10, nested=False)
            print("=== Recent Orders (last 10) ===")
            if not orders:
                print("No recent orders.")
            else:
                for o in orders:
                    print(f"{o.side.upper():4} {o.symbol:6}  qty={getattr(o,'qty',None):>6}  filled={getattr(o,'filled_qty',None)}  status={o.status}")
            print()
        except Exception:
            print("Could not fetch orders.")

        # Try to get last trade for AAPL (fallback)
        try:
            # Newer alpaca API wrappers have get_latest_trade / get_last_trade depending on version
            try:
                lt = api.get_latest_trade("AAPL")
                print("Latest AAPL trade price:", getattr(lt, 'price', getattr(lt, 'p', 'N/A')))
            except Exception:
                # older method
                barset = api.get_barset("AAPL", 'day', limit=1)
                bars = barset.get("AAPL")
                if bars:
                    last = bars[-1]
                    print(f"Latest AAPL OHLC: {last.o} / {last.h} / {last.l} / {last.c}")
                else:
                    print("No recent bars for AAPL")
        except Exception:
            print("Could not fetch example price data.")

        print("\nConnection test completed successfully (paper environment).")

    except Exception as e:
        print("ERROR: Exception while connecting to Alpaca API:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

