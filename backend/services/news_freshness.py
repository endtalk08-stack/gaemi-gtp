"""Read-only freshness guard shared by Render chat and market sidebar.

DigitalOcean owns news collection and original article-body verification. Render only filters Neon snapshots
using the original published_at of cited articles, never the AI/DB write time.
"""
from copy import deepcopy
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")


def _article_date(value):
    stamp = str(value or "").strip()
    if not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        try:
            parsed = parsedate_to_datetime(stamp)
        except (ValueError, TypeError, IndexError, OverflowError):
            return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


ISSUE_MODES = frozenset(("auto", "ai", "code", "both"))


def normalize_issue_mode(mode):
    """Safe per-request preference; unsupported values keep existing behavior."""
    value = str(mode or "").strip().lower()
    return value if value in ISSUE_MODES else "auto"


def issue_mode_for_question(question, *, explicit=None):
    """Route article-fact questions to code, movement reasons to existing AI."""
    requested = normalize_issue_mode(explicit)
    if requested != "auto":
        return requested
    content = str(question or "").replace(" ", "").lower()
    if any(word in content for word in ("왜올랐", "왜떨어", "왜하락", "왜상승", "상승이유", "하락이유", "주가원인", "주가이유")):
        return "ai"
    if any(word in content for word in ("이슈는", "이슈있", "최근이슈", "오늘이슈", "뉴스있", "뉴스는", "핵심재료", "관련기사", "새소식")):
        return "code"
    return "auto"



def _compact_code_news_title(brief):
    """Compose a short display headline from the verified article facts.

    Never reuse the publisher's truncated title or imply that a forecast,
    analysis or possibility has already happened. Ambiguous facts keep the
    original category label instead of producing an invented news headline.
    """
    original = str(brief.get("headline") or "").strip()
    if not original.endswith(" 이슈") and original not in {"기사 주요 내용", "관련 이슈"}:
        return original
    summary = re.sub(r"\s+", " ", str(brief.get("summary") or "")).strip()
    if not summary or summary == "원문 확인 불가":
        return original

    def actor_name():
        match = re.search(
            r"(?:전문기업|제약사|서비스 기업|소프트웨어 기업)\s+"
            r"([가-힣A-Za-z0-9·-]{2,28})", summary
        )
        if match:
            return re.sub(r"(?:이|가|은|는|의)$", "", match.group(1))
        match = re.match(r"([가-힣A-Za-z0-9·-]{2,25})(?:와|과|이|가|은|는)\b", summary)
        if match:
            return match.group(1)
        match = re.match(r"(?:일론\s+)?(머스크)(?:가|는|의)\b", summary)
        return match.group(1) if match else ""

    actor = actor_name()
    headline = ""
    if ("중동" in summary and "국제유가" in summary
            and "급등" in summary and "뉴욕 증시" in summary
            and re.search(r"(?:하락세|하락|내림세).*마감", summary)):
        headline = "중동 긴장·유가 급등에 뉴욕증시 하락"

    if not headline and re.search(r"암\s*백신", summary) and re.search(r"(?:임상\s*)?3상", summary):
        price = re.search(r"주가[^.!?]{0,30}?(\d{1,2}(?:\.\d+)?)%\s*(?:가까이|이상|넘게)?\s*급락", summary)
        if actor and price and re.search(r"(?:효과|입증|성공)", summary):
            approx = "약 " if "가까이" in price.group(0) else ""
            headline = f"{actor} 암백신, 3상 효과에도 주가 {approx}{price.group(1)}% 급락"
        elif actor and re.search(r"(?:재발|사망)\s*(?:또는\s*사망)?\s*위험[^.!?]{0,40}(?:낮췄|감소)", summary):
            partner = "·MSD" if "MSD" in summary[:110] else ""
            headline = f"{actor}{partner} 암백신, 3상서 재발·사망 위험 감소"

    if not headline and "AI" in summary and "데이터센터" in summary:
        amount = re.search(r"최대\s*(\d[\d,]*(?:조|억)?\s*(?:달러|원))", summary)
        if (amount and re.search(r"(?:투입|투자)", summary)
                and re.search(r"(?:투입할 수|가능성|분석이 나왔다|전망)", summary)):
            if actor:
                headline = f"{actor}, AI 데이터센터 최대 {amount.group(1)} 투자 가능성"
            else:
                headline = f"AI 데이터센터 최대 {amount.group(1)} 투자 가능성"

    if (not headline and "사이버트럭" in summary and "확보" in summary
            and "사업 확대" in summary and actor):
        if "광고" in summary and "렌트" in summary:
            headline = f"{actor}, 사이버트럭 확보해 광고·대여 사업 확대"
        else:
            headline = f"{actor}, 사이버트럭 확보해 사업 확대"

    if not headline and "컴퓨팅 공급 능력" in summary and "매진" in summary:
        name = re.search(r"([가-힣A-Za-z0-9·-]+)\(([A-Z]{2,8})\)의\s*컴퓨팅 공급 능력", summary)
        if name:
            until = "내년까지 " if "내년까지" in summary else ""
            prefix = "AI 컴퓨팅" if "AI" in summary else "컴퓨팅"
            headline = f"{name.group(2)}, {prefix} 공급능력 {until}매진"

    if not headline and re.search(r"(?:인공지능\(AI\)|AI)\s*컴퓨팅\s*수요\s*증가", summary):
        subject = re.search(r"([가-힣A-Za-z0-9·-]{2,25})의[^.!?]{0,40}(?:인공지능\(AI\)|AI)\s*컴퓨팅\s*수요\s*증가", summary)
        if subject:
            headline = f"{subject.group(1)}, AI 컴퓨팅 수요 증가"

    if not headline and actor:
        event_patterns = (
            (r"목표\s*주가\s*상향", "목표주가 상향"),
            (r"목표\s*주가\s*하향", "목표주가 하향"),
            (r"(?:공급\s*계약|납품\s*계약)[^.!?]{0,50}체결", "공급계약 체결"),
            (r"자사주[^.!?]{0,30}소각", "자사주 소각"),
            (r"신용\s*등급[^.!?]{0,25}상향", "신용등급 상향"),
            (r"신용\s*등급[^.!?]{0,25}하향", "신용등급 하향"),
        )
        for pattern, event in event_patterns:
            if re.search(pattern, summary):
                headline = f"{actor}, {event}"
                break

    if not headline or len(headline) > 48 or "..." in headline or "…" in headline:
        return original
    return headline

def _source_news_brief(brief, articles):
    """Display the selected article's provider text; never generate missing prose."""
    sources = [s for s in brief.get("source_articles") or [] if isinstance(s, dict)]
    sources.sort(key=lambda s: (_article_date(s.get("published_at"))
                               or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    for source in sources:
        url = str(source.get("url") or "").strip()
        article = articles.get(url, {})
        title = str(article.get("original_title") or article.get("title")
                    or source.get("original_title") or source.get("title") or "").strip()
        if not title:
            continue
        text = str(article.get("original_description") or article.get("description")
                   or source.get("original_description") or source.get("description") or "").strip()
        # A verified stored original excerpt remains usable when the feed has
        # no description. Do not substitute generated/unsupported issue prose.
        if not text and brief.get("evidence_source") != "original_unavailable":
            text = str(brief.get("original_summary") or brief.get("summary") or "").strip()
            if text == "원문 확인 불가":
                text = ""
        return {**brief, "headline": title, "summary": text,
                "display_content_source": "provider_news" if text else "title_only"}
    if brief.get("evidence_source") == "original_unavailable":
        return None
    return dict(brief)



# Fourteen event families are classified by the DigitalOcean worker; Render only
# selects and presents its stored classifications. Never recalculate them here.
CODE_EVENT_FAMILIES = frozenset((
    "EARNINGS", "GUIDANCE", "ANALYST", "MACRO", "COMMODITY", "SECTOR",
    "OPERATIONS", "CONTRACT", "PRODUCT", "REGULATION", "CAPITAL",
    "CORPORATE", "LEGAL", "FLOW",
))


def _code_event_article_briefs(articles_by_url, company_aliases):
    """Latest distinct, stock-mentioned, classified events from stored articles.

    Group by a reproducible combination of source-text similarity, actors and
    reported amounts, not by generic event family alone. Retain every source
    citation while displaying one latest representative per event.
    """
    from collections import Counter
    from math import log, sqrt

    aliases = [re.sub(r"\s+", "", str(a).casefold())
               for a in company_aliases if str(a or "").strip()]
    if not aliases:
        return []

    def normalized(value):
        return re.sub(r"\s+", " ", re.sub(
            r"[^a-z0-9가-힣]+", " ", str(value or "").casefold()
        )).strip()

    def mentions_stock(article):
        text = re.sub(r"\s+", "", (
            str(article.get("original_title") or article.get("title") or "") + " " +
            str(article.get("original_description") or article.get("description") or "")
        ).casefold())
        for name in aliases:
            if re.fullmatch(r"[a-z0-9.-]{1,5}", name):
                if re.search(r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])", text):
                    return True
            elif name in text:
                return True
        return False

    candidates = []
    for article in articles_by_url.values():
        classification = article.get("event_classification") or {}
        events = [e for e in (classification.get("events") or [])
                  if isinstance(e, dict) and e.get("family") in CODE_EVENT_FAMILIES]
        if not events or not mentions_stock(article):
            continue
        candidates.append((article, events))
    candidates.sort(key=lambda pair: _article_date(
        pair[0].get("published_at") or pair[0].get("pubDate")
    ) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    if not candidates:
        return []

    texts = [
        str(a.get("original_title") or a.get("title") or "") + " " +
        str(a.get("original_description") or a.get("description") or "")
        for a, _ in candidates
    ]

    def words(value):
        return {w for token in normalized(value).split()
                if len(w := re.sub(
                    r"(?:에서는|에서|으로|에게|까지|의|와|과|이|가|는|은|를|을|도|로|에)$",
                    "", token,
                )) >= 3}

    def trigrams(value):
        value = normalized(value)
        return Counter(value[i:i+3] for i in range(len(value)-2)
                       if " " not in value[i:i+3])

    def vectors(documents):
        counts = Counter()
        for doc in documents:
            counts.update(doc.keys())
        vectors_out = []
        total_docs = len(documents)
        for doc in documents:
            weighted = {key: (1 + log(freq)) *
                        (1 + log((total_docs+1)/(counts[key]+1)))
                        for key, freq in doc.items()}
            length = sqrt(sum(v*v for v in weighted.values())) or 1
            vectors_out.append({key: value/length for key, value in weighted.items()})
        return vectors_out

    def similarity(first, second):
        return sum(value * second.get(key, 0) for key, value in first.items())

    def amounts(value):
        return {re.sub(r"[,\s]", "", match).casefold() for match in re.findall(
            r"\d[\d,.]*\s*(?:조|억|만)\s*(?:달러|원|弗)?|"
            r"\d[\d,.]*\s*(?:million|billion)\s*(?:dollars|usd)?",
            str(value or ""), flags=re.I,
        )}

    character_vectors = vectors([trigrams(t) for t in texts])
    word_sets = [words(t) for t in texts]
    word_vectors = vectors([dict.fromkeys(ws, 1) for ws in word_sets])
    word_df = Counter(w for ws in word_sets for w in ws)
    title_words = [words(a.get("original_title") or a.get("title")) for a, _ in candidates]
    amount_sets = [amounts(t) for t in texts]
    parent = list(range(len(candidates)))

    def root(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for i in range(len(candidates)):
        for j in range(i+1, len(candidates)):
            score = (0.65 * similarity(character_vectors[i], character_vectors[j])
                     + 0.35 * similarity(word_vectors[i], word_vectors[j]))
            common_amounts = amount_sets[i] & amount_sets[j]
            common_words = {w for w in word_sets[i] & word_sets[j]
                            if 2 <= word_df[w] <= max(2, int(len(candidates)*0.68))
                            and w not in {"엔비디아", "nvidia"}}
            duplicate = (
                score >= 0.30
                or (score >= 0.24 and bool(common_amounts))
                or (bool(common_amounts) and len(common_words) >= 3
                    and bool(common_words & title_words[i] & title_words[j]))
            )
            if duplicate:
                parent[root(j)] = root(i)

    groups = {}
    for i, record in enumerate(candidates):
        groups.setdefault(root(i), []).append(record)
    selected = []
    for group in groups.values():
        # Candidates and group members are already in newest-first order.
        representative, events = group[0]
        published = _article_date(representative.get("published_at"))
        sources = [{
            "title": str(article.get("original_title") or article.get("title") or ""),
            "url": str(article.get("url") or article.get("link") or ""),
            "published_at": article.get("published_at") or "",
            "source": article.get("source") or "",
        } for article, _ in group]
        selected.append({
            "headline": sources[0]["title"],
            "summary": str(representative.get("original_description") or
                           representative.get("description") or ""),
            "tags": list(dict.fromkeys(e.get("label", "") for e in events
                                      if e.get("label")))[:3],
            "event_types": list(dict.fromkeys(e.get("event_type", "") for e in events
                                               if e.get("event_type"))),
            "event_families": list(dict.fromkeys(e["family"] for e in events)),
            "event_selection_revision": 1,
            "source_articles": sources,
            "stock_names": [str(company_aliases[0])],
            "time": published.astimezone(SEOUL).strftime("%H:%M") if published else "",
            "reaction_at": "",
            "display_content_source": "provider_news",
        })
    selected.sort(key=lambda b: _article_date(b["source_articles"][0]["published_at"])
                  or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return selected

def clean_us_snapshot(payload, *, now=None, issue_mode="auto", format_titles=True, company_aliases=()):
    """Read cited, 24-hour code and preserved AI channels without changing either.

    Both consumers use this function. Reject old source timestamps even when
    a snapshot was saved minutes ago. Unknown dates are not fabricated.
    """
    if not isinstance(payload, dict):
        return {}
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone-aware now required")
    cutoff = now.astimezone(timezone.utc) - timedelta(hours=24)
    upper = now.astimezone(timezone.utc)
    result = deepcopy(payload)
    # Both news channels are retained. UI preferences never invoke an AI
    # model, rerun article selection or write to Neon.
    v3 = (
        str(result.get("_title_only_revision") or "") == "3"
        and str(result.get("_code_fact_extraction_version") or "") == "3"
    )

    articles_by_url = {}
    # Prefer the full provider feed over enriched storyboard copies.
    for key in ("paired_news_items", "panel_news_items", "storyboard_news_items"):
        for article in result.get(key) or []:
            if not isinstance(article, dict):
                continue
            url = str(article.get("url") or article.get("link") or "").strip()
            pub = _article_date(article.get("published_at") or article.get("pubDate"))
            if url and pub is not None and cutoff <= pub <= upper:
                articles_by_url.setdefault(url, article)

    def fresh_source_briefs(briefs, *, code_only=False):
        if not isinstance(briefs, list):
            return []
        fresh = []
        for brief in briefs:
            if not isinstance(brief, dict):
                continue
            if code_only and brief.get("_issue_expires_at"):
                expiry = _article_date(brief["_issue_expires_at"])
                if expiry is None or expiry <= upper:
                    continue
            valid_sources = []
            for source in brief.get("source_articles") or []:
                if not isinstance(source, dict):
                    continue
                pub = _article_date(source.get("published_at"))
                url = str(source.get("url") or "").strip()
                if pub is None or not cutoff <= pub <= upper or not url.startswith(("https://", "http://")):
                    continue
                publisher = str(source.get("source") or "").strip() or (urlparse(url).hostname or "")
                if not publisher:
                    continue
                valid_sources.append((pub, {**source, "source": publisher}))
            if not valid_sources:
                continue
            valid_sources.sort(key=lambda pair: pair[0], reverse=True)
            latest = valid_sources[0][0]
            if code_only:
                brief = _source_news_brief(
                    {**brief, "source_articles": [source for _, source in valid_sources]},
                    articles_by_url,
                )
            if brief is None:
                continue
            headline = str(brief.get("headline") or "").strip()
            if code_only and format_titles and not any(
                str(source.get("title") or "").strip() for _, source in valid_sources
            ):
                headline = re.sub(r"\s*이슈\s*$", "", headline).strip()
            if not headline:
                continue
            fresh.append({
                **brief,
                "headline": headline,
                "time": latest.astimezone(SEOUL).strftime("%H:%M"),
                "reaction_at": "",
                "source_articles": [source for _, source in valid_sources],
            })
        # Keep every source-verified issue within the existing 24-hour window.
        fresh.sort(
            key=lambda brief: max(
                _article_date(source.get("published_at"))
                for source in brief["source_articles"]
            ),
            reverse=True,
        )
        return fresh

    channels = {
        "code": fresh_source_briefs(result.get("_code_issue_briefs"), code_only=True) if v3 else [],
        "ai": fresh_source_briefs(result.get("_ai_issue_briefs")),
    }
    if v3 and str(result.get("_event_taxonomy_revision") or "") == "1" and company_aliases:
        channels["code"] = _code_event_article_briefs(articles_by_url, company_aliases)
    mode = normalize_issue_mode(issue_mode)
    if mode == "code":
        selected, channel = channels["code"], "code"
    elif mode == "ai":
        selected, channel = channels["ai"], "ai"
    elif mode == "both":
        selected = channels["code"] + channels["ai"]
        channel = "both"
    else:
        # Automatic US news display uses source-cited CODE facts only.
        # Existing AI analyses remain stored but are not displayed as fallback.
        selected = channels["code"]
        channel = "code" if selected else "unavailable"
    result["issue_channels"] = channels
    result["issue_mode"] = mode
    result["_issue_display_channel"] = channel
    # Merged AI/CODE display must also respect published_at ordering.
    if mode == "both":
        selected.sort(
            key=lambda brief: max(
                _article_date(source.get("published_at"))
                for source in brief["source_articles"]
            ),
            reverse=True,
        )
    result["issue_briefs"] = selected[:3]

    # Price reason shares the same strict 24-hour cited-article freshness rule.
    reason = result.get("price_reason")
    if isinstance(reason, dict):
        sources = []
        for source in reason.get("source_articles") or []:
            if not isinstance(source, dict):
                continue
            pub = _article_date(source.get("published_at"))
            url = str(source.get("url") or "").strip()
            if pub is None or not cutoff <= pub <= upper or not url.startswith(("https://", "http://")):
                continue
            publisher = str(source.get("source") or "").strip() or (urlparse(url).hostname or "")
            if publisher:
                sources.append(source)
        result["price_reason"] = {**reason, "source_articles": sources} if sources else None

    # Do not let an old article become today's news merely because DigitalOcean
    # refreshed the snapshot or a cached panel reloaded.
    for key in ("paired_news_items", "panel_news_items", "storyboard_news_items"):
        items = result.get(key)
        if not isinstance(items, list):
            continue
        result[key] = [
            item for item in items
            if isinstance(item, dict)
            and (pub := _article_date(item.get("published_at") or item.get("pubDate"))) is not None
            and cutoff <= pub <= upper
        ]
    return result


