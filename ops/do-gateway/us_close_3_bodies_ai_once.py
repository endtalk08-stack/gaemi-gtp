"""Read exactly three verified Naver-sourced US market-close original articles; one Groq test.

No production service modification, Neon read/write, Render, trading, API retries
or new packages. Reuses existing server news_detail.py and exact user prompt.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0,"/opt/gaemigtp-news/app")
from backend.services.news_detail import read_selected_article_details

MODEL="openai/gpt-oss-120b"
US_CLOSE_PROMPT="""제공된 기사를 근거로 미국장은 어땠어? 를 작성해

제목은 핵심만 짧게, 내용은 쉽고 구체적으로, 해시태그는 최대 3개. 반말로 답변해.

한국어 JSON 객체만 반환해:
{"issues":[{"headline":"제목","summary":"기사에 근거한 내용","tags":["#핵심어"],"source_ids":[1]}]}"""

NEWS=[
    {"id":1,"source":"한국경제","published_kst":"2026-10-20 07:09",
     "title":"저가매수 유입에 반도체·AI주 상승…나스닥 1.11%↑ [뉴욕증시 브리핑]",
     "url":"https://www.hankyung.com/article/2026102019676"},
    {"id":2,"source":"서울파이낸스","published_kst":"2026-10-20 06:59",
     "title":"[뉴욕증시] AI·반도체주 '불안한 반등'…국채↓·유가↑",
     "url":"https://www.seoulfn.com/news/articleView.html?idxno=640458"},
    {"id":3,"source":"이데일리","published_kst":"2026-10-20 07:44",
     "title":"[마켓무버] 뉴욕증시 혼조 마감…반도체 8거래일 연속 하락 끊고 반등",
     "url":"https://www.edaily.co.kr/News/Read?newsId=02492806645614888&mediaCodeNo=257"},
]

def main():
    print("US3_SCOPE=2026-10-19_US_session_three_fixed_Naver_originals_one_Groq_call",flush=True)
    print("US3_PROMPT=exact_user_prompt_unchanged",flush=True)
    originals=read_selected_article_details(NEWS,limit=3,with_sources=True)
    inp=[]
    valid_count=0
    for a,result in zip(NEWS,originals):
        kind=str(result.get("source") or "fetch_failed")
        body=str(result.get("text") or "").strip()
        enough=len(body)>=500 and kind in ("jsonld_article_body","article_or_main_paragraphs")
        related=bool(re.search(r"뉴욕증시|나스닥|다우존스|S&P\s*500",body,re.I))
        good=enough and related
        valid_count+=int(good)
        print("US3_ORIGINAL="+json.dumps({
            "id":a["id"],"publisher":a["source"],"published_kst":a["published_kst"],
            "title":a["title"],"url":a["url"],
            "extract_source":kind,"body_chars":len(body),"body_words":len(body.split()),
            "market_relevance_in_body":related,"accepted":good,
            "body_excerpt_ko":body[:175],
        },ensure_ascii=False),flush=True)
        if good:
            inp.append({"source_id":a["id"],"title":a["title"],"description":body[:5000]})
    print("US3_ACCEPTED="+str(valid_count),flush=True)
    if valid_count!=3:
        print("US3_ERROR=not_three_valid_original_bodies_AI_not_called",flush=True)
        return 3
    key=os.getenv("GROQ_API_KEY","").strip()
    if not key:
        print("US3_ERROR=groq_key_missing_AI_not_called",flush=True)
        return 4
    payload={
        "model":MODEL,
        "messages":[
            {"role":"system","content":US_CLOSE_PROMPT},
            {"role":"user","content":json.dumps(inp,ensure_ascii=False)},
        ],
        "temperature":0.2,
        "max_completion_tokens":1800,
        "reasoning_effort":"low",
        "stream":False,
    }
    req=urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
        headers={"Authorization":"Bearer "+key,"Content-Type":"application/json",
            "User-Agent":"gaemiGTP-us-close-3-originals-test/1.0"},
        method="POST",
    )
    print("US3_AI_CALLS_MAX=1",flush=True)
    try:
        with urllib.request.urlopen(req,timeout=40) as resp:
            obj=json.loads(resp.read(190000))
    except urllib.error.HTTPError as exc:
        print("US3_ERROR=groq_http_"+str(exc.code),flush=True)
        return 5
    except Exception as exc:
        print("US3_ERROR=groq_"+type(exc).__name__,flush=True)
        return 6
    choice=(obj.get("choices") or [{}])[0]
    message=choice.get("message") or {}
    reply=str(message.get("content") or "").strip()
    tokens=obj.get("usage") or {}
    print("US3_AI_USAGE="+json.dumps({
        "prompt_tokens":tokens.get("prompt_tokens"),
        "completion_tokens":tokens.get("completion_tokens"),
        "total_tokens":tokens.get("total_tokens"),
        "finish_reason":choice.get("finish_reason"),
    },ensure_ascii=False),flush=True)
    try:
        parsed=json.loads(reply)
        if not isinstance(parsed,dict) or not isinstance(parsed.get("issues"),list):
            raise ValueError("shape")
        print("US3_AI_JSON="+json.dumps(parsed,ensure_ascii=False)[:5000],flush=True)
    except (TypeError,ValueError):
        print("US3_AI_RAW="+reply[:3600],flush=True)
        print("US3_ERROR=answer_not_json",flush=True)
        return 7
    print("US3_TEST_PASS",flush=True)
    return 0

if __name__=="__main__":
    sys.exit(main())
