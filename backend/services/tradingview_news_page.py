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
    ("earnings", "실적 발표", (
        "earnings", "quarterly results", "financial results", "실적 발표",
        "실적발표", "어닝", "매출", "영업이익", "순이익", "eps",
    )),
    ("guidance", "실적 전망", (
        "guidance", "outlook", "forecast", "가이던스", "전망 상향",
        "전망 하향", "연간 전망", "매출 전망",
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
    ("regulation", "기업 관련 인허가·규제", (
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


def _text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def classify_article(article):
    haystack = " ".join((
        _text(article.get("title")),
        _text(article.get("shortDescription") or article.get("short_description")),
    )).lower()
    matched = []
    for code, label, terms in CATEGORY_RULES:
        if any(str(term).lower() in haystack for term in terms):
            matched.append({"code": code, "label": label})
    if matched:
        return matched[0], matched
    return {"code": "other", "label": "기타"}, []


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
    primary, matches = classify_article(article)
    provider = article.get("provider")
    source = (
        _text(provider.get("name"))
        if isinstance(provider, dict)
        else "TradingView"
    ) or "TradingView"
    return {
        "id": article.get("id") or article.get("newsId"),
        "published_at": _published_iso(article),
        "title": _text(article.get("title")),
        "summary": _text(
            article.get("shortDescription") or article.get("short_description")
        ),
        "source": source,
        "url": _news_url(article),
        "symbols": _symbols(article),
        "event_category": primary,
        "event_matches": matches,
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
        if not row["title"]:
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
