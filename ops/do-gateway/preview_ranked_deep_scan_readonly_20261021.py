"""Proof-of-concept: price direction -> read original articles -> grounded event phrases.
Diagnostic only. No API-paid models, DB mutations, worker process, or service changes.
A direction-matched article is a candidate explanation, NEVER proof of causation.
"""
import os
import re
import sys
import json
import hashlib
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, "/opt/gaemigtp-news/app")
import psycopg
from backend.providers.market_price import fetch_kr_stock_quote
from backend.services.news_detail import read_selected_article_details

DB = os.environ.get("NEWS_DATABASE_URL") or os.environ.get("DATABASE_URL")
assert DB, "NEWS_DATABASE_URL unavailable"
CODES = {
    "삼성전자": "005930",
    "HT로보틱스": "396300",
    "SK하이닉스": "000660",
    "명신산업": "009900",
    "한화오션": "042660",
    "NAVER": "035420",
    "현대차": "005380",
    "삼성SDI": "006400",
    "LG전자": "066570",
    "HLB": "028300",
    "LG에너지솔루션": "373220",
    "셀트리온": "068270",
}
OTHERS = list(CODES) + ["포스코DX", "삼성전기", "삼성전자우", "뉴인텍", "자이언트스텝", "파트론", "SFA반도체"]
POSITIVE = {
    "확대": ("확대", 1), "확충": ("확충", 1), "늘리": ("확대", 1),
    "넓히": ("확대", 1), "증가": ("증가", 1), "신설": ("신설", 1),
    "가동": ("가동", 1), "출시": ("출시", 1), "양산": ("양산", 1),
    "신규 수주": ("신규수주", 1), "수주": ("수주", 1),
    "체결": ("체결", 1), "점유율": ("점유율", 1),
    "1위": ("1위", 1), "순매수": ("순매수", 1),
    "성장": ("성장", 1),
}
NEGATIVE = {
    "순매도": ("순매도", -1), "매도": ("매도", -1),
    "적자": ("적자", -1), "축소": ("축소", -1),
    "중단": ("중단", -1), "철수": ("철수", -1),
    "하향": ("하향", -1), "부진": ("부진", -1),
    "투자주의": ("투자주의", -1), "투자경고": ("투자경고", -1),
    "매입 종료": ("매입종료", -1), "매입 완료": ("매입완료", -1),
}
# Price reports, corporate speeches and background company blurbs are
# not investment catalysts without a separate explicit business event.
ACTION_RX = re.compile(
    r"확대|확충|늘리|넓히|증가|신설|가동|출시|양산|신규\s*수주|"
    r"수주|체결|점유율|1위|순\s*매수|성장|순\s*매도|적자|"
    r"축소|중단|철수|하향|부진|투자주의|투자경고|"
    r"(?:완료|마무리|종료|끝냈|끝나)",
    re.I,
)
POS_WORDS = re.compile(r"확대|확충|늘리|넓히|증가|신설|가동|출시|양산|수주|체결|점유율|1위|순\s*매수|성장")
NEG_WORDS = re.compile(r"순\s*매도|적자|축소|중단|철수|하향|부진|투자주의|투자경고")
NEGATION = re.compile(r"(?:계획이\s*없|확대하지\s*않|양산하지\s*않|진출하지\s*않|부인|무산)")
PRICE = re.compile(r"(?:전\s*거래일.{0,30}(?:올랐|내렸|상승|하락)|장중|거래량|거래대금)")
STOCK_END = re.compile(r"(?:은|는|이|가|의|와|과|을|를|도|측은|측이)?$")
PURCHASE = re.compile(r"자사주.{0,24}(?:매입|취득).{0,95}?(완료|마무리|종료|끝냈|끝나)")
TRADE = re.compile(r"외국인.{0,125}?(순\s*매수|순\s*매도)")
DUPLICATE_GROUP = (
    ("자사주", "매입"),
    ("외국인", "순매수"),
    ("외국인", "순매도"),
    ("메가특구", "피지컬AI"),
    ("로봇", "정밀부품"),
)
ALLOWED_BODY = {"jsonld_article_body", "article_or_main_paragraphs"}

def normalize(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()

def stock_anchor(s, stock):
    # A short Latin ticker is NOT a prefix for another listed legal entity.
    # HLB vs HLB이노베이션, QZ vs QZX, etc.
    if re.fullmatch(r"[A-Za-z0-9.]{2,5}",stock):
        pattern=rf"(?<![A-Za-z0-9]){re.escape(stock)}(?![A-Za-z0-9]|[가-힣]{{2,}})"
    else:
        pattern=re.escape(stock)
    return [(m.start(), m.end()) for m in re.finditer(pattern,s,flags=re.I)]

def compact_object(segment):
    segment = re.split(r"(?:바탕으로|통해|관련해|따라|그러나|한편|이에|중인|예정인)",segment)[-1]
    segment = re.sub(r"\([^)]{0,80}\)", "", segment)
    segment = re.sub(r"[^가-힣A-Za-z0-9· ]+", " ", segment)
    parts = segment.split()
    parts = [re.sub(r"(?:은|는|이|가|의|을|를|으로|로|에서|와|과)$","",w) for w in parts]
    parts = [w for w in parts if len(w)>1 and w not in
             {"삼성전자","HT로보틱스","SK하이닉스","업계","관련","이번","오는",
              "가운데","지난","이날","것으로","밝혔다","따르면","한다고"}]
    # Grounded phrase, never replace the subject with an invented topic.
    return " ".join(parts[-4:]).strip()[:31]

def nearest_owner(sentence, stock, pos):
    own = stock_anchor(sentence,stock)
    if not own: return False
    own_dist = min(min(abs(pos-st),abs(pos-en)) for st,en in own)
    if own_dist>135:return False
    for name in OTHERS:
        if name==stock:continue
        for st,en in stock_anchor(sentence,name):
            dist=min(abs(pos-st),abs(pos-en))
            if dist<own_dist:
                return False
    return True

def make_key(sentence, stock, match):
    raw=match.group(0).replace(" ","")
    # Conditional plans, retired actions and photo/caption UI controls cannot
    # be promoted to today's completed directional events.
    if re.search(r"(?:할|했을)\s*경우|(?:할|될)\s*수\s*있|가능성|예상|검토",sentence):
        if raw not in {"투자주의","투자경고"}:return None
    if re.search(r"이미지\s*확대|사진\s*확대|\[사진",sentence):
        return None
    if re.search(r"지난해|작년|지난\s*8월|지난\s*9월|10월\s*6일|올해\s*[1-6]월|인수\s*이후.{0,50}성장|성과를\s*보여주는",sentence):
        if raw not in {"투자주의","투자경고"}:return None
    if raw in {"부진","적자"} and re.search(r"(?:1위|회복|반등|성장|넘어섰)",sentence):
        return None
    left=sentence[max(0,match.start()-100):match.start()]
    right=sentence[match.end():match.end()+30]
    if "자사주" in sentence and re.search(r"매입|취득",sentence):
        if re.search(r"완료|마무리|종료|끝냈|끝나",sentence):
            return ("자사주매입종료",-1,"past_completion")
        if re.search(r"시작|결정|계획|추진",sentence):
            return ("자사주매입계획",1,"announced")
        # Isolated "buyback" is never enough to infer a reason.
        return None
    if raw in {"순매수","순매도"} and "외국인" in sentence:
        if nearest_owner(sentence,stock,match.start()):
            return ("외국인"+raw, 1 if raw=="순매수" else -1,"flow_news")
    if raw in {"투자주의","투자경고"}:
        return (raw+("예고" if "예고" in sentence else "지정"),-1,"regulatory_warning")
    if raw in {"완료","마무리","종료","끝냈","끝나"}:
        return None
    if raw in {"점유율","1위"}:
        if "스마트폰" not in sentence and "반도체" not in sentence and "시장" not in sentence:
            return None
        topic= "인도스마트폰" if ("인도" in sentence and "스마트폰" in sentence) else compact_object(left)
        return ((topic or "시장")+"점유율상승" if raw=="점유율" else (topic or "시장")+"1위",1,"market_position")
    positive=bool(POS_WORDS.fullmatch(raw))
    negative=bool(NEG_WORDS.fullmatch(raw))
    if not positive and not negative:return None
    # No synthetic positive catalyst for price-only headlines.
    if PRICE.search(sentence) and not re.search(r"계약|수주|설비|사업|정밀부품|메모리|출시",sentence):
        return None
    obj=compact_object(left)
    if not obj:return None
    # Require a meaningful article-grounded topic, not standalone generic verbs.
    if obj in {"투자","정부","기업","기술","사업","제품","시장"}:
        return None
    mapped = {
        "넓히":"확대","늘리":"확대","순매수":"순매수","순매도":"순매도"
    }.get(raw,raw)
    return (obj.replace(" ","")+mapped,1 if positive else -1,"event_action")

def extract(text, stock):
    sentences = [normalize(x) for x in re.split(r"(?<=[.!?。])\s+|\n+",text) if normalize(x)]
    candidates=[]
    for sentence in sentences:
        if not stock_anchor(sentence,stock):continue
        # Retrospective company background, stock-quote-only paragraphs and
        # hypothetical events must never be selected as real stock catalysts.
        if re.search(r"과거|지난해|작년|매입을\s*완료한\s*데\s*이어",sentence):
            continue
        if NEGATION.search(sentence):continue
        for match in ACTION_RX.finditer(sentence):
            if not nearest_owner(sentence,stock,match.start()):continue
            event=make_key(sentence,stock,match)
            if not event:continue
            key,direction,kind=event
            if len(key)<4 or len(key)>44:continue
            candidates.append({
                "keyword":key,"direction":direction,
                "event_kind":kind,
                "evidence":sentence[:140], 
            })
    # Retain first evidence, dedup within same article.
    return list({x["keyword"]:x for x in reversed(candidates)}.values())[::-1]

from backend.providers.market_price import fetch_kr_popular_ranking_raw
from backend.services.market_rankings import _normalize_kr_stock_rows


# Precision-first independent ownership guard: no inferred company event from
# mere proximity, target/object mentions or product/customer references.
def strict_subject(evidence,stock):
 s=normalize(evidence)
 for st,en in stock_anchor(s,stock):
  after=s[en:]
  if re.match(r"^(?:를|을|에게|에서|보다|만|측에|평택|기초자산)",after):
   continue
  if not re.match(r"^(?:은|는|이|가|와|과|도|측은|측이|[,，]|\\s+)",after):
   continue
  # Reject a competitor overtaking the selected stock and third-party fund
  # investments which only name the selected company as recipient.
  if re.search(r"(?:제치고|기초자산|투자 부문|집행됐고|투입됐다|제공 이미지)",s):
   continue
  return True
 return False

def strict_event(event,stock):
 line=normalize(event.get("evidence"))
 kind=event.get("event_kind") or ""
 if not strict_subject(line,stock):return ""
 if re.search(r"(?:지난해|작년|지난\\s+\\d+월|올해\\s*[1-6]월|종료|마무리|완료|인수 이후|누적|기존|관심|가능성|예상|추정|검토|전망|기대|수혜|추진될|할 경우|수 있다|계획|목표|준비)",line):
  # A documented *new* business action can have a future benefit, but a
  # future projection or historic example is not itself a current catalyst.
  return ""
 if re.search(r"(?:손실|기초자산|평가손실|실적부진|위험)",line) and event.get("direction")==1:return ""
 if kind=="past_completion":return ""
 if kind=="market_position":
  if "인도" in line and "스마트폰" in line and "1위" in line:
   return "인도스마트폰시장1위"
  return ""
 if "로봇" in line and ("정밀부품" in line or "핵심부품" in line) and re.search(r"사업.{0,8}(?:확대|넓히)|시장.{0,8}넓히",line):
  return "로봇부품사업확대"
 if re.search(r"(?:파트너십|업무협약|MOU|공급계약).{0,55}(?:체결|맺)",line,re.I):
  return ("공급계약체결" if "공급계약" in line else "협약체결")
 # These tokens do not establish a specific completed owner business event.
 return ""

MAX_STOCKS=2
MAX_BODY_PER_STOCK=50
raw=fetch_kr_popular_ranking_raw(limit=20)
if not raw:
 raise RuntimeError("live popular rankings unavailable")
ranking=_normalize_kr_stock_rows(raw,20)[:MAX_STOCKS]
assert ranking and ranking[0]["rank"]==1
# Keep the provider's actual order, do not re-rank on daily change.
OTHERS[:]=list(dict.fromkeys(OTHERS+[r["name"] for r in ranking]))
print("MODE=READ_ONLY_SEQUENTIAL_TOP2_DEEP_SCAN; NO_AI; NO_NEON_WRITES",flush=True)
print("RULE=ONLY_VERIFIED_BODY_AND_SAME_DIRECTION; UNCERTAIN=BLANK",flush=True)
for rank in ranking:
 stock=rank["name"]
 pct=rank.get("change_pct")
 sign=1 if isinstance(pct,(int,float)) and pct>0 else -1 if isinstance(pct,(int,float)) and pct<0 else 0
 with psycopg.connect(DB,connect_timeout=10) as conn:
  with conn.cursor() as cur:
   cur.execute("SET TRANSACTION READ ONLY")
   cur.execute("""SELECT a.ord,a.obj
     FROM public.news_processed_snapshots s,
     LATERAL jsonb_array_elements(COALESCE(s.result_payload->'paired_news_items','[]'::jsonb))
       WITH ORDINALITY a(obj,ord)
     WHERE s.market='국내' AND s.stock_name=%s
     ORDER BY a.ord LIMIT %s""",(stock,MAX_BODY_PER_STOCK))
   rows=cur.fetchall()
 seen=set()
 bodycount=0
 selected=[]
 examined=0
 for start in range(0,len(rows),3):
  if sign==0:break
  chunk=rows[start:start+3]
  details=read_selected_article_details([it for _,it in chunk],limit=len(chunk),with_sources=True)
  for (ord_num,item),detail in zip(chunk,details):
   examined+=1
   if detail.get("source") not in ALLOWED_BODY:continue
   text=detail.get("text") or ""
   if len(text)<130 or not stock_anchor(text,stock):continue
   bodycount+=1
   for event in extract(text,stock):
    if event["direction"]!=sign:continue
    line=event.get("evidence") or ""
    keyword=strict_event(event,stock)
    if not keyword:continue
    # Strict no-implied-comparison and no speculative/improper direction labels.
    if event["event_kind"]=="market_position":
     if "1위" not in line:continue
     if "인도" in line and "스마트폰" in line:
      keyword="인도스마트폰시장1위"
     elif "1위" in keyword:
      keyword=keyword.replace("점유율상승","1위")
     else:continue
    if event["event_kind"]=="past_completion":
     # A buyback that has already finished is not established as a fresh catalyst.
     continue
    if any(word in line for word in ("지난해","작년","완료한 데 이어","인수 이후","~할 경우","경우에는","가능성","수 있다","전망이다")):continue
    if re.search(r"(?:했다면|하는 경우|했을 경우|할 경우|계획이 없다|미확인)",line):continue
    if "확대" in keyword and "확대" not in line and "넓히" not in line and "늘리" not in line:continue
    # Only one independent reason per source article; three slots may remain blank.
    if item.get("url") in seen:continue
    seen.add(item.get("url"))
    selected.append({
      "keyword":keyword,"title":str(item.get("title") or "")[:100],
      "source":detail.get("source"),"ranked_article_order":ord_num,
      "quote_pct":pct,"evidence":line[:175],
    })
    break
  if len(selected)>=3:break
 # Deduplicate semantically identical event labels across publishers.
 unique=[]
 for ev in selected:
  key=re.sub(r"[^가-힣A-Za-z0-9]","",ev["keyword"])
  if not key or any(key in re.sub(r"[^가-힣A-Za-z0-9]","",x["keyword"])
                or re.sub(r"[^가-힣A-Za-z0-9]","",x["keyword"]) in key for x in unique):continue
  unique.append(ev)
 print("RANKED_STOCK "+json.dumps({"rank":rank["rank"],"stock":stock,"ticker":rank["symbol"],
  "pct":pct,"direction":"UP" if sign==1 else "DOWN" if sign==-1 else "FLAT",
  "articles_examined":examined,"verified_originals":bodycount,
  "keywords":[e["keyword"] for e in unique[:3]],
  "blank":not bool(unique)},ensure_ascii=False),flush=True)
 for ev in unique[:3]:print("RANKED_EVIDENCE "+json.dumps(ev,ensure_ascii=False),flush=True)
print("RANKED_DIRECTION_PREVIEW_FINISHED_NO_WRITES",flush=True)
