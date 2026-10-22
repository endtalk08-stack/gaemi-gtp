"""US close editorial: three date-verified NAVER indices and three verified original articles.

The existing DigitalOcean timer writes one Neon result; Render reads only.
The user-approved Groq 120B prompt remains byte-for-byte unchanged.
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
from backend.services.us_market_close_runtime import verified_originals, verified_indices

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
    """Only three genuinely extracted US-close articles; never snippets."""
    return verified_originals(session_date, now_utc=now_utc, search=search, reader=reader)

US_CLOSE_PROMPT = """제공된 기사를 근거로 미국장은 어땠어? 를 작성해

제목은 핵심만 짧게, 내용은 쉽고 구체적으로, 해시태그는 최대 3개. 반말로 답변해.

한국어 JSON 객체만 반환해:
{"issues":[{"headline":"제목","summary":"쉽고 구체적인 내용","tags":["#핵심어"],"source_ids":[1]}]}"""


def _prompt(articles, session_date, indices=None):
    """Pass original bodies, NY session and exact NAVER index closes."""
    news = [
        {"source_id": index + 1, "title": article["title"], "description": str(article["description"])[:1300]}
        for index, article in enumerate(articles)
    ]
    return json.dumps({
        "session_date_et": session_date.isoformat(),
        "market_indices": indices if indices is not None else [],
        "news": news,
    }, ensure_ascii=False)

def _generate(articles, session_date, indices=None):
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise RuntimeError("groq_key_missing")
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": US_CLOSE_PROMPT},
            {"role": "user", "content": _prompt(articles, session_date, indices=indices)},
        ],
        "temperature": 0.2,
        "max_completion_tokens": 1800,
        "reasoning_effort": "low",
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "us_close_issue_briefs",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "issues": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "headline": {"type": "string"},
                                    "summary": {"type": "string"},
                                    "tags": {"type": "array", "items": {"type": "string"}},
                                    "source_ids": {"type": "array", "items": {"type": "integer"}},
                                },
                                "required": ["headline", "summary", "tags", "source_ids"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["issues"],
                    "additionalProperties": False,
                },
            },
        },
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


def _structured_brief(raw_content):
    """Public display fields only; no publisher originals or AI source manifests."""
    try:
        document = json.loads(raw_content)
    except (TypeError, ValueError):
        return None
    if not isinstance(document, dict):
        return None
    indices = document.get("market_indices")
    issues = document.get("issues")
    date = document.get("session_date_et")
    if not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        return None
    if not isinstance(indices, list) or len(indices) != 3:
        return None
    if not isinstance(issues, list) or not issues:
        return None
    expected_names = ("다우존스", "나스닥 종합", "S&P 500")
    clean_indices = []
    for index, expected in zip(indices, expected_names):
        if not isinstance(index, dict) or index.get("name") != expected:
            return None
        if index.get("session_date_et") != date:
            return None
        try:
            close, change = float(index["close"]), float(index["change_pct"])
        except (KeyError, TypeError, ValueError):
            return None
        if not (0 < close < 10000000 and -40 < change < 40):
            return None
        clean_indices.append({"name": expected, "close": close, "change_pct": change})
    clean_issues = []
    for issue in issues[:3]:
        if not isinstance(issue, dict):
            continue
        headline = str(issue.get("headline") or "").strip()
        summary = str(issue.get("summary") or "").strip()
        tags = issue.get("tags")
        if not headline or not summary:
            continue
        clean_issues.append({
            "headline": headline[:200], "summary": summary[:2600],
            "tags": [str(tag).strip()[:48] for tag in
                     (tags if isinstance(tags, list) else [])[:3] if str(tag).strip()],
        })
    if not clean_issues:
        return None
    return {"session_date_et": date, "market_indices": clean_indices, "issues": clean_issues}


def _display_brief_content(raw_content):
    """Title, three verified closes, AI explanation, hashtags — in that order."""
    structured = _structured_brief(raw_content)
    if structured is None:
        # Existing unstructured/legacy text continues to render unchanged.
        return raw_content
    parts = []
    for issue in structured["issues"]:
        parts.append(issue["headline"])
        for index in structured["market_indices"]:
            parts.append(f'{index["name"]} {index["close"]:,.2f} ({index["change_pct"]:+.2f}%)')
        parts.append(issue["summary"])
        tags = " ".join("#" + tag.lstrip("#") for tag in issue["tags"])
        if tags:
            parts.append(tags)
    return "\n\n".join(parts)


def read_brief():
    """Read-only Render path; return sanitized structured presentation for UI."""
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
    presentation = _structured_brief(row[1])
    return {"session_date": row[0].isoformat(), "content": _display_brief_content(row[1]),
            "presentation": presentation, "published_at": row[2].isoformat()}


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
    # The 08:40 KST fallback must never repeat Naver article fetching or
    # spend a second AI call after the 07:00 run already claimed this session.
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM public.us_market_close_briefs WHERE session_date=%s",
                (session_date,),
            )
            prior = cur.fetchone()
    if prior is not None:
        return {"status": "already_attempted", "session_date": session_date.isoformat()}
    # All three indices and news must agree with the completed NY trading day.
    # Fail before any database claim/AI usage if one is missing or stale.
    indices = verified_indices(session_date)
    articles = collect_articles(session_date, now_utc=now, search=search, reader=reader)
    if len(articles) != 3:
        return {"status": "insufficient_verified_originals", "session_date": session_date.isoformat(),
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
        if generator:
            answer = generator(articles, session_date, indices)
        else:
            answer = _generate(articles, session_date, indices=indices)
        try:
            result = json.loads(answer)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("us_close_ai_invalid_json") from exc
        if not isinstance(result, dict) or not isinstance(result.get("issues"), list) or not result["issues"]:
            raise RuntimeError("us_close_ai_missing_issues")
        issues = []
        for entry in result["issues"][:3]:
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("headline") or "").strip()
            summary = str(entry.get("summary") or "").strip()
            if not title or not summary or re.search(r"코스피|코스닥|국내증시", title + summary):
                continue
            source_ids = [i for i in (entry.get("source_ids") or []) if isinstance(i, int) and 1 <= i <= 3]
            issues.append({
                "headline": title[:200], "summary": summary[:2600],
                "tags": [str(t)[:48] for t in (entry.get("tags") or [])[:3]],
                "source_ids": source_ids,
            })
        if not issues:
            raise RuntimeError("us_close_ai_no_usable_us_market_analysis")
        # Persist only AI editorial and verified numeric market facts, not
        # copyrighted publisher original bodies or NAVER snippet texts.
        content = json.dumps({
            "session_date_et": session_date.isoformat(),
            "market_indices": indices, "issues": issues,
        }, ensure_ascii=False)
        with _connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE public.us_market_close_briefs SET status='published',
                    content=%s,published_at=now(),expires_at=now()+interval '24 hours'
                    WHERE session_date=%s AND status='processing'""",
                    (content, session_date),
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
