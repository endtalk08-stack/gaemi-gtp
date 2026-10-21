import sys,ast,hashlib
sys.path.insert(0,"/opt/gaemigtp-news/app")
from backend.services.shared_v1_issue_titles import extract
print("SHARED_V1_SHA="+hashlib.sha256(extract.__code__.co_code).hexdigest(),flush=True)
code="\"\"\"Display-only concise domestic issue headlines. shared-v1 extractor stays unchanged.\"\"\"\nimport re\nfrom .shared_v1_issue_titles import clean\n\ndef compact_issue_title(extracted, article_title):\n    \"\"\"Shorten a selected event title using only wording in its source headline.\"\"\"\n    source=clean(article_title)\n    source=re.sub(r\"\\s*\\[[^\\]]{1,30}\\]\\s*$\",\"\",source).strip()\n    # News headline contains the clearest complete event; leave the extractor\n    # untouched and shorten just the selected brief display label.\n    clauses=[part.strip(\" ,.:…\") for part in re.split(r\"…|[|｜]\",source) if part.strip(\" ,.:…\")]\n    if not clauses:\n        return clean(extracted)\n    first=clauses[0]\n    # A leading named subject before a comma is unnecessary on a stock-specific panel.\n    first=re.sub(r\"^[^,，]{2,28}[,，]\\s*\",\"\",first)\n    first=re.sub(r\"\\b\\d+\\s*(?:일|주|달|개월)\\s*앞당겨\\s*\",\"\",first)\n    if len(clauses)>1 and len(first)<=23:\n        second=clauses[1]\n        if len(second)<=13 and re.search(r\"(?:완료|예정|확정|검토|추진)\",second):\n            joined=first+\"·\"+second\n            if len(joined)<=32:\n                return joined\n    if len(first)<=27:\n        return first\n    # Append a short second event clause only when it carries the completion\n    # state of the preceding first headline (e.g. 전량 소각 예정).\n    if len(first)<=29:\n        return first\n    # Prefer coherent, source-derived clauses over truncating characters.\n    fragments=[s.strip(\" ,.:\") for s in re.split(r\"[,，·] \",first) if s.strip(\" ,.:\")]\n    for part in fragments:\n        if 8<=len(part)<=27 and re.search(r\"(?:완료|예정|전망|추진|확대|계약|흑자|실적|공급|매입|소각|합병|투자|돌파|상향|하향)\",part):\n            return part\n    return first\n"
ast.parse(code)
ns={}
exec(code.replace("from .shared_v1_issue_titles import clean","from backend.services.shared_v1_issue_titles import clean"),ns)
fn=ns["compact_issue_title"]
cases=[("삼성·SK하닉, 3분기 영업익 합산 180조 돌파 전망…HBM4·메모리 가격 상승","3분기 영업익 합산 180조 돌파 전망"),("SK하이닉스, 40조 자사주 매입 한 달 앞당겨 완료…전량 소각 예정","40조 자사주 매입 완료·전량 소각 예정"),("삼성 가전 ‘실적 효자’ 된 하만…DX 적자에도 오디오 1조 흑자 기대","삼성 가전 ‘실적 효자’ 된 하만")]
for source,expected in cases:
 e=extract(source,source)
 actual=fn(e[0] if e else source,source)
 print("TITLE_TEST "+repr(actual)+" expected="+repr(expected),flush=True)
 assert actual==expected,(actual,expected)
print("COMPACT_TITLE_TEST_PASS",flush=True)
