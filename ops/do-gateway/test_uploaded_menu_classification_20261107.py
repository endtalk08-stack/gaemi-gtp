import json
from collections import Counter, defaultdict
from pathlib import Path

p=json.loads(Path("/var/lib/gaemigtp-news/tradingview-news-page.json").read_text(encoding="utf-8"))
items=p.get("items",[])

MAP={
 "stock":"종목",
 "earnings":"실적 발표",
 "analyst":"증권사 평가",
 "operations":"사업 성과",
 "contract":"계약·수주",
 "product":"제품·기술",
 "capital":"재무·주주환원",
 "corporate":"인수합병·구조조정",
 "legal":"법률·사고",
 "regulation":"인허가·규제",
 "flow":"종목별 수급",
 "rnd_clinical":"연구개발·임상",
 "partnership_supplychain":"제휴·공급망",
 "governance":"경영진·지배구조",
 "market":"증시",
 "economic":"경제지표",
 "fed":"연준",
 "policy":"정부정책",
 "tariff":"관세",
 "international":"국제정세",
 "energy":"에너지",
 "rates_bonds":"금리·환율",
 "fx_commodities":"금리·환율",
 "major_index":"주요지수",
 "market_trend":"시장동향",
 "market_close":"미국장 마감",
 "sector":"시장동향",
 "volatility_sentiment":"시장동향",
 "guidance":"실적 발표",
}

counts=Counter()
samples=defaultdict(list)
unmapped=[]
for x in items:
    cat=(x.get("event_category") or {}).get("code","")
    label=MAP.get(cat)
    title=str(x.get("title") or "")
    if not label:
        unmapped.append((cat,title))
        continue
    counts[label]+=1
    if len(samples[label])<5:
        samples[label].append(title)

print("TOTAL",len(items))
print("MAPPED",sum(counts.values()))
print("UNMAPPED",len(unmapped))
for label,n in counts.most_common():
    print("CATEGORY",label,"COUNT",n)
    for t in samples[label]:
        print("SAMPLE",label,"|",t[:180])
    print("---")
if unmapped:
    print("UNMAPPED_CODES",Counter(c for c,_ in unmapped))
    for c,t in unmapped[:20]:
        print("UNMAPPED_SAMPLE",c,"|",t[:180])
