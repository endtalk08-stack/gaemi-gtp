"""Deterministic rank-frozen US top-20 rotation for the DigitalOcean news worker.

Pure state machine: it does not fetch news, read/write Neon, or change the worker.
The worker must persist the returned JSON state under an exclusive lock between
calls and run plan_tick once per 300-second scheduling tick.
"""
from __future__ import annotations

from copy import deepcopy
import re

TOP_N = 20
SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,15}$")


class RankingUnavailable(ValueError):
    """No complete, validated top-20 ranking can start a new rotation."""


def normalize_ranking(rows):
    """Accept exactly 20 unique positions/tickers from one *complete* snapshot.

    Do not merge rankings gathered at different times; caller supplies all
    entries from a single committed market_rank_snapshots.id.
    """
    if not isinstance(rows, (list, tuple)) or len(rows) != TOP_N:
        raise RankingUnavailable("complete_top20_required")
    result, ranks, symbols = [], set(), set()
    for row in rows:
        if not isinstance(row, dict):
            raise RankingUnavailable("invalid_row")
        rank = row.get("rank")
        symbol = str(row.get("symbol") or "").strip().upper()
        name = str(row.get("display_name") or row.get("name") or "").strip()
        if type(rank) is not int or not 1 <= rank <= TOP_N:
            raise RankingUnavailable("invalid_rank")
        if rank in ranks or symbol in symbols or not SYMBOL_RE.fullmatch(symbol) or not name:
            raise RankingUnavailable("duplicate_or_invalid_ticker")
        ranks.add(rank)
        symbols.add(symbol)
        result.append({"rank": rank, "symbol": symbol, "name": name})
    if ranks != set(range(1, TOP_N + 1)):
        raise RankingUnavailable("rank_gap")
    return sorted(result, key=lambda row: row["rank"])


def _saved_cycle(state):
    items = state.get("cycle")
    if items is None:
        return None
    # Saved cycle must be a complete frozen snapshot, regardless of its
    # original rank ordering. Validate it again after process restart.
    return normalize_ranking(items)


def plan_tick(saved_state, latest_rank_rows):
    """Plan one ticker. A pending plan is replayed after restart, never skipped.

    Persist the returned state *before* invoking a network fetch. If the
    process dies, a retry uses the same symbol; finish_tick moves the cursor.
    """
    state = deepcopy(saved_state or {})
    pending = state.get("pending")
    if pending:
        cycle = _saved_cycle(state)
        idx = state.get("next_index")
        if (cycle is None or type(idx) is not int or not 0 <= idx < TOP_N
                or pending != cycle[idx]["symbol"]):
            raise ValueError("corrupt_pending_state")
        return deepcopy(cycle[idx]), state

    cycle = _saved_cycle(state)
    index = state.get("next_index", TOP_N)
    if type(index) is not int or not 0 <= index <= TOP_N:
        raise ValueError("invalid_next_index")
    if cycle is None or index == TOP_N:
        try:
            cycle = normalize_ranking(latest_rank_rows)
        except RankingUnavailable:
            if cycle is None:
                raise
            # If the live ranking feed fails, reuse the most recent complete
            # frozen set. Never start an incomplete or mixed-ranked round.
        state["cycle"] = deepcopy(cycle)
        state["next_index"] = 0
        state["cycle_number"] = int(state.get("cycle_number", 0)) + 1
        index = 0
    chosen = cycle[index]
    state["pending"] = chosen["symbol"]
    return deepcopy(chosen), state


def finish_tick(saved_state, symbol, *, ok):
    """Finish an attempted slot whether it succeeded or failed.

    A failed ticker is logged for retry on its next regular cycle; do not
    block other 19 stocks forever. Caller must durably persist this state.
    """
    state = deepcopy(saved_state or {})
    pending = state.get("pending")
    if pending != symbol or not SYMBOL_RE.fullmatch(str(symbol or "")):
        raise ValueError("pending_symbol_mismatch")
    cycle = _saved_cycle(state)
    idx = state.get("next_index")
    if cycle is None or type(idx) is not int or not 0 <= idx < TOP_N:
        raise ValueError("invalid_cursor")
    if cycle[idx]["symbol"] != symbol or type(ok) is not bool:
        raise ValueError("invalid_attempt")
    state["next_index"] = idx + 1
    state["pending"] = None
    state["last_attempt"] = {"symbol": symbol, "ok": ok, "rank": cycle[idx]["rank"]}
    if not ok:
        # Keep only the current cycle's failures. They will be tried again in
        # the next full ranked rotation, not ahead of higher ranked tickers.
        failures = list(state.get("failures") or [])
        if symbol not in failures:
            failures.append(symbol)
        state["failures"] = failures
    elif symbol in (state.get("failures") or []):
        state["failures"] = [x for x in state["failures"] if x != symbol]
    return state
