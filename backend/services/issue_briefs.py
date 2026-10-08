"""Build original, fact-bounded issue briefs from collected news metadata.

The central "notable flow" never receives an article title or description.
Those source fields are used only as evidence by the earlier classifier.  This
module turns its structured results into a short, consistent briefing that is
safe to render without repeating publisher wording.
"""

from __future__ import annotations


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
}


def _central_label_text(value):
    label = str(value or "").strip().lstrip("#")
    return _CENTRAL_LABEL_TEXT.get(label, label)


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
    labels = _clean_labels(item.get("storyboard_keywords") or item.get("article_keywords"), limit=3)
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


def _brief_text(labels, themes, issues, stock_names, fallback_stock):
    """Build a concise central issue from facts already extracted from the article."""
    label_set = {str(label or "").strip().lstrip("#") for label in labels or []}
    stock = next((str(name or "").strip() for name in stock_names or [] if str(name or "").strip()), "")
    stock = stock or str(fallback_stock or "").strip()

    if {"수익성개선", "HBM", "공급부족"}.issubset(label_set):
        return (
            "수익성 개선·HBM 공급 이슈",
            "수익성 개선 흐름과 HBM, 공급 부족 관련 내용이\n기사에서 함께 언급됐어요.",
        )

    if "메모리가격" in label_set and "가격상승" in label_set:
        return (
            "메모리 가격 상승 기대",
            "메모리 가격 상승과 반도체 업황 관련 기대가\n기사에서 함께 언급됐어요.",
        )

    if label_set.intersection({"실적발표", "잠정실적발표", "매출발표"}):
        if stock:
            return (
                "실적 발표 관련 이슈",
                f"실적 발표 관련 내용이 확인됐고,\n{stock}가 기사에서 직접 언급됐어요.",
            )
        return (
            "실적 발표 관련 이슈",
            "실적 발표 관련 내용이\n기사에서 확인됐어요.",
        )

    readable = _central_readable_labels(labels)
    if len(readable) >= 2:
        return (
            f"{readable[0]}·{readable[1]} 이슈",
            f"{', '.join(readable[:3])} 관련 내용이\n기사에서 함께 언급됐어요.",
        )
    if readable:
        return (
            f"{readable[0]} 관련 이슈",
            f"{readable[0]} 관련 내용이\n기사에서 언급됐어요.",
        )

    topic = str(next(iter(themes or []), "") or next(iter(issues or []), "") or "시장").strip()
    return (
        f"{topic} 관련 이슈",
        f"{topic} 관련 내용이\n기사에서 확인됐어요.",
    )


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
