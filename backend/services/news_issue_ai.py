"""Opt-in AI news issues: three reserved calls per stock per exchange-local date."""
import datetime
import hashlib
import json
import os
import re
import threading
from zoneinfo import ZoneInfo

_LOCK = threading.Lock()

def _day(market):
    tz = "America/New_York" if market in ("미국", "us") else "Asia/Seoul"
    return datetime.datetime.now(ZoneInfo(tz)).date().isoformat()

def _validated(text, articles, stock):
    try:
        data = json.loads(text)
        entries = data.get("issues", [])
    except (ValueError, AttributeError, TypeError):
        return []
    if not isinstance(entries, list):
        return []
    result, seen = [], set()
    sources = {str(i + 1): article for i, article in enumerate(articles)}
    number = re.compile(r"(?<![A-Za-z가-힣\d])\d[\d,]*(?:\.\d+)?")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        ids = entry.get("source_ids")
        title, summary, tags = entry.get("headline"), entry.get("summary"), entry.get("tags")
        kind, tone = entry.get("category"), entry.get("direction")
        event_key = str(entry.get("event_key") or "").strip().lower()[:70]
        if (not isinstance(ids, list) or not 1 <= len(ids) <= 5
                or any(str(x) not in sources for x in ids)
                or not isinstance(title, str) or not 7 <= len(title) <= 44
                or not isinstance(summary, str) or not 20 <= len(summary) <= 450
                or not isinstance(tags, list) or not 1 <= len(tags) <= 4
                or any(not isinstance(x, str) or not 2 <= len(x) <= 24 for x in tags)
                or kind not in ("company", "market")
                or tone not in ("positive", "negative", "neutral", "mixed")
                or not event_key or event_key in seen):
            continue
        evidence = " ".join(sources[str(i)]["body"] + " " + sources[str(i)]["title"] for i in ids)
        if not set(number.findall(title + " " + summary)).issubset(set(number.findall(evidence))):
            continue
        seen.add(event_key)
        first = sources[str(ids[0])]
        result.append({
            "headline": title.strip(), "summary": summary.strip(),
            "tags": list(dict.fromkeys(x.strip() for x in tags)),
            "material_type": kind, "material_direction": tone,
            "event_key": event_key, "stock_names": [stock],
            "evidence_source": "verified_article_body_ai",
            "source_urls": [sources[str(i)]["url"] for i in ids],
            "time": first["time"], "reaction_at": first["reaction_at"]
        })
        if len(result) == 3:
            break
    return result

def _analyze_and_save(stock, code, day, fingerprint, candidates):
    from backend.database.news_ai_store import complete_issue_call, fail_issue_call
    prompt = (
        "다음 뉴스 원문에서 중복 사건을 통합하여 서로 다른 핵심 사건 최대 3개를 골라라. "
        "시장 공통 재료와 기업 자체 재료를 구분해 다양하게 선정하고 중요도를 우선해라. "
        "각 제목, 원문 근거 중심 설명, 키워드, 시장/기업 구분, 호재/악재 방향을 작성하라. "
        "주가 원인이나 수치를 추측하지 말고 같은 사건은 하나로 묶어라. "
        "반드시 순수 JSON으로만 답해: {\"issues\":[{\"source_ids\":[1],"
        "\"headline\":\"사건 이슈\",\"summary\":\"원문에 명시된 사실을 설명한다.\","
        "\"tags\":[\"사건명\"],\"category\":\"market\","
        "\"direction\":\"negative\",\"event_key\":\"고유사건명\"}]}"
    )
    try:
        from .ai_test import _groq_answer
        answer, _, _ = _groq_answer(
            os.environ.get("NEWS_ISSUE_AI_MODEL", "openai/gpt-oss-20b"),
            prompt, {"stock": stock, "articles": [
                {"id": i + 1, "title": x["title"], "body": x["body"]}
                for i, x in enumerate(candidates)]},
            max_completion_tokens=1100)
        selected = _validated(answer, candidates, stock)
        if selected:
            if not complete_issue_call(code, stock, day, fingerprint, selected):
                fail_issue_call(code, stock, day, fingerprint)
        else:
            fail_issue_call(code, stock, day, fingerprint)
    except Exception as exc:
        print("[news issue AI] analysis failed: " + type(exc).__name__, flush=True)
        fail_issue_call(code, stock, day, fingerprint)


def select_ai_issues(stock, market, articles, fallback):
    """Never block the news response waiting for an AI provider call.

    Reservations and cached results live in Neon across deploys, not /tmp.
    """
    if os.environ.get("NEWS_ISSUE_AI_ENABLED") != "1" or not os.environ.get("GROQ_API_KEY"):
        return fallback
    allowlist = {name.strip() for name in os.environ.get("NEWS_ISSUE_AI_STOCKS", "").split(",") if name.strip()}
    if allowlist and stock not in allowlist:
        return fallback
    candidates = [{
        "title": str(row.get("title") or "")[:180],
        "body": str(row.get("body") or "")[:1600],
        "url": str(row.get("url") or "")[:300],
        "time": str(row.get("time") or ""),
        "reaction_at": str(row.get("reaction_at") or "")
    } for row in articles if len(str(row.get("body") or "").strip()) >= 60][:10]
    if not candidates:
        return fallback
    fingerprint = hashlib.sha256(json.dumps(
        candidates, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    code = "US" if market in ("미국", "us", "US") else "KR"
    day = _day(market)
    from backend.database.news_ai_store import reserve_issue_call, fail_issue_call
    state, cached = reserve_issue_call(code, stock, day, fingerprint)
    if state == "reserved":
        try:
            threading.Thread(
                target=_analyze_and_save,
                args=(stock, code, day, fingerprint, candidates),
                name="news-issue-ai", daemon=True,
            ).start()
        except Exception:
            fail_issue_call(code, stock, day, fingerprint)
    return cached if cached else fallback
