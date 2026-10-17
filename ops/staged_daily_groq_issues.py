"""Staged Groq issue response validator; not connected to the worker."""
import json

MODEL = "openai/gpt-oss-20b"
PROMPT = """주가에 영향을 줄 핵심 이슈를 0-3개 선정해.

제목은 핵심 짧게, 내용은 쉽게 설명 , 해시태그는 각각 최대 3개. 반말로 답변해

한국어 JSON만 반환해:

{"issues":[{"headline":"제목","summary":"내용","tags":["#핵심어"]}]}"""


def parse_issues(response_text):
    result = json.loads(response_text)
    if not isinstance(result, dict) or set(result) != {"issues"}:
        raise ValueError("Invalid issue response")
    issues = result["issues"]
    if not isinstance(issues, list) or len(issues) > 3:
        raise ValueError("Expected 0-3 issues")
    for item in issues:
        if not isinstance(item, dict) or set(item) != {"headline", "summary", "tags"}:
            raise ValueError("Invalid fields")
        if any(not isinstance(item[k], str) or not item[k].strip() for k in ("headline", "summary")):
            raise ValueError("Invalid text")
        tags = item["tags"]
        if not isinstance(tags, list) or len(tags) > 3 or any(not isinstance(t, str) or not t.startswith("#") for t in tags):
            raise ValueError("Invalid tags")
    return issues


def analyze_news(stock_name, articles):
    """One Groq request for one stock. Caller handles once-daily scheduling."""
    import os
    import urllib.request

    if not articles:
        return []
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Groq key is not configured on the news worker")

    news = []
    char_budget = 9000
    for article in articles:
        if not isinstance(article, dict) or len(news) >= 20 or char_budget <= 0:
            continue
        title = str(article.get("title") or "")[:300]
        content = str(article.get("body") or article.get("description") or "")
        if not title.strip() or not content.strip():
            continue
        content = content[:min(2400, char_budget)]
        char_budget -= len(content)
        news.append({
            "title": title,
            "content": content,
            "published_at": str(article.get("pubDate") or article.get("published_at") or "")[:80],
        })
    if not news:
        return []

    data = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": json.dumps(
                {"stock": stock_name, "news": news[:20]}, ensure_ascii=False)},
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
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=35) as response:
        result = json.load(response)
    return parse_issues(result["choices"][0]["message"]["content"])
