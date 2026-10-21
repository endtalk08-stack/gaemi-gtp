"""Staged, opt-in once-per-stock/day reservation using the existing Neon ledger.

Not imported by the production worker. Caller supplies a psycopg connection and
commits before making a paid request. A reservation is deliberately not retried
automatically after a crash: avoiding duplicate billable calls takes priority.
"""
import hashlib
import json


def reserve_once(conn, *, market, symbol, exchange_day, request_hash,
                 provider="groq", model_id="openai/gpt-oss-20b"):
    """Return True exactly once per (market, symbol, exchange_day).

    All workers must use this function. Advisory transaction lock serializes
    concurrent reservations even when their request hashes differ.
    """
    if market not in ("US", "KR") or not symbol or not request_hash:
        raise ValueError("Invalid reservation identity")
    key = f"{market}:{symbol}:{exchange_day.isoformat()}"
    lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (lock_id,))
        cur.execute(
            """SELECT 1 FROM public.news_ai_call_ledger
               WHERE market=%s AND symbol=%s AND exchange_day=%s LIMIT 1""",
            (market, symbol, exchange_day),
        )
        if cur.fetchone() is not None:
            return False
        cur.execute(
            """INSERT INTO public.news_ai_call_ledger
               (market, symbol, exchange_day, request_hash, status, provider, model_id)
               VALUES (%s, %s, %s, %s, 'reserved', %s, %s)""",
            (market, symbol, exchange_day, request_hash, provider, model_id),
        )
        return True


def finish_reservation(conn, *, market, symbol, exchange_day, request_hash,
                       status, result=None, failure_category=None, failure_reason=None):
    """Record outcome without clearing the daily reservation.

    A failed/invalid response is not retried automatically, preventing
    repeated billable requests. Caller must commit the outcome transaction.
    """
    if status not in ("completed", "invalid", "failed"):
        raise ValueError("Invalid terminal status")
    # A controlled diagnostic code, not provider text, can use the existing field.
    if failure_reason is not None and (
        not isinstance(failure_reason, str) or not failure_reason.isascii()
        or not failure_reason.replace("_", "").isalnum()
        or len(failure_reason) > 48
    ):
        raise ValueError("Invalid diagnostic code")
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE public.news_ai_call_ledger
               SET status=%s, result=%s::jsonb, failure_category=%s,
                   failure_reason=%s, completed_at=now()
               WHERE market=%s AND symbol=%s AND exchange_day=%s
                 AND request_hash=%s AND status='reserved'""",
            (status, json.dumps(result, ensure_ascii=False) if result is not None else None,
             failure_category, failure_reason, market, symbol, exchange_day, request_hash),
        )
        return cur.rowcount == 1

# Existing US coverage was bounded to 21 names. Keep that TOTAL daily budget
# for US+KR together (10 KR / 11 US) while allowing any worker-ranked name.
MAX_AI_CALLS_KST_DAY = 21
MARKET_AI_CALLS_KST_DAY = {"KR": 10, "US": 11}


def reserve_with_daily_budget(conn, *, market, symbol, exchange_day, request_hash,
                              provider="groq", model_id="openai/gpt-oss-20b"):
    """Atomically check global/market cost limits and preserve once/stock/day.

    This is called inside the caller's transaction, before the paid API call.
    Transaction advisory lock prevents two workers from overrunning the limit.
    Both markets share a Korean-calendar-day counter to avoid day-boundary gaps.
    """
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    if market not in MARKET_AI_CALLS_KST_DAY:
        raise ValueError("Invalid AI market")
    kst_today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    start = datetime.combine(kst_today, datetime.min.time(), ZoneInfo("Asia/Seoul"))
    stop = start + timedelta(days=1)
    lock_key = f"gaemigtp:ai:daily:{kst_today.isoformat()}"
    lock_id = int.from_bytes(hashlib.sha256(lock_key.encode()).digest()[:8],
                             "big", signed=True)
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (lock_id,))
        cur.execute(
            """SELECT COUNT(*) FILTER (WHERE market=%s), COUNT(*)
               FROM public.news_ai_call_ledger
               WHERE created_at >= %s AND created_at < %s""",
            (market, start, stop),
        )
        own_count, total_count = cur.fetchone()
    if (own_count >= MARKET_AI_CALLS_KST_DAY[market]
            or total_count >= MAX_AI_CALLS_KST_DAY):
        print("[news-ai] skipped reason=daily_budget_reached market=%s" % market,
              flush=True)
        return False
    return reserve_once(conn, market=market, symbol=symbol,
                        exchange_day=exchange_day, request_hash=request_hash,
                        provider=provider, model_id=model_id)
