"""Staged Groq issue response validator; not connected to the worker."""
import json
from datetime import datetime
from email.utils import parsedate_to_datetime

MODEL = "openai/gpt-oss-20b"
PROMPT = """주가에 영향을 줄 핵심 이슈를 0-3개 선정해.

제목은 핵심 짧게, 내용은 쉽게 설명 , 해시태그는 각각 최대 3개. 반말로 답변해

한국어 JSON만 반환해:

{"issues":[{"headline":"제목","summary":"내용","tags":["#핵심어"],"source_ids":[1]}]}"""


def parse_issues(response_text):
    result = json.loads(response_text)
    if not isinstance(result, dict) or set(result) != {"issues"}:
        raise ValueError("Invalid issue response")
    issues = result["issues"]
    if not isinstance(issues, list) or len(issues) > 3:
        raise ValueError("Expected 0-3 issues")
    for item in issues:
        if not isinstance(item, dict) or not {"headline", "summary", "tags"} <= set(item) or set(item) - {"headline", "summary", "tags", "source_ids"}:
            raise ValueError("Invalid fields")
        if any(not isinstance(item[k], str) or not item[k].strip() for k in ("headline", "summary")):
            raise ValueError("Invalid text")
        tags = item["tags"]
        if not isinstance(tags, list) or len(tags) > 3 or any(not isinstance(t, str) or not t.startswith("#") for t in tags):
            raise ValueError("Invalid tags")
        if "source_ids" in item:
            ids = item["source_ids"]
            if not isinstance(ids, list) or not 1 <= len(ids) <= 3 or any(
                type(source_id) is not int or source_id < 1 for source_id in ids
            ) or len(set(ids)) != len(ids):
                raise ValueError("Invalid article source IDs")
    return issues


def _article_published_epoch(article):
    """Sort both ISO and RFC news timestamps newest-first; undated last."""
    if not isinstance(article, dict):
        return float("-inf")
    value = str(article.get("published_at") or article.get("pubDate") or "").strip()
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            timestamp = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return float("-inf")
    return timestamp.timestamp() if timestamp.tzinfo is not None else float("-inf")


def build_model_news(articles):
    """Number only the 10 latest usable articles; share IDs with storage."""
    news, sources = [], []
    char_budget = 9000
    for article in sorted(articles, key=_article_published_epoch, reverse=True):
        if len(news) >= 10:
            break
        if not isinstance(article, dict) or char_budget <= 0:
            continue
        title = str(article.get("title") or "")[:300]
        content = str(article.get("body") or article.get("description") or "")
        if not title.strip() or not content.strip():
            continue
        content = content[:min(2400, char_budget)]
        char_budget -= len(content)
        published_at = str(article.get("pubDate") or article.get("published_at") or "")[:80]
        news.append({
            "source_id": len(news) + 1,
            "title": title,
            "content": content,
            "published_at": published_at,
        })
        link = str(article.get("url") or article.get("link") or "").strip()
        sources.append({
            "source_id": len(news),
            "title": title,
            "description": str(article.get("description") or "")[:1200],
            "published_at": published_at,
            "source": str(article.get("source") or "")[:120],
            "url": link if link.startswith(("https://", "http://")) else "",
        })
    return news, sources


def issue_source_metadata(issues, articles):
    """Resolve model-chosen IDs against originals; never invent an article URL/date."""
    _, source_records = build_model_news(articles)
    return [[
        source_records[source_id - 1]
        for source_id in issue.get("source_ids", [])
        if type(source_id) is int and 1 <= source_id <= len(source_records)
    ][:3] for issue in issues]


def _has_verifiable_published_at(value):
    """Article timestamps need an explicit timezone to be displayed as KST."""
    stamp = str(value or "").strip()
    if not stamp:
        return False
    try:
        dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(stamp)
        except (TypeError, ValueError, IndexError):
            return False
    return dt.tzinfo is not None and dt.utcoffset() is not None


def _keep_sourced_issues(issues, news):
    """One failed AI citation never becomes a fabricated article timestamp."""
    valid = {
        item["source_id"] for item in news
        if _has_verifiable_published_at(item.get("published_at"))
    }
    verified = []
    for issue in issues:
        source_ids = issue.get("source_ids")
        if (isinstance(source_ids, list) and 1 <= len(source_ids) <= 3
            and all(type(i) is int and i in valid for i in source_ids)
            and len(set(source_ids)) == len(source_ids)):
            verified.append(issue)
    if len(verified) != len(issues):
        print("[news-ai] missing_article_source dropped=%s" %
              (len(issues) - len(verified)), flush=True)
    return verified


def analyze_news(stock_name, articles):
    """One Groq request for one stock. Caller handles once-daily scheduling."""
    import os
    import urllib.request

    if not articles:
        return []
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Groq key is not configured on the news worker")

    news, _ = build_model_news(articles)
    if not news:
        return []

    data = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": json.dumps(
                {"stock": stock_name, "news": news[:10]}, ensure_ascii=False)},
        ],
        "temperature": 0.2,
        "max_completion_tokens": 900,
        "response_format": {"type": "json_object"},
    }, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=data,
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
            "User-Agent": "gaemiGTP-ai-test/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=35) as response:
        result = json.load(response)
    issues = parse_issues(result["choices"][0]["message"]["content"])
    return _keep_sourced_issues(issues, news)



def issue_records(issues, *, market, symbol, exchange_day):
    """Map validated AI issues to existing news_ai_issues columns.

    The database supplies generated_at; article publication times remain separate.
    No article-level evidence or invented timestamps are added.
    """
    from datetime import date

    if market not in ("US", "KR") or not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("Invalid market or symbol")
    if not isinstance(exchange_day, date) or hasattr(exchange_day, "hour"):
        raise ValueError("Invalid exchange day")
    if not isinstance(issues, list):
        raise ValueError("Invalid issues")
    validated = parse_issues(json.dumps({"issues": issues}, ensure_ascii=False))
    return [
        {
            "market": market,
            "symbol": symbol,
            "exchange_day": exchange_day,
            "headline": item["headline"],
            "summary": item["summary"],
            "tags": item["tags"],
            "model_id": MODEL,
        }
        for item in validated
    ]
