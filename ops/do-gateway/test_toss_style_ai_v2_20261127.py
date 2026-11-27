"""Read-only test v2: relevance-filtered articles with bodies, stricter keyword rules.

Fetches news, calls Groq once per stock, validates, prints. Writes nothing anywhere.
"""
import datetime as dt
import json
import os
import re
import ssl
import sys
import time
import urllib.request
from email.utils import parsedate_to_datetime

sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.services import news_feed
from backend.services.news_result import build_stock_news_result
from backend.services.news_detail import read_selected_article_details

MODEL = "openai/gpt-oss-120b"
SYSTEM = """너는 미국 주식 뉴스를 한국 개인투자자에게 쉽게 설명하는 분석가야.
주어진 뉴스 기사만 근거로 오늘 이 종목이 왜 움직였는지 정리해.

규칙
1. 반드시 지정된 JSON 형식으로만 답해. 다른 말은 쓰지 마.
2. keywords는 항상 정확히 3개. 각 4~12자 명사구. 기사에 실제로 나온 사건·재료만.
   예: "차세대 GPU 기대", "목표가 상향", "AI 서버 투자"
   "주가 상승", "주가 폭등", "급등", "하락" 같은 결과 표현은 키워드로 쓰지 마.
3. headline_keyword는 keywords 중 주가 움직임의 가장 직접적인 이유 1개를 그대로 복사.
4. lines는 정확히 3개, 각 1문장, 해요체, 60자 안팎.
   - lines[0]: 주가가 움직인 직접 원인 (어떤 뉴스·사건 때문인지)
   - lines[1]: 그 원인이 시장·업종·수급에 어떻게 이어졌는지
   - lines[2]: 회사 소개 (company_profile이 있으면 그대로, 없으면 무슨 회사인지 1문장)
5. 숫자(주가, 등락률, 퍼센트)는 쓰지 마. 숫자는 화면이 따로 붙여.
6. confidence는 이 종목이 주인공인 기사에서 원인을 찾았을 때만 "high".
   기사에 없는 이유를 지어내지 마. 근거가 약하면 confidence를 "low"로 하고
   lines[0]에 "뚜렷한 이유가 담긴 뉴스는 확인되지 않았어요."라고 써.
7. 다른 종목이 주인공인 기사는 근거로 쓰지 마.
8. source_ids에는 근거로 쓴 기사 번호만 넣어."""
SCHEMA = {
    "name": "stock_move_analysis",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["headline_keyword", "keywords", "lines", "confidence", "source_ids"],
        "properties": {
            "headline_keyword": {"type": "string"},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "lines": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "string", "enum": ["high", "low"]},
            "source_ids": {"type": "array", "items": {"type": "integer"}},
        },
    },
}


def top20():
    req = urllib.request.Request("https://127.0.0.1/market/trading-value?market=us",
                                 headers={"Origin": "https://gaemigtp-main.pages.dev"})
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    with opener.open(req, timeout=30) as resp:
        return json.load(resp)["items"]


def published(article):
    raw = str(article.get("published_at") or article.get("pubDate") or "")
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            return parsedate_to_datetime(raw)
        except Exception:
            return None


def validate(result, n_articles):
    problems = []
    kws = result.get("keywords")
    if not isinstance(kws, list) or len(kws) != 3:
        problems.append("keywords!=3")
    if result.get("headline_keyword") not in (kws or []):
        problems.append("headline_keyword_not_in_keywords")
    lines = result.get("lines")
    if not isinstance(lines, list) or len(lines) != 3:
        problems.append("lines!=3")
    elif any(re.search(r"\d+(?:\.\d+)?\s*%|\$\s*\d", line) for line in lines):
        problems.append("number_in_lines")
    if any(not (1 <= i <= n_articles) for i in result.get("source_ids") or []):
        problems.append("bad_source_id")
    return problems


def analyze(stock):
    direction = "상승" if (stock.get("change_pct") or 0) > 0 else "하락" if (stock.get("change_pct") or 0) < 0 else "보합"
    raw = news_feed.fetch_stock_news(stock["name"], market="미국", limit=50, raise_on_error=True) or []
    result = build_stock_news_result(stock["name"], market="미국", limit=50, storyboard_limit=3,
                                     display_timezone="Asia/Seoul", raw_news_list=raw)
    filtered = [a for a in (result.get("paired_news_items") or []) if isinstance(a, dict)]
    now = dt.datetime.now(dt.timezone.utc)
    dated = [(published(a), a) for a in filtered]
    recent = [a for p, a in sorted(dated, key=lambda x: x[0] or now, reverse=True)
              if p is not None and (now - p).total_seconds() <= 48 * 3600][:8]
    print("  FILTER raw=%d relevant=%d" % (len(raw), len(filtered)), flush=True)
    try:
        details = read_selected_article_details(
            [{"title": a.get("title"), "url": a.get("url") or a.get("link")} for a in recent[:6]],
            limit=6, with_sources=True)
        for a, d in zip(recent, details):
            text = str((d or {}).get("text") or "").strip() if isinstance(d, dict) else ""
            if len(text) >= 300:
                a["body"] = text[:1800]
    except Exception as exc:
        print("  BODY_ERROR " + type(exc).__name__, flush=True)
    print("  BODIES %d" % sum(1 for a in recent if a.get("body")), flush=True)
    print("STOCK %s %s change=%s direction=%s articles_total=%d recent48h=%d" % (
        stock["name"], stock["symbol"], stock.get("change_pct"), direction, len(raw), len(recent)), flush=True)
    for i, a in enumerate(recent[:5], 1):
        print("  ART[%d] %s | %s" % (i, str(a.get("source") or "")[:20], str(a.get("title") or "")[:90]), flush=True)
    if not recent:
        return
    body = "종목: %s (%s)\n오늘 움직임: %s\n\n기사:\n" % (stock["name"], stock["symbol"], direction)
    for i, a in enumerate(recent, 1):
        p = published(a)
        body += "[%d] (%s, %s) %s / %s\n" % (i, a.get("source") or "", p.strftime("%m-%d %H:%M") if p else "",
                                            a.get("title") or "", str(a.get("body") or a.get("description") or "")[:1800])
    payload = {"model": MODEL, "temperature": 0.2, "max_completion_tokens": 1500, "reasoning_effort": "low",
               "response_format": {"type": "json_schema", "json_schema": SCHEMA},
               "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": body}]}
    req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",
                                 data=json.dumps(payload, ensure_ascii=False).encode(),
                                 headers={"Authorization": "Bearer " + os.environ["GROQ_API_KEY"],
                                          "Content-Type": "application/json", "User-Agent": "gaemiGTP-ai-test/1.0"})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            out = json.load(resp)
    except urllib.error.HTTPError as exc:
        print("  GROQ_HTTP %s %s" % (exc.code, exc.read()[:300].decode("utf-8", "replace")), flush=True)
        return
    content = out["choices"][0]["message"]["content"]
    usage = out.get("usage") or {}
    try:
        result = json.loads(content)
    except ValueError:
        print("  NOT_JSON " + content[:300], flush=True)
        return
    print("  RESULT " + json.dumps(result, ensure_ascii=False), flush=True)
    print("  CHECK problems=%s tokens=%s seconds=%.1f" % (validate(result, len(recent)), usage.get("total_tokens"),
                                                          time.time() - started), flush=True)


def main():
    rows = top20()
    picks = rows[:2]
    movers = sorted(rows[2:], key=lambda r: abs(r.get("change_pct") or 0), reverse=True)
    picks.append(movers[0])
    for stock in picks:
        try:
            analyze(stock)
        except Exception as exc:
            print("ERROR %s %s" % (stock.get("symbol"), type(exc).__name__), flush=True)


if __name__ == "__main__":
    main()
