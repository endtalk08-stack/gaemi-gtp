"""Build original, fact-bounded issue briefs from collected news metadata.

The central "notable flow" never receives an article title or description.
Those source fields are used only as evidence by the earlier classifier.  This
module turns its structured results into a short, consistent briefing that is
safe to render without repeating publisher wording.
"""

from __future__ import annotations

import re


_SIGNAL_BRIEFS = {
    "AI메모리": (
        "AI 메모리 기대감에 반도체주 주목",
        "AI 서버 수요와 고대역폭 메모리 기대가 이어지며\n관련 종목에 관심이 모이고 있어요.",
    ),
    "메모리가격": (
        "메모리 가격 흐름에 반도체주 주목",
        "메모리 가격 변화가 반도체 업황 기대에 영향을 주면서\n관련 종목에 관심이 모이고 있어요.",
    ),
    "실적상회": (
        "호실적 신호에 {stock} 주목",
        "실적 개선 신호가 확인되면서\n주가와 수급 반응에 관심이 모이고 있어요.",
    ),
    "호실적": (
        "호실적 이슈에 {stock} 주목",
        "실적 발표 이후 주가와 수급 반응을\n함께 살펴볼 필요가 있어요.",
    ),
    "사상최대실적": (
        "사상 최대 실적 발표에 {stock} 주목",
        "실적 자체와 별개로 시장 전반의 수급 흐름이\n주가에 영향을 줄 수 있어요.",
    ),
    "외국인매도": (
        "외국인 매도세에 {stock} 수급 주목",
        "외국인 수급 변화가 이어지며\n단기 주가 흐름에 관심이 모이고 있어요.",
    ),
    "금리부담": (
        "금리 부담에 시장 흐름 주목",
        "금리 변화가 투자 심리에 영향을 주면서\n관련 종목의 변동성이 커질 수 있어요.",
    ),
    "수주·계약": (
        "수주·계약 이슈에 {stock} 주목",
        "사업 진행과 실적 반영 가능성을 두고\n관련 종목에 관심이 모이고 있어요.",
    ),
    "주주환원": (
        "주주환원 이슈에 {stock} 주목",
        "주주환원 방향이 확인되면서\n주가와 투자자 반응에 관심이 모이고 있어요.",
    ),
    "차익실현": (
        "차익실현 흐름에 {stock} 주목",
        "단기 매물 출회 가능성이 거론되면서\n수급 변화를 함께 볼 필요가 있어요.",
    ),
    "실적부진": (
        "실적 부담에 {stock} 주목",
        "실적 우려가 투자 심리에 영향을 주면서\n주가와 수급 흐름을 함께 확인할 필요가 있어요.",
    ),
    "전망하향": (
        "전망 변화에 {stock} 주목",
        "향후 실적 기대가 바뀌면서\n관련 종목의 반응에 관심이 모이고 있어요.",
    ),
}


# Central "오늘 눈에 띄는 흐름" copy stays fact-bounded.
# These labels were already extracted from the article title + description;
# the central brief only makes them readable and never adds price/supply claims.
_CENTRAL_LABEL_TEXT = {
    "수익성개선": "수익성 개선",
    "HBM": "HBM",
    "HBM수요": "HBM 수요",
    "HBM수요급증": "HBM 수요 급증",
    "HBM공급부족": "HBM 공급 부족",
    "HBM공급확대": "HBM 공급 확대",
    "공급부족": "공급 부족",
    "가격상승": "가격 상승",
    "가격하락": "가격 하락",
    "메모리가격": "메모리 가격",
    "반도체호황": "반도체 업황",
    "반도체업황개선": "반도체 업황 개선",
    "AI메모리": "AI 메모리",
    "실적발표": "실적 발표",
    "잠정실적발표": "실적 발표",
    "매출발표": "실적 발표",
    "실적개선": "실적 개선",
    "실적상회": "실적 상회",
    "호실적": "호실적",
    "사상최대실적": "사상 최대 실적",
    "외국인매도": "외국인 매도",
    "수주·계약": "수주·계약",
    "주주환원": "주주환원",
    "차익실현": "차익실현",
    "실적부진": "실적 부진",
    "전망하향": "전망 하향",
    "공급확대": "공급 확대",
    "공급축소": "공급 축소",
    "생산확대": "생산 확대",
    "생산축소": "생산 축소",
    "해외진출": "해외 진출",
    "시장진출": "시장 진출",
    "사업확대": "사업 확대",
    "수요증가": "수요 증가",
    "수요급증": "수요 급증",
    "판매증가": "판매 증가",
    "판매감소": "판매 감소",
    "원화강세": "원화 강세",
    "원화약세": "원화 약세",
    "환율상승": "환율 상승",
    "환율하락": "환율 하락",
    "매출증가": "매출 증가",
    "매출감소": "매출 감소",
    "영업이익증가": "영업이익 증가",
    "영업이익감소": "영업이익 감소",
    "자사주매입": "자사주 매입",
    "자사주소각": "자사주 소각",
    "어닝서프라이즈": "어닝 서프라이즈",
    "공급계약": "공급 계약",
    "AI인프라": "AI 인프라",
    "AI데이터센터": "AI 데이터센터",
}


def _central_label_text(value):
    label = str(value or "").strip().lstrip("#")
    mapped = _CENTRAL_LABEL_TEXT.get(label)
    if mapped:
        return mapped

    # Numeric facts are stored compactly for matching, but central copy should
    # read like normal Korean: 영업이익100조원기대 -> 영업이익 100조원 기대.
    match = re.match(
        r"^(영업이익률|영업이익|매출|순이익|HBM매출|D램매출|낸드매출|"
        r"목표가|생산능력|생산량|공급량|출하량|판매량)(.+)$",
        label,
    )
    if not match:
        return label

    prefix, tail = match.groups()
    tail = re.sub(r"^(전망치)(?=\d)", r"\1 ", tail)
    tail = re.sub(
        r"(증가|감소|상승|하락|확대|축소|상향|하향|상회|하회)"
        r"(?=\s*(?:검토|계획|예정|전망|예상|추정|관측|가능성|기대)?$)",
        r" \1",
        tail,
    )
    tail = re.sub(
        r"(검토|계획|예정|전망|예상|추정|관측|가능성|기대)$",
        r" \1",
        tail,
    )
    tail = re.sub(r"\s+", " ", tail).strip()
    return f"{prefix} {tail}".strip()


def _central_readable_labels(labels):
    output = []
    for label in labels or []:
        value = _central_label_text(label)
        if value and value not in output:
            output.append(value)
    return output


def _clean_labels(values, limit=3):
    labels = []
    for value in values or []:
        label = str(value or "").strip().lstrip("#")
        if label and label not in labels:
            labels.append(label)
        if len(labels) >= limit:
            break
    return labels


def _signal_labels(item):
    """Merge the representative event with other grounded facts from the same article."""
    labels = []
    for values in (
        item.get("storyboard_keywords") or [],
        item.get("article_keywords") or [],
    ):
        for value in values:
            label = str(value or "").strip().lstrip("#")
            if label and label not in labels:
                labels.append(label)
            if len(labels) >= 3:
                return labels

    for signal in item.get("movement_signals") or []:
        label = str((signal or {}).get("label") or "").strip().lstrip("#")
        if label and label not in labels:
            labels.append(label)
        if len(labels) >= 3:
            break
    return labels


def _stock_names(item, fallback):
    names = _clean_labels(item.get("stock_entities"), limit=4)
    for stock in item.get("stocks") or []:
        name = str((stock or {}).get("name") or "").strip()
        if name and name not in names:
            names.append(name)
        if len(names) >= 4:
            break
    return names or _clean_labels([fallback], limit=1)


def _korean_particle(value, consonant, vowel):
    """Choose a Korean particle from the final Hangul syllable when possible."""
    text = str(value or "").strip()
    if not text:
        return vowel
    code = ord(text[-1]) - 0xAC00
    if 0 <= code <= 11171:
        return consonant if code % 28 else vowel
    return vowel


def _join_brief_facts(values):
    facts = [str(value or "").strip() for value in values or [] if str(value or "").strip()]
    if len(facts) <= 1:
        return facts[0] if facts else ""
    if len(facts) == 2:
        particle = _korean_particle(facts[0], "과", "와")
        return f"{facts[0]}{particle} {facts[1]}"
    return ", ".join(facts)


def _compose_brief_summary(headline, remaining, fallback_stock):
    """Turn grounded labels into one readable, fact-bounded central sentence."""
    stock = str(fallback_stock or "").strip()
    extra = [str(value or "").strip() for value in remaining[:2] if str(value or "").strip()]
    if not stock or not extra:
        return ""

    uncertainty_endings = (
        "기대", "전망", "예상", "추정", "관측", "가능성", "검토", "계획", "예정",
    )
    if headline.endswith(uncertainty_endings):
        particle = _korean_particle(headline, "이", "가")
        return f"{stock}는 {headline}{particle} 나오고, {', '.join(extra)}도 함께 언급됐어요."

    facts = [headline, *extra]
    joined = _join_brief_facts(facts)
    particle = _korean_particle(facts[-1], "이", "가")
    return f"{stock} 관련해서는 {joined}{particle} 함께 언급됐어요."


def _brief_text(labels, themes, issues, stock_names, fallback_stock):
    """Compose natural central copy from grounded facts without source-copy filler."""
    raw_labels = [str(label or "").strip().lstrip("#") for label in labels or []]
    raw_labels = [label for label in raw_labels if label]

    # Do not spend central-copy space on generic earnings labels when a more
    # concrete earnings fact from the same item already exists.
    has_numeric_earnings = any(
        label.startswith(("영업이익", "매출", "순이익", "영업이익률"))
        and any(char.isdigit() for char in label)
        for label in raw_labels
    )
    display_labels = list(raw_labels)
    if has_numeric_earnings:
        display_labels = [
            label for label in display_labels
            if label not in {"실적발표", "잠정실적발표", "매출발표"}
        ]
    if "어닝서프라이즈" in display_labels or "사상최대실적" in display_labels:
        display_labels = [label for label in display_labels if label != "호실적"]

    readable = _central_readable_labels(display_labels)
    if not readable:
        topic = str(next(iter(themes or []), "") or next(iter(issues or []), "") or "시장").strip()
        return f"{topic} 관련 흐름", ""

    label_set = set(display_labels)
    if "가격상승" in label_set and "메모리가격" in label_set:
        headline = "메모리 가격 상승"
        consumed = {"가격 상승", "메모리 가격"}
    elif "수익성개선" in label_set and "HBM" in label_set:
        headline = "수익성 개선·HBM"
        consumed = {"수익성 개선", "HBM"}
    else:
        headline = readable[0]
        consumed = {headline}

    remaining = [value for value in readable if value not in consumed]
    if not remaining:
        return headline, ""

    summary = _compose_brief_summary(headline, remaining, fallback_stock)
    return headline, summary
def build_issue_briefs(items, stock_name, limit=3):
    """Return display-only issue briefs without publisher title/description fields."""
    briefs = []
    for item in items or []:
        labels = _signal_labels(item)
        stock_names = _stock_names(item, stock_name)
        headline, summary = _brief_text(
            labels,
            item.get("themes") or [],
            item.get("issues") or [],
            stock_names,
            stock_name,
        )
        if not headline or not summary:
            continue
        briefs.append({
            "time": str(item.get("storyboard_time") or "").strip(),
            "headline": headline,
            "summary": summary,
            "tags": labels[:3],
            "stock_names": stock_names[:4],
        })
        if len(briefs) >= max(1, int(limit)):
            break
    return briefs


def build_news_test_articles(items, stock_name, limit=3):
    """Build article-shaped test output from structured news facts only.

    Unlike ``build_issue_briefs``, this produces a headline and two short
    paragraphs for the right-panel test view.  It never passes through an
    original publisher title, description, source, or URL.
    """
    articles = []
    for index, item in enumerate(items or [], start=1):
        labels = _signal_labels(item)
        stock_names = _stock_names(item, stock_name)
        headline, body, tags = _article_text(
            labels,
            item.get("themes") or [],
            item.get("issues") or [],
            stock_names,
            stock_name,
        )
        articles.append({
            "id": f"news-test-{index}",
            "time": str(item.get("storyboard_time") or "").strip(),
            "headline": headline,
            "body": body,
            "tags": tags,
            "stock_names": stock_names[:4],
        })
        if len(articles) >= max(1, int(limit)):
            break
    return articles


def _stock_phrase(stock_names, fallback):
    names = _clean_labels(stock_names, limit=3) or _clean_labels([fallback], limit=1)
    if len(names) == 2:
        return f"{names[0]}와 {names[1]}"
    return ", ".join(names)


def _article_tags(labels, themes, primary=""):
    tags = ["특징주"]
    for label in [primary, *(themes or []), *labels]:
        label = str(label or "").strip().lstrip("#")
        if label and label not in tags:
            tags.append(label)
        if len(tags) >= 3:
            break
    return tags


def _article_text(labels, themes, issues, stock_names, fallback):
    """Return original article-style copy derived from classifier facts."""
    primary = next((label for label in labels if label in _SIGNAL_BRIEFS), "")
    subject = _stock_phrase(stock_names, fallback)
    theme = next(iter(themes or []), "") or "관련 업종"

    if primary == "AI메모리":
        detail = "관련 기업별 실적 개선 기대와 HBM 수요가\n주가 흐름의 핵심 재료로 언급됐어요."
        if "삼성전자" in stock_names and "SK하이닉스" in stock_names:
            detail = (
                "삼성전자는 실적 개선 기대가, SK하이닉스는 HBM 수요가\n"
                "각각 주가 흐름의 핵심 재료로 언급됐어요."
            )
        return (
            "AI 메모리 기대감에 반도체주 강세",
            f"AI 서버 투자와 메모리 가격 상승 기대가 이어지며\n{subject}에 매수세가 유입되고 있어요.\n\n{detail}",
            _article_tags(labels, themes, primary),
        )

    if primary == "메모리가격":
        return (
            "메모리 가격 기대에 반도체주 관심",
            f"메모리 가격 흐름 개선 기대가 이어지며\n{subject}을 중심으로 투자자 관심이 커지고 있어요.\n\n{theme} 업황 회복 가능성이 주가 흐름의\n주요 재료로 언급됐어요.",
            _article_tags(labels, themes, primary),
        )

    if primary in {"실적상회", "호실적", "사상최대실적"}:
        return (
            f"실적 기대에 {subject} 주목",
            f"실적 개선 기대가 이어지며\n{subject}의 주가 흐름에 관심이 모이고 있어요.\n\n발표된 실적과 향후 전망이 시장 기대에 부합하는지가\n추가 흐름을 가를 핵심으로 언급됐어요.",
            _article_tags(labels, themes, primary),
        )

    topic = next(iter(issues or []), "") or theme or next(iter(labels or []), "시장")
    return (
        f"{topic} 이슈에 {subject} 관심",
        f"{topic} 관련 흐름이 이어지며\n{subject}에 투자자 관심이 모이고 있어요.\n\n관련 뉴스와 수급 변화가\n단기 주가 흐름의 재료로 언급됐어요.",
        _article_tags(labels, themes, primary),
    )
