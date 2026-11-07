"""Build a standalone news-page snapshot from the shared TradingView cache.

No API calls, database writes, or AI calls happen here. The snapshot is a
screen-facing intermediate artifact that can later be copied to R2 unchanged.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import re
import tempfile

NEWS_PAGE_PATH = Path("/var/lib/gaemigtp-news/tradingview-news-page.json")
MAX_PAGE_ITEMS = 2000

# gaemiGTP's fixed 14 stock-news event taxonomy.
# Rules only provide a first-pass page filter. AI interpretation stays separate.
CATEGORY_RULES = (
    ("guidance", "실적 전망", (
        "guidance", "outlook", "forecast", "가이던스", "전망 상향",
        "전망 하향", "연간 전망", "매출 전망",
    )),
    ("earnings", "실적 발표", (
        "earnings", "quarterly results", "financial results", "실적 발표",
        "실적발표", "어닝", "매출", "영업이익", "순이익", "eps",
    )),
    ("analyst", "증권사 평가", (
        "price target", "target price", "upgrade", "downgrade", "initiates",
        "coverage", "rating", "목표주가", "투자의견", "매수의견",
        "중립", "비중확대", "증권사",
    )),
    ("operations", "사업 성과", (
        "sales rose", "sales growth", "shipments", "deliveries", "subscribers",
        "production", "판매량", "가입자", "생산 확대", "생산량", "출하량",
        "점유율", "사업 성과",
    )),
    ("contract", "계약·수주", (
        "contract", "order", "award", "procurement", "수주", "공급계약",
        "계약 체결", "계약 해지", "정부 수주", "대형 계약",
    )),
    ("product", "제품·기술", (
        "launches", "unveils", "new product", "chip", "semiconductor",
        "technology", "신제품", "출시", "신기술", "반도체 개발", "기술 공개",
    )),
    ("capital", "재무·주주환원", (
        "buyback", "share repurchase", "dividend", "offering", "capital raise",
        "자사주", "배당", "유상증자", "증자", "회사채", "채권 발행",
    )),
    ("corporate", "인수합병·구조조정", (
        "acquisition", "acquire", "merger", "m&a", "spin-off", "spinoff",
        "divest", "restructuring", "인수", "합병", "매각", "분사", "구조조정",
    )),
    ("legal", "법률·사고", (
        "lawsuit", "sued", "litigation", "recall", "breach", "cyberattack",
        "outage", "accident", "소송", "리콜", "보안 사고", "해킹", "사고",
    )),
    ("regulation", "인허가·규제", (
        "fda", "approval", "approved", "rejects", "rejected", "ban",
        "regulator", "antitrust", "승인", "승인 거절", "판매 금지", "인허가",
        "규제 당국",
    )),
    ("flow", "종목별 수급", (
        "short interest", "short selling", "institutional buying",
        "institutional selling", "공매도", "기관 순매수", "기관 순매도",
        "순매수", "순매도", "수급",
    )),
    ("rnd_clinical", "연구개발·임상", (
        "clinical trial", "phase 1", "phase 2", "phase 3", "trial results",
        "study results", "research", "임상", "3상", "2상", "1상", "신약",
        "연구 결과", "효능",
    )),
    ("partnership_supplychain", "제휴·공급망", (
        "partnership", "partners with", "collaboration", "supply chain",
        "supplier", "supply disruption", "제휴", "협력", "파트너십",
        "공급망", "공급 차질", "고객사",
    )),
    ("governance", "경영진·지배구조", (
        "ceo", "cfo", "chairman", "board", "director", "management change",
        "activist", "proxy fight", "경영권", "경영진", "ceo 교체", "이사회",
        "대표이사",
    )),
)

MARKET_RULES = (
    ("market", "증시", ("stock market", "wall street", "equities", "stocks", "증시", "주식시장")),
    ("economic", "경제지표", ("cpi", "pce", "gdp", "jobs", "payroll", "employment", "inflation", "retail sales", "pmi", "경제지표", "고용", "물가", "소비자물가")),
    ("fed", "연준", ("federal reserve", "fed ", "fomc", "powell", "rate cut", "rate hike", "연준", "파월", "금리 인하", "금리 인상")),
    ("policy", "정부정책", ("white house", "congress", "treasury", "administration", "government", "policy", "정부", "정책", "백악관", "의회")),
    ("rates_bonds", "금리·환율", ("treasury yield", "bond yield", "10-year", "2-year", "yield curve", "interest rate", "exchange rate", "forex", "currency", "국채금리", "채권금리", "10년물", "2년물", "수익률곡선", "환율", "엔화", "유로화", "달러지수")),
    ("energy", "에너지", ("oil", "crude", "opec", "natural gas", "energy", "원유", "유가", "천연가스", "에너지")),
    ("fx_commodities", "금리·환율", ("dollar index", "dxy", "exchange rate", "forex", "currency", "달러지수", "환율", "엔화", "유로화")),
    ("tariff", "관세", ("tariff", "trade war", "import duty", "관세", "무역전쟁")),
    ("market_close", "미국장 마감", ("market close", "closing bell", "closed higher", "closed lower", "마감", "종가")),
    ("major_index", "주요지수", ("s&p 500", "nasdaq", "dow jones", "dow ", "index", "나스닥", "다우", "s&p")),
    ("sector", "시장동향", ("sector", "semiconductor stocks", "tech stocks", "financial stocks", "energy stocks", "healthcare stocks", "섹터", "업종", "반도체주", "기술주", "금융주", "에너지주", "헬스케어주")),
    ("volatility_sentiment", "시장동향", ("vix", "volatility", "fear gauge", "risk appetite", "risk-on", "risk-off", "investor sentiment", "변동성", "공포지수", "위험선호", "위험회피", "투자심리")),
    ("market_trend", "시장동향", ("futures", "rally", "selloff", "market sentiment", "선물", "랠리", "매도세", "시장 동향")),
    ("international", "국제정세", ("middle east", "iran", "war", "sanction", "geopolitical", "중동", "이란", "전쟁", "제재", "지정학")),
)


def _text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _has_us_equity_symbol(article):
    related = article.get("relatedSymbols") or article.get("related_symbols") or []
    if not isinstance(related, list):
        return False
    for entry in related:
        if not isinstance(entry, dict):
            continue
        symbol = str(entry.get("symbol") or "").upper()
        if symbol.startswith(("NASDAQ:", "NYSE:", "AMEX:", "NYSEARCA:", "NYSEAMERICAN:", "BATS:")):
            return True
    return False


def classify_article(article):
    haystack = _text(article.get("title")).lower()
    source_categories = article.get("news_categories") or []
    if not isinstance(source_categories, list):
        source_categories = []

    stock_source = "stock" in source_categories or (
        "overall" in source_categories and _has_us_equity_symbol(article)
    )
    stock_matches = [
        {"code": code, "label": label}
        for code, label, terms in CATEGORY_RULES
        if any(str(term).lower() in haystack for term in terms)
    ] if stock_source else []
    # An explicit stock feed / US equity association takes precedence over
    # broad words like "stocks" and "market" in a company headline.
    if stock_source:
        if stock_matches:
            return stock_matches[0], stock_matches, "stock"
        return {"code": "stock", "label": "종목"}, [], "stock"

    # Specific market events take precedence over generic market terms.
    market_matches = [
        {"code": code, "label": label}
        for code, label, terms in MARKET_RULES
        if any(str(term).lower() in haystack for term in terms)
    ]
    specific = [match for match in market_matches
                if match["code"] not in ("market", "market_trend", "sector")]
    if specific:
        return specific[0], market_matches, "market"
    if "economic" in source_categories:
        return {"code": "economic", "label": "경제지표"}, market_matches, "market"
    if "index" in source_categories:
        return {"code": "major_index", "label": "주요지수"}, market_matches, "market"
    if market_matches:
        return market_matches[0], market_matches, "market"
    if "overall" in source_categories or "futures" in source_categories:
        return {"code": "market_trend", "label": "시장동향"}, [], "market"
    return {"code": "other", "label": "기타"}, [], "other"


def _symbols(article):
    rows = article.get("relatedSymbols") or article.get("related_symbols") or []
    result = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            raw = _text(row.get("symbol"))
            if not raw:
                continue
            ticker = raw.rsplit(":", 1)[-1].upper()
            if ticker and ticker not in result:
                result.append(ticker)
    return result


def _published_iso(article):
    value = article.get("published")
    try:
        return dt.datetime.fromtimestamp(
            float(value), dt.timezone.utc
        ).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def _news_url(article):
    story_path = _text(article.get("storyPath"))
    if story_path.startswith("/news/"):
        return "https://www.tradingview.com" + story_path
    return ""


def normalize_article(article):
    primary, matches, section = classify_article(article)
    provider = article.get("provider")
    source = (
        _text(provider.get("name"))
        if isinstance(provider, dict)
        else "TradingView"
    ) or "TradingView"
    # An API response containing article text is not proof of
    # republication rights. Keep full text private by default.
    may_publish_body = (
        article.get("detail_publication_allowed") is True
        and article.get("permission") != "headline"
        and article.get("detail_permission") != "headline"
    )
    body = _text(article.get("detail_body"))
    return {
        "id": article.get("id") or article.get("newsId"),
        "published_at": _published_iso(article),
        "title": _text(article.get("title")),
        "summary": _text(article.get("detail_summary") or article.get("summary")),
        # Preserve the original API detail excerpt separately from a true summary.
        "description": _text(article.get("shortDescription") or article.get("detail_description")),


        "content_source": "api_detail" if article.get("detail_checked") else "news_list",
        "body_available": bool(body) and may_publish_body,
        "body": body if may_publish_body else "",
        "detail_status": _text(article.get("detail_checked")),
        # Full source article bodies are never copied into publicly readable Pages JSON.
        "source": source,
        "url": _news_url(article),
        "symbols": _symbols(article),
        "event_category": primary,
        "event_matches": matches,
        "news_section": section,
        "source_categories": article.get("news_categories") or [],
        "paywall": article.get("paywall"),
        "permission": article.get("permission"),
        "provider": "tradingview",
    }


def build_snapshot(items, *, generated_at=None):
    rows = []
    seen = set()
    for article in list(items or []):
        if not isinstance(article, dict):
            continue
        row = normalize_article(article)
        if not row["title"] or row["event_category"]["code"] == "other":
            continue
        key = str(row["id"] or "") or (
            row["published_at"] + "|" + row["title"]
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
        if len(rows) >= MAX_PAGE_ITEMS:
            break

    stamp = generated_at or dt.datetime.now(dt.timezone.utc).isoformat()
    counts = {}
    for row in rows:
        code = row["event_category"]["code"]
        counts[code] = counts.get(code, 0) + 1
    return {
        "ok": True,
        "generated_at": stamp,
        "source": "tradingview",
        "taxonomy": "gaemigtp-stock-events-v1",
        "count": len(rows),
        "category_counts": counts,
        "items": rows,
    }


def write_snapshot(items, *, path=NEWS_PAGE_PATH):
    snapshot = build_snapshot(items)
    path = Path(path)
    if not path.parent.is_dir() or path.parent.is_symlink() or path.is_symlink():
        raise ValueError("unsafe_news_page_path")
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=str(path.parent),
            prefix=".tv-news-page-", delete=False,
        ) as f:
            name = f.name
            os.fchmod(f.fileno(), 0o600)
            json.dump(snapshot, f, ensure_ascii=False, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
    return snapshot
