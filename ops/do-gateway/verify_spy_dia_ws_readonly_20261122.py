#!/usr/bin/env python3
"""Read-only check that the existing quote WebSocket publishes SPY and DIA."""
import asyncio
import json
import sys
import time

async def main():
    try:
        from websockets import connect
    except ImportError:
        print("SPY_DIA_WS_RESULT=websockets_module_missing", flush=True)
        return 3

    seen = {}
    deadline = time.monotonic() + 45
    try:
        async with connect(
            "ws://127.0.0.1:8765/ws/us-live-quotes",
            origin="https://github-pages-preview.gaemigtp-main.pages.dev",
            open_timeout=8,
            close_timeout=2,
            ping_interval=None,
            max_size=131072,
        ) as ws:
            while time.monotonic() < deadline and len(seen) < 2:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=3)
                except asyncio.TimeoutError:
                    continue
                try:
                    message = json.loads(raw)
                except (TypeError, ValueError):
                    continue
                if message.get("type") != "industry-quotes":
                    continue
                for row in message.get("items", []):
                    if not isinstance(row, dict) or row.get("symbol") not in ("SPY", "DIA"):
                        continue
                    seen[row["symbol"]] = {
                        "price": row.get("price"),
                        "change_pct": row.get("change_pct"),
                        "source": row.get("source"),
                        "stale": row.get("stale"),
                        "age_ms": max(0, int(time.time() * 1000) - int(row.get("received_at_ms") or 0)),
                    }
    except Exception as exc:
        print("SPY_DIA_WS_ERROR=" + type(exc).__name__, flush=True)
        return 4

    print("SPY_DIA_WS_RESULT=" + json.dumps(seen, sort_keys=True, allow_nan=False), flush=True)
    if set(seen) != {"SPY", "DIA"}:
        return 5
    if any(not isinstance(row.get("price"), (int, float)) or row["price"] <= 0 for row in seen.values()):
        return 6
    return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
