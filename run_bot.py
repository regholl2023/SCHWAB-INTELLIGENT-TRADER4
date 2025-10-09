# run_bot.py
"""
Robust runner wrapper for SMA/EMA paper trading.

Key improvements over previous version:
 - Defer import of quantbot.runner.Runner so import-time errors can be caught and explained
 - Print helpful diagnostics when import fails (e.g. Broker missing)
 - Support a --once flag to run a single step for quick tests
 - Preserve graceful SIGINT handling and exponential backoff on repeated errors
"""

import time
import signal
import traceback
import argparse
import importlib
import sys
from datetime import datetime

# We still import config early for POLL_INTERVAL_SECONDS only if available.
# If import fails here we'll handle it later after trying to import Runner.
POLL_INTERVAL_SECONDS = 30

running = True
BASE_BACKOFF = 5
MAX_BACKOFF = 120
ERRORS_TO_DOUBLE = 2

def handle_sigint(sig, frame):
    global running
    print("\nStopping runner (signal received). Exiting cleanly...")
    running = False

signal.signal(signal.SIGINT, handle_sigint)
signal.signal(signal.SIGTERM, handle_sigint)

def try_import_runner():
    """
    Attempt to import Runner. If it fails, print helpful diagnostics and raise.
    """
    try:
        # direct import attempt
        from quantbot.runner import Runner  # type: ignore
        return Runner
    except Exception as e:
        print("ERROR: Importing quantbot.runner failed.")
        traceback.print_exc()
        # Try to give actionable diagnostics about quantbot.broker
        try:
            mod = importlib.import_module("quantbot.broker")
            names = [n for n in dir(mod) if not n.startswith("_")]
            print(f"quantbot.broker module loaded. top-level names: {names}")
            print("If 'Broker' is not present, ensure quantbot/broker.py defines a top-level class named 'Broker'.")
        except Exception as e2:
            print("Could not import quantbot.broker for diagnostics (it may be missing or contain syntax errors).")
            traceback.print_exc()
        # Also show file path for quantbot package
        try:
            pkg = importlib.import_module("quantbot")
            print("quantbot package location:", getattr(pkg, '__file__', repr(pkg)))
        except Exception:
            pass
        # Re-raise for the caller to decide
        raise

def main_once(runner):
    """Run a single step and print the info; useful for quick tests."""
    try:
        info = runner.step()
        if not isinstance(info, dict):
            print("runner.step returned unexpected value:", repr(info))
            return
        ts = info.get('ts', datetime.utcnow().isoformat())
        sig = info.get('signal', 'HOLD')
        price = info.get('price')
        equity = info.get('equity')
        price_str = f"{float(price):.2f}" if price is not None else "N/A"
        equity_str = f"{float(equity):.2f}" if equity is not None else "N/A"
        print(f"[{ts}] Signal={sig:5} Price={price_str:>8} Equity={equity_str:>10}")
    except Exception:
        print("Error during single-run step:")
        traceback.print_exc()

def main(loop_once: bool = False):
    global POLL_INTERVAL_SECONDS

    # Try to import config (optional)
    try:
        cfg = importlib.import_module("quantbot.config")
        POLL_INTERVAL_SECONDS = getattr(cfg, "POLL_INTERVAL_SECONDS", POLL_INTERVAL_SECONDS)
    except Exception:
        # config missing or broken — keep default POLL_INTERVAL_SECONDS and continue
        print("Warning: could not import quantbot.config (using default POLL_INTERVAL_SECONDS).")
        # print traceback for debugging
        traceback.print_exc()

    # Now import Runner with diagnostics
    try:
        Runner = try_import_runner()
    except Exception as e:
        print("Fatal: cannot continue without quantbot.runner.Runner. Fix the import errors above and retry.")
        return

    # instantiate runner
    try:
        runner = Runner()
    except Exception as e:
        print("Failed to initialize Runner instance (construction error):")
        traceback.print_exc()
        return

    print("Runner initialized. Starting main loop." if not loop_once else "Runner initialized. Running single step (--once).")

    if loop_once:
        main_once(runner)
        try:
            runner.close()
        except Exception:
            pass
        return

    error_count = 0
    backoff = BASE_BACKOFF

    try:
        while running:
            try:
                info = runner.step()
                if not isinstance(info, dict):
                    print(f"[{datetime.utcnow().isoformat()}] Runner.step returned unexpected: {repr(info)}")
                    info = {'ts': datetime.utcnow().isoformat(), 'signal': 'HOLD', 'price': None, 'equity': 0.0}

                ts = info.get('ts', datetime.utcnow().isoformat())
                sig = info.get('signal', 'HOLD')
                price = info.get('price')
                equity = info.get('equity')
                price_str = f"{float(price):.2f}" if price is not None else "N/A"
                equity_str = f"{float(equity):.2f}" if equity is not None else "N/A"
                print(f"[{ts}] Signal={sig:5} Price={price_str:>8} Equity={equity_str:>10}")

                # reset errors on success
                error_count = 0
                backoff = BASE_BACKOFF

            except KeyboardInterrupt:
                print("KeyboardInterrupt caught. Stopping runner.")
                break

            except Exception as e:
                error_count += 1
                print(f"[{datetime.utcnow().isoformat()}] Runner exception: {repr(e)}")
                traceback.print_exc()
                # exponential backoff
                if error_count <= 1:
                    backoff = BASE_BACKOFF
                else:
                    backoff = min(MAX_BACKOFF, BASE_BACKOFF * (2 ** ((error_count - 1) // ERRORS_TO_DOUBLE)))
                print(f"[{datetime.utcnow().isoformat()}] Sleeping for {backoff} seconds (error_count={error_count})")
                slept = 0
                while slept < backoff and running:
                    time.sleep(1)
                    slept += 1
                continue

            # normal poll sleep (small increments to be responsive)
            slept = 0
            while slept < POLL_INTERVAL_SECONDS and running:
                time.sleep(1)
                slept += 1

    finally:
        try:
            runner.close()
        except Exception:
            pass
        print("Runner stopped. Exiting.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SMA/EMA paper runner")
    parser.add_argument("--once", action="store_true", help="Run a single step and exit (useful for testing)")
    args = parser.parse_args()
    main(loop_once=args.once)

