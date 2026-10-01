# gaemiGTP - 공시 전용 키워드 분류
# 현재 확보된 공시 제목/설명/유형/거래 정보만 사용한다.
# 공시 본문 수집은 다음 단계에서 추가한다.

DISCLOSURE_KEYWORD_RULES = [
    ("자사주", ["자기주식취득", "자기주식 취득", "자기주식처분", "자기주식 처분", "자사주"]),
    ("주주환원", ["주주환원", "주주가치"]),
    ("배당", ["배당"]),
    ("수주", ["수주", "단일판매", "공급계약", "판매ㆍ공급계약", "판매·공급계약"]),
    ("실적발표", ["잠정실적", "실적발표", "실적 발표", "매출액", "영업이익", "2.02"]),
    ("유상증자", ["유상증자"]),
    ("무상증자", ["무상증자"]),
    ("전환사채", ["전환사채", "CB"]),
    ("신주인수권", ["신주인수권부사채", "BW"]),
    ("합병", ["합병"]),
    ("분할", ["분할"]),
    ("인수합병", ["인수", "인수·합병", "인수합병"]),
    ("시설투자", ["시설투자", "시설 투자"]),
    ("임원인사", ["임원", "임원 인사", "5.02"]),
    ("내부자거래", ["내부자 거래", "내부자 매수", "내부자 매도", "내부자 취득"]),
    ("주요계약", ["중요 계약", "중요계약", "계약·협약", "계약 협약", "1.01"]),
    ("소송", ["소송", "소송제기", "소송 제기"]),
    ("특허", ["특허"]),
    ("임상", ["임상"]),
    ("최대주주", ["최대주주", "최대 주주"]),
    ("주요주주", ["주요주주", "주요 주주"]),
    ("영업양수도", ["영업양수", "영업양도", "영업 양수", "영업 양도"]),
]

def extract_disclosure_keywords(item):
    if not isinstance(item, dict):
        return []

    parts = [
        item.get("report", ""),
        item.get("title", ""),
        item.get("description", ""),
        item.get("form", ""),
        item.get("item", ""),
        item.get("items", ""),
        item.get("transaction_kind", ""),
        item.get("transaction_summary", ""),
    ]
    text = " ".join(str(value or "") for value in parts).lower()

    keywords = []
    # SEC Form 4 자체가 내부자 거래 공시이므로 거래 문구가 없어도 분류한다.
    if str(item.get("form", "")).strip().upper() == "4":
        keywords.append("내부자거래")

        transaction_code = str(item.get("transaction_code", "") or "").upper().strip()
        transaction_keyword_map = {
            "P": "매수",
            "S": "매도",
            "A": "주식취득",
            "D": "주식반환",
            "F": "세금·행사가격",
            "M": "옵션행사",
            "G": "주식증여",
            "V": "자발적신고",
            "J": "기타거래",
        }
        if transaction_code in transaction_keyword_map:
            keywords.append(transaction_keyword_map[transaction_code])

        officer_title = str(item.get("officer_title", "") or "").lower()
        if "director" in officer_title or "officer" in officer_title or "이사" in officer_title or "임원" in officer_title:
            keywords.append("임원")
        elif "10% owner" in officer_title:
            keywords.append("10%주주")

    for label, patterns in DISCLOSURE_KEYWORD_RULES:
        if any(str(pattern).lower() in text for pattern in patterns):
            keywords.append(label)

    # 여러 분류 규칙이 같은 키워드를 잡아도 화면에는 한 번만 표시한다.
    unique_keywords = []
    seen = set()
    for keyword in keywords:
        normalized = str(keyword).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_keywords.append(normalized)

    return unique_keywords

def score_disclosure(item):
    result = dict(item) if isinstance(item, dict) else {}
    result["keywords"] = extract_disclosure_keywords(result)
    return result

def score_disclosures(items):
    return [score_disclosure(item) for item in (items or [])]
