"""Staged, opt-in once-per-US-day reservation using the existing Neon ledger.

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
