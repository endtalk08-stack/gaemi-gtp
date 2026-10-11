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
    """Turn checked article-detail facts into an issue explanation, not a reading report."""
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

    if label_set & contract_labels:
        if counterparty:
            particle = _korean_particle(counterparty, "과", "와")
            sentences.append(f"{counterparty}{particle}의 계약이 핵심이야.")
        if amount:
            sentences.append(f"계약 금액은 {amount}로 정리돼 있어.")
    elif label_set & investment_labels:
        if counterparty:
            sentences.append(f"{counterparty}가 투자에 연관돼 있어.")
        if amount:
            sentences.append(f"투자 관련 금액은 {amount}야.")
        if regions:
            sentences.append(f"관련 지역은 {regions[0]}이야.")
    elif label_set & {"해외진출", "시장진출", "사업확대"}:
        if regions:
            sentences.append(f"{regions[0]} 시장 진출·사업 확대가 핵심이야.")
        if amount:
            sentences.append(f"관련 금액은 {amount}야.")

    # key_numbers can be an unrelated percentage or measurement. Do not
    # display numbers unless their business meaning is explicitly known.
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


_ISSUE_FACT_SENTENCES = {
    "원화 강세": "원화 강세 흐름이 나타났어.",
    "원화 약세": "원화 약세 흐름이 나타났어.",
    "외국인 매도": "외국인 매도 움직임이 나타났어.",
    "역대급 실적": "실적이 역대급이라는 평가가 나왔어.",
    "자사주 소각": "자사주 소각도 주요 이슈야.",
    "자사주 매입": "자사주 매입도 주요 이슈야.",
    "공급 계약": "공급 계약이 주요 이슈야.",
    "계약 체결": "계약 체결이 주요 이슈야.",
}


def _compose_brief_summary(headline, remaining, summary_index=0):
    """Describe the issue itself, with no references to reading an article."""
    facts = [str(headline or "").strip()]
    facts.extend(str(value or "").strip() for value in remaining[:2])
    facts = [value for value in facts if value]
    if len(facts) < 2:
        return ""

    uncertainty_endings = (
        "기대", "전망", "예상", "추정", "관측", "가능성", "검토", "계획", "예정",
    )
    sentences = []
    for fact in facts[:3]:
        if fact in _ISSUE_FACT_SENTENCES:
            sentences.append(_ISSUE_FACT_SENTENCES[fact])
            continue
        if any(char.isdigit() for char in fact):
            certainty = next((value for value in uncertainty_endings if fact.endswith(value)), "")
            base = fact[:-len(certainty)].strip() if certainty else fact
            if certainty:
                particle = _korean_particle(certainty, "이", "가")
                sentences.append(f"{base} {certainty}{particle} 나왔어.")
            else:
                sentences.append(f"{fact} 수치가 나왔어. 확정치나 비교 기준은 추가 확인이 필요해.")
        else:
            particle = _korean_particle(fact, "이", "가")
            sentences.append(f"{fact}{particle} 주요 이슈야.")
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
_METRIC_AMOUNT_RE = re.compile(
    r"(?P<metric>영업\s*이익|영업익|매출액|매출|순이익)"
    r"[^\n,;:]{0,42}?"
    r"(?P<value>\d+(?:\.\d+)?\s*조(?:\s*\d+(?:,\d+)*\s*억)?\s*원?"
    r"|\d+(?:,\d+)*\s*억\s*원)",
    re.IGNORECASE,
)
_METRIC_RATE_RE = re.compile(
    r"(?P<metric>영업\s*이익|영업익|매출액|매출|순이익)"
    r"[^\n,;:]{0,48}?"
    r"(?P<value>\d+(?:\.\d+)?\s*%)\s*(?P<direction>증가|감소|상승|하락)",
    re.IGNORECASE,
)
_RATIO_RE = re.compile(
    r"(?:최근|전년도|지난해|직전)?\s*매출(?:액)?\s*(?:대비|의)\s*"
    r"(?P<percent>\d+(?:\.\d+)?\s*%)",
    re.IGNORECASE,
)
_PERIOD_RE = re.compile(
    r"20\d{2}년(?:\s*[1-4]분기)?|올해|내년|지난해|"
    r"(?:올|지난)\s*[1-4]분기|[1-4]분기|상반기|하반기|연간"
)


def _issue_evidence_summary(item, stock_name, labels):
    """Write factual issue details from *existing* selected-article evidence.

    Raw article text is ephemeral and is not included in the returned brief.
    Never assign an unexplained percentage to a contract or claim causality.
    """
    title = str(item.get("title") or "").strip()
    description = str(item.get("description") or "").strip()
    detail_text = str(item.get("_brief_detail_text") or "").strip()
    sources = [(title, False), (description, False), (detail_text, True)]
    sources = [(value, is_body) for value, is_body in sources if value]
    if not sources:
        return ""

    raw_labels = {str(v or "").strip().lstrip("#") for v in labels or []}
    subject = str(stock_name or "").strip()
    sentences = []
    seen_metrics = set()
    profit_related = any(
        label.startswith(("영업이익", "매출", "순이익")) for label in raw_labels
    )

    if profit_related:
        # Prioritize the headline's precise numerical context, then its snippet,
        # and consult the selected body only when the shorter evidence lacks it.
        for pattern in (_METRIC_AMOUNT_RE, _METRIC_RATE_RE):
            found = False
            for source, is_body in sources:
                for match in pattern.finditer(source):
                    metric = re.sub(r"\s+", "", match.group("metric"))
                    metric = "영업이익" if metric == "영업익" else metric
                    if not any(label.startswith(metric) for label in raw_labels):
                        continue
                    value = re.sub(r"\s+", "", match.group("value"))
                    # An article can mention multiple companies' earnings.
                    # Match the reported figure to the stock-owned selected
                    # numeric keyword, not merely the metric name.
                    figure_digits = re.sub(r"\D", "", value)
                    matching_labels = [
                        label for label in raw_labels if label.startswith(metric)
                    ]
                    numeric_labels = [
                        re.sub(r"\D", "", label[len(metric):])
                        for label in matching_labels
                        if re.search(r"\d", label[len(metric):])
                    ]
                    if numeric_labels and figure_digits not in numeric_labels:
                        continue
                    unique_key = (metric, "rate" if pattern is _METRIC_RATE_RE else "amount")
                    if unique_key in seen_metrics:
                        continue
                    # Body text may mention other companies. Require this stock
                    # near the figure before using the lower-priority full body.
                    vicinity = source[max(0, match.start() - 130):match.end() + 45]
                    if is_body and subject and subject not in vicinity:
                        continue
                    # Restrict qualifiers/periods to the nearby clause.
                    before = source[max(0, match.start() - 75):match.start()]
                    period_context = before[-55:] + match.group(0)
                    period_match = list(_PERIOD_RE.finditer(period_context))
                    period = period_match[-1].group(0) if period_match else ""
                    period_text = f" {period}" if period else ""
                    local = source[max(0, match.start() - 40):match.end() + 28]
                    expectation = bool(re.search(r"전망|예상|추정|기대|관측|컨센서스", local))
                    tentative = bool(re.search(r"잠정|가결산", local))
                    if pattern is _METRIC_RATE_RE:
                        direction = match.group("direction")
                        comparison = re.findall(
                            r"전년\s*동기\s*대비|전년\s*대비|지난해\s*대비|"
                            r"전분기\s*대비|직전\s*분기\s*대비",
                            before[-55:] + match.group(0),
                        )
                        if comparison:
                            comparison_text = re.sub(r"\s*대비$", "", comparison[-1]).strip()
                            statement = f"{subject}의{period_text} {metric}이 {comparison_text}보다 {value} {direction}했어."
                        else:
                            statement = f"{subject}의{period_text} {metric} {value} {direction} 흐름이야. 비교 기준은 확인되지 않았어."
                    elif expectation:
                        statement = f"{subject}의{period_text} {metric}이 {value} 수준으로 전망됐어."
                    elif tentative:
                        statement = f"{subject}의{period_text} {metric} 잠정치가 {value}로 나왔어."
                    else:
                        statement = f"{subject}의{period_text} {metric}으로 {value}이 제시됐어. 확정 실적인지는 확인이 필요해."
                    sentences.append(re.sub(r"\s+", " ", statement).strip())
                    seen_metrics.add(unique_key)
                    found = True
                    break
                if found:
                    break
            if len(sentences) >= 2:
                break

    is_contract = any(
        "계약" in label or "수주" in label or "단일판매" in label
        for label in raw_labels
    )
    if is_contract:
        detail = item.get("detail_facts") or {}
        counterparty = str(detail.get("counterparty") or "").strip()
        amount = str(detail.get("amount") or "").strip()
        if counterparty:
            particle = _korean_particle(counterparty, "과", "와")
            sentences.insert(0, f"{subject}가 {counterparty}{particle} 공급 계약을 맺었어.")
        elif any(re.search(r"계약.{0,4}체결|계약을?\s*맺", src)
                 for src, is_body in sources if not is_body):
            sentences.insert(0, f"{subject}가 공급 계약을 체결했어.")
        elif any(re.search(r"공급\s*계약|단일판매", src)
                 for src, is_body in sources if not is_body):
            sentences.insert(0, f"{subject}의 공급 계약이 핵심 이슈야.")
        if amount and counterparty:
            sentences.append(f"계약 규모는 {amount}로 알려졌어.")
        for source, _ in (part for part in sources if not part[1]):
            share = _RATIO_RE.search(source)
            if share and is_contract:
                sentences.append(f"계약 규모는 매출액 대비 {share.group('percent').strip()} 수준이야.")
                break
        # When the body is the only place with the ratio, require its contract
        # context instead of borrowing an unrelated company's percentage.
        if detail_text and not any("매출액 대비" in v for v in sentences):
            for match in _RATIO_RE.finditer(detail_text):
                nearby = detail_text[max(0, match.start() - 140):match.end() + 40]
                if subject in nearby and re.search(r"계약|수주|단일판매", nearby):
                    sentences.append(
                        f"계약 규모는 매출액 대비 {match.group('percent').strip()} 수준이야."
                    )
                    break

    # A separate flow must be corroborated by its original source, not simply
    # placed next to profit figures because keyword extraction returned it.
    if any("외국인매도" in label for label in raw_labels) and any(
        re.search(r"외국인[^.\n]{0,16}(?:순매도|매도세|매도)", source)
        for source, is_body in sources if not is_body
    ):
        sentences.append("외국인 매도세도 나타났어.")

    return "\n".join(dict.fromkeys(sentences[:3]))



# The three existing hashtags define which facts belong in the central brief.
# Select short, evidence-backed source passages; never manufacture "issue" copy.
_HASHTAG_EVIDENCE_RULES = {
    "외국인매도": r"외국인.{0,24}(?:순매도|매도|매도세|매물|팔아|팔았)",
    "외국인매수": r"외국인.{0,24}(?:순매수|매수|사들)",
    "자사주매입": r"(?:자사주|자기주식).{0,24}(?:매입|취득|매수)|(?:매입|취득).{0,12}(?:자사주|자기주식)",
    "자사주소각": r"(?:자사주|자기주식).{0,20}소각|소각.{0,15}(?:자사주|자기주식)",
    "매출발표": r"매출(?:액)?.{0,32}(?:발표|공개|공시|잠정|\d)|(?:발표|잠정).{0,25}매출",
    "실적발표": r"(?:실적|영업이익|매출).{0,35}(?:발표|잠정|공개|공시)|(?:발표|잠정).{0,25}실적",
    "잠정실적발표": r"(?:잠정|가결산).{0,35}(?:실적|영업이익|매출)|(?:실적|영업이익|매출).{0,25}잠정",
    "호실적": r"호실적|(?:실적|매출|영업이익|순이익).{0,45}(?:최대|상회|증가|급증|흑자|개선|늘었)",
    "역대급실적": r"(?:실적|영업이익|매출).{0,40}(?:역대|사상|최대)|역대급.{0,15}실적",
    "계약체결": r"(?:계약|수주).{0,22}(?:체결|맺|확정)|공급\s*계약|단일판매",
    "공급계약": r"공급\s*계약|계약.{0,25}공급|단일판매",
    "단일판매": r"단일판매|(?:계약\s*금액|공급\s*계약).{0,45}(?:매출액|\d)|매출액\s*대비\s*\d+(?:\.\d+)?\s*%",
    "원화강세": r"원화.{0,18}(?:강세|가치\s*상승)|원/달러.{0,18}하락",
    "원화약세": r"원화.{0,18}(?:약세|가치\s*하락)|원/달러.{0,18}상승",
    "HBM": r"HBM|고대역폭\s*메모리",
    "AI메모리": r"(?:AI.{0,20}메모리|메모리.{0,20}AI|HBM)",
}


_ARTICLE_LIST_MARKERS = (
    "관련 기사", "많이 본 뉴스", "추천 기사", "실시간 인기", "주요 뉴스",
    "랭킹 뉴스", "연관 뉴스", "최신 뉴스", "전체 기사", "함께 읽",
)


def _is_article_listing(sentence):
    """Reject sidebar headlines / navigation fragments mistaken for article prose."""
    text = str(sentence or "").strip()
    if not text:
        return True
    if any(marker in text for marker in _ARTICLE_LIST_MARKERS):
        return True
    if re.search(r"^\s*\d{1,4}\s*[-–]\s+", text):
        return True
    # A cluster of news headlines, not an individual factual sentence.
    if len(re.findall(r"\s[-–]\s", text)) >= 2:
        return True
    if re.search(r"(?:뉴스|증시|주가|관련주).{0,20}(?:속보|더보기|기사\s*목록)", text):
        return True
    return False


def _issue_sentences(value):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return []
    # Selected detail bodies have already been flattened into plain text.
    pieces = re.split(r"(?<=[.!?。])\s+|[\n]+|\s*[;；]\s*", text)
    result = []
    for part in pieces:
        cleaned = part.strip(" \t-•▶■“”\"'")
        if len(cleaned) >= 12 and not _is_article_listing(cleaned):
            result.append(cleaned)
    return result


def _issue_tag_matches(label, sentence):
    tag = str(label or "").strip().lstrip("#")
    if not tag:
        return False
    rule = _HASHTAG_EVIDENCE_RULES.get(tag)
    if rule:
        if not re.search(rule, sentence, re.IGNORECASE):
            return False
    else:
        metric = re.match(r"^(영업이익률|영업이익|매출|순이익)(\d+)", tag)
        if metric:
            metric_rule = re.escape(metric.group(1)).replace("영업이익", r"영업\s*이익")
            if not re.search(metric_rule, sentence):
                return False
        else:
            compact_tag = re.sub(r"[^0-9a-z가-힣]", "", tag.lower())
            compact_text = re.sub(r"[^0-9a-z가-힣]", "", sentence.lower())
            if len(compact_tag) < 3 or compact_tag not in compact_text:
                return False
    number = re.search(r"\d+(?:\.\d+)?", tag)
    if number:
        wanted = re.sub(r"\D", "", number.group())
        available = [
            re.sub(r"\D", "", value)
            for value in re.findall(r"\d+(?:[,.]\d+)*", sentence)
        ]
        if wanted not in available:
            return False
    return True


def _issue_brief_actor(sentence):
    match = re.search(
        r"(?:^|[.!?]\s+)(?P<name>[가-힣A-Za-z][가-힣A-Za-z0-9·&.-]{1,25})(?:은|는|이|가)\s+",
        sentence,
    )
    return match.group("name") if match else ""


def _issue_brief_fact(sentence, tag, stock_name):
    """Compose only the business fact matched by this hashtag, not source prose."""
    sentence = str(sentence or "").strip()
    actor = _issue_brief_actor(sentence) or stock_name
    contract_tags = {"계약체결", "공급계약", "단일판매", "장기공급계약"}
    if tag in contract_tags:
        contract = re.search(
            r"(?P<actor>[가-힣A-Za-z][가-힣A-Za-z0-9·&.-]{1,25})(?:은|는|이|가)\s+"
            r"(?P<partner>[가-힣A-Za-z][가-힣A-Za-z0-9·&. -]{1,45}?)(?:와|과)\s+"
            r"(?P<scope>.{4,100}?)\s*계약(?:을)?\s*(?:체결|맺|수주)",
            sentence,
        )
        if contract:
            company, partner, scope = (
                contract.group(field).strip()
                for field in ("actor", "partner", "scope")
            )
            scope = re.sub(r"(?:에\s*관한|관련)\s*$", "", scope).strip()
            if len(scope) >= 4:
                return f"{company} → {partner}: {scope} 계약 체결."
        # The selected stock can be the buyer, not the contractor. An isolated
        # company mention must never become "삼성전자가 계약을 체결했어".
        if (
            actor
            and re.search(rf"{re.escape(actor)}(?:은|는|이|가)\s", sentence)
            and re.search(r"계약.{0,16}체결|공급\s*계약", sentence)
        ):
            return f"{actor}: 공급 계약 체결."
        return ""

    if tag == "외국인매도":
        if not re.search(r"외국인.{0,24}(?:순매도|매도|매도세)", sentence):
            return ""
        amount = re.search(
            r"외국인.{0,32}?(?P<amt>\d[\d,.]*(?:억|조)\s*원).{0,15}(?:순매도|매도)",
            sentence,
        )
        if amount:
            return f"외국인: {stock_name} {amount.group('amt')} 순매도."
        if re.search(r"사상\s*(?:최고|최대).{0,20}분기\s*실적", sentence):
            return f"{stock_name}: 사상 최고 분기 실적에도 외국인 매도세 지속."
        if re.search(r"이어지|지속|연속", sentence):
            return f"{stock_name}: 외국인 매도세 지속."
        if "확대" in sentence:
            return f"{stock_name}: 외국인 매도세 확대."
        return ""

    if tag == "자사주매입":
        if not re.search(
            r"자사주.{0,20}(?:매입|취득)|자기주식.{0,20}(?:매입|취득)",
            sentence,
        ):
            return ""
        joint = re.search(
            r"(?P<actors>[가-힣A-Za-z0-9·]+(?:와|과|·)\s*[가-힣A-Za-z0-9·]+)의?\s*자사주",
            sentence,
        )
        company = joint.group("actors") if joint else actor
        company = re.sub(r"와|과", "·", company).replace(" ", "").removesuffix("의")
        if re.search(r"막바지|마무리|종료\s*단계", sentence):
            ending = ", 수급 공백 우려." if "수급 공백" in sentence else "."
            return f"{company}: 자사주 매입 마무리 단계{ending}"
        amount = re.search(
            r"(?P<amt>\d[\d,.]*(?:조|억)\s*원).{0,20}자사주\s*매입"
            r"|자사주.{0,20}(?P<amt2>\d[\d,.]*(?:조|억)\s*원)",
            sentence,
        )
        if amount:
            return f"{company}: 자사주 매입 규모 {amount.group('amt') or amount.group('amt2')}."
        return ""

    earning_tags = {"호실적", "실적발표", "매출발표", "잠정실적발표", "사상최대실적"}
    if tag in earning_tags or tag.startswith(("영업이익", "매출", "순이익")):
        metric = re.search(
            r"(?P<metric>매출(?:액)?|영업\s*이익|순이익).{0,25}?"
            r"(?P<amt>\d[\d,.]*(?:조|억)\s*원)",
            sentence,
        )
        period = re.search(
            r"(?:20\d{2}년\s*)?[1-4]분기|상반기|하반기|연간|올해|지난해",
            sentence,
        )
        period_text = f"{period.group()} " if period else ""
        if metric:
            certainty = (
                "잠정" if "잠정" in sentence
                else "전망" if re.search(r"전망|예상|추정", sentence)
                else ""
            )
            metric_name = re.sub(r"\s+", "", metric.group("metric"))
            status = f" ({certainty})" if certainty else ""
            return f"{actor}: {period_text}{metric_name} {metric.group('amt')}{status}."
        rate = re.search(
            r"(?P<metric>매출(?:액)?|영업\s*이익|순이익).{0,42}?"
            r"(?P<rate>\d+(?:\.\d+)?\s*%).{0,9}?"
            r"(?P<direction>증가|감소|상승|하락|늘었)",
            sentence,
        )
        if rate:
            basis = (
                "전년 동기 대비 " if re.search(r"전년\s*동기", sentence)
                else "전년 대비 " if "전년" in sentence else ""
            )
            metric_name = re.sub(r"\s+", "", rate.group("metric"))
            return (
                f"{actor}: {period_text}{metric_name} {basis}"
                f"{rate.group('rate').strip()} {rate.group('direction')}."
            )
        if re.search(r"사상\s*(?:최고|최대).{0,8}분기\s*실적", sentence):
            return f"{actor}: 사상 최고 수준의 분기 실적."
    return ""


def _issue_contract_amount(sentences):
    for sentence in sentences:
        match = re.search(
            r"계약\s*(?:금액|대금|규모|액)\s*(?:은|이|:|으로)?\s*"
            r"(?P<value>\d[\d,]*(?:조|억|만)\s*\d*[\d,]*(?:억|만)?\s*원)",
            sentence,
        )
        if match:
            vat = " (부가세 별도)" if re.search(
                r"부가(?:가치)?세.{0,18}(?:포함되지|제외|별도)", sentence
            ) else ""
            return f"계약금액: {match.group('value')}{vat}."
    return ""


def _issue_contract_ratio(sentences):
    for sentence in sentences:
        match = re.search(
            r"(?:최근\s*)?매출액?\s*대비\s*(\d+(?:\.\d+)?\s*%)",
            sentence,
        )
        if match:
            return f"계약 규모: 매출액 대비 {match.group(1).strip()}."
    return ""


def _hashtag_core_summary(item, stock_name, labels):
    """Rewrite grounded hashtag facts as our own concise briefing, without AI."""
    sources = [
        (str(item.get("_brief_detail_text") or ""), 3),
        (str(item.get("description") or ""), 2),
        (str(item.get("title") or ""), 1),
    ]
    if not any(source for source, _ in sources):
        return ""
    other_stocks = [
        str(name).strip()
        for name in item.get("stock_entities") or []
        if str(name).strip() and str(name).strip() != stock_name
    ]
    chosen = []
    for label in labels[:3]:
        choices = []
        for source, priority in sources:
            for sentence in _issue_sentences(source):
                if not _issue_tag_matches(label, sentence):
                    continue
                if any(name in sentence for name in other_stocks) and stock_name not in sentence:
                    continue
                brief = _issue_brief_fact(sentence, label, stock_name)
                if not brief:
                    continue
                specific = bool(re.search(r"\d|사상|막바지|수급 공백", brief))
                score = priority * 2 + (3 if specific else 0) + len(brief) / 200
                choices.append((score, brief))
        choices.sort(key=lambda value: value[0], reverse=True)
        if choices and choices[0][1] not in chosen:
            chosen.append(choices[0][1])

    if any(label in {"계약체결", "공급계약", "단일판매", "장기공급계약"} for label in labels):
        passages = [
            sentence
            for source, _ in sources
            for sentence in _issue_sentences(source)
        ]
        for detail in (_issue_contract_amount(passages), _issue_contract_ratio(passages)):
            if detail and detail not in chosen:
                chosen.append(detail)
    return "\n".join(chosen[:3])


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
                summary = f"{concrete_subject} 제품 공개가 주요 이슈야."

        hashtag_summary = _hashtag_core_summary(item, stock_name, labels)
        evidence_summary = _issue_evidence_summary(item, stock_name, labels)
        structured_summary = _structured_detail_summary(
            item,
            labels,
            summary_index=len(briefs),
        )
        if hashtag_summary:
            summary = hashtag_summary
        elif item.get("title") or item.get("description") or item.get("_brief_detail_text"):
            # Do not fall back to "호실적이 주요 이슈야" when no factual
            # passage exists for the chosen hashtags.
            summary = "해시태그와 연결되는 구체적인 내용은 확인되지 않았어."
        elif evidence_summary:
            summary = evidence_summary
        elif structured_summary:
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
