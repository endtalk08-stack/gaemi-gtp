"""READ-ONLY: sample real Korean publisher article bodies using existing reader.
No Neon mutation, AI invocation, paid quote API, or production code alteration.
"""
import sys
sys.path.insert(0, "/opt/gaemigtp-news/app")
import re
from backend.services.news_detail import read_selected_article_details
from backend.analysis.news.scoring import build_connected_keyword_test

cases = [
 ("삼성전자","down","buyback_completed", "“이젠 진짜 큰일났다” SK하이닉스마저…자사주 매입 종료 임박",
  "https://biz.heraldcorp.com/article/10910113?ref=naver",
  "국내 증시를 떠받쳐온 삼성전자와 SK하이닉스의 대규모 자사주 매입이 잇따라 종료되면서 코스피 수급에 비상이 걸렸다. 삼성전자가 15조원 규모의 자사주 매입을 마무리한 데 이어 SK하이닉스도 이르면 이번 주 매입을 종료할 전망이다."),
 ("삼성전자","down","buyback_completed_second", "SK하이닉스, 40조 자사주 매입 한 달 앞당겨 끝냈다",
  "https://news.tvchosun.com/site/data/html_dir/2026/10/21/2026102190273.html",
  "SK하이닉스에 앞서 삼성전자도 지난 8월 24일부터 10월 6일까지 약 15조원을 투입해 자사주 5천685만주를 취득했다."),
 ("삼성전자","down","foreign_net_sell_summary", "SK하이닉스·삼성전자 거래대금 9.3조…상위 50종목의 56%",
  "http://www.kjdaily.com/article.php?aid=1792583226689910276",
  "외국인 두 종목 6천535억원"),
 ("삼성전자","down","new_product_dev", "삼성전자 반도체, '코어팀' 신설",
  "https://www.etoday.co.kr/news/view/2638576",
  "삼성전자 반도체(DS) 부문이 차세대 메모리 개발을 전담할 핵심 인력 조직을 새로 꾸리고 이들에 대한 보상 수준을 높였다."),
 ("HT로보틱스","up","regional_ai", "경북, 피지컬AI 중심 메가특구 본격 추진",
  "https://www.etoday.co.kr/news/view/2638410",
  "HT로보틱스는 로봇용 정밀부품 사업을 확대하며 미래 제조시장 선점에 힘을 보탠다."),
 ("HT로보틱스","up","regional_ai_second", "경북, 피지컬AI 메가특구 추진…포스코DX·HT로보틱스 주도",
  "https://www.wikitree.co.kr/articles/1168051",
  "로보틱스 핵심부품 사업을 확대하는 HT로보틱스는 피지컬AI와 로봇 기반 미래 제조로"),
 ("HT로보틱스","up","caution", "HT로보틱스, 투자경고종목 지정 가능성에 따른 투자주의종목 예고",
  "https://www.topstarnews.net/news/articleView.html?idxno=16254044",
  "HT로보틱스가 주가 급등에 따라 투자경고종목으로 지정될 가능성이 있어 2026년 10월 22일 1일간 투자주의종목으로 지정돼 투자에 유의해야 한다고 한국거래소가 공시했다.")
]
words = ("자사주", "매입", "완료", "마무리", "종료", "외국인", "순매도", "순매수", "메가특구", "피지컬", "로봇", "신설", "투자경고", "투자주의", "공급", "매출", "하락", "급등")
print("TEST_MODE=READ_ONLY REAL_ARTICLE_BODY current extraction, hypothetical price direction", flush=True)
print("PRICE_DIRECTION_NOTE=User-stated scenario, no historical quote verification", flush=True)
for offset in range(0,len(cases),3):
    chunk=cases[offset:offset+3]
    inputs=[{"title": title,"url": url,"description":desc} for name,direction,tag,title,url,desc in chunk]
    records=read_selected_article_details(inputs, limit=3, with_sources=True)
    for (name,direction,tag,title,url,desc), record in zip(chunk,records):
        body=record.get("text") or ""
        source=record.get("source")
        current=build_connected_keyword_test([{"title":title,"description":desc}],name)["articles"][0]
        full=build_connected_keyword_test([{"title":title,"description":body}],name)["articles"][0] if body else {}
        small=[]
        for token in words:
            match=re.search(re.escape(token),body,flags=re.I)
            if match:
                snippet=body[max(0,match.start()-46):min(len(body),match.end()+85)].replace("\\n"," ")
                small.append(token+"="+snippet[:160])
            if len(small)>=5:break
        print("CASE="+tag+" stock="+name+" direction="+direction+" src="+str(source)+" chars="+str(len(body)),flush=True)
        print("CURRENT="+repr(current.get("keywords"))+" owner="+str(current.get("event_owner"))+" relation="+str(current.get("relation_type")),flush=True)
        print("WITH_BODY="+repr(full.get("keywords"))+" owner="+str(full.get("event_owner"))+" relation="+str(full.get("relation_type")),flush=True)
        print("EVIDENCE="+repr(small),flush=True)
print("BODY_READER_DIAGNOSTIC_COMPLETE",flush=True)
