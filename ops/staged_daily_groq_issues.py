"""Staged Groq issue response validator; not connected to the worker."""
import json
import re
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

MODEL = "openai/gpt-oss-20b"
PROMPT = """제공된 종목의 현재 주가와 뉴스 원문을 분석해서 친구처럼 반말로 답변해.

1. 현재 주가가 상승했으면 왜 상승했어?
   현재 주가가 하락했으면 왜 하락했어?

2. 현재 해당 종목에서 중요한 이슈를 0~3개 선정해.

각 이슈의 태그는 최대 3개이고 # 기호 없이 작성해.
한국어 JSON 객체만 반환해:
{"price_reason":{"headline":"상승 또는 하락 이유 제목","summary":"상승 또는 하락한 이유","source_ids":[1]},"issues":[{"headline":"이슈 제목","summary":"이슈 내용","tags":["키워드1"],"source_ids":[1]}]}"""


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
            # Citation IDs are model output, not trusted application metadata.
            # A malformed ID must not fail the entire stock analysis.
            ids = item["source_ids"]
            cleaned = []
            for raw_id in ids if isinstance(ids, list) else []:
                if type(raw_id) is int:
                    source_id = raw_id
                elif isinstance(raw_id, str) and raw_id.strip().isdecimal():
                    source_id = int(raw_id.strip())
                else:
                    continue
                if source_id > 0 and source_id not in cleaned:
                    cleaned.append(source_id)
            item["source_ids"] = cleaned[:3]
    return issues


def parse_analysis(response_text):
    """Validate the new reason + 0-3 sourced issues without changing issue storage."""
    result = json.loads(response_text)
    if not isinstance(result, dict) or set(result) != {"price_reason", "issues"}:
        raise ValueError("Invalid analysis response")
    reason = result["price_reason"]
    if not isinstance(reason, dict) or set(reason) != {"headline", "summary", "source_ids"}:
        raise ValueError("Invalid price reason")
    if not all(isinstance(reason[k], str) and reason[k].strip() for k in ("headline", "summary")):
        raise ValueError("Invalid price reason")
    if not isinstance(reason["source_ids"], list):
        raise ValueError("Invalid article source IDs")
    reason_ids = []
    for value in reason["source_ids"]:
        if type(value) is int and value > 0 and value not in reason_ids:
            reason_ids.append(value)
    issues = parse_issues(json.dumps({"issues": result["issues"]}, ensure_ascii=False))
    for issue in issues:
        issue["tags"] = [tag.lstrip("#") for tag in issue["tags"]]
    return {"price_reason": {**reason, "source_ids": reason_ids[:3]}, "issues": issues}


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


def recent_ai_articles(articles, *, now=None):
    """Keep collected articles, newest first, without an intermediate 24h filter."""
    if now is not None and now.tzinfo is None:
        raise ValueError("Expected timezone-aware now")
    return sorted(
        (article for article in (articles or []) if isinstance(article, dict)),
        key=_article_published_epoch, reverse=True,
    )


def _safe_token_usage(response):
    """Use Groq's reported counters only; do not estimate or log content."""
    raw = response.get("usage") if isinstance(response, dict) else None
    if not isinstance(raw, dict):
        return {}
    result = {
        key: raw[key] for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        if type(raw.get(key)) is int and 0 <= raw[key] <= 100000000
    }
    details = raw.get("completion_tokens_details")
    if isinstance(details, dict) and type(details.get("reasoning_tokens")) is int:
        result["reasoning_tokens"] = details["reasoning_tokens"]
    return result


_EVENT_DATE_PATTERN = re.compile(r"(?:(?:20\d{2})년\s*)?(?:1[0-2]|0?[1-9])월\s*(?:3[01]|[12]\d|0?[1-9])일")
_PRIOR_MONTH_PATTERN = re.compile(r"지난\s*(?:1[0-2]|0?[1-9])월")


def _historical_event_mentions(content, published_at):
    """Tag explicit old dates from the actual article, never infer an event date."""
    try:
        epoch = _article_published_epoch({"published_at": published_at})
        if epoch == float("-inf"):
            return []
        publication = datetime.fromtimestamp(epoch, timezone.utc)
    except (ValueError, OverflowError, OSError):
        return []
    hits = []
    for match in _EVENT_DATE_PATTERN.finditer(content):
        month_day = re.search(r"(\d{1,2})월\s*(\d{1,2})일", match.group())
        if not month_day:
            continue
        month, day = map(int, month_day.groups())
        explicit_year = re.search(r"(20\d{2})년", match.group())
        year = int(explicit_year.group(1)) if explicit_year else publication.year
        try:
            event_day = datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            continue
        if (publication - event_day).total_seconds() >= 7 * 86400:
            if match.group() not in hits:
                hits.append(match.group())
    for match in _PRIOR_MONTH_PATTERN.finditer(content):
        if match.group() not in hits:
            hits.append(match.group())
    return hits[:3]


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
            "historical_event_mentions": _historical_event_mentions(content, published_at),
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
        # Retain genuinely sourced issues even when another citation is wrong.
        # Never invent IDs or keep an issue lacking any real dated source.
        matched = []
        for source_id in issue.get("source_ids") or []:
            if type(source_id) is int and source_id in valid and source_id not in matched:
                matched.append(source_id)
        if matched:
            verified.append({**issue, "source_ids": matched[:3]})
    if len(verified) != len(issues):
        print("[news-ai] missing_article_source dropped=%s" %
              (len(issues) - len(verified)), flush=True)
    return verified


def analyze_news(stock_name, articles, *, usage_callback=None, price_context=None):
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
                {"stock": stock_name, "price": price_context or {}, "news": news[:10]}, ensure_ascii=False)},
        ],
        "temperature": 0.2,
        "reasoning_effort": "low",
        "max_completion_tokens": 1000,
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
    usage = _safe_token_usage(result)
    if usage and callable(usage_callback):
        usage_callback(usage)
    choice = result["choices"][0]
    if choice.get("finish_reason") == "length":
        # A partial JSON response must never be marked as a successful AI issue.
        raise ValueError("model_response_truncated")
    content = choice["message"].get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("model_response_empty")
    parsed = parse_analysis(content)
    parsed["issues"] = _keep_sourced_issues(parsed["issues"], news)
    valid_source_ids = {
        row["source_id"] for row in news
        if _has_verifiable_published_at(row.get("published_at"))
    }
    reason = parsed["price_reason"]
    reason["source_ids"] = [source_id for source_id in reason["source_ids"]
                            if source_id in valid_source_ids]
    if not reason["source_ids"]:
        parsed["price_reason"] = None
    return parsed



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
