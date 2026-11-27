"""Sample only (nothing published): Fed / White House primary-source headlines in Korean,
with the price reaction after each one (session high % and low % from the news time).

Read-only except Groq calls (one per item, small). Prints a report to the job log.
"""
import datetime as dt
import json
import os
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
KST = ZoneInfo("Asia/Seoul")
NOW = dt.datetime.now(dt.timezone.utc)
SINCE = NOW - dt.timedelta(days=6)
UA = {"User-Agent": "Mozilla/5.0 (compatible; news-sample/1.0)", "Accept": "*/*"}
FEEDS = [
    ("연준", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("연준", "https://www.federalreserve.gov/feeds/speeches.xml"),
    ("백악관", "https://www.whitehouse.gov/news/feed/"),
    ("백악관", "https://www.whitehouse.gov/presidential-actions/feed/"),
    ("백악관", "https://www.whitehouse.gov/briefings-statements/feed/"),
]
ASSETS = {"QQQ": "나스닥100", "SPY": "S&P500", "DIA": "다우", "IWM": "러셀2000", "TLT": "미 장기채",
          "GLD": "금", "USO": "원유", "UUP": "달러"}
MAX_ITEMS = 18
STORE_PCT = 1.0     # sample rule: a move of 1% or more either way -> keep long term


def get(url, timeout=20):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def strip_html(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def read_feed(label, url):
    try:
        root = ET.fromstring(get(url))
    except Exception as exc:
        print("FEED_FAIL %s %s" % (url, type(exc).__name__), flush=True)
        return []
    rows = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        when = item.findtext("pubDate") or ""
        try:
            published = parsedate_to_datetime(when).astimezone(dt.timezone.utc)
        except Exception:
            continue
        if not title or published < SINCE:
            continue
        rows.append({"label": label, "title": title, "published": published,
                     "link": (item.findtext("link") or "").strip(),
                     "summary": strip_html(item.findtext("description"))[:700]})
    print("FEED_OK %s items=%d" % (url, len(rows)), flush=True)
    return rows


SCHEMA = {"name": "macro_headline", "strict": True, "schema": {
    "type": "object", "additionalProperties": False,
    "required": ["market_relevant", "headline", "category", "importance", "assets"],
    "properties": {
        "market_relevant": {"type": "boolean"},
        "headline": {"type": "string"},
        "category": {"type": "string", "enum": ["연준", "백악관", "무역·관세", "경제지표", "규제", "기타"]},
        "importance": {"type": "integer", "enum": [1, 2, 3]},
        "assets": {"type": "array", "items": {"type": "string", "enum": list(ASSETS)}},
    }}}
PROMPT = """너는 미국 거시경제 속보를 한국 투자자용 한 줄 헤드라인으로 쓰는 기자야.
주어진 공식 발표(연준·백악관 원문 제목과 요약)만 근거로 써.
- market_relevant: 주식·채권·환율·원자재 시장에 영향을 줄 만한 내용이면 true. 기념일 선포, 의전, 인사 축하 등은 false.
- headline: "[분류] 핵심 내용" 형태, 45자 이내, 숫자는 원문에 있는 것만. 발언은 큰따옴표로 짧게 인용.
  예: [연준] 파월 "추가 금리인하 서두르지 않겠다" / [백악관] 중국산 반도체 관세 25%로 인상
- importance: 3=시장 전체를 움직일 내용(금리 결정, 대형 관세), 2=업종·자산 영향, 1=참고.
- assets: 영향을 받을 자산 0~2개 (QQQ 나스닥100, SPY S&P500, DIA 다우, IWM 러셀2000, TLT 미 장기채, GLD 금, USO 원유, UUP 달러).
- 원문에 없는 내용은 지어내지 마. JSON으로만 답해."""


def groq(item):
    body = {"model": "openai/gpt-oss-120b", "temperature": 0.2, "max_completion_tokens": 700,
            "reasoning_effort": "low", "response_format": {"type": "json_schema", "json_schema": SCHEMA},
            "messages": [{"role": "system", "content": PROMPT},
                         {"role": "user", "content": "출처: %s\n제목: %s\n요약: %s" % (
                             item["label"], item["title"], item["summary"] or "(없음)")}]}
    req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",
                                 data=json.dumps(body, ensure_ascii=False).encode(),
                                 headers={"Authorization": "Bearer " + os.environ["GROQ_API_KEY"].strip(),
                                          "Content-Type": "application/json", "User-Agent": "gaemiGTP-sample/1.0"},
                                 method="POST")
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
            return json.loads(data["choices"][0]["message"]["content"]), (data.get("usage") or {}).get("total_tokens")
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt == 0:
                time.sleep(20)
                continue
            raise


BARS = {}


def bars(symbol):
    if symbol not in BARS:
        try:
            data = json.loads(get("https://query1.finance.yahoo.com/v8/finance/chart/%s?interval=5m&range=7d" % symbol))
            res = data["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            rows = []
            for i, ts in enumerate(res.get("timestamp") or []):
                if None in (q["open"][i], q["high"][i], q["low"][i], q["close"][i]):
                    continue
                rows.append((dt.datetime.fromtimestamp(ts, dt.timezone.utc), q["open"][i], q["high"][i],
                             q["low"][i], q["close"][i]))
            BARS[symbol] = rows
        except Exception as exc:
            print("BARS_FAIL %s %s" % (symbol, type(exc).__name__), flush=True)
            BARS[symbol] = []
    return BARS[symbol]


def reaction(symbol, when):
    """Base = last regular-session price at the news time; window = rest of that session,
    or the next full session when the news came outside regular hours."""
    rows = [b for b in bars(symbol)
            if dt.time(9, 30) <= b[0].astimezone(NY).time() < dt.time(16, 0)]
    if not rows:
        return None
    before = [b for b in rows if b[0] <= when]
    if not before:
        return None
    base = before[-1][4]
    ny = when.astimezone(NY)
    in_session = before[-1][0] > when - dt.timedelta(minutes=5) and dt.time(9, 30) <= ny.time() < dt.time(16, 0)
    if in_session:
        day = ny.date()
        window = [b for b in rows if b[0] > when and b[0].astimezone(NY).date() == day]
    else:
        later = [b for b in rows if b[0] > when]
        if not later:
            return {"base": base, "pending": True}
        day = later[0][0].astimezone(NY).date()
        window = [b for b in later if b[0].astimezone(NY).date() == day]
    if not window:
        return {"base": base, "pending": True}
    hi = max(b[2] for b in window)
    lo = min(b[3] for b in window)
    return {"base": base, "day": day.isoformat(), "in_session": in_session,
            "high_pct": (hi / base - 1) * 100, "low_pct": (lo / base - 1) * 100,
            "close_pct": (window[-1][4] / base - 1) * 100}


items = []
for label, url in FEEDS:
    items += read_feed(label, url)
seen, unique = set(), []
for it in sorted(items, key=lambda x: x["published"], reverse=True):
    key = it["title"].lower()
    if key not in seen:
        seen.add(key)
        unique.append(it)
unique = unique[:MAX_ITEMS]
print("ITEMS %d (since %s)" % (len(unique), SINCE.date()), flush=True)

tokens = 0
report = []
for it in unique:
    try:
        result, used = groq(it)
        tokens += used or 0
    except Exception as exc:
        print("GROQ_FAIL %s" % type(exc).__name__, flush=True)
        continue
    time.sleep(4)
    stamp = it["published"].astimezone(KST).strftime("%m/%d %H:%M")
    if not result.get("market_relevant"):
        print("\nSKIP %s [%s] %s" % (stamp, it["label"], it["title"]), flush=True)
        continue
    print("\n%s KST  중요도%d  %s" % (stamp, result["importance"], result["headline"]), flush=True)
    print("  원문: %s" % it["title"], flush=True)
    keep = False
    for sym in result["assets"][:2]:
        r = reaction(sym, it["published"])
        if not r:
            print("  %s(%s): 시세 없음" % (ASSETS[sym], sym), flush=True)
        elif r.get("pending"):
            print("  %s(%s): 다음 장 대기" % (ASSETS[sym], sym), flush=True)
        else:
            big = max(abs(r["high_pct"]), abs(r["low_pct"])) >= STORE_PCT
            keep = keep or big
            print("  %s(%s) %s %s: 최고 %+.2f%%  최저 %+.2f%%  마감 %+.2f%%%s" % (
                ASSETS[sym], sym, r["day"], "장중 발표" if r["in_session"] else "장외 발표→다음 장",
                r["high_pct"], r["low_pct"], r["close_pct"], "  ★장기저장" if big else ""), flush=True)
    report.append((stamp, result["headline"], keep))
print("\nSUMMARY relevant=%d keep=%d groq_tokens=%d" % (len(report), sum(1 for r in report if r[2]), tokens),
      flush=True)
