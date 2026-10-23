"""Apply minimal live-worker edits; caller owns backup and service restart."""
from pathlib import Path
import ast
import sys


def pause_ai(path, names):
    source = Path(path)
    text = source.read_text()
    tree = ast.parse(text)
    defs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if len(defs) != len(names):
        raise RuntimeError("AI entrypoint drift " + path)
    lines = text.splitlines(keepends=True)
    inserts = []
    for node in defs:
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            after = first.end_lineno
        else:
            after = first.lineno - 1
        snippet = (
            '    # News-AI paused: do not reserve or invoke the paid AI.\n'
            '    if __import__("os").environ.get("GAEMIGTP_NEWS_AI_PAUSED", "1") != "0":\n'
            '        print("[news-ai] PAUSED ' + node.name + '", flush=True)\n'
            '        return 0\n'
        )
        inserts.append((after, snippet))
    for offset, snippet in sorted(inserts, reverse=True):
        lines.insert(offset, snippet)
    candidate = ''.join(lines)
    ast.parse(candidate)
    source.write_text(candidate)


def choose_code_issue_in_store():
    p = Path('backend/services/news_processed_store.py')
    source = p.read_text()
    anchor = 'normalized = _prefer_same_day_ai(normalized, previous_payload,'
    if source.count(anchor) != 1:
        raise RuntimeError("Store call no longer matches expected implementation")
    lines = source.splitlines(keepends=True)
    index = next(i for i, line in enumerate(lines) if anchor in line)
    if index + 1 >= len(lines) or 'stock_name, day)' not in lines[index + 1]:
        raise RuntimeError("Store call continuation changed")
    lines.insert(index + 2,
        '                normalized["issue_briefs"] = normalized.get("_code_issue_briefs") or []\n')
    candidate = ''.join(lines)
    ast.parse(candidate)
    p.write_text(candidate)


def backfill():
    import psycopg
    from psycopg.types.json import Jsonb
    from backend.services.article_fact_keywords import build_article_fact_briefs, read_us_price_change_pct
    from backend.services.news_processed_store import database_url
    url = database_url()
    if not url:
        raise RuntimeError("No existing Neon connection configured")
    with psycopg.connect(url, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT stock_name, result_payload
                FROM public.news_processed_snapshots
                WHERE market='미국' AND expires_at>now()
                  AND result_limit=50 AND storyboard_limit=3
                FOR UPDATE
            """)
            rows = cur.fetchall()
            updated, ready = 0, 0
            for stock, payload in rows:
                articles = payload.get('paired_news_items') if isinstance(payload, dict) else None
                if not isinstance(articles, list):
                    continue
                quote = read_us_price_change_pct(stock)
                briefs = build_article_fact_briefs(articles, stock, price_change_pct=quote, limit=3)
                cur.execute("""
                    UPDATE public.news_processed_snapshots
                    SET result_payload = jsonb_set(
                        jsonb_set(result_payload, '{_code_issue_briefs}', %s, true),
                        '{issue_briefs}', %s, true)
                    WHERE market='미국' AND stock_name=%s AND result_limit=50 AND storyboard_limit=3
                """, (Jsonb(briefs), Jsonb(briefs), stock))
                updated += 1
                if briefs:
                    ready += 1
            print("CODE_FACTS_BACKFILL_STOCKS", updated, "READY", ready, flush=True)
            if updated < 1 or ready < 1:
                raise RuntimeError("No US stock fact briefs extracted")
    print("CODE_FACTS_BACKFILL_COMMITTED", flush=True)


def verify():
    from datetime import datetime, timezone
    from backend.services.article_fact_keywords import build_article_fact_briefs
    from ops.staged_ai_sequential_batch import apply_worker_ai, apply_unchanged_worker_ai
    from ops.staged_auto_ai_daily import process_due_ai_snapshots
    article = {
        'title': '테슬라, 설비투자 계획 250억 달러에서 200억 달러로 축소',
        'description': '테슬라가 설비투자 계획을 축소한다고 밝혔다.',
        'published_at': datetime.now(timezone.utc).isoformat(),
        'url': 'https://example.com/article',
    }
    result = build_article_fact_briefs([article], '테슬라', price_change_pct=-0.5)
    if len(result) != 1 or not result[0].get('tags'):
        raise RuntimeError("Fact extraction smoke test failed")
    assert apply_worker_ai(store=None, market="미국", stock_name="테슬라",
                           raw=[], fingerprint="", result={}, params={}) == 0
    assert apply_unchanged_worker_ai(store=None, market="미국", stock_name="테슬라",
                                     raw=[], fingerprint="", params={}) == 0
    assert process_due_ai_snapshots() == 0
    print("AI_PAUSE_AND_CODE_FACTS_IMPORT_VERIFIED", flush=True)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'patch':
        pause_ai('ops/staged_ai_sequential_batch.py', {'apply_worker_ai', 'apply_unchanged_worker_ai'})
        pause_ai('ops/staged_auto_ai_daily.py', {'process_due_ai_snapshots'})
        choose_code_issue_in_store()
        print("LIVE_PATCH_COMPILED", flush=True)
    elif mode == 'verify':
        verify()
    elif mode == 'backfill':
        backfill()
    else:
        raise SystemExit("Expected patch|verify|backfill")
