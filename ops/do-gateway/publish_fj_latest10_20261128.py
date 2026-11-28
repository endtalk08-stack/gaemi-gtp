"""Publish the 10 newest FinancialJuice headlines as read-aloud Korean scripts into the news widget feed."""
import datetime as dt, hashlib, json, os, pathlib, re, sys, urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
sys.path.insert(0, "/opt/gaemigtp-news/app")
for line in pathlib.Path("/var/lib/gaemigtp-news/r2.env").read_text().splitlines():
    m = re.match(r"^(?:export\s+)?(R2_[A-Z_]+)\s*=\s*(.*)$", line.strip())
    if m:
        os.environ[m.group(1)] = m.group(2).strip().strip("'\"")
import backend.us_macro_news as macro
SCRIPTS = [
    ("Adviser to Iran", "이란 최고지도자의 고문이 국경이 닫힌 뒤 이라크에 '트럼프의 도구가 되지 말라'고 경고했어요."),
    ("Saudi-led coalition: intercepts and destroys ballistic", "사우디 주도 연합군이 예멘 후티 반군이 남부 지역으로 쏜 탄도미사일을 요격해 파괴했다고 밝혔어요."),
    ("Saudi civil defense: danger has passed in Jazan", "사우디 민방위가 지잔 지역의 위험이 지나갔다고 발표했어요."),
    ("Saudi civil defense issues warning over potential hazard in Jazan", "사우디 민방위가 지잔 지역에 위험이 있을 수 있다며 경보를 내렸어요."),
    ("UKMTO: unauthorized individuals", "영국 해사무역기구가 허가받지 않은 인원들이 선박을 장악하고 있다고 밝혔어요."),
    ("Ukmto: master of cargo ship", "영국 해사무역기구에 따르면 화물선 선장이 무장한 인원들에게 배가 점거됐다고 보고했어요."),
    ("UKMTO reports incident 64nm", "영국 해사무역기구가 예멘 발하프 남서쪽 64해리 해상에서 사건이 일어났다고 보고했어요."),
    ("Musk: Google shows interest", "일론 머스크가 구글이 스페이스X의 컴퓨팅 자원을 추가로 빌리는 데 관심을 보이고 있다고 말했어요."),
    ("Saudi-led coalition: cruise missile", "사우디 주도 연합군이 후티 반군이 리야드를 향해 쏜 순항미사일을 요격해 파괴했다고 밝혔어요."),
    ("Cryptostar Corp shareholders", "크립토스타가 최대 30대 1 비율의 주식 병합을 주주 투표에 부칠 예정이에요."),
]
req = urllib.request.Request("https://www.financialjuice.com/feed.ashx?xy=rss",
                             headers={"User-Agent": "Mozilla/5.0 (compatible; news-probe/1.0)"})
with urllib.request.urlopen(req, timeout=20) as r:
    root = ET.fromstring(r.read())
feed = []
for it in root.iter("item"):
    title = re.sub(r"\s+", " ", it.findtext("title") or "").strip()
    title = re.sub(r"^FinancialJuice:\s*", "", title)
    link = (it.findtext("link") or "").strip()
    feed.append((title, link, parsedate_to_datetime(it.findtext("pubDate")).astimezone(dt.timezone.utc)))
rows = []
for prefix, script in SCRIPTS:
    match = next((f for f in feed if f[0].startswith(prefix)), None)
    if not match:
        print("MISSING " + prefix, flush=True)
        continue
    title_en, link, when = match
    if not link.startswith("https://"):
        link = "https://www.financialjuice.com/home"
    rows.append({"id": hashlib.sha1(("fj:" + title_en + when.isoformat()).encode()).hexdigest()[:16],
                 "source": "FinancialJuice", "category": "정책·규제", "title": script, "title_en": title_en,
                 "url": link, "published_at": when.isoformat(), "want_summary": False, "haeyo": True})
state = macro.read_state()
items = [r for r in state.get("items") or [] if r.get("id") not in {x["id"] for x in rows}]
items = sorted(items + rows, key=lambda r: r["published_at"], reverse=True)[:macro.KEEP_ITEMS]
macro.upload_json({"ok": True, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "items": items}, macro.OBJECT_KEY)
state["items"] = items
macro.write_state(state)
for r in rows:
    print("PUBLISHED %s | %s" % (dt.datetime.fromisoformat(r["published_at"]).astimezone(macro.dt.timezone(dt.timedelta(hours=9))).strftime("%m-%d %H:%M"), r["title"]), flush=True)
print("TOTAL_FEED_ITEMS %d" % len(items), flush=True)
