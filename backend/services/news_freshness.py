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


def clean_us_snapshot(payload, *, now=None, issue_mode="auto", format_titles=True):
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


