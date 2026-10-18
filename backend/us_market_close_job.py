"""Entrypoint for a future separate 07:00 KST DO systemd timer.

Run manually or via a dedicated service only; importing this file has no side effects.
No API provider calls are made by Render or viewers.
"""
import json
import sys

from backend.services.us_market_close import publish_once


def main():
    try:
        result = publish_once()
    except Exception as exc:
        # Never log article contents, API keys or provider error response bodies.
        print("us_market_close_failed=" + type(exc).__name__, flush=True)
        return 1
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
