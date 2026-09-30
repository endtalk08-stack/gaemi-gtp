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
    for label, patterns in DISCLOSURE_KEYWORD_RULES:
        if any(str(pattern).lower() in text for pattern in patterns):
            keywords.append(label)

    return keywords

def score_disclosure(item):
    result = dict(item) if isinstance(item, dict) else {}
    result["keywords"] = extract_disclosure_keywords(result)
    return result

def score_disclosures(items):
    return [score_disclosure(item) for item in (items or [])]
