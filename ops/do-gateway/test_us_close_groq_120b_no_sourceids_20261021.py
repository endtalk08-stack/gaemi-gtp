"""One-time authorized live Groq 120B A/B check, no DB/service changes.
Re-fetch the exact three publisher URLs in the Neon 2026-10-20 manifest.
If any full original cannot be recovered, do not spend a Groq request.
Never print credentials or unabridged third-party articles.
"""
import datetime as dt
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.services import news_detail
from backend.services.us_market_close_runtime import _verified_article

DAY = dt.date(2026, 10, 20)
MODEL = "openai/gpt-oss-120b"
PROMPT = """제공된 기사를 근거로 미국장은 어땠어? 를 작성해

제목은 핵심만 짧게, 내용은 쉽고 구체적으로, 해시태그는 최대 3개. 반말로 답변해.

한국어 JSON 객체만 반환해:
{"issues":[{"headline":"제목","summary":"쉽고 구체적인 내용","tags":["#핵심어"]}]}"""
ARTICLES = [
    {
        "title": "[ 뉴욕증시 마감 시황]실적호조 스페이스X 시간외 급반등… 샌디스크 등 ...",
        "publisher": "www.moneystorm.kr",
        "url": "https://www.moneystorm.kr/news/articleView.html?idxno=7451",
    },
    {
        "title": "뉴욕증시 , 실적 호조·유가 하락에 투자심리 개선…다우 1%↑",
        "publisher": "biz.heraldcorp.com",
        "url": "https://biz.heraldcorp.com/article/10909205?ref=naver",
    },
    {
        "title": "뉴욕증시 , 혼조 마감 … 기술주 숨 고르기 속 전통 우량주 강세",
        "publisher": "biz.chosun.com",
        "url": "https://biz.chosun.com/international/international_economy/2026/10/21/OFKYWAWT2BAZBO33WK3UQSSSZE/?utm_source=naver&utm_medium=original&utm_campaign=biz",
    },
]
INDICES = [
    {"symbol": ".DJI", "name": "다우존스", "session_date_et": "2026-10-20", "close": 52495.88, "change": 529.85, "change_pct": 1.02},
    {"symbol": ".IXIC", "name": "나스닥 종합", "session_date_et": "2026-10-20", "close": 26424.82, "change": -6.07, "change_pct": -0.02},
    {"symbol": ".INX", "name": "S&P 500", "session_date_et": "2026-10-20", "close": 7712.57, "change": 21.84, "change_pct": 0.28},
]

def main():
    assert "source_ids" not in PROMPT
    print("TEST_MODE_ONE_LIVE_CALL_NO_DB_WRITES", flush=True)
    print("SESSION_ET", DAY.isoformat(), "MODEL", MODEL, flush=True)
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        print("TEST_STOP_NO_GROQ_KEY", flush=True)
        return 2
    news_detail.REQUEST_TIMEOUT = 8
    results = news_detail.read_selected_article_details(ARTICLES, limit=3, with_sources=True)
    news = []
    for i, (article, result) in enumerate(zip(ARTICLES, results), 1):
        full = str(result.get("text") or "").strip()
        kind = str(result.get("source") or "")
        entry = {"title": article["title"]}
        verified = _verified_article(entry, full, kind, DAY)
        print("ARTICLE_CHECK",json.dumps({
            "source_id":i,"title":article["title"],"publisher":article["publisher"],
            "url":article["url"],"extraction":kind,"text_length":len(full),
            "full_article_verified":verified,"body_sha256":hashlib.sha256(full.encode()).hexdigest()[:16],
        },ensure_ascii=False),flush=True)
        if not verified:
            print("TEST_STOP_ARTICLE_BODY_UNAVAILABLE_NO_GROQ_CALL",flush=True)
            return 3
        news.append({"source_id":i,"title":article["title"],"description":full[:5000]})
    user_payload={"session_date_et":DAY.isoformat(),"market_indices":INDICES,"news":news}
    request_payload={
        "model":MODEL,
        "messages":[
            {"role":"system","content":PROMPT},
            {"role":"user","content":json.dumps(user_payload,ensure_ascii=False)},
        ],
        "temperature":0.2,"max_completion_tokens":1800,
        "reasoning_effort":"low","stream":False,
    }
    print("LIVE_CALL_START",json.dumps({
        "model":MODEL,"articles":len(news),"article_source_ids":[n["source_id"] for n in news],
        "prompt_source_ids_included":False,"input_body_lengths":[len(n["description"]) for n in news],
    }),flush=True)
    req=urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(request_payload,ensure_ascii=False).encode("utf-8"),
        headers={"Authorization":"Bearer "+key,"Content-Type":"application/json",
                 "User-Agent":"gaemiGTP-us-close-live-test/1.0"},
        method="POST")
    try:
        with urllib.request.urlopen(req,timeout=65) as resp:
            completion=json.loads(resp.read(120000).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print("LIVE_CALL_HTTP_ERROR",exc.code,flush=True)
        return 4
    except Exception as exc:
        print("LIVE_CALL_ERROR_TYPE",type(exc).__name__,flush=True)
        return 5
    choices=completion.get("choices") or []
    raw=str((choices[0].get("message") or {}).get("content") or "").strip() if choices else ""
    try:
        data=json.loads(raw)
    except Exception:
        print("LIVE_CALL_UNPARSABLE_JSON",raw[:1000],flush=True)
        return 6
    print("LIVE_CALL_SUCCESS",flush=True)
    print("LIVE_MODEL_OUTPUT_JSON",json.dumps(data,ensure_ascii=False)[:7200],flush=True)
    print("USAGE",json.dumps(completion.get("usage") or {},ensure_ascii=False)[:1400],flush=True)
    print("COMPLETE_NO_DATABASE_OR_PRODUCTION_FILE_CHANGES",flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
