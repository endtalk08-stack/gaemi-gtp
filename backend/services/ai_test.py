"""Private, opt-in Groq evaluation API. Separate from the existing analysis routes.

No Groq calls occur unless AI_TEST_ENABLED, AI_TEST_TOKEN and GROQ_API_KEY
are set. Administrator /ai-test calls use Groq's provider quotas directly.
Existing private central-chat in-process quotas stay unchanged.
"""
import datetime
import hmac
import json
import math
import os
import re
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict, deque
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request
from .market_rankings import get_market_selection, get_market_menu_rows, analysis_ticker_for_selection

ai_test_bp = Blueprint("ai_test", __name__)

MODELS = {
    "news": {"id": "openai/gpt-oss-20b", "limit": 10, "label": "뉴스·일반"},
    "deep": {"id": "openai/gpt-oss-120b", "limit": 5, "label": "공시·심층"},
    "compare": {"id": "qwen/qwen3.8-27b", "limit": 5, "label": "비교 테스트"},
    "cloudflare": {"id": "@cf/openai/gpt-oss-20b", "limit": 0, "label": "Cloudflare 뉴스 분석"},
}
MAX_TOTAL_PER_DAY = 20
MAX_CALLS_PER_MINUTE = 2
_COUNTS = defaultdict(int)
_RECENT = []
_LOCK = threading.Lock()
_DAY = ""
# A short-lived reuse of the same processed /analyze data, not another collector.
_CHAT_CONTEXT_CACHE = {}
_CHAT_CONTEXT_LOCK = threading.Lock()
_CHAT_CONTEXT_TTL = 15 * 60

# Groq's own organization/project quotas govern administrator evaluation calls.
# Reference values are from the Free organization's Limits page, not remaining usage.
_GROQ_REFERENCE_LIMITS = {
    "requests_per_minute": 30,
    "requests_per_day": 1000,
    "tokens_per_minute": 8000,
    "tokens_per_day": 200000,
}
_GROQ_RATE_LIMIT_EVENTS = deque(maxlen=100)
_GROQ_RATE_LIMIT_LOCK = threading.Lock()

# Administrator /ai-test usage only. Groq remains the sole quota enforcer.
_GROQ_CALL_EVENTS = deque(maxlen=100)
_GROQ_CALL_LOCK = threading.Lock()
_GROQ_USAGE_DAY = ""
_GROQ_DAILY_USAGE = {}
_GROQ_LATEST_REMAINING = {}  # Last observed Groq response headers, by model.




def _chat_cache_key(stock, selection=None):
    return (stock, selection["market"], selection["symbol"]) if selection else stock


def remember_chat_analysis(stock, result, selection=None):
    from .private_access import private_enabled
    if not private_enabled() or result.get("ok") is False:
        return
    try:
        context = _context(stock, result)
    except (TypeError, ValueError, AttributeError):
        return  # Never fail the existing /analyze route for a chat-only cache.
    with _CHAT_CONTEXT_LOCK:
        _CHAT_CONTEXT_CACHE[_chat_cache_key(str(stock).strip(), selection)] = (time.monotonic(), context)


def _cached_chat_context(stock, selection=None):
    with _CHAT_CONTEXT_LOCK:
        entry = _CHAT_CONTEXT_CACHE.get(_chat_cache_key(stock, selection))
        if entry and time.monotonic() - entry[0] < _CHAT_CONTEXT_TTL:
            return entry[1]
    return None


def _question_stock(question):
    from .engine import TICKERS
    value = str(question or "").strip().casefold()
    for name in sorted(TICKERS, key=len, reverse=True):
        normalized = name.casefold()
        if value.startswith(normalized) and (
            len(value) == len(normalized) or
            value[len(normalized)] in " \t,，:：?？"
        ):
            return name
    return ""



def _is_market_gainers_question(question):
    """Recognize market-wide gainer questions, not a named stock's movement."""
    compact = re.sub(r"\s+", "", str(question or "").casefold())
    pattern = (
        r"(?:상승(?:한)?(?:종목|주식|주)|상승률(?:순위|상위|랭킹|top\d*)|"
        r"급등(?:주|종목)|오른(?:종목|주식)|많이오른(?:종목|주식))"
    )
    if not re.search(pattern, compact, flags=re.IGNORECASE):
        return False
    return not _question_stock(question)



def _market_ranking_request(question):
    """Recognize direct questions about either existing market menu."""
    compact = re.sub(r"\s+", "", str(question or "").casefold())
    if re.search(r"(왜|이유|원인|전망|분석|추천|매수|매도)", compact):
        return None
    if "거래대금" in compact:
        menu = "value"
    elif re.search(r"(인기순위|인기랭킹|인기종목|인기주식|인기top|인기상위)", compact):
        menu = "popular"
    else:
        return None
    if not re.search(r"(순위|랭킹|상위|top\d*|\d+위|몇위|누구|뭐야|종목|목록|알려|보여)", compact):
        return None
    market = "us" if re.search(r"(미국|미장|해외|나스닥|뉴욕증시)", compact) else "kr"
    return market, menu


def _market_ranking_reply(question):
    """Read existing sidebar rows and answer only the requested rank or range."""
    request_info = _market_ranking_request(question)
    if not request_info:
        return None
    market, menu = request_info
    rows = get_market_menu_rows(market, menu)
    if not rows:
        from .market_rankings import (
            build_kr_trading_value_result, build_us_trading_value_result,
            build_kr_popular_result, build_us_popular_result,
        )
        builder = {
            ("kr", "value"): build_kr_trading_value_result,
            ("us", "value"): build_us_trading_value_result,
            ("kr", "popular"): build_kr_popular_result,
            ("us", "popular"): build_us_popular_result,
        }[(market, menu)]
        builder(limit=20)
        rows = get_market_menu_rows(market, menu)
    label = ("미국" if market == "us" else "국내") + (" 거래대금" if menu == "value" else " 인기순위")
    if not rows:
        return label + " 데이터를 지금 확인하지 못했어."
    compact = re.sub(r"\s+", "", question.casefold())

    def rank_of(row):
        try:
            return int(row.get("rank"))
        except (TypeError, ValueError):
            return None

    def describe(row):
        rank = rank_of(row)
        name = str(row.get("name") or "").strip()
        result = (str(rank) + "위 " if rank is not None else "") + name
        if menu == "value":
            amount = row.get("trading_value_text")
            if amount:
                result += " · 거래대금 " + str(amount)
            elif isinstance(row.get("trading_value"), (int, float)):
                value = row["trading_value"]
                result += (" · 거래대금 " + format(value / 1e8, ",.1f") + "억원"
                           if market == "kr" else " · 거래대금 $" + format(value, ",.0f"))
        return result

    # A named stock's rank is different from requesting an entire list.
    names = [row for row in rows if row.get("name") and str(row["name"]).casefold() in compact]
    if names and re.search(r"(몇위|순위|랭킹)", compact):
        row = max(names, key=lambda item: len(str(item["name"])))
        return str(row["name"]) + "은(는) " + label + " " + describe(row) + "야."

    between = re.search(r"(\d{1,2})위(?:부터|~|-)(\d{1,2})위", compact)
    if between:
        start, end = int(between.group(1)), int(between.group(2))
        if start < 1 or end < start:
            return "순위 범위를 다시 확인해 줘."
    else:
        ordinal = re.search(r"(\d{1,2})위", compact)
        if ordinal:
            rank = int(ordinal.group(1))
            row = next((item for item in rows if rank_of(item) == rank), None)
            return (label + " " + describe(row) + "야." if row else
                    label + " " + str(rank) + "위는 현재 조회된 TOP 20에서 확인할 수 없어.")
        count = re.search(r"(?:top|상위)(\d{1,2})", compact, re.IGNORECASE)
        start, end = 1, int(count.group(1)) if count else 20

    if end < 1:
        return "순위는 1위부터 확인할 수 있어."
    selected_rows = [row for row in rows if rank_of(row) is not None
                     and start <= rank_of(row) <= min(end, 20)]
    if re.search(r"(상승한|오른종목|상승종목|상승중|플러스)", compact):
        selected_rows = [row for row in selected_rows
                         if isinstance(row.get("change_pct"), (int, float)) and row["change_pct"] > 0]
    if not selected_rows:
        return label + " 조건에 맞는 종목이 조회 결과에 없어."
    header = label + " " + str(start) + "~" + str(min(end, 20)) + "위야:"
    return header + "\n" + "\n".join(describe(row) for row in selected_rows)


SYSTEM_PROMPT = "쉽게 설명 반말로 대답해"
INFO_STYLE_PROMPT = "답변은 간결하게 작성하고, 불필요한 표와 코드블록은 사용하지 마."
PRIVATE_CHAT_MAX_ANSWER_CHARS = 1500
PRIVATE_CHAT_LENGTH_PROMPT = "답변은 1500자 이내로 작성하고 문장을 완결해."
PRIVATE_CHAT_PRICE_PROMPT = (
    "주가와 등락률은 참고 데이터의 확인된 숫자만 사용해. "
    "가격 제공사 이름, 시세 수신·연결 상태, 내부 데이터 처리 과정을 답변에 언급하지 마. "
    "확인된 가격의 기준 시각이 과거라면 실시간 거래 가격이라고 표현하지 마. "
    "가격이 없으면 추측하지 말고 가격을 묻는 경우에만 확인된 값이 없다고 간단히 답해."
)


def _settings_ready():
    return (
        os.getenv("AI_TEST_ENABLED") == "1"
        and len(os.getenv("AI_TEST_TOKEN", "")) >= 16
        and bool(os.getenv("GROQ_API_KEY", "").strip())
    )


def _private_provider_ready(role):
    """Preview chat is authorized by its private session, not admin test flags."""
    if role == "cloudflare":
        return bool(
            os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
            and (os.environ.get("CLOUDFLARE_API_TOKEN")
                 or os.environ.get("CLOUDFLARE_API_KEY")
                 or os.environ.get("CLOUDFLARE_AUTH_TOKEN") or "").strip()
        )
    return bool(os.environ.get("GROQ_API_KEY", "").strip())


def _authorized():
    if not _settings_ready():
        return False
    provided = request.headers.get("Authorization", "")
    if not provided.startswith("Bearer "):
        return False
    secret = os.getenv("AI_TEST_TOKEN", "")
    return hmac.compare_digest(provided[7:], secret)


def _state():
    global _DAY
    today = datetime.datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
    if today != _DAY:
        _COUNTS.clear()
        _DAY = today
    cutoff = time.monotonic() - 60
    _RECENT[:] = [stamp for stamp in _RECENT if stamp > cutoff]
    return today


def _remaining():
    with _LOCK:
        day = _state()
        used = {role: _COUNTS[role] for role in MODELS}
        return {
            "date_kst": day,
            "total": {"used": sum(used.values()), "limit": MAX_TOTAL_PER_DAY},
            "models": {
                role: {
                    "label": model["label"],
                    "model_id": model["id"],
                    "used": used[role],
                    "limit": model["limit"],
                }
                for role, model in MODELS.items()
            },
            "per_minute_limit": MAX_CALLS_PER_MINUTE,
            "reset_warning": "서버 재시작·재배포 시 테스트 카운터가 초기화될 수 있습니다.",
        }


def _today_kst():
    return datetime.datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()


def _empty_usage_totals():
    return {
        "successful_calls": 0, "failed_calls": 0, "metered_calls": 0,
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
    }


def _usage_numbers(usage):
    source = usage if isinstance(usage, dict) else {}
    fields = ("prompt_tokens", "completion_tokens", "total_tokens")
    return {
        key: source[key] if isinstance(source.get(key), int)
        and not isinstance(source.get(key), bool) and source[key] >= 0 else None
        for key in fields
    }


def _record_groq_call(role, outcome, usage=None, limit_type="", http_status=None):
    global _GROQ_USAGE_DAY, _GROQ_DAILY_USAGE
    now = datetime.datetime.now(ZoneInfo("Asia/Seoul"))
    measured = _usage_numbers(usage)
    event = {
        "timestamp_kst": now.isoformat(timespec="seconds"),
        "role": role, "model_id": MODELS[role]["id"], "status": outcome,
        **measured,
    }
    if limit_type:
        event["limit_type"] = limit_type
    if http_status is not None:
        event["http_status"] = http_status
    with _GROQ_CALL_LOCK:
        today = now.date().isoformat()
        if _GROQ_USAGE_DAY != today:
            _GROQ_USAGE_DAY = today
            _GROQ_DAILY_USAGE = {key: _empty_usage_totals() for key in MODELS}
        totals = _GROQ_DAILY_USAGE[role]
        if outcome == "success":
            totals["successful_calls"] += 1
            if all(value is not None for value in measured.values()):
                totals["metered_calls"] += 1
                for key, value in measured.items():
                    totals[key] += value
        else:
            totals["failed_calls"] += 1
        _GROQ_CALL_EVENTS.append(event)
    # No question, response text, credential, or unfiltered provider error in logs.
    print("[Groq AI test call] " + json.dumps(event, ensure_ascii=False), flush=True)
    return event


def _groq_remaining_headers(headers):
    """Only use Groq-documented values: requests/day and tokens/minute."""
    def quantity(name):
        raw = str(headers.get(name) or "").strip() if headers is not None else ""
        return int(raw) if raw.isascii() and raw.isdecimal() and len(raw) <= 15 else None

    return {
        "requests_per_day": {
            "limit": quantity("x-ratelimit-limit-requests"),
            "remaining": quantity("x-ratelimit-remaining-requests"),
        },
        "tokens_per_minute": {
            "limit": quantity("x-ratelimit-limit-tokens"),
            "remaining": quantity("x-ratelimit-remaining-tokens"),
        },
    }


def _remember_groq_remaining(role, headers):
    values = _groq_remaining_headers(headers)
    if not any(value is not None for group in values.values() for value in group.values()):
        return
    values["observed_at_kst"] = datetime.datetime.now(
        ZoneInfo("Asia/Seoul")
    ).isoformat(timespec="seconds")
    with _GROQ_CALL_LOCK:
        _GROQ_LATEST_REMAINING[role] = values


def _provider_info():
    with _GROQ_RATE_LIMIT_LOCK:
        events = list(reversed(_GROQ_RATE_LIMIT_EVENTS))[:20]
    with _GROQ_CALL_LOCK:
        date_kst = _today_kst()
        daily_usage = {
            role: dict(_GROQ_DAILY_USAGE.get(role, _empty_usage_totals()))
            if _GROQ_USAGE_DAY == date_kst else _empty_usage_totals()
            for role in MODELS
        }
        recent_calls = list(reversed(_GROQ_CALL_EVENTS))[:20]
        provider_remaining = {
            role: dict(_GROQ_LATEST_REMAINING[role])
            for role in MODELS if role in _GROQ_LATEST_REMAINING
        }
    return {
        "limit_source": "groq",
        "models": {
            role: {
                "label": model["label"],
                "model_id": model["id"],
                "reference_limits": ({} if role == "cloudflare" else dict(_GROQ_REFERENCE_LIMITS)),
            }
            for role, model in MODELS.items()
        },
        "recent_rate_limits": events,
        "date_kst": date_kst,
        "daily_usage": daily_usage,
        "recent_calls": recent_calls,
        "provider_remaining": provider_remaining,
        "note": "Groq에서 직접 한도를 적용합니다. 표시된 숫자는 조직 Free 한도 참고값이며 실제 프로젝트 한도와 남은 사용량은 Groq 콘솔에서 확인하세요.",
        "history_warning": "하루 예상 잔여 토큰은 오늘 이 서버의 관리자 테스트에서 관측한 사용량만 차감한 참고값입니다(한국시간 기준). Groq의 실제 하루 잔여 토큰은 응답 헤더에서 제공되지 않습니다. 실제 응답 잔여량도 마지막 호출 시점의 값입니다. 기록은 서버 재시작 시 초기화되고 다른 앱·프로젝트 사용량은 포함하지 않습니다.",
    }


def _take_slot(role):
    with _LOCK:
        _state()
        if _COUNTS[role] >= MODELS[role]["limit"]:
            return "model_daily_limit"
        if sum(_COUNTS.values()) >= MAX_TOTAL_PER_DAY:
            return "total_daily_limit"
        if len(_RECENT) >= MAX_CALLS_PER_MINUTE:
            return "minute_limit"
        _COUNTS[role] += 1
        _RECENT.append(time.monotonic())
    return None


def _groq_limit_type(exc):
    # Do not log or expose provider error text: it may include account details.
    try:
        response = json.loads(exc.read(8192).decode("utf-8", errors="replace"))
        details = response.get("error") if isinstance(response, dict) else {}
        message = str((details or {}).get("message") or "").lower()
    except (ValueError, TypeError, AttributeError, OSError):
        message = ""
    for kind, pattern in (
        ("tokens_per_minute", r"tokens?\s+per\s+minute|\btpm\b"),
        ("tokens_per_day", r"tokens?\s+per\s+day|\btpd\b"),
        ("requests_per_minute", r"requests?\s+per\s+minute|\brpm\b"),
        ("requests_per_day", r"requests?\s+per\s+day|\brpd\b"),
    ):
        if re.search(pattern, message):
            return kind
    return "unknown"


def _record_groq_rate_limit(role, model_id, exc):
    event = {
        "timestamp_kst": datetime.datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
        "role": role,
        "model_id": model_id,
        "limit_type": _groq_limit_type(exc),
        "retry_after": str(exc.headers.get("Retry-After") or "").strip()[:32],
    }
    with _GROQ_RATE_LIMIT_LOCK:
        _GROQ_RATE_LIMIT_EVENTS.append(event)
    print("[Groq AI test rate limit] " + json.dumps(event, ensure_ascii=False), flush=True)
    return event


def _compact(value, limit=240):
    return str(value or "").strip()[:limit]


def _context(stock, data):
    # Existing /analyze() data is reused; NO additional market provider is created.
    first = next(
        (section for section in data.get("sections", [])
         if section.get("id") == "why-up"), {}
    )
    price_lines = []
    for line in str(first.get("content") or "").splitlines():
        if any(token in line for token in ("현재 주가는", "고가 ", "저가 ", "20일선 ", "52주")):
            # Provider labels are infrastructure details, not user-facing facts.
            clean_line = re.sub(r"\s*\([^)]*(?:키움|시세\s*미수신)[^)]*\)", "", line)
            clean_line = re.sub(r"(?:키움\s*(?:실시간\s*)?(?:현재가|시세)[^:：]*[:：]?|(?:키움|시세)\s*미수신[^:：]*[:：]?)", "", clean_line).strip()
            if clean_line:
                price_lines.append(_compact(clean_line, 230))

    # Reuse the existing first-analysis hashtags; do not collect or analyze again.
    analysis_tags = []
    for tag in list(first.get("tags") or []) + str(first.get("content") or "").split():
        tag = str(tag).strip()
        if tag.startswith("#") and tag not in analysis_tags:
            analysis_tags.append(_compact(tag, 60))
        if len(analysis_tags) >= 20:
            break

    news = []
    for item in (data.get("paired_news_items") or [])[:6]:
        news.append({
            "title": _compact(item.get("title") or item.get("storyboard_title"), 200),
            "summary": _compact(item.get("description") or item.get("summary"), 280),
            "published_at": _compact(item.get("published_at") or item.get("pub_date"), 60),
            "source_url": _compact(item.get("link") or item.get("url"), 240),
        })

    brief = []
    for item in (data.get("issue_briefs") or [])[:3]:
        # Reuse the very same verified low/high figures shown in central chat.
        # Exclude unavailable values rather than inventing a price reaction.
        reactions = []
        for reaction in (item.get("stock_reactions") or [])[:3]:
            if not isinstance(reaction, dict):
                continue
            name = _compact(reaction.get("name"), 60)
            low_pct, high_pct = reaction.get("low_pct"), reaction.get("high_pct")
            if not name or not all(
                isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value)
                for value in (low_pct, high_pct)
            ):
                continue
            reactions.append({
                "name": name,
                "low_pct": low_pct,
                "high_pct": high_pct,
            })
        brief.append({
            "headline": _compact(item.get("headline"), 120),
            "summary": _compact(item.get("summary"), 240),
            "reaction_at": _compact(item.get("reaction_at"), 60),
            "stock_reactions": reactions,
        })

    disclosures = []
    for item in (data.get("disclosures") or data.get("us_filings") or [])[:5]:
        disclosures.append({
            "title": _compact(item.get("title"), 180),
            "date": _compact(item.get("date"), 50),
            "keywords": list(item.get("keywords") or [])[:6],
            "source_url": _compact(item.get("link"), 240),
        })

    return {
        "stock": stock,
        "price_information": price_lines[:5],
        "analysis_hashtags": analysis_tags,
        "price_metrics": {k: v for k, v in (data.get("price_snapshot") or {}).items() if k != "quote_source"},
        "news": news,
        "issue_briefs": brief,
        "official_disclosures": disclosures,
        "note": (
            "price_metrics.change_pct는 현재 표시가격의 직전 종가 대비 등락률입니다. "
            "price_metrics.previous_trading_day는 날짜가 확인된 직전 완료 거래일의 고가·종가·당일 등락률입니다. "
            "두 등락률을 혼동하지 말고 거래일 날짜를 명시하세요. "
            "issue_briefs.stock_reactions의 low_pct/high_pct는 해당 뉴스 발행 시각을 기준으로 "
            "이후 첫 거래 세션의 최저가/최고가에서 계산한 변동률(%)입니다. "
            "이는 현재가 등락률이나 뉴스 이후 모든 거래일의 최고/최저 수익률이 아닙니다. "
            "기준가격은 뉴스 시각 이전에 시작한 마지막 5분봉의 종가이며 시세 갱신 시각을 보장하지 않습니다. "
            "분석 해시태그는 기존 종목 분석에서 생성된 참고 신호이며 장기 추세의 확정 근거가 아닙니다. "
            "질문과 관련된 해시태그는 활용하되, 없는 장기 이동평균이나 추세 데이터를 추측하지 마세요. "
            "시세 원천의 실시간성은 보장되지 않습니다. 누락된 값은 추측하지 마세요."
        ),
    }




def _refresh_us_live_chat_quote(stock, selection, context):
    """Give both chat models only verified US prices, not provider/status chatter.

    Prefer the current short-lived quote; use the same recent saved quote that
    the site's US ranking/analysis can display when markets are closed.
    """
    if not stock or not isinstance(context, dict):
        return context
    from .engine import TICKERS
    from .market_rankings import analysis_ticker_for_selection
    from .us_price_push import read_fresh_us_quote
    from .kiwoom_us_value_board import read_recent_saved_us_quote

    ticker = (analysis_ticker_for_selection(selection)
              if selection and selection.get("market") == "us" else None)
    ticker = ticker or TICKERS.get(stock)
    if ticker is None and isinstance(stock, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9.\\.-]{0,19}", stock):
        ticker = stock.upper()
    if not ticker or ticker.endswith((".KS", ".KQ")):
        return context

    fresh_quote = read_fresh_us_quote(ticker)
    quote = fresh_quote or read_recent_saved_us_quote(ticker)
    metrics = dict(context.get("price_metrics") or {})
    for field in ("current", "change_pct", "rise_to_52w_high_pct", "quote_source", "quote_received_at_ms"):
        metrics.pop(field, None)
    market_row = dict(context.get("market_selection") or {})
    price_lines = []
    if quote:
        price = quote["price"]
        metrics["current"] = price
        if quote.get("received_at_ms") is not None:
            metrics["quote_received_at_ms"] = quote["received_at_ms"]
        change = quote.get("change_pct")
        if change is not None:
            metrics["change_pct"] = change
        high = metrics.get("week_52_high")
        if isinstance(high, (int, float)) and high > 0:
            metrics["rise_to_52w_high_pct"] = round(max(0.0, (high - price) / price * 100), 2)
        detail = f", 전일 대비 {change:+.2f}%" if change is not None else ""
        price_lines = [f"가격 ${price:,.2f}{detail}"]
        if market_row:
            market_row["price"] = price
            market_row["change_pct"] = change
    elif market_row:
        market_row["price"] = None
        market_row["change_pct"] = None

    refreshed = {**context, "price_metrics": metrics,
                 "price_information": price_lines,
                 "analysis_hashtags": []}
    if market_row:
        refreshed["market_selection"] = market_row
    return refreshed

def _previous_day_reply(question, metrics):
    """Answer dated prior-session OHLCV facts without confusing them with today's quote."""
    normalized = re.sub(r"\s+", "", str(question or ""))
    refers_to_previous = any(key in normalized for key in ("전일", "어제", "전거래일", "지난거래일"))
    is_today_vs_previous = any(
        key in normalized for key in ("전일대비", "어제대비", "전거래일대비", "지난거래일대비")
    )
    wants_high = "최고가" in normalized or "고가" in normalized
    wants_change = any(
        key in normalized
        for key in ("프로", "퍼센트", "%", "등락률", "상승률", "하락률", "올랐", "내렸", "떨어졌")
    )
    if (not refers_to_previous or is_today_vs_previous or "52주" in normalized
            or "신고가" in normalized or not (wants_high or wants_change)):
        return None

    previous = metrics.get("previous_trading_day")
    if not isinstance(previous, dict) or not previous.get("date"):
        return "전 거래일의 날짜가 확인된 시세 데이터가 없어."

    date_text = str(previous["date"])
    facts = []
    if wants_high:
        high = previous.get("high")
        if isinstance(high, (int, float)) and not isinstance(high, bool) and math.isfinite(high) and high > 0:
            currency = metrics.get("currency")
            if currency == "KRW":
                facts.append(f"최고가 {high:,.0f}원")
            elif currency == "USD":
                facts.append(f"최고가 ${high:,.2f}")
            else:
                facts.append(f"최고가 {high:,.2f}(통화 단위 미확인)")
        else:
            facts.append("최고가 자료 없음")
    if wants_change:
        change = previous.get("change_pct")
        if isinstance(change, (int, float)) and not isinstance(change, bool) and math.isfinite(change):
            movement = "상승" if change > 0 else "하락" if change < 0 else "보합"
            facts.append(f"그날의 등락률 {change:+.2f}% ({movement})")
        else:
            facts.append("그날의 등락률 자료 없음")
    return f"전 거래일({date_text}) 기준 " + ", ".join(facts) + "."


def _groq_answer(model_id, question, context, max_completion_tokens=1500, style_prompt=None):
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT + ("\n" + style_prompt if style_prompt else "")},
            {
                "role": "user",
                "content": "참고 데이터(JSON):\n"
                + json.dumps(context, ensure_ascii=False)
                + "\n\n질문: " + question,
            },
        ],
        "max_completion_tokens": max_completion_tokens,
        "temperature": 0.2,
        "reasoning_effort": "none" if model_id.startswith("qwen/") else "low",
        "stream": False,
    }
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + os.environ["GROQ_API_KEY"],
            "Content-Type": "application/json",
            "User-Agent": "gaemiGTP-ai-test/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=23) as response:
        result = json.loads(response.read().decode("utf-8"))
        provider_headers = response.headers
    choices = result.get("choices") or []
    if not choices:
        raise ValueError("empty_choices")
    answer = (choices[0].get("message") or {}).get("content") or ""
    if not answer.strip():
        raise ValueError("empty_response")
    usage = result.get("usage")
    return answer.strip()[:4000], (usage if isinstance(usage, dict) else None), provider_headers


def _cloudflare_answer(question, context, max_completion_tokens=1500, style_prompt=None):
    """Cloudflare Workers AI serves private info chat and admin model 4 tests."""
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    api_token = (os.environ.get("CLOUDFLARE_API_TOKEN") or
                 os.environ.get("CLOUDFLARE_API_KEY") or
                 os.environ.get("CLOUDFLARE_AUTH_TOKEN") or "").strip()
    if not account_id or not api_token:
        raise ValueError("cloudflare_not_configured")
    payload = {
        "model": "@cf/openai/gpt-oss-20b",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT + ("\n" + style_prompt if style_prompt else "")},
            {"role": "user", "content": "참고 데이터(JSON):\n"
             + json.dumps(context, ensure_ascii=False) + "\n\n질문: " + question},
        ],
        "max_tokens": max_completion_tokens,
        "temperature": 0.2,
        "reasoning_effort": "low",
        "stream": False,
    }
    url = ("https://api.cloudflare.com/client/v4/accounts/" +
           account_id + "/ai/v1/chat/completions")
    req = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_token,
                 "Content-Type": "application/json",
                 "User-Agent": "gaemiGTP-ai-test/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=23) as response:
        result = json.loads(response.read().decode("utf-8"))
        provider_headers = response.headers
    choices = result.get("choices") or []
    answer = (choices[0].get("message") or {}).get("content") if choices else ""
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("empty_response")
    usage = result.get("usage")
    return answer.strip()[:4000], usage if isinstance(usage, dict) else None, provider_headers


@ai_test_bp.get("/api/ai-test/status")
def ai_test_status():
    if not _authorized():
        return jsonify({"ok": False, "error": "admin_test_disabled_or_unauthorized"}), 403
    return jsonify({"ok": True, **_provider_info()})


@ai_test_bp.post("/api/ai-test/chat")
def ai_test_chat():
    # The site login is accepted only in private preview mode. The existing
    # bearer token continues to authorize the standalone administrator test.
    from .private_access import _authorized as dev_session_authorized, private_enabled
    admin_test = _authorized()
    private_chat = not admin_test and private_enabled() and dev_session_authorized()
    if not admin_test and not private_chat:
        return jsonify({"ok": False, "error": "admin_test_disabled_or_unauthorized"}), 403
    limits_for_request = _provider_info

    if (request.content_length or 0) > 4500:
        return jsonify({"ok": False, "error": "request_too_large"}), 413
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "invalid_json"}), 400
    question = str(body.get("question") or "").strip()
    if private_chat:
        # Client mode is a request, not a membership entitlement. Never accept
        # an arbitrary model role from a site visitor. Future membership policy
        # belongs here, on the server, before enabling paid tiers.
        app_mode = str(body.get("app_mode") or "gaemi").strip().lower()
        if app_mode not in ("gaemi", "info", "pro"):
            return jsonify({"ok": False, "error": "unsupported_mode"}), 400
        # News editorial keeps model 1 (20B) and model 2 (120B).
        # Chat uses the existing independent model 4 (Cloudflare) and
        # model 3 (Groq Qwen) without touching the editorial workers.
        role = {"gaemi": None, "info": "cloudflare", "pro": "compare"}[app_mode]
    else:
        app_mode = None
        role = str(body.get("role") or "news")
        if role not in MODELS:
            return jsonify({"ok": False, "error": "unsupported_model"}), 400
    if not question or len(question) > 800:
        return jsonify({"ok": False, "error": "invalid_input"}), 400

    if private_chat and _is_market_gainers_question(question):
        # The market-ranking schema is present, but its source collection and
        # read path are not connected. Never fabricate a stock ranking or
        # answer the market-wide question using the previously selected stock.
        return jsonify({
            "ok": True,
            "stock": "",
            "answer": (
                "오늘 상승 종목은 시장 전체 상승률 순위 데이터로 확인해야 해. "
                "현재 순위 데이터 수집·조회가 연결되지 않아 정확한 종목 목록을 제공할 수 없어."
            ),
            "model": "market-ranking-unavailable",
            "limits": limits_for_request(),
        })

    if private_chat:
        ranking_answer = _market_ranking_reply(question)
        if ranking_answer is not None:
            return jsonify({
                "ok": True, "stock": "", "answer": ranking_answer,
                "model": "market-menu-result", "limits": limits_for_request(),
            })

    # gaemi may use the existing deterministic read paths above and the
    # stock-analysis UI. It never accesses a text-generation provider.
    deterministic_quote = ("52주" in question or
                           any(word in question for word in ("전일", "어제", "전 거래일", "지난 거래일")))
    if private_chat and app_mode == "gaemi" and not deterministic_quote:
        return jsonify({"ok": False, "error": "ai_mode_disabled"}), 403

    stock = _question_stock(question) or str(body.get("stock") or "").strip()
    if len(stock) > 50 or (not stock and not (private_chat and app_mode in ("info", "pro"))):
        return jsonify({"ok": False, "error": "invalid_input"}), 400
    selected = None
    choice = body.get("market_selection")
    if private_chat and isinstance(choice, dict):
        selected = get_market_selection(
            choice.get("market"), choice.get("menu"), choice.get("symbol"), stock=stock,
        )
        if selected:
            order = "change_pct" if choice.get("sort") == "change_pct" else "source"
            ordered_rows = get_market_menu_rows(selected["market"], selected["menu"], sort=order)
            match = next(
                (row for row in ordered_rows if row["symbol"] == selected["symbol"]),
                None,
            )
            selected = {**selected,
                        "sort": order,
                        "display_rank": match["display_rank"] if match else selected.get("rank")}

    # Both administrator tests and central chat use Groq's native limits.

    # Use the private conversation's existing processed result when possible.
    # Only a new-stock question falls back to the established analysis function.
    provider_called = False
    try:
        # General info/pro questions without a stock should not require
        # unrelated /analyze calls. Stock questions still reuse existing data.
        context = (_cached_chat_context(stock, selected) if private_chat and stock
                   else ({"stock": "", "news": [], "official_disclosures": [],
                          "issue_briefs": [], "price_information": [],
                          "price_metrics": {}} if private_chat else None))

        # A quote-only cache cannot answer later news/disclosure questions.
        if context and stock and not ("52주" in question and ("최고가" in question or "신고가" in question)):
            if not any((context["news"], context["official_disclosures"], context["issue_briefs"], context["price_information"])):
                context = None

        # A 52-week price question requires only the existing shared price
        # result. Do not block a fresh chat on unrelated news/disclosures.
        is_52week_question = private_chat and "52주" in question and ("최고가" in question or "신고가" in question)
        if context is None and is_52week_question:
            from backend.services.engine import TICKERS
            from backend.services.stock_analysis import fetch_stock_price_result
            ticker = TICKERS.get(stock) or (stock.upper() if stock.isascii() else "")
            if ticker:
                is_krw = ticker.endswith((".KS", ".KQ"))
                clean_code = "".join(char for char in ticker if char.isdigit()) if is_krw else None
                quote = fetch_stock_price_result(is_krw=is_krw, ticker_symbol=ticker, clean_code=clean_code)
                current = float(quote.get("current_price") or 0)
                high = float(((quote.get("indicators") or {}).get("week_52") or {}).get("high") or 0)
                if not (current > 0 and high > 0):
                    return jsonify({"ok": False, "error": "stock_data_unavailable"}), 422
                metrics = {
                    "current": current, "week_52_high": high,
                    "rise_to_52w_high_pct": round(max(0.0, (high - current) / current * 100), 2),
                }
                context = {
                    "stock": stock, "price_information": [], "price_metrics": metrics,
                    "news": [], "issue_briefs": [], "official_disclosures": [],
                }
                with _CHAT_CONTEXT_LOCK:
                    _CHAT_CONTEXT_CACHE[stock] = (time.monotonic(), context)

        if context is None:
            from backend.services.engine import analyze_stock
            ticker = analysis_ticker_for_selection(selected)
            result = (analyze_stock(
                stock, ticker_symbol_override=ticker,
                kr_market_override=bool(selected and selected["market"] == "kr"),
            ) if ticker else analyze_stock(stock))
            if result.get("ok") is False:
                return jsonify({"ok": False, "error": "stock_data_unavailable", "limits": limits_for_request()}), 422
            context = _context(stock, result)
            if private_chat:
                remember_chat_analysis(stock, result, selection=selected)
        if selected:
            # Include only the server's existing menu result, not client-priced data.
            context = {**context, "market_selection": {
                key: selected.get(key) for key in (
                    "market", "menu", "symbol", "name", "rank", "display_rank",
                    "sort", "price", "change_pct", "trading_value", "trading_value_text",
                    "industry", "currency"
                )
            }}
            if selected["market"] == "us" and selected["menu"] == "value":
                context["note"] = context.get("note", "") + (
                    " market_selection은 미국 거래대금 TOP 20의 선택 종목 정보다."
                    " 가격·등락률은 최종 확인된 price_metrics 숫자만 사용한다."
                )
            else:
                context["note"] = context.get("note", "") + (
                    " market_selection은 메뉴 조회 당시 선택한 종목 정보다."
                    " 현재 실시간 시세나 전체 시장 순위로 일반화하지 마세요."
                )
        if selected and re.search(r"인기|순위|랭킹|거래대금|상위|TOP\s*20", question, re.IGNORECASE):
            # Market-menu comparison uses the SAME cached result that built
            # the sidebar; no extra collection and no fabricated global ranks.
            rows = get_market_menu_rows(
                selected["market"], selected["menu"], sort=selected["sort"],
            )
            context["market_menu_rows"] = [
                {key: row.get(key) for key in (
                    "rank", "display_rank", "name", "symbol", "industry", "price",
                    "change_pct", "trading_value",
                )} for row in rows[:20]
            ]
            context["note"] += (
                " market_menu_rows는 선택 메뉴의 TOP 20 목록입니다."
                " rank는 원천 순위, display_rank는 표시된 정렬 위치입니다."
                " 전체 시장 상승률 순위나 실시간 주가로 해석하지 마세요."
            )
        if stock:
            context = _refresh_us_live_chat_quote(stock, selected, context)
        if stock and not any((context["news"], context["official_disclosures"],
                              context["price_information"], context["price_metrics"])):
            return jsonify({"ok": False, "error": "stock_data_unavailable", "limits": limits_for_request()}), 422

        # The same shared quote supports exact arithmetic in the general chat.
        metrics = context.get("price_metrics") or {}
        if private_chat:
            previous_answer = _previous_day_reply(question, metrics)
            if previous_answer is not None:
                return jsonify({"ok": True, "stock": stock, "answer": previous_answer, "model": "calculation"})
        if private_chat and "52주" in question and ("최고가" in question or "신고가" in question):
            needed = metrics.get("rise_to_52w_high_pct")
            if isinstance(needed, (int, float)):
                answer = f"{needed:.1f}% 남았어." if needed > 0 else "이미 52주 최고가에 도달했어."
                return jsonify({"ok": True, "stock": stock, "answer": answer, "model": "calculation"})

        if private_chat:
            # Final server-side guard: even special quote paths must never fall
            # through to Groq when the UI is in gaemi mode.
            if app_mode == "gaemi":
                return jsonify({"ok": False, "error": "ai_mode_disabled"}), 403
            if not _private_provider_ready(role):
                return jsonify({"ok": False, "error": "ai_test_not_configured"}), 503
            # Private single-admin preview: rely on each provider's real
            # account/project quotas. Do not fabricate local daily/minute
            # limits, which would also reset on a Render redeployment.
            # Production memberships require a separate shared quota policy.

        history = body.get("history") or []
        dialogue = []
        if private_chat and isinstance(history, list):
            for item in history[-6:]:
                if isinstance(item, dict) and item.get("role") in ("user", "assistant"):
                    message = str(item.get("text") or "").strip()[:240]
                    if message:
                        dialogue.append(f"{item['role']}: {message}")
        prompt = question
        if dialogue:
            prompt = "이전 대화:\n" + "\n".join(dialogue) + "\n\n현재 질문: " + question
        provider_called = True
        answer, usage, provider_headers = (_cloudflare_answer(prompt, context, style_prompt=(INFO_STYLE_PROMPT + "\n" + PRIVATE_CHAT_LENGTH_PROMPT + "\n" + PRIVATE_CHAT_PRICE_PROMPT) if private_chat and app_mode == "info" else None) if role == "cloudflare" else _groq_answer(
            MODELS[role]["id"], prompt, context,
            style_prompt=(PRIVATE_CHAT_LENGTH_PROMPT + "\n" + PRIVATE_CHAT_PRICE_PROMPT) if private_chat and app_mode == "pro" else None,
        ))
        if private_chat and app_mode in ("info", "pro"):
            answer = answer[:PRIVATE_CHAT_MAX_ANSWER_CHARS]
        if admin_test:
            if role != "cloudflare":
                _remember_groq_remaining(role, provider_headers)
            _record_groq_call(role, "success", usage=usage)
        print("[AI test success] " + json.dumps({
            "timestamp_kst": datetime.datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
            "role": role, "model_id": MODELS[role]["id"],
        }, ensure_ascii=False), flush=True)
        response_data = {
            "ok": True, "stock": stock, "answer": answer,
            "model": MODELS[role]["id"],
            "source_counts": {
                "news": len(context["news"]),
                "disclosures": len(context["official_disclosures"]),
                "issue_briefs": len(context["issue_briefs"]),
            },
            "limits": limits_for_request(),
        }
        if admin_test:
            response_data["usage"] = _usage_numbers(usage)
        return jsonify(response_data)
    except urllib.error.HTTPError as exc:
        if admin_test and provider_called and role != "cloudflare":
            _remember_groq_remaining(role, exc.headers)
        if exc.code == 429 and role == "cloudflare":
            if admin_test and provider_called:
                _record_groq_call(role, "rate_limit", http_status=429)
            return jsonify({"ok": False, "error": "cloudflare_rate_limit", "limits": limits_for_request()}), 429
        if exc.code == 429:
            event = _record_groq_rate_limit(role, MODELS[role]["id"], exc)
            if admin_test and provider_called:
                _record_groq_call(role, "rate_limit", limit_type=event["limit_type"], http_status=429)
            return jsonify({
                "ok": False, "error": "groq_rate_limit",
                "model": event["model_id"],
                "rate_limit_type": event["limit_type"],
                "retry_after": event["retry_after"],
                "limits": limits_for_request(),
            }), 429
        if admin_test and provider_called:
            _record_groq_call(role, "provider_error", http_status=exc.code)
        print(f"[AI test provider error] role={role} model={MODELS[role]['id']} status={exc.code}", flush=True)
        return jsonify({
            "ok": False, "error": "cloudflare_request_failed" if role == "cloudflare" else "groq_request_failed",
            "limits": limits_for_request(),
        }), 502
    except Exception as exc:
        if admin_test and provider_called:
            _record_groq_call(role, "request_error")
        print(f"[Groq AI test] failed: {type(exc).__name__}", flush=True)
        return jsonify({"ok": False, "error": "ai_test_failed", "limits": limits_for_request()}), 502
