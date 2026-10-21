"""Read real article bodies and compare present extraction for one + / one - movement.
Read-only: no DB writes, AI inference, paid provider, or production modifications.
"""
import sys, re
sys.path.insert(0, "/opt/gaemigtp-news/app")
from backend.services.news_detail import read_selected_article_details
from backend.analysis.news.scoring import build_connected_keyword_test

articles=[
 {"stock":"삼성전자","dir":"up","title":"삼성전자와 SK하이닉스 자사주 매입 종료","url":"https://biz.heraldcorp.com/article/10910113?ref=naver",
  "description":"국내 증시를 떠받쳐온 삼성전자와 SK하이닉스의 대규모 자사주 매입이 잇따라 종료되면서 코스피 수급에 비상이 걸렸다. 삼성전자가 15조원 규모의 자사주 매입을 마무리한 데 이어 SK하이닉스도 이르면 이번 주 매입을 종료할 전망이다. 외국인의 매도세가 이어지는 가운데 대규모 매수 수요마저 사라지면서 코스피의 하방 압력이 커질 수 있다는 우려가 나온다."},
 {"stock":"삼성전자","dir":"up","title":"삼성전자 스마트폰 인도 시장 점유율 1위","url":"https://www.sedaily.com/article/20104562?ref=naver",
  "description":"삼성전자가 글로벌 스마트폰 시장에서 두 번째로 큰 인도에서 시장 점유율 19%를 기록하며 1위 자리에 올랐다."},
 {"stock":"삼성전자","dir":"up","title":"삼성전자 D램·낸드 코어팀 전격 가동","url":"https://www.dnews.co.kr/uhtml/view.jsp?idxno=202610212021222360613",
  "description":"삼성전자 디바이스솔루션 부문이 차세대 메모리 반도체 개발을 전담하는 정예 조직 코어팀을 가동한다."},
 {"stock":"HT로보틱스","dir":"up","title":"경북도 피지컬AI 메가특구 추진 HT로보틱스 사업 확대","url":"https://www.etoday.co.kr/news/view/2638410",
  "description":"HT로보틱스는 로봇용 정밀부품 사업을 확대하며 미래 제조시장 선점에 힘을 보탠다."},
 {"stock":"HT로보틱스","dir":"up","title":"HT로보틱스 투자경고종목 지정 가능성","url":"https://www.topstarnews.net/news/articleView.html?idxno=16254044",
  "description":"HT로보틱스가 주가 급등에 따라 투자경고종목으로 지정될 가능성이 있어 2026년 10월 22일 투자주의종목으로 지정돼 투자에 유의해야 한다고 한국거래소가 공시했다."},
 {"stock":"HT로보틱스","dir":"up","title":"경북도 AI로 제조 현장 혁신 HT로보틱스 미래 제조 전환","url":"https://www.eroun.net/news/articleView.html?idxno=93095",
  "description":"경상북도는 포스코DX의 AI와 지능형 공장 구현, 구미 HT로보틱스의 정밀부품 기반 미래 제조 전환을 결합해 혁신을 추진한다."},
]
for k in range(0,len(articles),3):
 batch=articles[k:k+3]
 details=read_selected_article_details(batch,limit=len(batch),with_sources=True)
 for item,detail in zip(batch,details):
  txt=str(detail.get("text") or "")
  name=item["stock"]
  extract=build_connected_keyword_test([dict(item)],name)["articles"][0]
  print("ARTICLE stock="+name+" direction="+item["dir"]+" source="+str(detail.get("source"))+
        " chars="+str(len(txt))+" old_keywords="+repr(extract.get("keywords"))+
        " old_relation="+str(extract.get("relation_type")),flush=True)
  for name_label,pattern in (
    ("buyback_completed",r"자사주.{0,12}매입.{0,35}(?:마무리|완료|종료|끝냈|종결)|자사주.{0,12}매입.{0,12}종료"),
    ("foreign_selling",r"외국인.{0,35}(?:순?매도|매도세|팔아|매물)"),
    ("future_expansion",r"(?:로봇.{0,22}(?:사업|부품)).{0,30}(?:확대|확장|진출|선점)|(?:확대|확장).{0,30}로봇"),
    ("caution",r"투자(?:경고|주의).{0,35}(?:지정|예고|가능)"),
    ("smartphone_share",r"(?:점유율.{0,30}(?:1위|상승|기록)|스마트폰.{0,35}1위)"),
    ("core_team",r"(?:코어팀|핵심.{0,10}조직).{0,20}(?:가동|신설|꾸리)"),
  ):
   m=re.search(pattern,txt,flags=re.I)
   if m:
    print("  BODY_EVIDENCE "+name_label+"="+repr(txt[max(0,m.start()-22):m.end()+22].replace("\\n"," ")[:160]),flush=True)
print("REAL_ARTICLE_BODY_PROBE_COMPLETE",flush=True)
