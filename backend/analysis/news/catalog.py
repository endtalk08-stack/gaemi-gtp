"""Shared stock/alias catalog for news collection and analysis."""

STOCK_UNIVERSE = {
    "국내": {
        "삼성전자": ["삼성전자", "samsung electronics"],
        "SK하이닉스": ["sk하이닉스", "하이닉스", "sk hynix"],
        "LG에너지솔루션": ["lg에너지솔루션", "lg energy solution"],
        "삼성바이오로직스": ["삼성바이오로직스", "samsung biologics"],
        "현대차": ["현대차", "현대자동차", "hyundai motor"],
        "기아": ["기아", "kia"],
        "한화에어로스페이스": ["한화에어로스페이스", "한화에어로", "hanwha aerospace"],
        "KB금융": ["kb금융", "kb financial"],
        "NAVER": ["naver", "네이버"],
        "두산에너빌리티": ["두산에너빌리티", "doosan enerbility"],
        "셀트리온": ["셀트리온", "celltrion"],
        "삼성SDI": ["삼성sdi", "samsung sdi"],
        "현대모비스": ["현대모비스", "hyundai mobis"],
        "신한지주": ["신한지주", "신한금융", "shinhan financial"],
        "POSCO홀딩스": ["posco홀딩스", "포스코홀딩스", "posco holdings"],
        "LG화학": ["lg화학", "lg chem"],
        "HD현대중공업": ["hd현대중공업", "현대중공업", "hd hyundai heavy industries"],
        "삼성물산": ["삼성물산", "samsung c&t"],
        "카카오": ["카카오", "kakao"],
        "한국전력": ["한국전력", "한전", "korea electric power", "kepco"],
    },
    "미국": {
        "엔비디아": ["NVDA", "엔비디아", "nvidia"],
        "애플": ["AAPL", "애플", "apple"],
        "마이크로소프트": ["MSFT", "마이크로소프트", "microsoft"],
        "아마존": ["AMZN", "아마존", "amazon"],
        "알파벳": ["GOOGL", "GOOG", "알파벳", "구글", "google", "alphabet"],
        "메타": ["META", "메타", "메타 플랫폼스", "meta platforms"],
        "브로드컴": ["AVGO", "브로드컴", "broadcom"],
        "테슬라": ["TSLA", "테슬라", "tesla"],
        "버크셔 해서웨이": ["BRK.B", "BRK.A", "버크셔 해서웨이", "버크셔", "berkshire hathaway", "berkshire"],
        "일라이 릴리": ["LLY", "일라이 릴리", "릴리", "eli lilly"],
        "AMD": ["AMD", "에이엠디", "어드밴스드 마이크로 디바이시스", "advanced micro devices"],
        "마이크론 테크놀로지": ["MU", "마이크론", "마이크론 테크놀로지", "micron", "micron technology"],
        "퀄컴": ["QCOM", "퀄컴", "qualcomm"],
        "TSMC": ["TSM", "TSMC", "대만 TSMC", "타이완 반도체", "taiwan semiconductor"],
        "ASML": ["ASML", "에이에스엠엘", "asml holding"],
        "팔란티어": ["PLTR", "팔란티어", "palantir", "palantir technologies"],
        "로빈후드": ["HOOD", "로빈후드", "robinhood", "robinhood markets"],
        "오라클": ["ORCL", "오라클", "oracle"],
        "록히드마틴": ["LMT", "록히드마틴", "록히드 마틴", "lockheed martin"],
        "엑슨모빌": ["XOM", "엑슨모빌", "엑슨 모빌", "exxonmobil", "exxon mobil"],
        "스페이스X": ["SPCX", "스페이스X", "스페이스엑스", "SpaceX", "space exploration technologies"],
        "샌디스크": ["SNDK", "샌디스크", "SanDisk", "sandisk corporation"],
    },
}


from .stock_identity import resolve_us_identity, news_snapshot_names


# Exact Naver US listing labels observed alongside the news catalog names.
# Only these verified spelling variants are mapped. Unknown companies and KR
# names retain their original identity. A supplied ticker must match as well.
_US_NEWS_LISTING_NAMES = {
    "알파벳 Class A": ("알파벳", "GOOGL"),
    "아마존닷컴": ("아마존", "AMZN"),
    "팔란티어 테크놀로지스": ("팔란티어", "PLTR"),
    "NVIDIA": ("엔비디아", "NVDA"),
    "Apple": ("애플", "AAPL"),
    "Microsoft": ("마이크로소프트", "MSFT"),
}


def canonical_us_news_name(name, *, symbol=None):
    """Identify a known US listing's news-company name without altering UI labels.

    A ranking symbol may have Naver's exchange suffix (.O/.N). If it conflicts
    with a known company ticker, return the original name: never cross-join.
    """
    value = str(name or "").strip()
    resolved = resolve_us_identity(value, symbol)
    if resolved["status"] == "verified":
        return resolved["news_name"]
    match = _US_NEWS_LISTING_NAMES.get(value)
    if not match:
        return value
    canonical, expected_ticker = match
    if symbol:
        ticker = str(symbol).strip().upper()
        if ticker.endswith((".O", ".N")):
            ticker = ticker[:-2]
        if ticker != expected_ticker:
            return value
    return canonical
