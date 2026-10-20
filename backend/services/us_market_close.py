"""US market close editorial: NAVER headlines/snippets -> one AI -> Neon.

Runs only on the independent DigitalOcean close worker. No article-page fetches,
stock-news processing, or AI calls from Render. One generated brief per session.
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

NY = ZoneInfo("America/New_York")
KST = ZoneInfo("Asia/Seoul")
UTC = datetime.timezone.utc
QUERY = "뉴욕증시 마감"
MODEL = "openai/gpt-oss-120b"
def _clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", "", str(value or "")))).strip()


def _publisher(url):
    try:
        return urllib.parse.urlsplit(str(url or "")).hostname or ""
    except ValueError:
        return ""


def _published(row):
    try:
        parsed = parsedate_to_datetime(str(row.get("pubDate") or row.get("raw_pub_date") or ""))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(KST)
    except (TypeError, ValueError, IndexError):
        return None


def select_close_articles(rows, session_date, now_utc=None):
    """Latest 10 NAVER results published after the US market close, in Korean time."""
    market_close_kst = datetime.datetime.combine(
        session_date, datetime.time(16), tzinfo=NY
    ).astimezone(KST)
    selected = []
    for row in sorted(
        (r for r in (rows or []) if isinstance(r, dict)),
        key=lambda r: _published(r) or datetime.datetime.min.replace(tzinfo=KST),
        reverse=True,
    ):
        published = _published(row)
        if published is None or published < market_close_kst:
            continue
        url = str(
            row.get("raw_original_link") or row.get("originallink")
            or row.get("raw_link") or row.get("link") or ""
        ).strip()
        selected.append({
            "title": _clean(row.get("raw_title") or row.get("title")),
            "description": _clean(row.get("raw_description") or row.get("description")),
            "url": url,
            "published_at": published.isoformat(),
            "publisher": _publisher(url),
        })
        if len(selected) >= 10:
            break
    return selected


def collect_articles(session_date, now_utc=None, search=None, reader=None):
    """Use NAVER API snippets only. Never fetch a publisher article page."""
    fetch = search or naver_news.fetch_news
    rows = fetch(QUERY, display=10, raise_on_error=True)
    selected = select_close_articles(rows, session_date, now_utc=now_utc)
    print(
        f"[us-close] naver_search={len(rows or [])} snippets_selected={len(selected)} "
        f"session={session_date.isoformat()}",
        flush=True,
    )
    return selected


US_CLOSE_PROMPT = """제공된 기사를 근거로 미국장은 어땠어? 를 작성해

제목은 핵심만 짧게, 내용은 쉽고 구체적으로, 해시태그는 최대 3개. 반말로 답변해.

한국어 JSON 객체만 반환해:
{"issues":[{"headline":"제목","summary":"기사에 근거한 내용","tags":["#핵심어"],"source_ids":[1]}]}"""


def _prompt(articles, session_date):
    news = [
        {"source_id": index + 1, "title": article["title"], "description": article["description"]}
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
        "max_completion_tokens": 1800,
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


def _display_brief_content(raw_content):
    """Display stored AI JSON as title, summary and hashtags; retain source JSON in Neon."""
    try:
        result = json.loads(raw_content)
    except (TypeError, ValueError):
        return raw_content
    if not isinstance(result, dict) or not isinstance(result.get("issues"), list):
        return raw_content
    sections = []
    for issue in result["issues"]:
        if not isinstance(issue, dict):
            continue
        title = str(issue.get("headline") or "").strip()
        summary = str(issue.get("summary") or "").strip()
        if not title or not summary:
            continue
        tags = issue.get("tags")
        tags = tags if isinstance(tags, list) else []
        hashtags = " ".join(
            "#" + str(tag).strip().lstrip("#")
            for tag in tags[:3] if str(tag).strip().lstrip("#")
        )
        sections.append("\n\n".join(part for part in (title, summary, hashtags) if part))
    return "\n\n".join(sections) if sections else raw_content


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
    return {"session_date": row[0].isoformat(), "content": _display_brief_content(row[1]),
            "published_at": row[2].isoformat()}


def publish_once(now_utc=None, search=None, reader=None, generator=None):
    """One claim per NY trading date; no automatic repeat of a paid AI call.

    Run only on the DO worker after US close. The claim is saved BEFORE the
    provider call, preventing duplicate spending from a retried job.
    """
    now = now_utc or datetime.datetime.now(UTC)
    market_time = now.astimezone(NY)
    session_date = market_time.date()
    if market_time.hour < 16 or market_time.weekday() >= 5:
        return {"status": "market_not_closed", "session_date": session_date.isoformat()}
    articles = collect_articles(session_date, now_utc=now, search=search, reader=reader)
    if not articles:
        return {"status": "insufficient_news_snippets", "session_date": session_date.isoformat(),
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
