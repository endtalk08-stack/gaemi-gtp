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
    ("economic", "경제지표", ("cpi", "pce", "gdp", "jobs", "payroll", "employment", "inflation", "retail sales", "pmi", "경제지표", "고용", "물가", "소비자물가",
        "ppi", "adp", "jolts", "ism", "jobless claims", "unemployment claims", "initial claims", "job openings", "consumer confidence", "consumer sentiment", "productivity", "실업수당", "구인건수", "생산성", "소비자심리", "소비자신뢰", "생산자물가", "비농업고용", "실업률", "고용보고서", "소매판매"
    )),
    ("fed", "연준", ("federal reserve", "fed ", "fomc", "powell", "rate cut", "rate hike", "연준", "파월", "금리 인하", "금리 인상",
        "central bank", "european central bank", "bank of england", "bank of japan", "lagarde", "bailey", "ueda", "waller", "williams", "hammack", "barkin", "bowman", "goolsbee", "daly", "라가르드", "베일리", "우에다", "월러", "윌리엄스", "해맥", "바킨", "보먼", "굴스비", "연은 총재", "금리 동결", "기준금리", "점도표", "연준 의사록", "양적긴축", "양적완화", "매파", "비둘기파"
    )),
    ("policy", "정부정책", ("white house", "congress", "treasury", "administration", "government", "policy", "정부", "정책", "백악관", "의회",
        "trump", "hassett", "트럼프", "해싯", "수출통제", "수출 제한", "수출규제", "반독점", "보조금", "재무장관", "백악관 발표"
    )),
    ("rates_bonds", "국채·금리", ("treasury yield", "bond yield", "10-year", "2-year", "yield curve", "interest rate", "국채금리", "채권금리", "10년물", "2년물", "수익률곡선")),
    ("energy", "에너지", ("oil", "crude", "opec", "natural gas", "energy", "원유", "유가", "천연가스", "에너지")),
    ("fx_commodities", "환율·원자재", ("dollar index", "dxy", "exchange rate", "forex", "currency", "달러지수", "환율", "엔화", "유로화")),
    ("tariff", "관세", ("tariff", "trade war", "import duty", "관세", "무역전쟁")),
    ("market_close", "미국장 마감", ("market close", "closing bell", "closed higher", "closed lower", "마감", "종가")),
    ("major_index", "주요지수", ("s&p 500", "nasdaq", "dow jones", "dow ", "index", "나스닥", "다우", "s&p")),
    ("sector", "시장동향", ("sector", "semiconductor stocks", "tech stocks", "financial stocks", "energy stocks", "healthcare stocks", "섹터", "업종", "반도체주", "기술주", "금융주", "에너지주", "헬스케어주")),
    ("volatility_sentiment", "시장동향", ("vix", "volatility", "fear gauge", "risk appetite", "risk-on", "risk-off", "investor sentiment", "변동성", "공포지수", "위험선호", "위험회피", "투자심리",
        "net inflows", "net outflows", "fund inflows", "fund outflows", "capital flows", "money market fund", "mmf", "liquidity", "credit spread", "credit default", "default risk", "short selling", "short interest", "institutional buying", "institutional selling", "자금 유입", "자금 유출", "자금유입", "자금유출", "기관 순매수", "기관 순매도", "순매수", "순매도", "공매도", "유동성", "신용스프레드", "신용 스프레드", "채무불이행", "국채 입찰", "옵션 만기"
    )),
    ("market_trend", "시장동향", ("futures", "rally", "selloff", "market sentiment", "선물", "랠리", "매도세", "시장 동향")),
    ("international", "국제정세", ("middle east", "iran", "war", "sanction", "geopolitical", "중동", "이란", "전쟁", "제재", "지정학")),
)


def _text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _article_body(value):
    """Preserve API paragraphs and remove clearly identified publisher boilerplate."""
    if not isinstance(value, str):
        return ""
    body = re.sub(r"[ \t]+", " ", value.replace("\r\n", "\n").replace("\r", "\n")).strip()
    body = re.sub(
        r"\s*\(로이터는 영어 원어민이 아닌 독자들의 편의를 위해[\s\S]*?"
        r"로이터는 완전 자동화된 번역 기능 사용으로 인한 어떠한 종류의 손해나 손실에 대해 "
        r"어떠한 책임도 지지 않습니다\.\)\s*$",
        "", body,
    ).strip()
    if not body:
        return ""
    if "\n" in body:
        return re.sub(r"\n[ \t]*\n+", "\n\n", body)
    sentences = re.split(r'(?<=[.!?]) +(?=[가-힣A-Z“‘"(])', body)
    if len(sentences) < 2:
        return body
    paragraphs = []
    group = []
    for sentence in sentences:
        if group and (len(group) >= 2 or sum(map(len, group)) > 350):
            paragraphs.append(" ".join(group))
            group = []
        group.append(sentence)
    if group:
        paragraphs.append(" ".join(group))
    return "\n\n".join(paragraphs)


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
        # Stock-feed membership alone is not a match for any of the 14 events.
        # Exclude unclassified stock headlines from the public news snapshot.
        return {"code": "other", "label": "기타"}, [], "other"

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
    # The overall feed by itself does not qualify a story for publication.
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



def extract_body_highlights(body, title=""):
    """Extract up to three informative original article sentences, without AI or API calls."""
    if not isinstance(body, str) or not body.strip():
        return ""
    title_words = set(re.findall(r"[가-힣A-Za-z]{2,}|\d+(?:\.\d+)?%?", _text(title).lower()))
    candidates = []
    for paragraph in re.split(r"\n\s*\n+", body):
        paragraph = " ".join(paragraph.split())
        if not paragraph or len(paragraph) > 3000:
            continue
        sentences = re.split(r'(?<=[.!?。])\s+(?=[가-힣A-Za-z0-9“‘"(])', paragraph)
        for sentence in sentences:
            sentence = sentence.strip()
            if not 18 <= len(sentence) <= 420:
                continue
            lower = sentence.lower()
            if lower.startswith(("면책", "법적 고지", "회사 소개", "관련 문의",
                                 "forward-looking", "about ", "본 자료는")):
                continue
            if len(re.findall(r"\d+(?:[,.]\d+)*", sentence)) >= 12:
                continue
            words = set(re.findall(r"[가-힣A-Za-z]{2,}|\d+(?:\.\d+)?%?", lower))
            score = len(words & title_words) * 3
            if re.search(r"\d+(?:[,.]\d+)*\s*(?:%|달러|원|억|조|명|개)", sentence):
                score += 1
            candidates.append((score, len(candidates), sentence))
    selected = []
    total = 0
    for score, index, sentence in sorted(candidates, key=lambda item: (-item[0], item[1])):
        if any(existing == sentence for _, existing in selected):
            continue
        length = len(sentence) + (1 if selected else 0)
        if total + length > 420:
            continue
        selected.append((index, sentence))
        total += length
        if len(selected) == 3:
            break
    return " ".join(sentence for _, sentence in sorted(selected))



def normalize_article(article):
    primary, matches, section = classify_article(article)
    # A news item keeps one ID while carrying both market and stock tags.
    market_matches = matches if section == "market" else [
        {"code": code, "label": label}
        for code, label, terms in MARKET_RULES
        if any(str(term).lower() in _text(article.get("title")).lower() for term in terms)
    ]
    market_evidence = [
        item for item in market_matches
        if item["code"] not in ("market", "market_trend")
    ]
    if section == "other" and market_evidence:
        primary, matches, section = market_evidence[0], market_matches, "market"
    stock_matches = matches if section == "stock" else []
    market_primary = (
        next((m for m in market_matches
              if m["code"] not in ("market", "market_trend", "sector")), None)
        or (market_evidence[0] if market_evidence else None)
        or (primary if section == "market" else None)
    )
    news_sections = ["stock"] if section == "stock" else []
    if section == "market" or (section == "stock" and market_evidence):
        news_sections.append("market")
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
        and (
            article.get("detail_rights_confirmed") is True
            or (article.get("permission") != "headline"
                and article.get("detail_permission") != "headline")
        )
    )
    body = _article_body(article.get("detail_body"))
    return {
        "id": article.get("id") or article.get("newsId"),
        "published_at": _published_iso(article),
        "title": _text(article.get("title")),
        # Compatibility display field for the existing Pages news-card renderer.
        # This is an API excerpt, not an AI-generated summary.
        "summary": _text(article.get("detail_summary") or article.get("summary") or article.get("shortDescription") or article.get("detail_description")),
        # Preserve the original API detail excerpt separately from a true summary.
        "description": _text(article.get("shortDescription") or article.get("detail_description")),


        "content_source": "api_detail" if article.get("detail_checked") else "news_list",
        "body_available": bool(body) and may_publish_body,
        "body": body if may_publish_body else "",
        "list_excerpt": extract_body_highlights(body, article.get("title")) if may_publish_body else "",
        "detail_status": _text(article.get("detail_checked")),
        # Full source article bodies are never copied into publicly readable Pages JSON.
        "source": source,
        "url": _news_url(article),
        "symbols": _symbols(article),
        "event_category": primary,
        "event_matches": matches,
        "news_section": section,
        "news_sections": news_sections,
        "stock_event_matches": stock_matches,
        "market_event_category": market_primary,
        "market_event_matches": market_matches if "market" in news_sections else [],
        "source_categories": article.get("news_categories") or [],
        "paywall": article.get("paywall"),
        "permission": article.get("permission"),
        "provider": "tradingview",
    }



def select_articles(items):
    """Select only displayable news before any article-detail request.

    Exact matching headlines are deduplicated even when TradingView returns
    different article IDs. Prefer an existing full body so it is not fetched again.
    """
    selected = {}
    seen_ids = set()
    for article in items or []:
        if not isinstance(article, dict):
            continue
        title = _text(article.get("title"))
        if not title:
            continue
        id_key = str(article.get("id") or article.get("newsId") or "").strip()
        if id_key and id_key in seen_ids:
            continue
        normalized = normalize_article(article)
        if normalized["event_category"]["code"] == "other":
            continue
        if id_key:
            seen_ids.add(id_key)
        title_key = title.casefold()
        previous = selected.get(title_key)
        if previous is None:
            selected[title_key] = article
            continue
        # Retain previously retrieved details for duplicate headlines.
        current_body = str(article.get("detail_body") or "")
        previous_body = str(previous.get("detail_body") or "")
        if len(current_body) > len(previous_body):
            selected[title_key] = article
    return list(selected.values())



def build_snapshot(items, *, generated_at=None):
    rows = []
    seen = set()
    for article in select_articles(items):
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


def preserve_saved_article_content(snapshot, previous):
    """Never replace a verified, previously published article field with blank.

    Match by exact article ID only; do not mix content between similarly
    titled articles. Keep the older paid rows when they leave the 48h feed.
    """
    if not isinstance(previous, dict) or not isinstance(previous.get("items"), list):
        return snapshot
    previous_by_id = {
        str(row["id"]): row for row in previous["items"]
        if isinstance(row, dict) and row.get("id")
    }
    for row in snapshot["items"]:
        old = previous_by_id.get(str(row.get("id") or ""))
        if not old:
            continue
        for field in ("body", "list_excerpt", "summary", "description"):
            if not str(row.get(field) or "").strip() and str(old.get(field) or "").strip():
                row[field] = old[field]
        if row.get("body") and old.get("body_available") is True:
            row["body_available"] = True
            if not row.get("detail_status") and old.get("detail_status"):
                row["detail_status"] = old["detail_status"]
            if row.get("content_source") == "news_list":
                row["content_source"] = old.get("content_source", "api_detail")
    # The API's 48-hour listing is not the retention policy for paid content.
    # Keep older public records even when they fall outside the collection cache.
    new_ids = {str(row.get("id")) for row in snapshot["items"] if row.get("id")}
    missing = [
        row for row in previous["items"]
        if isinstance(row, dict) and row.get("id")
        and str(row["id"]) not in new_ids
    ]
    snapshot["items"].extend(missing)
    snapshot["items"].sort(
        key=lambda row: str(row.get("published_at") or ""), reverse=True
    )
    snapshot["items"] = snapshot["items"][:MAX_PAGE_ITEMS]
    snapshot["count"] = len(snapshot["items"])
    counts = {}
    for row in snapshot["items"]:
        cat = row.get("event_category") or {}
        code = cat.get("code") if isinstance(cat, dict) else ""
        counts[code or "other"] = counts.get(code or "other", 0) + 1
    snapshot["category_counts"] = counts
    return snapshot


def write_snapshot(items, *, path=NEWS_PAGE_PATH):
    snapshot = build_snapshot(items)
    path = Path(path)
    if not path.parent.is_dir() or path.parent.is_symlink() or path.is_symlink():
        raise ValueError("unsafe_news_page_path")
    # Safe local continuity even if an API refresh returns only headlines.
    # Never treat a corrupt previous snapshot as an empty one and wipe it.
    if path.exists():
        if not path.is_file():
            raise ValueError("unsafe_previous_news_snapshot")
        previous = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(previous, dict)
                or previous.get("ok") is not True
                or not isinstance(previous.get("items"), list)):
            raise ValueError("invalid_previous_news_snapshot")
        snapshot = preserve_saved_article_content(snapshot, previous)
        # No news change: keep the same file/content hash, and avoid R2
        # archive writes once a minute for a changed generated_at timestamp.
        if (previous.get("source") == snapshot["source"]
                and previous.get("taxonomy") == snapshot["taxonomy"]
                and previous.get("items") == snapshot["items"]):
            return previous
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
