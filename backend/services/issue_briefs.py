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


def _brief_text(labels, themes, issues, stock_name):
    primary = next((label for label in labels if label in _SIGNAL_BRIEFS), "")
    stock = str(stock_name or "관련 종목").strip() or "관련 종목"
    if primary:
        headline, summary = _SIGNAL_BRIEFS[primary]
        return headline.format(stock=stock), summary

    topic = next(iter(themes or []), "") or next(iter(issues or []), "") or next(iter(labels or []), "시장")
    return (
        f"{topic} 이슈에 {stock} 주목",
        f"{topic} 관련 흐름이 확인되면서\n관련 종목에 관심이 모이고 있어요.",
    )


def build_issue_briefs(items, stock_name, limit=3):
    """Return display-only issue briefs without publisher title/description fields."""
    briefs = []
    for item in items or []:
        labels = _signal_labels(item)
        stock_names = _stock_names(item, stock_name)
        subject = stock_names[0] if stock_names else stock_name
        headline, summary = _brief_text(labels, item.get("themes") or [], item.get("issues") or [], subject)
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
    """Build the test-panel article payload from the same extracted news facts.

    The central issue flow remains unchanged.  This is a separate article-shaped
    output used only by the right-panel "뉴스 테스트" view, and it deliberately
    has no publisher title, description, source, or URL fields.
    """
    articles = []
    for index, brief in enumerate(build_issue_briefs(items, stock_name, limit=limit), start=1):
        articles.append({
            "id": f"news-test-{index}",
            "time": brief["time"],
            "headline": brief["headline"],
            "body": brief["summary"],
            "tags": brief["tags"],
            "stock_names": brief["stock_names"],
        })
    return articles
