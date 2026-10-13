"""Build central issue briefs from the shared stock-news selection.

When a verified article body is supplied, the central summary uses original
source sentences in their original order. The keyword-based legacy format is
kept only for callers that do not supply article bodies.
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
    """Render a few explicit detail facts without copying article prose."""
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

    facts = []
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
            facts.append(f"{counterparty}{particle} 계약")
        if amount:
            facts.append(f"규모 {amount}")
        for value in key_numbers:
            if value not in facts:
                facts.append(value)
            if len(facts) >= 3:
                break
    elif label_set & investment_labels:
        if counterparty:
            facts.append(counterparty)
        if amount:
            facts.append(f"규모 {amount}")
        if regions:
            facts.append(regions[0])
    elif label_set & {"해외진출", "시장진출", "사업확대"}:
        if regions:
            facts.append(regions[0])
        if amount:
            facts.append(f"규모 {amount}")

    facts = list(dict.fromkeys(facts))[:3]
    if not facts:
        return ""

    endings = (
        "관련 내용을 확인했어.",
        "관련 내용도 확인했어.",
        "관련 핵심 내용이야.",
    )
    ending = endings[min(max(int(summary_index or 0), 0), len(endings) - 1)]
    return f"{', '.join(facts)} {ending}"


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
    """Turn grounded labels into one readable, fact-bounded central sentence."""
    extra = [str(value or "").strip() for value in remaining[:2] if str(value or "").strip()]
    if not extra:
        return ""

    endings = (
        "관련 이슈가 있어.",
        "관련 내용을 확인했어.",
        "관련 이슈도 있었어.",
    )
    ending = endings[min(max(int(summary_index or 0), 0), len(endings) - 1)]

    uncertainty_endings = (
        "기대", "전망", "예상", "추정", "관측", "가능성", "검토", "계획", "예정",
    )
    if headline.endswith(uncertainty_endings):
        particle = _korean_particle(headline, "이", "가")
        return f"{headline}{particle} 나오고, {', '.join(extra)} {ending}"

    facts = [headline, *extra]
    joined = _join_brief_facts(facts)
    return f"{joined} {ending}"


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
def _article_excerpt(text, limit=3):
    """Show up to three complete source sentences without rewriting content."""
    content = re.sub(r"[\ufeff\u200b\u2060]", "", str(text or ""))
    content = re.sub(r"\s+", " ", content).strip()
    if not content:
        return ""

    # Publishers sometimes place a heading or other lead-in before the AI
    # disclosure. Remove only unmistakable notices in the opening section,
    # rather than deleting or rewriting any factual article sentence.
    opening, remainder = content[:1200], content[1200:]
    for notice in (
        r"(?<![가-힣A-Za-z0-9])(?:AI|인공지능(?:\s*\(AI\))?)(?:가|이)?\s*"
        r"자동(?:으로)?\s*생성한\s*요약[^.!?]{0,240}[.!?]",
        r"(?<![가-힣A-Za-z0-9])이\s*기사는\s*(?:인공지능(?:\s*\(AI\))?|AI)\s*번역"
        r"(?=[^.!?]{0,350}(?:콘텐츠|원문|전문\s*기자))[^.!?]{0,450}[.!?]",
    ):
        opening = re.sub(notice, " ", opening, count=1, flags=re.IGNORECASE)

    # A location/agency credit may follow those notices rather than lead the
    # extraction. Its "reporter =" marker distinguishes it from actual news.
    opening = re.sub(
        r"(?<![가-힣A-Za-z0-9])(?:\([가-힣]{2,12}\s*=\s*[^()]{2,30}\)"
        r"|\[[가-힣]{2,12}\s*=\s*[^\[\]]{2,30}\])\s*"
        r"(?:(?:[가-힣]{2,4}(?:[·ㆍ,]\s*[가-힣]{2,4})*\s*)?"
        r"(?:기자|특파원)\s*=\s*)?",
        " ",
        opening,
        count=1,
    )
    content = re.sub(r"\s+", " ", opening + remainder).strip()

    # Strip only leading publication notes and bylines, even if notices come
    # before a reporter credit. Keep the actual article sentences unchanged.
    prefix_patterns = (
        r"^(?:AI|인공지능(?:\s*\(AI\))?)(?:가|이)?\s*자동(?:으로)?\s*"
        r"생성한\s*요약[^.!?]{0,240}[.!?]\s*",
        r"^이\s*기사는\s*(?:인공지능(?:\s*\(AI\))?|AI)\s*번역"
        r"(?=[^.!?]{0,350}(?:콘텐츠|원문|전문\s*기자))[^.!?]{0,450}[.!?]\s*",
        r"^(?:\([가-힣]{2,12}\s*=\s*[^()]{2,30}\)"
        r"|\[[가-힣]{2,12}\s*=\s*[^\[\]]{2,30}\])\s*",
        r"^(?:(?:연합뉴스|뉴시스|뉴스1|뉴스핌)\s+)?"
        r"(?:[가-힣]{2,4}(?:[·ㆍ,]\s*[가-힣]{2,4})*\s*)?"
        r"(?:기자|특파원)\s*=\s*",
    )
    for _ in range(5):
        previous = content
        for pattern in prefix_patterns:
            content = re.sub(pattern, "", content, count=1, flags=re.IGNORECASE)
        if content == previous:
            break

    sentences = re.split(r'(?<=[.!?])\s+(?=[가-힣A-Za-z0-9"“‘(])', content)
    selected = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not (10 <= len(sentence) <= 600):
            continue
        if not re.search(r'[.!?]["”’)]?$', sentence):
            continue
        if sentence not in selected:
            selected.append(sentence)
        if len(selected) >= max(1, int(limit)):
            break
    return " ".join(selected)



# Display-only topics: evidence must appear in the actual central excerpt.
# The earlier storyboard keywords still control article selection, not the title.
_BODY_DISPLAY_TOPICS = (
    ("한미동맹", "한미 동맹", r"한\s*[·\-]?\s*미\s*동맹"),
    ("국익외교", "국익 외교", r"국익\s*외교"),
    ("행정수도", "행정수도", r"행정수도|세종\s*이전"),
    ("외교안보", "외교·안보", r"외교\s*[·/및과\s]{1,6}안보"),
    ("AI반도체", "AI 반도체", r"(?:AI|인공지능\s*(?:\(AI\))?)\s*반도체"),
    ("HBM4", "HBM4", r"\bHBM\s*4(?:E)?\b"),
    ("HBM3E", "HBM3E", r"\bHBM\s*3E\b"),
    ("HBM", "HBM", r"\bHBM\b(?!\w)|고대역폭\s*메모리"),
    ("AI서버", "AI 서버", r"(?:AI|인공지능)\s*서버"),
    ("기판공급부족", "기판 공급 부족", r"기판.{0,18}공급\s*부족"),
    ("스마트폰수요둔화", "스마트폰 수요 둔화", r"스마트폰[^.!?\n]{0,80}?수요(?:는|가)?\s*(?:둔화|부진|감소)|스마트폰[^.!?\n]{0,24}?부진"),
    ("반도체공급부족", "반도체 공급 부족", r"반도체.{0,18}공급\s*부족"),
    ("자사주소각", "자사주 소각", r"(?:자사주|자기\s*주식).{0,10}소각"),
    ("자사주매입", "자사주 매입", r"(?:자사주|자기\s*주식).{0,10}(?:매입|취득)"),
    ("전환사채발행", "전환사채 발행", r"전환사채.{0,12}발행"),
    ("공급계약", "공급 계약", r"공급\s*계약|장기\s*공급\s*계약"),
    ("대형수주", "수주", r"(?:신규|대형)\s*수주|수주\s*계약"),
    # An AI-company investment is a concrete event, even without facility or
    # financial-amount wording. Only match investment explicitly stated in text.
    ("AI투자", "AI 기업 투자",
     r"(?:(?:프랑스|미국|중국|한국|일본|영국|독일|대만)\s+)?"
     r"(?:AI|인공지능)(?:\s*\(AI\))?\s*기업(?:들)?\s*"
     r"(?:에\s*대한|에|의)?\s*투자"),
    ("AI투자", "AI 투자",
     r"(?:AI|인공지능)(?:\s*\(AI\))?\s*(?:분야|기술|산업|생태계)?"
     r"(?:에\s*대한|에)?\s*투자"),
    # Country-specific capital investment: grounded in the displayed body.
    ("인도투자", "인도 투자",
     r"인도[^.!?]{0,130}?투자|투자[^.!?]{0,90}?인도"),
    # Shared event families, not company-specific exceptions. These are
    # recognized only when evidenced in the visible article excerpt.
    ("공장증설", "공장 증설",
     r"(?:공장|생산\s*시설|생산\s*라인|신규\s*라인)[^.!?]{0,24}?"
     r"(?:증설|확장|신설|건설|착공)|(?:증설|확장)[^.!?]{0,14}?"
     r"(?:공장|생산\s*시설|생산\s*라인)"),
    ("기업인수", "기업 인수",
     r"(?:기업|회사|지분|사업부)[^.!?]{0,28}?(?:인수|합병)|"
     r"(?:인수|합병)[^.!?]{0,24}?(?:계약|결정|발표|완료)"),
    ("전략제휴", "사업 제휴",
     r"(?:전략적?\s*)?(?:협력|제휴|파트너십|업무\s*협약)"
     r"[^.!?]{0,28}?(?:체결|맺|발표|합의|확대|구축)|"
     r"(?:협약|파트너십)[^.!?]{0,20}?(?:체결|맺)"),
    ("신제품출시", "신제품 출시",
     r"(?:신제품|신형\s*제품|차세대\s*제품|새로운\s*제품)"
     r"[^.!?]{0,36}?(?:출시|공개|발표|선보|판매\s*시작)"),
    ("신규투자", "신규 투자",
     r"(?:\d[\d,]*(?:\.\d+)?\s*(?:조|억)\s*(?:원|달러))"
     r"[^.!?]{0,65}?투자(?:를|에|금|하기로|할\s*계획|한다고|하겠다고|계획|발표|결정|확대|추진)|"
     r"(?:신규|추가|대규모|시설|설비)\s*투자"
     r"[^.!?]{0,30}?(?:계획|발표|결정|확대|추진|단행)"),
    ("경영진교체", "경영진 교체",
     r"(?:대표이사|최고경영자|CEO|사장|회장)[^.!?]{0,35}?"
     r"(?:선임|사임|해임|교체|퇴임|취임)"),
    ("사업진출", "신규 사업 진출",
     r"(?:신규|새로운|해외|글로벌)[^.!?]{0,30}?(?:시장|사업)"
     r"[^.!?]{0,25}?(?:진출|확대)|(?:시장|사업)\s*진출(?:을|에|에\s*나선다)?"),
    ("설비투자", "설비 투자", r"설비\s*투자|생산\s*시설.{0,10}투자"),
    ("해외투자", "해외 투자", r"해외\s*투자|해외.{0,12}투자\s*확대"),
    ("생산확대", "생산 확대", r"생산\s*(?:능력|량)?\s*(?:확대|증설)"),
    ("양산개시", "양산 개시", r"양산\s*(?:시작|개시|출하)"),
    ("실적발표", "실적 발표", r"(?:잠정|분기|연간)\s*실적|실적\s*(?:발표|공시)"),
    ("매출증가", "매출 증가", r"매출.{0,15}(?:증가|성장|상승)"),
    ("영업이익증가", "영업이익 증가", r"영업\s*이익.{0,15}(?:증가|상승|개선)"),
    ("임상시험", "임상시험", r"임상\s*(?:시험|\d상)"),
    ("품목허가", "품목 허가", r"품목\s*허가|FDA\s*승인"),
    ("외국인매도", "외국인 매도", r"외국인.{0,16}(?:순\s*매도|매도세|매도)"),
    ("외국인매수", "외국인 매수", r"외국인.{0,16}(?:순\s*매수|매수세|매수)"),
    ("원화강세", "원화 강세", r"원화\s*강세"),
    ("원화약세", "원화 약세", r"원화\s*약세"),
    ("환율상승", "환율 상승", r"환율.{0,8}(?:상승|급등)"),
    ("환율하락", "환율 하락", r"환율.{0,8}(?:하락|급락)"),
    ("반도체규제", "반도체 규제", r"반도체.{0,18}(?:규제|수출\s*통제)"),
    ("수출규제", "수출 규제", r"수출\s*(?:규제|통제)"),
    ("관세", "관세", r"관세\s*(?:인상|부과|인하|유예|협상)"),
    ("전기차판매", "전기차 판매", r"전기차.{0,16}(?:판매|인도량)"),
    ("반도체업황", "반도체 업황", r"반도체.{0,12}(?:시장|업황|경쟁)"),
)


def _body_title_and_tags(excerpt):
    """Make only display title/tags from evidenced phrases in shown sentences.

    Never reuse upstream selection labels if the visible text does not support
    them. A neutral title and no hashtags are safer than a false topic.
    """
    matches = []
    for tag, heading, pattern in _BODY_DISPLAY_TOPICS:
        found = re.search(pattern, excerpt, flags=re.IGNORECASE)
        if found:
            if tag == "인도투자":
                budget = re.search(
                    r"(?<!\d)(\d[\d,]*(?:\.\d+)?)\s*억\s*달러"
                    r"[^.!?]{0,55}?투자",
                    excerpt,
                )
                if budget:
                    heading = f"인도 {budget.group(1)}억 달러 투자"
            if tag == "AI투자" and heading == "AI 기업 투자":
                country = re.match(
                    r"(프랑스|미국|중국|한국|일본|영국|독일|대만)\s+",
                    found.group(),
                )
                if country:
                    heading = f"{country.group(1)} {heading}"
            matches.append((found.start(), -len(found.group()), found.end(), tag, heading))

    if not matches:
        # Reuse known display labels when their words actually occur in the
        # excerpt; unknown upstream labels must never leak into the headline.
        compact_excerpt = re.sub(r"\s+", "", excerpt).casefold()
        for tag, heading in _CENTRAL_LABEL_TEXT.items():
            phrase = re.sub(r"\s+", "", heading).casefold()
            if len(phrase) < 4:
                continue
            position = compact_excerpt.find(phrase)
            if position >= 0:
                matches.append((position, -len(phrase), position + len(phrase), tag, heading))

    matches.sort()
    tags = []
    used_ranges = []
    main_heading = ""
    for start, _, end, tag, heading in matches:
        # A long phrase and its substring are one topic, not two hashtags.
        if any(start < old_end and end > old_start for old_start, old_end in used_ranges):
            continue
        if tag in tags:
            continue
        if not main_heading:
            main_heading = heading
        tags.append(tag)
        used_ranges.append((start, end))
        if len(tags) == 3:
            break
    return (f"{main_heading} 이슈" if main_heading else "기사 주요 내용"), tags


def central_material_brief_supported(excerpt):
    """Central-only quality gate: a stock mention or price print is not an event.

    Reuse the same article-grounded display topics as the central heading.
    An unsupported story stays in the full news list; it is not filler in chat.
    """
    title, tags = _body_title_and_tags(str(excerpt or ""))
    if not tags or title == "기사 주요 내용":
        return False

    # A daily market quote can carry price/action words that resemble news.
    # Permit it only when its visible body also contains a business/flow event.
    snapshot = sum(bool(re.search(pattern, excerpt, flags=re.IGNORECASE)) for pattern in (
        r"전\s*거래일\s*(?:보다|대비)",
        r"(?:원|달러)에\s*거래(?:됐다|되고|중|를\s*마쳤)",
        r"(?:등락률|등락폭|장중\s*변동폭)",
        r"(?:고가|최고가)[^.!?]{0,65}?(?:저가|최저가)",
        r"\d{1,2}시\s*\d{0,2}분?\s*기준",
    )) >= 2
    if not snapshot:
        return True

    # Price/market descriptions alone are not material central events.
    # Topics backed by business actions, policy or investor flows still pass.
    market_only_tags = {
        "가격상승", "가격하락", "환율상승", "환율하락",
        "원화강세", "원화약세",
    }
    return any(tag not in market_only_tags for tag in tags)


def build_issue_briefs(items, stock_name, limit=3, body_texts=None):
    """Return display-only issue briefs without publisher title/description fields."""
    briefs = []
    for index, item in enumerate(items or []):
        article_summary = ""
        if body_texts is not None:
            body_text = body_texts[index] if index < len(body_texts) else ""
            article_summary = _article_excerpt(body_text)
            if not article_summary:
                continue
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

        if body_texts is not None:
            summary = article_summary
        else:
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

        # Only the central title/hashtags switch to the already-shown excerpt.
        # Do not modify the summary, selected article, ownership or reaction data.
        if body_texts is not None:
            display_headline, display_tags = _body_title_and_tags(article_summary)

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
