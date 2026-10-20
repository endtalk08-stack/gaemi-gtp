"""US market close editorial: 2-3 original articles -> one AI briefing -> Neon.

Independent of existing stock news filters and live chat AI calls. Only the
DigitalOcean scheduled worker calls publish_once(); Render calls read_brief().
Article bodies are never persisted, and no source text is sent to the browser.
"""
import datetime as datetime
import html
import json
import os
import re
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from backend.providers import naver_news
from backend.services.news_detail import read_selected_article_details

NY = ZoneInfo("America/New_York")
UTC = datetime.timezone.utc
QUERY = "뉴욕증시 마감"
MODEL = "openai/gpt-oss-120b"
PUBLISHERS = (
    "yna.co.kr", "hankyung.com", "mk.co.kr", "sedaily.com",
    "edaily.co.kr", "mt.co.kr", "newsis.com", "fnnews.com",
    "heraldcorp.com", "biz.chosun.com", "chosun.com",
)
CLOSE_NAMES = ("뉴욕증시", "뉴욕 증시", "미국증시", "미국 증시")
FINISH_WORDS = ("마감", "장 마쳐", "거래 마쳐", "장 마감")


def _clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", "", str(value or "")))).strip()


def _publisher(url):
    try:
        parts = urllib.parse.urlsplit(str(url or ""))
        host = (parts.hostname or "").lower()
        if parts.scheme != "https" or parts.username or parts.password:
            return ""
        return next((name for name in PUBLISHERS if host == name or host.endswith("." + name)), "")
    except ValueError:
        return ""


def _published(row):
    try:
        parsed = parsedate_to_datetime(str(row.get("pubDate") or row.get("raw_pub_date") or ""))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(NY)
    except (TypeError, ValueError, IndexError):
        return None


def select_close_articles(rows, session_date, now_utc=None):
    """Only time/title/publisher filters; AI decides which topics matter."""
    now = now_utc or datetime.datetime.now(UTC)
    selected, seen_publishers, seen_titles, seen_urls = [], set(), set(), set()
    for row in sorted(rows or [], key=lambda r: _published(r) or datetime.datetime.min.replace(tzinfo=NY), reverse=True):
        # Native NAVER provider rows use raw_*; keep compatibility with
        # already-normalized rows used by other sources/tests.
        title = _clean(row.get("title") or row.get("raw_title"))
        url = str(
            row.get("originallink") or row.get("raw_original_link")
            or row.get("link") or row.get("raw_link") or ""
        ).strip()
        publisher = _publisher(url)
        published = _published(row)
        normalized = re.sub(r"[^가-힣a-z0-9]", "", title.casefold())
        if not (title and publisher and published):
            continue
        if not any(word in title for word in CLOSE_NAMES) or not any(word in title for word in FINISH_WORDS):
            continue
        if published.date() != session_date or published.hour < 13:
            continue
        if published.astimezone(UTC) > now + datetime.timedelta(minutes=2):
            continue
        if publisher in seen_publishers or normalized in seen_titles or url in seen_urls:
            continue
        selected.append({"title": title, "url": url, "published_at": published.isoformat(), "publisher": publisher})
        seen_publishers.add(publisher)
        seen_titles.add(normalized)
        seen_urls.add(url)
        if len(selected) >= 8:
            break
    return selected


def collect_articles(session_date, now_utc=None, search=None, reader=None):
    """Read up to eight candidates, keep two or three genuinely readable bodies."""
    fetch = search or naver_news.fetch_news
    rows = fetch(QUERY, display=20, raise_on_error=True)
    candidates = select_close_articles(rows, session_date, now_utc=now_utc)
    if not candidates:
        return []
    read = reader or read_selected_article_details
    details = read(candidates, limit=len(candidates), with_sources=True)
    verified = []
    for article, detail in zip(candidates, details):
        if not isinstance(detail, dict):
            continue
        body = _clean(detail.get("text"))
        source = detail.get("source")
        # Avoid sending short search snippets or generic HTML metadata to AI.
        if source not in {"jsonld_article_body", "article_or_main_paragraphs", "all_page_paragraphs"} or len(body) < 450:
            continue
        # Preserve the actual extracted article text, not just a search snippet.
        # Bound only the combined provider request budget; prefer two complete
        # articles to three heavily truncated articles.
        if len(verified) >= 2 and sum(len(a["body"]) for a in verified) + len(body) > 11000:
            continue
        verified.append({**article, "body": body, "body_source": source})
        if len(verified) == 3:
            break
    return verified


US_CLOSE_PROMPT = """제공된 기사를 근거로 미국장은 어땠어? 를 작성해

제목은 핵심만 짧게, 내용은 쉽고 구체적으로, 해시태그는 최대 3개. 반말로 답변해.

한국어 JSON 객체만 반환해:
{"issues":[{"headline":"제목","summary":"기사에 근거한 내용","tags":["#핵심어"],"source_ids":[1]}]}"""


def _prompt(articles, session_date):
    news = [
        {"source_id": index + 1, "title": article["title"], "content": article["body"]}
        for index, article in enumerate(articles)
    ]
    return json.dumps(news, ensure_ascii=False)


def _generate(articles, session_date):
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise RuntimeError("groq_key_missing")
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": US_CLOSE_PROMPT},
            {"role": "user", "content": _prompt(articles, session_date)},
        ],
        "temperature": 0.2,
        "max_completion_tokens": 1150,
        "reasoning_effort": "low",
        "stream": False,
    }
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                 "User-Agent": "gaemiGTP-us-close/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=35) as response:
        result = json.loads(response.read().decode("utf-8"))
    choices = result.get("choices") or []
    text = str((choices[0].get("message") or {}).get("content") or "").strip() if choices else ""
    if len(text) < 100:
        raise RuntimeError("insufficient_ai_answer")
    return text[:3600]


def _connection():
    import psycopg
    db_url = os.environ.get("NEWS_DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("news_database_missing")
    return psycopg.connect(db_url, connect_timeout=5)


def read_brief():
    """Read-only Render path. Never initiate AI, news collection or article fetch."""
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT session_date, content, published_at FROM public.us_market_close_briefs
                WHERE status='published' AND expires_at > now()
                ORDER BY session_date DESC LIMIT 1"""
            )
            row = cur.fetchone()
    if not row:
        return None
    return {"session_date": row[0].isoformat(), "content": row[1],
            "published_at": row[2].isoformat()}


def publish_once(now_utc=None, search=None, reader=None, generator=None):
    """One claim per NY trading date; no automatic retry on AI failures.

    Run only on the DO worker after US close. The claim is saved BEFORE the
    provider call, preventing duplicate spending from a retried job.
    """
    now = now_utc or datetime.datetime.now(UTC)
    market_time = now.astimezone(NY)
    session_date = market_time.date()
    if market_time.hour < 16 or market_time.weekday() >= 5:
        return {"status": "market_not_closed", "session_date": session_date.isoformat()}
    articles = collect_articles(session_date, now_utc=now, search=search, reader=reader)
    if len(articles) < 2:
        return {"status": "insufficient_full_articles", "session_date": session_date.isoformat(),
                "count": len(articles)}
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.us_market_close_briefs WHERE expires_at < now()")
            cur.execute(
                """INSERT INTO public.us_market_close_briefs
                (session_date,status,published_at,expires_at,source_manifest,model)
                VALUES (%s,'processing',now(),now()+interval '24 hours',%s::jsonb,%s)
                ON CONFLICT (session_date) DO NOTHING RETURNING session_date""",
                (session_date, json.dumps([
                    {key: a[key] for key in ("title", "url", "published_at", "publisher")}
                    for a in articles
                ], ensure_ascii=False), MODEL),
            )
            claimed = cur.fetchone() is not None
    if not claimed:
        return {"status": "already_attempted", "session_date": session_date.isoformat()}
    try:
        answer = (generator or _generate)(
            articles, session_date,
        )
        with _connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE public.us_market_close_briefs SET status='published',
                    content=%s,published_at=now(),expires_at=now()+interval '24 hours'
                    WHERE session_date=%s AND status='processing'""",
                    (answer, session_date),
                )
        return {"status": "published", "session_date": session_date.isoformat(),
                "article_count": len(articles)}
    except Exception:
        with _connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE public.us_market_close_briefs SET status='failed' WHERE session_date=%s",
                    (session_date,),
                )
        raise
