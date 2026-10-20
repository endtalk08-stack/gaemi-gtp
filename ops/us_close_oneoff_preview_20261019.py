import datetime as dt
import sys
import json
import os
import urllib.request
import psycopg
from psycopg.types.json import Jsonb
session=dt.date(2026,10,19)
data=[
  {
    "title":"나스닥, 반도체·AI 관련주 반등에 1.11% 상승 마감",
    "description":"로이터: 지난주 하락했던 기술주에 매수세가 돌아오며 나스닥이 1.11%, S&P500이 0.41% 올랐다. 다우는 0.07% 소폭 하락했다. 반도체 업종은 8거래일 연속 하락을 끝내고 1.6% 상승했다.",
    "publisher":"Reuters",
    "url":"https://www.reuters.com/business/wall-st-futures-climb-ai-stocks-rebound-oil-yields-fall-2026-10-19/"
  },
  {
    "title":"미국 주요 지수, 기술주 강세와 다우 약세가 엇갈린 마감",
    "description":"AP: 현지 10월 19일 나스닥 종합지수는 26,430.89, S&P500은 7,690.73에 마감해 각각 약 1.1%, 0.4% 올랐다. 다우는 51,966.03으로 약 0.1% 내렸다. 비기술주 상당수는 약세를 보여 시장 전반의 반등은 제한적이었다.",
    "publisher":"AP",
    "url":"https://apnews.com/article/5aec11ee466841cc2a69b2d23ab77f0e"
  },
  {
    "title":"미국 기술주 상승에도 금리·AI 투자비용 우려는 지속",
    "description":"로이터: 인공지능 관련주의 반등이 뉴욕증시를 지지했으나 시장은 AI 인프라 투자 비용과 금리 부담을 여전히 의식했다. 아마존과 테슬라 강세가 소비재·기술주 상승에 기여했고, 유틸리티·부동산 등 방어적 업종은 상대적으로 부진했다.",
    "publisher":"Reuters",
    "url":"https://www.reuters.com/commentary/reuters-open-interest/global-markets-trading-day-graphic-2026-10-19/"
  },
  {
    "title":"미국장 혼조 마감, 소비재·기술 강세와 유틸리티·금융 약세",
    "description":"인베스팅닷컴: 10월 19일 뉴욕증시 마감에서 다우 -0.07%, S&P500 +0.41%, 나스닥 +1.11%를 기록했다. 소비자 서비스와 기술 부문이 상승을 이끌었고 유틸리티, 통신, 금융 관련주가 상대적으로 약했다.",
    "publisher":"Investing.com",
    "url":"https://www.investing.com/news/stock-market-news/us-stocks-mixed-at-close-of-trade-dow-jones-industrial-average-down-007-4958294"
  },
  {
    "title":"기술주 낙폭 되돌림에 미국장 반등, 주요 기업 실적 주목",
    "description":"야후파이낸스: 지난주 부진했던 기술주를 중심으로 매수세가 유입돼 나스닥과 S&P500이 반등했다. 미국 반도체·메모리 관련 기업들에도 반등이 나타났으며, 투자자들은 이번 주 예정된 주요 기술기업 실적 발표에 주목했다.",
    "publisher":"Yahoo Finance",
    "url":"https://finance.yahoo.com/markets/stocks/articles/markets-news-oct-19-2026-105341429.html"
  },
]
intro=("※ 시험판: 네이버 뉴스 API 연결 대신 Reuters·AP 등 공개 보도 5건의 제목·짧은 요약으로 생성한 미국장 마감시황이야. 정식 7시 자동 분석은 아직 전환 전이야.\\n\\n")
with open(sys.argv[1],encoding="utf-8") as stream:
    creds=json.load(stream)
key=str(creds.get("GROQ_API_KEY") or "").strip()
db=str(creds.get("NEWS_DATABASE_URL") or "").strip()
if not key or not db:
    raise RuntimeError("required_service_credentials_missing")
# Exactly one technical retry, only for the first attempt's HTTP 403 failure.
with psycopg.connect(db,connect_timeout=6) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE public.us_market_close_briefs
               SET status='processing', published_at=now(), expires_at=now()+interval '24 hours'
             WHERE session_date=%s AND status='failed' AND content IS NULL
             RETURNING session_date
        """,(session,))
        claimed=cur.fetchone() is not None

if not claimed:
    print("US_CLOSE_ONEOFF_SKIPPED_EXISTING_SESSION")
    raise SystemExit(0)
try:
    prompt=(
      "질문: 미국장은 어땠어? 미국 거래일 2026-10-19.\\n"
      "아래는 이날 마감 보도의 제목과 짧은 소개 5건만 추린 것으로, 기사 전문이 아니다. "
      "확인된 자료들에서 시장 전체 흐름과 주요 상승·하락 요인, 반도체·AI 관련 흐름, 한국장에 "
      "의미 있는 확인된 사항을 종합적으로 설명해. 같은 말을 반복하지 말고 뉴스 목록을 나열하지 마. "
      "기사에 확인되지 않은 사유·숫자는 만들지 마. 미확인 내용은 미확인이라고 밝혀. "
      "한국어 반말로 자연스러운 짧은 제목과 설명 단락을 작성해. 600~1100자로 충분히 구체적으로 써. "
      "출처 링크를 나열하지 말고, 기사 제목/요약에서 확인된 정보에 한정됐다는 점을 마지막에 알려.\\n"
      +json.dumps([{"headline":d["title"],"description":d["description"]} for d in data],ensure_ascii=False)
    )
    body=json.dumps({
      "model":"openai/gpt-oss-120b",
      "messages":[{"role":"system","content":"근거 없는 추측을 피하는 gaemiGTP 미국장 마감시황 편집자야."},
        {"role":"user","content":prompt}],
      "temperature":0.2,"max_completion_tokens":2000,"reasoning_effort":"low","stream":False,
    },ensure_ascii=False).encode("utf-8")
    req=urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",
        data=body,method="POST",headers={"Authorization":"Bearer "+key,"Content-Type":"application/json","User-Agent":"gaemiGTP-us-close/1.0"})
    with urllib.request.urlopen(req,timeout=65) as res:
        response=json.load(res)
    result=str(((response.get("choices")or [{}])[0].get("message")or {}).get("content")or "").strip()
    if len(result)<100:
        raise RuntimeError("empty_or_short_ai_response")
    final=intro+result[:3550]
    with psycopg.connect(db,connect_timeout=6) as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE public.us_market_close_briefs
              SET status='published',content=%s,published_at=now(),expires_at=now()+interval '24 hours'
              WHERE session_date=%s AND status='processing'""",(final,session))
    print("US_CLOSE_ONEOFF_PUBLISHED session=2026-10-19 sources=5 model=120b length="+str(len(final)))
except Exception as exc:
    with psycopg.connect(db,connect_timeout=6) as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE public.us_market_close_briefs SET status='failed' WHERE session_date=%s AND status='processing'",(session,))
    print("US_CLOSE_ONEOFF_FAILED "+type(exc).__name__)
    raise
