"""Daily Toss-style AI move analysis for the US trading-value TOP20 (DigitalOcean).

Runs once per US trading day at 10:30 New York time (00:30 KST in winter) from
gaemigtp-us-news-ai.timer, one stock every five minutes in trading-value order so
the widget receives a new article at a readable pace for live broadcasts.
For each TOP20 stock:

  Naver news -> keep only articles since the previous US close whose title names the company
  -> article bodies -> one Groq request (JSON schema) -> validate -> R2.

R2 objects (allowed by the existing uploader):
  news/ai/us/{SYMBOL}.json   one stock
  news/ai/us/TOP20.json      the whole list in ranking order, for the widget
  news/ai/us/PROFILES.json   one-sentence company intros, shown under 관련 종목

Company intros are written by the model once, the first time a stock is analysed,
and reused verbatim afterwards. A sentence in backend/data/us/company_intros.json
(edited by hand) always wins and is never overwritten.

Numbers (price, change) always come from the Kiwoom quote service, never from
the model. One run per US day is reserved in a local state file BEFORE any paid
request, so a crash or manual restart never repeats the day's AI calls.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.request
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
KST = ZoneInfo("Asia/Seoul")
MODEL = "openai/gpt-oss-120b"
STATE_PATH = Path("/var/lib/gaemigtp-news/us-news-ai-state.json")
RANKING_URL = "https://127.0.0.1/market/trading-value?market=us"
RANKING_FILE = Path("/var/lib/gaemigtp-news/kiwoom-us-top20-news.json")
SYMBOL = re.compile(r"[A-Z][A-Z0-9.-]{0,14}\Z")
MAX_ARTICLES = 6
BODY_CHARS = 1200
PACE_SECONDS = 300           # one article every 5 minutes (also far below Groq limits)
PROFILES_KEY = "news/ai/us/PROFILES.json"
MANUAL_INTROS_PATH = Path(__file__).resolve().parent / "data" / "us" / "company_intros.json"
NO_NEWS_LINE = "뚜렷한 이유가 담긴 뉴스는 확인되지 않았어요."

SYSTEM_PROMPT = """너는 미국 주식 뉴스를 한국 개인투자자에게 쉽게 설명하는 분석가야.
주어진 뉴스 기사만 근거로 오늘 이 종목이 왜 움직였는지 정리해.

먼저 type을 정해.
- "reason": 기사에서 이 종목이 오늘 움직인 직접적인 원인을 찾았을 때.
- "news": 원인이 뚜렷하지 않을 때. 이때는 이 종목에 관한 가장 중요한 최신 소식을
  기사처럼 전해. 주가가 움직인 이유라고 말하지 마.
- "none": 원인도, 전할 만한 이 종목의 소식도 없을 때.
주가가 올랐다·내렸다는 사실만 전하는 시황·장 마감 기사(예: "뉴욕증시 기술주 혼조…
○○ 상승")는 원인도 소식도 아니야. 그런 기사뿐이면 type은 "none"이야.

규칙
1. 반드시 지정된 JSON 형식으로만 답해. 다른 말은 쓰지 마.
2. keywords는 항상 정확히 3개. 각 4~12자 명사구. 기사에 실제로 나온 사건·재료만.
   예: "차세대 GPU 기대", "목표가 상향", "AI 서버 투자"
   "주가 상승", "주가 폭등", "급등", "하락" 같은 결과 표현은 키워드로 쓰지 마.
   키워드에 회사 이름은 넣지 마. (나쁜 예: "앤트로픽 상승", "엔비디아 옴니버스 호환")
3. headline_keyword는 keywords 중 주가 움직임의 가장 직접적인 이유 1개를 그대로 복사.
4. lines는 정확히 3개, 각 1문장, 해요체(~했어요, ~이에요), 60자 안팎. "~습니다"체는 쓰지 마.
   type이 "reason"이면
   - lines[0]: 주가가 움직인 직접 원인 (어떤 뉴스·사건 때문인지)
   - lines[1]: 그 원인이 시장·업종·수급에 어떻게 이어졌는지 (원인과 같은 방향으로)
   type이 "news"이면
   - lines[0]: 가장 중요한 소식 ("~한다는 소식이 있어요" 형태)
   - lines[1]: 그 소식의 배경이나 의미
   - lines[2]: 회사 소개 (두 type 모두 같음. company_profile이 있으면 그대로, 없으면 무슨 회사인지 1문장.
     종목명·티커·업종에 맞는 회사인지 확인하고, 확실하지 않은 사업 내용은 쓰지 말고 업종 수준으로만 써.)
   headline: 기사 제목 한 줄. "회사명, 핵심 내용" 형태로 회사명은 한 번만, 35자 이내.
   reason이면 원인을, news면 소식을 담아. 숫자·퍼센트는 쓰지 말고, "주가 상승"이나 "~에 하락"처럼
   주가가 움직였다는 표현으로 끝내지 마.
   예: "브로드컴, UBS '반등 여력 충분' 평가", "테슬라, 독일 정밀기계 기업 EMAG 인수 추진"
5. 숫자(주가, 등락률, 퍼센트)는 쓰지 마. 숫자는 화면이 따로 붙여.
6. 기사에 없는 내용을 지어내지 마.
7. 다른 종목이 주인공인 기사는 근거로 쓰지 마.
8. source_ids에는 근거로 쓴 기사 번호만 넣어."""

RESPONSE_SCHEMA = {
    "name": "stock_move_analysis",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["type", "headline", "headline_keyword", "keywords", "lines", "source_ids"],
        "properties": {
            "type": {"type": "string", "enum": ["reason", "news", "none"]},
            "headline_keyword": {"type": "string"},
            "headline": {"type": "string"},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "lines": {"type": "array", "items": {"type": "string"}},
            "source_ids": {"type": "array", "items": {"type": "integer"}},
        },
    },
}


# ---------------------------------------------------------------- schedule --

def us_trading_day(now=None):
    """The New York trading date if a regular session is open today, else None."""
    now = now or dt.datetime.now(dt.timezone.utc)
    day = now.astimezone(NEW_YORK).date()
    if day.weekday() >= 5:
        return None
    try:
        from backend.kiwoom_us_top20_api import _is_us_market_holiday
        if _is_us_market_holiday(day):
            return None
    except Exception:
        pass
    return day


def _is_market_holiday(day):
    try:
        from backend.kiwoom_us_top20_api import _is_us_market_holiday
        return _is_us_market_holiday(day)
    except Exception:
        return False


def previous_close(now=None):
    """16:00 New York on the last trading day before today's New York date.

    Only articles published after it can explain today's move; older ones
    (for example last quarter's earnings reaction) are left out.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    day = now.astimezone(NEW_YORK).date() - dt.timedelta(days=1)
    while day.weekday() >= 5 or _is_market_holiday(day):
        day -= dt.timedelta(days=1)
    return dt.datetime.combine(day, dt.time(16), tzinfo=NEW_YORK)


def read_state(path=STATE_PATH):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(state, path=STATE_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


# ------------------------------------------------------------------ inputs --

def read_top20(opener=None):
    """Ranking with Kiwoom-verified change rates; fall back to the local file."""
    try:
        request = urllib.request.Request(RANKING_URL, headers={"Origin": "https://gaemigtp-main.pages.dev"})
        opener = opener or urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
        with opener.open(request, timeout=30) as response:
            items = json.load(response).get("items") or []
    except Exception:
        data = json.loads(RANKING_FILE.read_text(encoding="utf-8"))
        items = data.get("items") or []
    industries = {}
    try:
        for row in json.loads(RANKING_FILE.read_text(encoding="utf-8")).get("items") or []:
            if isinstance(row, dict) and isinstance(row.get("industry"), str) and row["industry"].strip():
                industries[str(row.get("symbol") or "").upper()] = row["industry"].strip()
    except (OSError, ValueError):
        pass
    rows = []
    for index, item in enumerate(items[:20]):
        symbol = str(item.get("symbol") or "").strip().upper()
        name = str(item.get("name") or "").strip()
        if not SYMBOL.fullmatch(symbol) or not name:
            continue
        change = item.get("change_pct")
        rows.append({
            "rank": item.get("rank") or index + 1, "symbol": symbol, "name": name,
            "price": item.get("price") if type(item.get("price")) in (int, float) else None,
            "change_pct": change if type(change) in (int, float) else None,
            "reference_close_date": item.get("reference_close_date"),
            "industry": (item.get("industry") if isinstance(item.get("industry"), str) else "")
                        or industries.get(symbol, ""),
        })
    return rows


def published_at(article):
    raw = str(article.get("published_at") or article.get("pubDate") or "")
    try:
        stamp = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            stamp = parsedate_to_datetime(raw)
        except Exception:
            return None
    return stamp if stamp.tzinfo else None


def title_terms(stock):
    terms = {stock["name"], stock["symbol"]}
    try:
        from backend.services.news_identity_registry import resolve_us_news_identity
        terms.update(resolve_us_news_identity(stock["name"]).get("search_terms") or [])
    except Exception:
        pass
    return {str(t).strip().lower() for t in terms if isinstance(t, str) and len(str(t).strip()) >= 2}


def title_names(title, term):
    """Long names match anywhere; short names (3 chars or less) only as a whole word."""
    lowered = title.lower()
    if len(term) > 3:
        return term in lowered
    pattern = r"(?<![0-9a-z가-힣])" + re.escape(term) + r"(?![0-9a-z가-힣])"
    # Korean particles may follow a short name: 메타가, 릴리의 ...
    particle = r"(?<![0-9a-z가-힣])" + re.escape(term) + r"(?:은|는|이|가|을|를|의|도|와|과|에|로|,|·)"
    return bool(re.search(pattern, lowered) or re.search(particle, lowered))


def select_articles(stock, raw, now=None):
    """Articles since the previous close whose title names this company, newest first."""
    now = now or dt.datetime.now(dt.timezone.utc)
    since = previous_close(now)
    terms = title_terms(stock)
    seen, picked = set(), []
    for article in raw or []:
        if not isinstance(article, dict):
            continue
        title = str(article.get("title") or "").strip()
        url = str(article.get("url") or article.get("originallink") or article.get("link") or "").strip()
        stamp = published_at(article)
        if (not title or not url.startswith(("https://", "http://")) or stamp is None
                or not since <= stamp <= now + dt.timedelta(minutes=5)
                or (url or title) in seen):
            continue
        if not any(title_names(title, term) for term in terms):
            continue
        seen.add(url or title)
        picked.append({**article, "title": title, "url": url, "_published": stamp})
    picked.sort(key=lambda a: a["_published"], reverse=True)
    return picked[:MAX_ARTICLES]


def attach_bodies(articles, reader=None):
    if not articles:
        return articles
    try:
        if reader is None:
            from backend.services.news_detail import read_selected_article_details as reader
        details = reader([{"title": a["title"], "url": a["url"]} for a in articles],
                         limit=len(articles), with_sources=True)
        for article, detail in zip(articles, details or []):
            text = str((detail or {}).get("text") or "").strip() if isinstance(detail, dict) else ""
            if len(text) >= 300:
                article["body"] = text[:BODY_CHARS]
    except Exception as exc:
        print("[us-news-ai] body_error=" + type(exc).__name__, flush=True)
    return articles


# -------------------------------------------------------------------- model --

def build_user_message(stock, articles, company_profile=None):
    change = stock.get("change_pct")
    direction = "상승" if change and change > 0 else "하락" if change and change < 0 else "보합"
    lines = [f"종목: {stock['name']} ({stock['symbol']})", f"오늘 움직임: {direction}"]
    if stock.get("industry"):
        lines.append("업종: " + stock["industry"])
    if company_profile:
        lines.append("company_profile: " + company_profile)
    lines += ["", "기사:"]
    for index, article in enumerate(articles, 1):
        stamp = article["_published"].astimezone(KST).strftime("%m-%d %H:%M")
        content = str(article.get("body") or article.get("description") or "")[:BODY_CHARS]
        lines.append(f"[{index}] ({article.get('source') or ''}, {stamp}) {article['title']} / {content}")
    return "\n".join(lines)


RESULT_WORDS = re.compile(r"(?:주가\s*)?(?:상승|하락|급등|급락|폭등|폭락|반등)$")


# Only a headline that reports the price move itself is rejected ("…에 상승", "주가 급등");
# a cause such as "UBS 상승 가능성" or "반등 기대" is fine.
MOVE_WORDS = re.compile(r"주가\s*(?:상승|하락|급등|급락|폭등|폭락)|(?:에|로|으로)\s*(?:상승|하락|급등|급락|폭등|폭락)\s*$")


def validate(result, article_count, company_terms=()):
    problems = []
    if not isinstance(result, dict):
        return ["not_object"]
    kind = result.get("type")
    if kind not in ("reason", "news"):
        problems.append("type")
    keywords = result.get("keywords")
    if (not isinstance(keywords, list) or len(keywords) != 3
            or any(not isinstance(k, str) or not 2 <= len(k.strip()) <= 20 for k in keywords)):
        problems.append("keywords")
    elif any(RESULT_WORDS.search(k.strip()) for k in keywords):
        problems.append("result_keyword")
    elif any(term in k.lower() for k in keywords for term in company_terms if len(term) >= 2):
        problems.append("company_in_keyword")
    if result.get("headline_keyword") not in (keywords or []):
        problems.append("headline_keyword")
    lines = result.get("lines")
    if (not isinstance(lines, list) or len(lines) != 3
            or any(not isinstance(l, str) or not 5 <= len(l.strip()) <= 160 for l in lines)):
        problems.append("lines")
    else:
        if any(re.search(r"\d+(?:\.\d+)?\s*%|\$\s*\d", line) for line in lines):
            problems.append("number_in_lines")
        if any(re.search(r"(?:습니다|입니다|됩니다)\.?$", line.strip()) for line in lines):
            problems.append("formal_ending")
    headline = result.get("headline")
    if (not isinstance(headline, str) or not 5 <= len(headline.strip()) <= 40
            or re.search(r"\d+(?:\.\d+)?\s*%", headline) or MOVE_WORDS.search(headline)):
        problems.append("headline")
    ids = result.get("source_ids")
    if not isinstance(ids, list) or not ids or any(type(i) is not int or not 1 <= i <= article_count for i in ids):
        problems.append("source_ids")
    return problems


def call_groq(user_message, *, api_key=None, opener=urllib.request.urlopen, sleeper=time.sleep):
    api_key = api_key or os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("groq_key_missing")
    payload = {
        "model": MODEL, "temperature": 0.2, "max_completion_tokens": 1500, "reasoning_effort": "low",
        "response_format": {"type": "json_schema", "json_schema": RESPONSE_SCHEMA},
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": user_message}],
    }
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json",
                 "User-Agent": "gaemiGTP-us-news-ai/1.0"}, method="POST")
    for attempt in range(2):
        try:
            with opener(request, timeout=60) as response:
                body = json.load(response)
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt == 0:
                wait = float(exc.headers.get("retry-after") or 30) if exc.headers else 30
                sleeper(min(max(wait, 5), 90))
                continue
            raise RuntimeError("groq_http_" + str(exc.code)) from None
    choice = body["choices"][0]
    if choice.get("finish_reason") == "length":
        raise RuntimeError("groq_truncated")
    usage = body.get("usage") or {}
    return json.loads(choice["message"]["content"]), usage.get("total_tokens")


# ----------------------------------------------------------------- results --

def stock_payload(stock, day, now, *, status, result=None, articles=(), tokens=None, diagnostics=None):
    payload = {
        "ok": status == "ok", "status": status, "market": "US", "exchange_day": day.isoformat(),
        "generated_at": now.isoformat(), "rank": stock["rank"], "symbol": stock["symbol"],
        "name": stock["name"], "price": stock.get("price"), "change_pct": stock.get("change_pct"),
        "reference_close_date": stock.get("reference_close_date"), "model": MODEL,
    }
    if stock.get("industry"):
        payload["industry"] = stock["industry"]
    if result:
        used = set(result.get("source_ids") or [])
        payload.update({
            "type": result["type"],
            "headline_keyword": result["headline_keyword"].strip(),
            "headline": result["headline"].strip(),
            "keywords": [k.strip() for k in result["keywords"]],
            "lines": [l.strip() for l in result["lines"]],
            # Stored for checking only; the site never shows these sources.
            "sources": [{
                "title": a["title"], "url": a["url"], "source": str(a.get("source") or "")[:80],
                "published_at": a["_published"].isoformat(),
            } for i, a in enumerate(articles, 1) if i in used],
        })
    if tokens is not None:
        payload["tokens"] = tokens
    if diagnostics:
        payload["diagnostics"] = diagnostics
    return payload


def upload_json(payload, object_key, uploader=None):
    if uploader is None:
        from backend.services.r2_news_uploader import upload_file as uploader
    path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            path = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        if not uploader(path, object_key=object_key):
            raise RuntimeError("r2_upload_failed")
    finally:
        if path is not None:
            path.unlink(missing_ok=True)


# ---------------------------------------------------------------- intros --

def read_manual_intros(path=MANUAL_INTROS_PATH):
    """Hand-edited intros {SYMBOL: sentence}; missing or broken file means none."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {symbol: text.strip() for symbol, text in data.items()
            if isinstance(symbol, str) and SYMBOL.fullmatch(symbol)
            and isinstance(text, str) and 5 <= len(text.strip()) <= 160}


def intro_map(ai_profiles, manual):
    """Hand-edited sentences win over model-written ones."""
    merged = {symbol: text for symbol, text in (ai_profiles or {}).items()
              if isinstance(text, str) and text.strip()}
    merged.update(manual)
    return merged


def publish_profiles(ai_profiles, manual, now, upload=None):
    upload = upload or upload_json
    items = {}
    for symbol, text in sorted(intro_map(ai_profiles, manual).items()):
        items[symbol] = {"intro": text, "source": "manual" if symbol in manual else "ai"}
    upload({"ok": True, "generated_at": now.isoformat(), "items": items}, PROFILES_KEY)
    return len(items)


def analyze_stock(stock, profiles, *, fetch=None, reader=None, groq=call_groq, now=None):
    """Returns (status, result, articles, tokens, diagnostics)."""
    if fetch is None:
        from backend.services.news_feed import fetch_stock_news as fetch
    raw = fetch(stock["name"], market="미국", limit=50, raise_on_error=True) or []
    articles = attach_bodies(select_articles(stock, raw, now=now), reader=reader)
    diagnostics = {"fetched": len(raw), "articles": len(articles),
                   "bodies": sum(1 for a in articles if a.get("body")), "attempts": 0}
    if not articles:
        return "no_news", None, [], None, diagnostics
    message = build_user_message(stock, articles, profiles.get(stock["symbol"]))
    tokens = 0
    for attempt in range(2):
        diagnostics["attempts"] = attempt + 1
        result, used = groq(message)
        tokens += used or 0
        if isinstance(result, dict) and result.get("type") == "none":
            # Only market wraps that restate the move: nothing to publish.
            return "no_news", None, articles, tokens, diagnostics
        problems = validate(result, len(articles), company_terms=title_terms(stock))
        if not problems:
            return "ok", result, articles, tokens, diagnostics
        diagnostics["problems"] = problems
        print("[us-news-ai] %s invalid=%s attempt=%d" % (stock["symbol"], problems, attempt + 1), flush=True)
    return "invalid", None, articles, tokens, diagnostics


def run(now=None, *, top20=read_top20, analyze=analyze_stock, upload=upload_json,
        state_path=STATE_PATH, sleeper=time.sleep, force=False, clock=None,
        read_manual=read_manual_intros, manual_path=MANUAL_INTROS_PATH):
    now = now or dt.datetime.now(dt.timezone.utc)
    day = us_trading_day(now)
    if day is None:
        print("[us-news-ai] not_a_trading_day", flush=True)
        return {"status": "not_trading_day"}
    state = read_state(state_path)
    if state.get("last_day") == day.isoformat() and not force:
        print("[us-news-ai] already_ran day=" + day.isoformat(), flush=True)
        return {"status": "already_ran"}
    stocks = top20()
    if not stocks:
        raise RuntimeError("top20_unavailable")
    # Reserve the day before any paid request; a crash never repeats it.
    state["last_day"] = day.isoformat()
    state.setdefault("profiles", {})
    write_state(state, state_path)
    manual = read_manual(manual_path)
    items, counts = [], {}

    def publish_intros():
        try:
            publish_profiles(state["profiles"], manual, clock() if clock else now, upload=upload)
        except Exception as exc:
            print("[us-news-ai] profiles_upload_error=" + type(exc).__name__, flush=True)

    # Hand edits reach the site on the next run even if no new stock appears.
    publish_intros()

    def publish_list(done):
        upload({"ok": True, "market": "US", "exchange_day": day.isoformat(),
                "generated_at": now.isoformat(), "complete": done, "counts": dict(counts),
                "items": items}, "news/ai/us/TOP20.json")

    for index, stock in enumerate(stocks):
        if index:
            sleeper(PACE_SECONDS)
        stock_time = clock() if clock else now
        try:
            status, result, articles, tokens, diagnostics = analyze(stock, intro_map(state["profiles"], manual))
        except Exception as exc:
            print("[us-news-ai] %s error=%s" % (stock["symbol"], type(exc).__name__), flush=True)
            status, result, articles, tokens, diagnostics = "failed", None, [], None, None
        payload = stock_payload(stock, day, stock_time, status=status, result=result, articles=articles,
                                tokens=tokens, diagnostics=diagnostics)
        if status == "ok":
            new_intro = stock["symbol"] not in state["profiles"] and stock["symbol"] not in manual
            state["profiles"].setdefault(stock["symbol"], payload["lines"][2])
            write_state(state, state_path)
            if new_intro:
                publish_intros()
            try:
                upload(payload, f"news/ai/us/{stock['symbol']}.json")
            except Exception as exc:
                print("[us-news-ai] %s upload_error=%s" % (stock["symbol"], type(exc).__name__), flush=True)
        counts[status] = counts.get(status, 0) + 1
        items.append(payload)
        print("[us-news-ai] %s %s tokens=%s" % (stock["symbol"], status, tokens), flush=True)
        # Publish after every stock so a new article appears every five minutes.
        if status == "ok":
            try:
                publish_list(False)
            except Exception as exc:
                print("[us-news-ai] list_upload_error=" + type(exc).__name__, flush=True)
    publish_list(True)
    print("[us-news-ai] done day=%s counts=%s" % (day.isoformat(), counts), flush=True)
    return {"status": "done", "counts": counts}


def main():
    app_root = str(Path(__file__).resolve().parents[1])
    if app_root not in sys.path:
        sys.path.insert(0, app_root)
    try:
        if "--publish-profiles" in sys.argv[1:]:
            # No AI call: republish the saved intros (after a hand edit).
            count = publish_profiles(read_state(STATE_PATH).get("profiles") or {},
                                     read_manual_intros(), dt.datetime.now(dt.timezone.utc))
            print("[us-news-ai] profiles_published=%d" % count, flush=True)
            return 0
        run(force="--force" in sys.argv[1:], clock=lambda: dt.datetime.now(dt.timezone.utc))
    except Exception as exc:
        print("[us-news-ai] failed=" + type(exc).__name__, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
