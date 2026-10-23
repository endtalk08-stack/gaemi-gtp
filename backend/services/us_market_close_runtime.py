"""Production US-close source verification for the existing DigitalOcean timer.

NAVER's actual major-index closes + two validated newspaper article bodies.
No artificial indices, cached old sessions, summary-only sources, or AI calls.
Render only reads the resulting Neon brief and never imports this module.
"""
import datetime as dt
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
import html
import json
import re
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
KST = ZoneInfo("Asia/Seoul")
UTC = dt.timezone.utc
INDEX_CODES = {".DJI": "다우존스", ".IXIC": "나스닥 종합", ".INX": "S&P 500"}
US_TITLE = re.compile(r"뉴욕\s*증시|미국\s*증시|美\s*증시|나스닥|다우존스", re.I)
CLOSE_TITLE = re.compile(r"마감|혼조|반등|상승|하락", re.I)
KR_TITLE = re.compile(r"코스피|코스닥|국장|한국\s*증시|국내\s*증시|삼성전자|코스피200", re.I)
PRE_OPEN = re.compile(r"개장|장중|선물|프리마켓|장전|전망|예상", re.I)
US_BODY = re.compile(r"뉴욕\s*증시|미국\s*증시|뉴욕증권거래소|NYSE|나스닥|다우존스|S&P\s*500", re.I)
INVALID_BODY = re.compile(r"Google 검색에서|이용약관|개인정보처리방침|저작물로 저작권", re.I)
BODY_MARKETS = (re.compile("나스닥"), re.compile(r"다우(?:존스)?"), re.compile(r"S&P\s*500|스탠더드앤드푸어스", re.I))
TOPICS = ("반도체", "AI", "인공지능", "기술주", "금리", "국채", "유가", "원유", "프랑스", "중동", "경기", "매수", "실적", "수익성")


def _text(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", str(value or "")))).strip()


def _date(value):
    try:
        stamp = parsedate_to_datetime(str(value or ""))
        if stamp.tzinfo:
            return stamp.astimezone(KST)
    except (TypeError, ValueError, IndexError):
        pass
    return None


def _url_identity(url):
    try:
        url_parts = urllib.parse.urlsplit(url)
        if url_parts.scheme not in ("http", "https") or not url_parts.hostname:
            return None
        if url_parts.hostname.lower() in ("naver.com", "news.naver.com"):
            return None
        query_keys = ("idxno", "newsid", "articleid", "ud", "no", "id", "news_id", "mediacodeno")
        query = [(k.lower(), v) for k, v in urllib.parse.parse_qsl(url_parts.query) if k.lower() in query_keys]
        return (url_parts.hostname.lower().removeprefix("www.") + url_parts.path.rstrip("/")
                + "?" + urllib.parse.urlencode(sorted(query)))
    except ValueError:
        return None


def _headline_score(title):
    score = sum(weight for word, weight in
                (("뉴욕증시", 4), ("마감", 3), ("혼조", 2), ("나스닥", 1),
                 ("다우", 1), ("반도체", 2), ("금리", 2), ("유가", 2))
                if word in title.replace(" ", ""))
    return score - 3 if "속보" in title else score


def _article_topic(title):
    if re.search(r"금리|국채|유가|중동|프랑스", title):
        return "macro"
    if re.search(r"반도체|AI|인공지능|기술주", title, re.I):
        return "technology"
    return "market"


def _verified_article(entry, body, source, session_date):
    if source not in ("article_or_main_paragraphs", "jsonld_article_body") or len(body) < 700:
        return False
    if INVALID_BODY.search(body[:420]) or not US_BODY.search(body[:500]):
        return False
    if len(US_BODY.findall(body[:1800])) < 2:
        return False
    if sum(bool(p.search(body)) for p in BODY_MARKETS) < 2:
        return False
    if not re.search(r"마감|거래를\s*마쳤|장을\s*마쳤|종가|하락|상승|혼조", body[:1500]):
        return False
    if not any(re.search(re.escape(term), entry["title"], re.I) and
               re.search(re.escape(term), body, re.I) for term in TOPICS):
        return False
    # Body must identify the covered U.S. trading day, not merely be published today.
    if not re.search(rf"(?<!\d){session_date.day}일\b", body[:1800]):
        return False
    return True


def verified_originals(session_date, now_utc=None, search=None, reader=None):
    """Search date-locked NAVER publisher headlines and verify two actual bodies.

    No source that fails body checks is passed to Groq, not even as a fallback.
    """
    from backend.providers.naver_news import fetch_news
    from backend.services.news_detail import read_selected_article_details

    now = (now_utc or dt.datetime.now(UTC)).astimezone(KST)
    close = dt.datetime.combine(session_date, dt.time(16), tzinfo=NY).astimezone(KST)
    upper = min(now, close + dt.timedelta(hours=7))
    if upper <= close:
        return []
    search_fn = search or fetch_news
    all_rows = []
    for query in ("뉴욕증시 마감", "뉴욕증시 혼조 마감", f"나스닥 다우 {session_date.day}일 마감"):
        all_rows.extend(search_fn(query, display=100, raise_on_error=True))
    candidate = {}
    for row in all_rows:
        if not isinstance(row, dict):
            continue
        published = _date(row.get("raw_pub_date") or row.get("pubDate"))
        if published is None or not close <= published <= upper:
            continue
        title = _text(row.get("raw_title") or row.get("title"))
        if (not US_TITLE.search(title) or not CLOSE_TITLE.search(title)
                or KR_TITLE.search(title) or PRE_OPEN.search(title)):
            continue
        url = str(row.get("raw_original_link") or row.get("originallink")
                  or row.get("raw_link") or row.get("link") or "").strip()
        identity = _url_identity(url)
        if not identity:
            continue
        entry = {"title": title, "url": url,
                 "publisher": urllib.parse.urlsplit(url).hostname or "",
                 "published_at": published.isoformat(),
                 "score": _headline_score(title)}
        previous = candidate.get(identity)
        if previous is None or entry["score"] > previous["score"]:
            candidate[identity] = entry
    short = sorted(candidate.values(), key=lambda a: (-a["score"], a["published_at"]))[:36]
    if not short:
        print("[us-close] zero US-only matching headlines", flush=True)
        return []
    read_fn = reader or read_selected_article_details
    results = read_fn(short, limit=len(short), with_sources=True)
    valid = []
    for entry, result in zip(short, results):
        if not isinstance(result, dict):
            continue
        body = str(result.get("text") or "").strip()
        if not _verified_article(entry, body, str(result.get("source") or ""), session_date):
            continue
        valid.append({**entry, "description": body[:5000], "body_chars": len(body),
                      "group": _article_topic(entry["title"])})
    # Keep the most substantial articles; eliminate duplicate wording and publishers.
    unique = []
    for entry in sorted(valid, key=lambda a: (a["body_chars"], a["score"]), reverse=True):
        if any(entry["publisher"] == old["publisher"]
               or SequenceMatcher(None, entry["description"][:900], old["description"][:900]).ratio() >= .78
               or SequenceMatcher(None, entry["title"], old["title"]).ratio() >= .82
               for old in unique):
            continue
        unique.append(entry)
    chosen = []
    for topic in ("market", "macro", "technology"):
        group = [a for a in unique if a["group"] == topic and a not in chosen]
        if group:
            chosen.append(max(group, key=lambda a: a["body_chars"]))
    for entry in unique:
        if len(chosen) >= 2:
            break
        if entry not in chosen:
            chosen.append(entry)
    chosen = chosen[:2]
    print(f"[us-close] search={len(all_rows)} originals_tested={len(short)} "
          f"verified={len(valid)} distinct={len(unique)} selected={len(chosen)} "
          f"session={session_date}", flush=True)
    return chosen if len(chosen) == 2 else []


def verified_indices(session_date, opener=None):
    """Require three actual NASDAQ/Dow/S&P NAVER closes for exactly one NY day."""
    url = ("https://stock.naver.com/api/polling/worldstock/index?"
           + urllib.parse.urlencode({"reutersCodes": ",".join(INDEX_CODES)}))
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
        "Referer": "https://stock.naver.com/", "Accept": "application/json",
    })
    with (opener or urllib.request.urlopen)(req, timeout=10) as resp:
        payload = json.loads(resp.read(210000))
    if not isinstance(payload, dict) or not isinstance(payload.get("datas"), list):
        raise ValueError("us_indices_bad_shape")
    rows = {}
    for entry in payload["datas"]:
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("reutersCode") or "")
        if code not in INDEX_CODES or code in rows:
            continue
        time = dt.datetime.fromisoformat(str(entry.get("localTradedAt") or "").replace("Z", "+00:00"))
        if not time.tzinfo or time.astimezone(NY).date() != session_date:
            raise ValueError("us_index_wrong_trade_date_" + code)
        if str(entry.get("marketStatus") or "").upper() != "CLOSE":
            raise ValueError("us_index_not_closed_" + code)
        def number(key):
            return float(str(entry.get(key + "Raw") or entry.get(key) or "").replace(",", ""))
        close = number("closePrice")
        delta = number("compareToPreviousClosePrice")
        pct = number("fluctuationsRatio")
        if not 0 < close < 10_000_000 or abs(delta) > close * .5 or abs(pct) > 40 or close - delta <= 0:
            raise ValueError("us_index_invalid_price_" + code)
        rows[code] = {"symbol": code, "name": INDEX_CODES[code],
                      "session_date_et": session_date.isoformat(), "close": round(close, 2),
                      "change": round(delta, 2), "change_pct": round(pct, 2)}
    if set(rows) != set(INDEX_CODES):
        raise ValueError("us_indices_incomplete")
    return [rows[code] for code in (".DJI", ".IXIC", ".INX")]
