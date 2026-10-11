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
    "HBM가격상승": "HBM 가격 상승",
    "HBM가격하락": "HBM 가격 하락",
    "메모리가격상승": "메모리 가격 상승",
    "메모리가격하락": "메모리 가격 하락",
    "D램가격상승": "D램 가격 상승",
    "D램가격하락": "D램 가격 하락",
    "낸드가격상승": "낸드 가격 상승",
    "낸드가격하락": "낸드 가격 하락",
    "제품가격상승": "제품 가격 상승",
    "제품가격하락": "제품 가격 하락",
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
    "역대급실적": "역대급 실적",
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
    "제품공개": "제품 공개",
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


_CENTRAL_SIMPLE_NUMERIC_PREFIXES = (
    "영업이익률",
    "영업이익",
    "매출",
    "순이익",
    "HBM매출",
    "D램매출",
    "낸드매출",
    "목표가",
)


def _central_simple_numeric_label(value):
    """Hide extraction-shaped numeric labels in the central display only."""
    label = str(value or "").strip().lstrip("#")
    if not any(char.isdigit() for char in label):
        return ""
    return next(
        (prefix for prefix in _CENTRAL_SIMPLE_NUMERIC_PREFIXES if label.startswith(prefix)),
        "",
    )


def _central_display_tags(labels):
    tags = []
    for raw in labels or []:
        label = str(raw or "").strip().lstrip("#")
        if not label:
            continue
        display = _central_simple_numeric_label(label) or label
        if display not in tags:
            tags.append(display)
        if len(tags) >= 3:
            break
    return tags


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


_EVENT_SUBJECT_BLOCKLIST = {
    "미국", "한국", "중국", "일본", "유럽", "아시아", "중동",
    "SEC", "FDA", "코스피", "코스닥", "나스닥", "뉴욕증시", "WTI",
}


def _concrete_event_subject(item, labels, stock_names):
    """Use only structured/grounded product facts to clarify generic events."""
    primary = str(next(iter(labels or []), "") or "").strip().lstrip("#")
    if primary != "제품공개":
        return ""

    detail_product = str((item.get("detail_facts") or {}).get("product_name") or "").strip()
    if detail_product:
        return detail_product

    stock_set = {str(name or "").strip() for name in stock_names or []}
    for value in item.get("grounded_tags") or []:
        tag = str(value or "").strip().lstrip("#")
        if not tag or tag in stock_set or tag in _EVENT_SUBJECT_BLOCKLIST:
            continue
        return tag
    return ""


def _structured_detail_summary(item, labels, summary_index=0):
    """Explain confirmed article facts separately, without copying publisher prose."""
    detail = item.get("detail_facts") or {}
    if not isinstance(detail, dict):
        return ""

    label_set = {
        str(value or "").strip().lstrip("#")
        for value in labels or []
        if str(value or "").strip()
    }
    contract_labels = {"공급계약", "장기공급계약", "계약체결", "수주·계약", "대형수주", "신규수주"}
    investment_labels = {"신규투자", "투자확대", "설비투자", "인수합병", "지분인수"}

    sentences = []
    counterparty = str(detail.get("counterparty") or "").strip()
    amount = str(detail.get("amount") or "").strip()
    regions = [
        str(value or "").strip()
        for value in (detail.get("region") or [])
        if str(value or "").strip()
    ]
    key_numbers = [
        str(value or "").strip()
        for value in (detail.get("key_numbers") or [])
        if str(value or "").strip()
    ]

    if label_set & contract_labels:
        if counterparty:
            particle = _korean_particle(counterparty, "과", "와")
            sentences.append(f"기사에는 {counterparty}{particle}의 계약이 언급돼 있어.")
        if amount:
            sentences.append(f"계약 관련 금액은 {amount}로 제시돼 있어.")
        if key_numbers:
            sentences.append(f"추가로 {', '.join(dict.fromkeys(key_numbers[:2]))}라는 수치도 나와 있어.")
    elif label_set & investment_labels:
        if counterparty:
            sentences.append(f"관련 기업으로 {counterparty}가 언급돼 있어.")
        if amount:
            sentences.append(f"투자 관련 금액은 {amount}로 제시돼 있어.")
        if regions:
            sentences.append(f"관련 지역으로 {regions[0]}이 언급돼 있어.")
    elif label_set & {"해외진출", "시장진출", "사업확대"}:
        if regions:
            sentences.append(f"관련 지역으로 {regions[0]}이 언급돼 있어.")
        if amount:
            sentences.append(f"기사에 나온 관련 금액은 {amount}야.")

    return "\n".join(sentences[:3])


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


def _compose_brief_summary(headline, remaining, summary_index=0):
    """Show each grounded fact as its own sentence, not an invented relationship."""
    facts = [str(headline or "").strip()]
    facts.extend(str(value or "").strip() for value in remaining[:2])
    facts = [value for value in facts if value]
    if len(facts) < 2:
        return ""

    uncertainty_endings = (
        "기대", "전망", "예상", "추정", "관측", "가능성", "검토", "계획", "예정",
    )
    sentences = []
    for index, fact in enumerate(facts[:3]):
        if any(char.isdigit() for char in fact):
            certainty = next((value for value in uncertainty_endings if fact.endswith(value)), "")
            base = fact[:-len(certainty)].strip() if certainty else fact
            if certainty in {"기대", "가능성"}:
                particle = _korean_particle(certainty, "이", "가")
                sentences.append(f"{base}에 대한 {certainty}{particle} 기사에 언급돼 있어.")
            elif certainty in {"전망", "예상", "추정", "관측"}:
                particle = _korean_particle(base, "을", "를")
                sentences.append(f"기사에서는 {base}{particle} {certainty}한 내용을 다뤘어.")
            elif certainty:
                sentences.append(f"기사에는 {base} 관련 {certainty}이 언급돼 있어.")
            elif index == 0:
                sentences.append(f"기사에는 {fact}라는 수치가 제시돼 있어.")
            else:
                sentences.append(f"{fact}라는 수치도 별도로 언급돼 있어.")
        elif fact == "역대급 실적":
            sentences.append("실적에 대해 '역대급'이라는 평가도 함께 언급돼 있어.")
        elif index == 0:
            sentences.append(f"기사에서는 {fact} 관련 내용을 다루고 있어.")
        else:
            sentences.append(f"{fact} 관련 내용도 함께 언급돼 있어.")
    return "\n".join(sentences)


def _brief_text(labels, themes, issues, stock_names, fallback_stock, summary_index=0):
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

    summary = _compose_brief_summary(headline, remaining, summary_index=summary_index)
    display_headline = headline if headline.endswith("이슈") else f"{headline} 이슈"
    return display_headline, summary
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
            summary_index=len(briefs),
        )
        concrete_subject = _concrete_event_subject(item, labels, stock_names)
        if concrete_subject and labels and labels[0] == "제품공개":
            headline = f"{concrete_subject} 제품 공개 이슈"
            if summary:
                summary = summary.replace("제품 공개", f"{concrete_subject} 제품 공개", 1)
            else:
                summary = f"{concrete_subject} 제품 공개 관련 내용을 확인했어."

        structured_summary = _structured_detail_summary(
            item,
            labels,
            summary_index=len(briefs),
        )
        if structured_summary:
            summary = structured_summary

        if not headline or not summary:
            continue

        # Keep the rich numeric facts in summary/internal data, but present the
        # central title and hashtags as stable topic labels rather than exposing
        # extractor-shaped values such as 영업이익107조4000억원.
        primary_display = _central_simple_numeric_label(labels[0] if labels else "")
        display_headline = f"{primary_display} 이슈" if primary_display else headline
        if concrete_subject and labels and labels[0] == "제품공개":
            display_headline = headline
        display_tags = _central_display_tags(labels)
        if concrete_subject and concrete_subject not in display_tags:
            display_tags = [concrete_subject, *display_tags][:3]

        briefs.append({
            "time": str(item.get("storyboard_time") or "").strip(),
            "reaction_at": str(item.get("published_at") or "").strip(),
            "headline": display_headline,
            "summary": summary,
            "tags": display_tags,
            "stock_names": stock_names[:4],
        })
        if len(briefs) >= max(1, int(limit)):
            break
    return briefs
