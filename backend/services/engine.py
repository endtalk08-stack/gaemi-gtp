import yfinance as yf
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import datetime
import os
import re
import math
import io
import html
import zipfile
import urllib.error
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime

from .news import fetch_realtime_news, get_news_ai_candidates
from .market_levels import (
    calculate_volume_profile_levels,
    format_volume_profile,
    format_shares,
    round_krw_tick,
)

FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY', '').strip().strip('\'"')

US_KOREAN_NAMES = {
    'ORCL': '오라클 ORCL',
    'ADBE': '어도비 ADBE',
    'NVDA': '엔비디아 NVDA',
    'MSFT': '마이크로소프트 MSFT',
    'TSLA': '테슬라 TSLA',
    'AAPL': '애플 AAPL',
    'GOOGL': '구글 GOOGL',
    'AMZN': '아마존 AMZN',
    'META': '메타 META',
    'LLY': '일라이릴리 LLY',
    'MU': '마이크론 MU',
    'AMD': 'AMD AMD',
    'AVGO': '브로드컴 AVGO',
    'NFLX': '넷플릭스 NFLX',
    'CRM': '세일즈포스 CRM',
    'COST': '코스트코 COST',
    'NKE': '나이키 NKE',
    'WMT': '월마트 WMT',
    'JPM': 'JP모건 JPM',
    'BAC': '뱅크오브아메리카 BAC',
    'GS': '골드만삭스 GS',
    'MS': '모건스탠리 MS',
    'FDX': '페덱스 FDX',
    'UPS': 'UPS UPS',
    'CTAS': '신타스 CTAS',
    'DRI': '다든 레스토랑 DRI',
    'NVO': '노보노디스크 NVO'
}

TICKERS = {
    '삼성전자': '005930.KS',
    'SK하이닉스': '000660.KS',
    '현대차': '005380.KS',
    '현대자동차': '005380.KS',
    '기아': '000270.KS',
    '셀트리온': '068270.KS',
    '에코프로': '086520.KQ',
    '에코프로비엠': '247540.KQ',
    '알테오젠': '196170.KQ',
    '카카오': '035720.KS',
    '카카오페이': '377300.KS',
    '카카오뱅크': '323410.KS',
    'NAVER': '035420.KS',
    '네이버': '035420.KS',
    'LG에너지솔루션': '373220.KS',
    '삼성바이오로직스': '207940.KS',
    'POSCO홀딩스': '005490.KS',
    '포스코홀딩스': '005490.KS',
    '포스코퓨처엠': '003670.KS',
    '삼성SDI': '006400.KS',
    'LG화학': '051910.KS',
    '한미반도체': '042700.KS',
    '삼천당제약': '000250.KQ',
    '레인보우로보틱스': '277810.KQ',
    '리가켐바이오': '141080.KQ',
    'HLB': '028300.KQ',
    '에이치엘비': '028300.KQ',
    '크래프톤': '259960.KS',
    '신한지주': '055550.KS',
    'KB금융': '105560.KS',
    '두산에너빌리티': '034020.KS',
    '두산로보틱스': '454910.KS',
    '현대모비스': '012330.KS',
    'HD현대중공업': '329180.KS',
    '한화에어로스페이스': '012450.KS',
    '하이브': '352820.KS',
    '한국전력': '015760.KS',
    '엔씨소프트': '036570.KS',
    '유한양행': '000100.KS',
    '루닛': '328130.KQ',
    '엔비디아': 'NVDA',
    '테슬라': 'TSLA',
    '애플': 'AAPL',
    '마이크로소프트': 'MSFT',
    '아마존': 'AMZN',
    '구글': 'GOOGL',
    '오라클': 'ORCL',
    'ORCL': 'ORCL',
    '어도비': 'ADBE',
    'ADBE': 'ADBE',
    '비트코인': 'BTC-USD'
}


US_CIKS = {
    "NVDA": "0001045810",
    "TSLA": "0001318605",
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "AMZN": "0001018724",
    "GOOGL": "0001652044",
    "ORCL": "0001341439",
    "ADBE": "0000796343",
    "META": "0001326801",
    "LLY": "0000059478",
    "NVO": "0000353278",
}

US_FILING_CACHE = {}

# 국내 기업 공식 공시(OpenDART)
# 인증키가 없으면 공시 기능만 건너뛰고 기존 화면/기능은 그대로 동작한다.
OPENDART_API_KEY = (
    os.environ.get("OPENDART_API_KEY", "").strip()
    or os.environ.get("DART_API_KEY", "").strip()
)
DART_CORP_CACHE = {"ts": 0.0, "map": {}}
DART_DISCLOSURE_CACHE = {}
# 같은 종목을 동시에 여러 사용자가 조회해도 DART/SEC 외부 요청이 중복되지 않도록
# 종목별 단일 비행(single-flight) 락을 사용한다. 서로 다른 종목은 동시에 처리한다.
_DART_SINGLEFLIGHT_LOCKS = {}
_SEC_SINGLEFLIGHT_LOCKS = {}
_SINGLEFLIGHT_LOCK_GUARD = threading.Lock()
_DART_CORP_LOCK = threading.Lock()
DART_RECEIPT_TIME_CACHE = {}

def _get_singleflight_lock(lock_map, key):
    with _SINGLEFLIGHT_LOCK_GUARD:
        lock = lock_map.get(key)
        if lock is None:
            lock = threading.Lock()
            lock_map[key] = lock
        return lock


OPTIONS_RESULT_CACHE = {}
OPTIONS_CACHE_TTL = 60


# 실시간 데이터는 아주 짧게, 과거 계산 데이터는 길게 캐시한다.
# 캐시는 정확도를 떨어뜨리는 것이 아니라 같은 순간의 중복 외부 호출을 줄이는 용도다.
KR_QUOTE_CACHE = {}
KR_QUOTE_CACHE_TTL = 5
KR_TREND_CACHE = {}
KR_TREND_CACHE_TTL = 20
KR_VOLUME_PROFILE_CACHE = {}
KR_VOLUME_PROFILE_CACHE_TTL = 600
US_YAHOO_CACHE = {}
US_YAHOO_CACHE_TTL = 15
KR_SEARCH_CACHE = {}
KR_SEARCH_CACHE_TTL = 3600
_ANALYSIS_CACHE_LOCKS = {}


US_MATERIAL_FORMS = {
    "8-K", "10-Q", "10-K", "6-K", "20-F", "424B5",
    "S-3", "S-1", "SC 13D", "SC 13G", "SC 13G/A", "4"
}

def _fetch_dart_corp_map_uncached():
    """OpenDART corpCode.xml에서 stock_code -> corp_code 매핑을 만든다."""
    if not OPENDART_API_KEY:
        return {}

    now = datetime.datetime.now().timestamp()
    if DART_CORP_CACHE["map"] and now - DART_CORP_CACHE["ts"] < 86400:
        return DART_CORP_CACHE["map"]

    try:
        url = (
            "https://opendart.fss.or.kr/api/corpCode.xml"
            f"?crtfc_key={urllib.parse.quote(OPENDART_API_KEY)}"
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = resp.read()

        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            xml_name = next(
                (name for name in zf.namelist() if name.upper().endswith("CORPCODE.XML")),
                None,
            )
            if not xml_name:
                print("[국내 공시] CORPCODE.xml을 찾지 못했습니다.")
                return {}

            xml_bytes = zf.read(xml_name)

        root = ET.fromstring(xml_bytes)
        mapping = {}
        for item in root.findall(".//list"):
            stock_code = (item.findtext("stock_code") or "").strip()
            corp_code = (item.findtext("corp_code") or "").strip()
            if stock_code and corp_code:
                mapping[stock_code] = corp_code

        DART_CORP_CACHE["ts"] = now
        DART_CORP_CACHE["map"] = mapping
        print(f"[국내 공시] DART 기업코드 매핑 완료: {len(mapping)}개")
        return mapping

    except Exception as e:
        print(f"[국내 공시] 기업코드 조회 실패: {type(e).__name__}: {e}")
        return {}


def fetch_dart_corp_map():
    """DART 기업코드 전체맵을 서버 프로세스당 한 번만 갱신한다."""
    if not OPENDART_API_KEY:
        return {}
    now = datetime.datetime.now().timestamp()
    if DART_CORP_CACHE["map"] and now - DART_CORP_CACHE["ts"] < 86400:
        return DART_CORP_CACHE["map"]
    with _DART_CORP_LOCK:
        now = datetime.datetime.now().timestamp()
        if DART_CORP_CACHE["map"] and now - DART_CORP_CACHE["ts"] < 86400:
            return DART_CORP_CACHE["map"]
        return _fetch_dart_corp_map_uncached()


def _dart_report_score(report_name):
    """주가 영향 가능성이 높은 공시를 우선한다."""
    text = str(report_name or "").lower()
    high = [
        "단일판매ㆍ공급계약", "단일판매·공급계약", "공급계약",
        "수주", "자기주식취득", "자기주식 취득", "자기주식처분",
        "유상증자", "무상증자", "전환사채", "신주인수권부사채",
        "교환사채", "합병", "분할", "영업양수", "영업양도",
        "최대주주", "주요주주", "임상", "특허", "소송",
        "잠정실적", "매출액", "영업이익", "배당",
    ]
    medium = ["주요사항보고서", "타법인주식및출자증권", "주식등의대량보유"]
    score = sum(8 for k in high if k in text)
    score += sum(3 for k in medium if k in text)
    return score


def _fetch_dart_receipt_time_uncached(receipt_no):
    """DART 원문 페이지에서 공시 접수시간을 가져온다. 실패하면 빈 문자열을 반환한다."""
    receipt_no = str(receipt_no or "").strip()
    if not receipt_no:
        return ""
    try:
        url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html,*/*"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        patterns = [
            r"접수시간\s*</[^>]+>\s*([^<]+)",
            r"접수시간\s*[:：]\s*([0-9]{1,2}:[0-9]{2})",
            r"접수일자[^0-9]*(?:[0-9]{4}[-./]?[0-9]{2}[-./]?[0-9]{2})[^0-9]*([0-9]{1,2}:[0-9]{2})",
        ]
        for pattern in patterns:
            m = re.search(pattern, html, flags=re.I | re.S)
            if m:
                value = re.sub(r"\s+", " ", m.group(1)).strip()
                tm = re.search(r"([0-9]{1,2}:[0-9]{2})", value)
                if tm:
                    return tm.group(1).zfill(5)
    except Exception:
        pass
    return ""


def _fetch_dart_receipt_time(receipt_no):
    """DART 접수시간은 접수번호별로 캐시해 같은 공시를 반복 조회하지 않는다."""
    receipt_no = str(receipt_no or "").strip()
    if not receipt_no:
        return ""
    now_ts = datetime.datetime.now().timestamp()
    cached = DART_RECEIPT_TIME_CACHE.get(receipt_no)
    if cached and now_ts - cached[0] < 86400:
        return cached[1]
    lock = _get_singleflight_lock(_DART_SINGLEFLIGHT_LOCKS, ("receipt", receipt_no))
    with lock:
        now_ts = datetime.datetime.now().timestamp()
        cached = DART_RECEIPT_TIME_CACHE.get(receipt_no)
        if cached and now_ts - cached[0] < 86400:
            return cached[1]
        value = _fetch_dart_receipt_time_uncached(receipt_no)
        DART_RECEIPT_TIME_CACHE[receipt_no] = (now_ts, value)
        return value


def _fetch_kr_official_disclosures_uncached(stock_code, days=7):
    """OpenDART에서 국내 기업의 최근 공시를 코드로 조회한다."""
    if not OPENDART_API_KEY or not stock_code:
        return []

    stock_code = str(stock_code).strip()
    cache_key = (stock_code, days)
    cached = DART_DISCLOSURE_CACHE.get(cache_key)
    now_ts = datetime.datetime.now().timestamp()
    if cached and now_ts - cached[0] < 300:
        return cached[1]

    corp_map = fetch_dart_corp_map()
    corp_code = corp_map.get(stock_code)
    if not corp_code:
        print(f"[국내 공시] {stock_code} DART 기업코드 없음")
        DART_DISCLOSURE_CACHE[cache_key] = (now_ts, [])
        return []

    end_date = datetime.date.today()
    begin_date = end_date - datetime.timedelta(days=days)

    try:
        params = urllib.parse.urlencode({
            "crtfc_key": OPENDART_API_KEY,
            "corp_code": corp_code,
            "bgn_de": begin_date.strftime("%Y%m%d"),
            "end_de": end_date.strftime("%Y%m%d"),
            "page_no": 1,
            "page_count": 30,
        })
        url = f"https://opendart.fss.or.kr/api/list.json?{params}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        status = str(data.get("status", ""))
        if status not in ("000", ""):
            print(
                f"[국내 공시] {stock_code} DART 응답 "
                f"status={status} message={data.get('message', '')}"
            )
            DART_DISCLOSURE_CACHE[cache_key] = (now_ts, [])
            return []

        # 먼저 목록 API의 가벼운 데이터만으로 상위 3건을 고른다.
        # 접수시간을 얻기 위해 모든 공시의 원문 페이지를 조회하면 최대 30회의
        # 추가 HTTP 요청이 발생하므로, 실제 화면에 보여줄 3건에 대해서만 원문을 읽는다.
        results = []
        for item in data.get("list", []) or []:
            report_name = str(item.get("report_nm", "")).strip()
            receipt_date = str(item.get("rcept_dt", "")).strip()
            receipt_no = str(item.get("rcept_no", "")).strip()
            if not report_name or not receipt_date:
                continue

            results.append({
                # 국내 공시 날짜는 기존 화면과 동일하게 9/9 형태로 유지한다.
                "date": (
                    f"{int(receipt_date[4:6])}/{int(receipt_date[6:8])}"
                    if len(receipt_date) == 8 and receipt_date.isdigit() else receipt_date
                ),
                "report": report_name,
                "receipt_no": receipt_no,
                "time": "",
                "time_zone": "",
                "receipt_datetime": receipt_date,
                "score": _dart_report_score(report_name),
            })

        # 영향도가 높은 공시를 우선하고, 같은 날에는 최신 접수번호를 우선한다.
        results.sort(
            key=lambda x: (x["score"], x["date"], x["receipt_no"]),
            reverse=True,
        )
        results = results[:3]

        # 최종 3건의 DART 접수시간 보강은 서로 독립적이므로 병렬 조회한다.
        # 첫 검색에서 최대 3번의 순차 HTTP 대기를 제거한다.
        receipt_items = list(results)
        with ThreadPoolExecutor(max_workers=min(3, len(receipt_items) or 1)) as receipt_executor:
            receipt_futures = {
                receipt_executor.submit(_fetch_dart_receipt_time, item.get("receipt_no", "")): item
                for item in receipt_items
            }
            for future, item in receipt_futures.items():
                try:
                    receipt_time = future.result()
                except Exception:
                    receipt_time = ""
                item["time"] = receipt_time
                item["time_zone"] = "KST" if receipt_time else ""
                receipt_date_raw = str(item.get("receipt_datetime") or "")[:8]
                item["receipt_datetime"] = (
                    f"{receipt_date_raw} {receipt_time}".strip()
                    if receipt_time and len(receipt_date_raw) == 8
                    else item.get("receipt_datetime", "")
                )

        print(f"[국내 공시] {stock_code} 성공 / 선택={len(results)}")
        DART_DISCLOSURE_CACHE[cache_key] = (now_ts, results)
        return results

    except urllib.error.HTTPError as e:
        print(f"[국내 공시] {stock_code} DART 실패: HTTP {e.code}")
    except Exception as e:
        print(f"[국내 공시] {stock_code} DART 실패: {type(e).__name__}: {e}")

    DART_DISCLOSURE_CACHE[cache_key] = (now_ts, [])
    return []


def fetch_kr_official_disclosures(stock_code, days=7):
    """DART 조회를 종목별로 단일화해 동시 요청 중복을 막는다."""
    if not OPENDART_API_KEY or not stock_code:
        return []
    stock_code = str(stock_code).strip()
    cache_key = (stock_code, days)
    now_ts = datetime.datetime.now().timestamp()
    cached = DART_DISCLOSURE_CACHE.get(cache_key)
    if cached and now_ts - cached[0] < 300:
        return cached[1]
    lock = _get_singleflight_lock(_DART_SINGLEFLIGHT_LOCKS, cache_key)
    with lock:
        now_ts = datetime.datetime.now().timestamp()
        cached = DART_DISCLOSURE_CACHE.get(cache_key)
        if cached and now_ts - cached[0] < 300:
            return cached[1]
        return _fetch_kr_official_disclosures_uncached(stock_code, days)


def format_kr_official_disclosures(stock_code, disclosures=None):
    if disclosures is None:
        disclosures = fetch_kr_official_disclosures(stock_code)
    if not disclosures:
        return ""

    return "\n".join(
        f"📌 {item['date']} · {item['report']}"
        for item in disclosures
    )


def format_us_sec_filing(filing):
    """SEC 공시를 화면용으로 짧고 이해하기 쉽게 표시한다."""
    form = str(filing.get("form") or filing.get("form_type") or "").upper().strip()
    date = str(filing.get("filing_date") or filing.get("date") or "").strip()
    title = str(filing.get("title") or filing.get("description") or "").strip()

    display_date = date
    try:
        display_date = datetime.datetime.strptime(date[:10], "%Y-%m-%d").strftime("%m/%d").lstrip("0").replace("/0", "/")
    except Exception:
        pass

    if form == "4":
        code = str(filing.get("transaction_code") or filing.get("code") or "").upper().strip()
        kind = {
            "P": "내부자 매수",
            "S": "내부자 매도",
            "A": "내부자 취득",
            "D": "회사로 반환",
            "F": "세금·행사가격 지급",
            "M": "옵션·파생상품 행사",
            "G": "주식 증여",
            "V": "자발적 신고",
            "J": "기타 거래",
        }.get(code, "내부자 거래")
        summary = title or str(filing.get("person") or filing.get("reporting_person") or "").strip()
        return f"📌 {display_date} · {kind}\n📰 {summary}".strip()

    if form == "8-K":
        item = str(filing.get("item") or filing.get("items") or "").strip()
        kind = "기업 주요 공시"
        if "1.01" in item:
            kind = "중요 계약·협약"
        elif "2.01" in item:
            kind = "인수·매각"
        elif "2.02" in item:
            kind = "실적 발표"
        elif "5.02" in item:
            kind = "임원 인사"
        elif "8.01" in item:
            kind = "기타 주요 사항"
        summary = title or item or "주요 내용 발표"
        return f"📌 {display_date} · {kind}\n📰 {summary}".strip()

    summary = title or "주요 공시 내용 확인"
    return f"📌 {display_date} · {form or 'SEC 공시'}\n📰 {summary}".strip()




def _tag_value(text, tag_name):
    """SEC 제출 원문에서 XML/SGML 태그의 텍스트 값을 안전하게 추출한다."""
    if not text or not tag_name:
        return ""
    pattern = rf"<(?:[A-Za-z0-9_.-]+:)?{re.escape(tag_name)}\b[^>]*>(.*?)</(?:[A-Za-z0-9_.-]+:)?{re.escape(tag_name)}>"
    match = re.search(pattern, text, flags=re.I | re.S)
    if not match:
        return ""
    value = re.sub(r"<[^>]+>", " ", match.group(1))
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _has_tag_value(text, tag_name):
    """SEC 원문에서 지정 태그가 true/1/Y 등 활성값을 갖는지 확인한다."""
    value = _tag_value(text, tag_name).strip().lower()
    return value in {"1", "true", "yes", "y"}


def _enrich_us_form4_from_submission(filing, ticker_symbol):
    """SEC Form 4 1건을 공식 제출 TXT에서 보강한다. 네트워크 I/O는 호출측에서 병렬화한다."""
    filing_url = str(filing.get("original_document_url") or "").strip()
    accession = str(filing.get("accession") or "").strip()
    if not filing_url or not accession:
        return filing

    try:
        sec_headers = {
            "User-Agent": os.environ.get("SEC_USER_AGENT", "gaemiGTP/1.0"),
            "Accept": "text/html,application/xml,text/xml,*/*",
        }
        clean_accession = accession.replace("-", "")
        cik = str(filing.get("cik") or "").strip()
        submission_txt_url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{int(cik)}/{clean_accession}/{accession}.txt"
        )
        txt_req = urllib.request.Request(submission_txt_url, headers=sec_headers)
        with urllib.request.urlopen(txt_req, timeout=5) as txt_resp:
            submission_text = txt_resp.read().decode("utf-8", errors="ignore")

        filing["person"] = _tag_value(submission_text, "rptOwnerName")
        filing["officer_title"] = _tag_value(submission_text, "officerTitle")
        if not filing["officer_title"]:
            if _has_tag_value(submission_text, "isDirector"):
                filing["officer_title"] = "Director"
            elif _has_tag_value(submission_text, "isOfficer"):
                filing["officer_title"] = "Officer"
            elif _has_tag_value(submission_text, "isTenPercentOwner"):
                filing["officer_title"] = "10% Owner"
            elif _has_tag_value(submission_text, "isOther"):
                filing["officer_title"] = _tag_value(submission_text, "otherText")

        transactions = []
        txn_blocks = re.findall(
            r"<(?:[A-Za-z0-9_.-]+:)?nonDerivativeTransaction\b[^>]*>(.*?)</(?:[A-Za-z0-9_.-]+:)?nonDerivativeTransaction>",
            submission_text, flags=re.I | re.S,
        )
        for block in txn_blocks:
            code = _tag_value(block, "transactionCode").upper()
            shares = _tag_value(block, "transactionShares")
            price = _tag_value(block, "transactionPricePerShare")
            acquired_disposed = _tag_value(block, "transactionAcquiredDisposedCode").upper()
            if code or shares:
                transactions.append({"code": code, "shares": shares, "price": price, "acquired_disposed": acquired_disposed})

        filing["transactions"] = transactions
        if transactions:
            filing["transaction_code"] = transactions[0]["code"]
            filing["shares"] = transactions[0]["shares"]
            filing["price"] = transactions[0]["price"]
            code_labels = {
                "P": "내부자 매수", "S": "내부자 매도", "A": "내부자 취득",
                "D": "회사로 반환", "F": "세금·행사가격 지급", "M": "옵션·파생상품 행사",
                "G": "주식 증여", "V": "자발적 신고", "J": "기타 거래",
            }
            code_counts = {}
            for tx in transactions:
                tx_code = str(tx.get("code") or "").upper().strip()
                if tx_code:
                    code_counts[tx_code] = code_counts.get(tx_code, 0) + 1
            priority = ["P", "S", "A", "G", "F", "M", "D", "C", "J", "V"]
            ordered_codes = sorted(code_counts, key=lambda c: priority.index(c) if c in priority else len(priority))
            if len(ordered_codes) == 1:
                c = ordered_codes[0]
                filing["transaction_kind"] = code_labels.get(c, "내부자 거래")
                filing["transaction_summary"] = f"{filing['transaction_kind']} · {code_counts[c]}건"
            elif ordered_codes:
                filing["transaction_kind"] = code_labels.get(ordered_codes[0], "내부자 거래")
                filing["transaction_summary"] = " · ".join(f"{code_labels.get(c, '내부자 거래')} {code_counts[c]}건" for c in ordered_codes)
            else:
                filing["transaction_kind"] = "내부자 거래"
                filing["transaction_summary"] = "내부자 거래"
            filing["transaction_count"] = len(transactions)
            filing["price_range"] = ""
        else:
            filing["transaction_kind"] = "내부자 거래"
            filing["transaction_summary"] = "내부자 거래"
            filing["transaction_count"] = 0
            filing["price_range"] = ""
        return filing
    except Exception as detail_err:
        print(f"[미국 공시] {ticker_symbol} Form 4 원문 보강 실패: {type(detail_err).__name__}: {detail_err}")
        return filing


def _fetch_us_official_filings_uncached(ticker_symbol, days=7):
    """SEC 공식 제출자료 중 최근 주요 공시를 수집한다. AI/웹검색 없이 코드로만 수집."""
    ticker_symbol = ticker_symbol.upper()
    cik = US_CIKS.get(ticker_symbol)
    cache_key = (ticker_symbol, days)
    cached = US_FILING_CACHE.get(cache_key)
    if cached and (datetime.datetime.now().timestamp() - cached[0] < 300):
        return cached[1]
    if not cik:
        return []

    try:
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": os.environ.get("SEC_USER_AGENT", "gaemiGTP/1.0"),
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        docs = recent.get("primaryDocument", [])
        descriptions = recent.get("primaryDocDescription", [])
        acceptance_datetimes = recent.get("acceptanceDateTime", [])

        today = datetime.date.today()
        results = []

        for i, form in enumerate(forms):
            if form not in US_MATERIAL_FORMS:
                continue
            try:
                filing_date = datetime.datetime.strptime(dates[i], "%Y-%m-%d").date()
            except Exception:
                continue
            if (today - filing_date).days > days:
                continue

            accession = accessions[i] if i < len(accessions) else ""
            document = docs[i] if i < len(docs) else ""
            description = descriptions[i] if i < len(descriptions) else ""
            clean_accession = accession.replace("-", "")
            filing_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{int(cik)}/{clean_accession}/{document}"
                if accession and document else ""
            )

            filing_page_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{int(cik)}/{accession.replace('-', '')}/{accession}-index.htm"
                if accession else filing_url
            )
            acceptance_datetime = acceptance_datetimes[i] if i < len(acceptance_datetimes) else ""
            filing_time = ""
            if acceptance_datetime:
                tm = re.search(r"T(\d{2}:\d{2})", str(acceptance_datetime))
                if tm:
                    filing_time = tm.group(1)

            filing = {
                "date": dates[i],
                "form": form,
                "description": description or "SEC 공식 공시",
                "time": filing_time,
                "acceptance_datetime": acceptance_datetime,
                "url": filing_page_url,
                "original_document_url": filing_url,
                "accession": accession,
                "cik": str(cik),
            }

            # Form 4 원문 보강은 서로 독립적이므로 아래에서 최대 3건을 병렬 처리한다.
            # 기존처럼 Form 4마다 순차 HTTP 요청을 기다리지 않는다.
            if form == "4" and filing_url:
                filing["_needs_form4_enrichment"] = True

            results.append(filing)

            if len(results) >= 3:
                break

        # Form 4 세부 원문 요청은 최대 3건을 병렬로 실행한다.
        enrich_targets = [f for f in results if f.get("_needs_form4_enrichment")]
        if enrich_targets:
            with ThreadPoolExecutor(max_workers=min(3, len(enrich_targets))) as enrich_executor:
                future_map = {
                    enrich_executor.submit(_enrich_us_form4_from_submission, filing, ticker_symbol): filing
                    for filing in enrich_targets
                }
                for future, filing in future_map.items():
                    try:
                        enriched = future.result()
                        filing.update(enriched)
                    except Exception as enrich_err:
                        print(f"[미국 공시] {ticker_symbol} Form 4 병렬 보강 실패: {type(enrich_err).__name__}: {enrich_err}")
                    filing.pop("_needs_form4_enrichment", None)

        US_FILING_CACHE[cache_key] = (datetime.datetime.now().timestamp(), results)
        return results
    except urllib.error.HTTPError as e:
        print(f"[미국 공시] {ticker_symbol} SEC 실패: HTTP {e.code}")
    except Exception as e:
        print(f"[미국 공시] {ticker_symbol} SEC 실패: {type(e).__name__}: {e}")
    US_FILING_CACHE[cache_key] = (datetime.datetime.now().timestamp(), [])
    return []

def fetch_us_official_filings(ticker_symbol, days=7):
    """SEC 조회를 종목별로 단일화해 동시 요청 중복을 막는다."""
    ticker_symbol = str(ticker_symbol or "").upper().strip()
    if not ticker_symbol or ticker_symbol not in US_CIKS:
        return []
    cache_key = (ticker_symbol, days)
    now_ts = datetime.datetime.now().timestamp()
    cached = US_FILING_CACHE.get(cache_key)
    if cached and now_ts - cached[0] < 300:
        return cached[1]
    lock = _get_singleflight_lock(_SEC_SINGLEFLIGHT_LOCKS, cache_key)
    with lock:
        now_ts = datetime.datetime.now().timestamp()
        cached = US_FILING_CACHE.get(cache_key)
        if cached and now_ts - cached[0] < 300:
            return cached[1]
        return _fetch_us_official_filings_uncached(ticker_symbol, days)


def format_us_official_filings(ticker_symbol, filings=None):
    if filings is None:
        filings = fetch_us_official_filings(ticker_symbol)
    if not filings:
        return ""

    lines = []
    code_labels = {
        "P": "내부자 매수",
        "S": "내부자 매도",
        "A": "주식 취득",
        "D": "회사로 반환",
        "F": "세금·행사가격 지급",
        "M": "옵션·파생상품 행사",
        "G": "주식 증여",
        "C": "전환 거래",
        "J": "기타 거래",
        "V": "자발적 신고",
    }

    # 같은 Form 4 안의 여러 거래를 한 블록으로 요약한다.
    # 화면에는 최대 3개의 공시 블록만 표시하고, 개별 거래내역은 내부 데이터로 유지한다.
    for item in filings[:3]:
        date = str(item.get("date", "")).strip()
        try:
            display_date = datetime.datetime.strptime(
                date[:10], "%Y-%m-%d"
            ).strftime("%m/%d").lstrip("0").replace("/0", "/")
        except Exception:
            display_date = date

        form = str(item.get("form", "")).upper().strip()

        if form == "4":
            transactions = item.get("transactions") or []
            person = str(item.get("person", "")).strip()
            officer_title = str(item.get("officer_title", "")).strip()

            # 실제 거래가 여러 건이면 거래코드별 건수를 집계한다.
            code_counts = {}
            prices = []
            for tx in transactions:
                code = str(tx.get("code", "")).upper().strip()
                if not code:
                    continue
                code_counts[code] = code_counts.get(code, 0) + 1

                price = str(tx.get("price", "")).strip().replace(",", "")
                if price:
                    try:
                        price_value = float(price)
                        if price_value > 0:
                            prices.append(price_value)
                    except Exception:
                        pass

            # 거래코드가 없는 구버전/예외 데이터도 기존 fallback으로 처리한다.
            if not code_counts:
                code = str(item.get("transaction_code", "")).upper().strip()
                if code:
                    code_counts[code] = 1

            # 가장 중요한 거래 유형을 앞에 표시한다.
            priority = ["P", "S", "A", "G", "F", "M", "D", "C", "J", "V"]
            ordered_codes = sorted(
                code_counts.keys(),
                key=lambda c: priority.index(c) if c in priority else len(priority)
            )

            if ordered_codes:
                if len(ordered_codes) == 1:
                    code = ordered_codes[0]
                    summary = f"{code_labels.get(code, '내부자 거래')} · {code_counts[code]}건"
                else:
                    summary = " · ".join(
                        f"{code_labels.get(code, '내부자 거래')} {code_counts[code]}건"
                        for code in ordered_codes
                    )
            else:
                summary = "내부자 거래"

            # 미국 SEC 직책은 화면에서 일반 사용자가 이해하기 쉬운 한글로 표시한다.
            title_ko = {
                "DIRECTOR": "이사",
                "OFFICER": "임원",
                "10% OWNER": "10% 이상 주주",
                "10% OWNER OF CLASS": "10% 이상 주주",
            }.get(officer_title.upper(), officer_title)
            role = f" · {title_ko}" if title_ko else ""
            who = (person + role) if person else f"회사 내부자{role}"

            lines.append(f"📌 {display_date} · 내부자 거래")
            lines.append(f"🔴 {summary}" if any(c in ("P", "S") for c in ordered_codes) else f"🟡 {summary}")
            lines.append(f"📰 {who}")

            # 실제 거래가격이 여러 건이면 최소~최대 가격만 간결하게 표시한다.
            if prices:
                min_price = min(prices)
                max_price = max(prices)
                if abs(min_price - max_price) < 0.000001:
                    price_text = f"${min_price:,.2f}"
                else:
                    price_text = f"${min_price:,.2f} ~ ${max_price:,.2f}"
                lines.append(f"💰 {price_text}")
        else:
            desc = str(item.get("description", "")).strip()
            lines.append(f"📌 {display_date} · {'기업 주요 공시' if form == '8-K' else form}")
            lines.append(f"📰 {desc or '주요 내용 발표'}")

    return "\n".join(lines)

def search_krx_code(stock_name):
    key = str(stock_name or "").strip()
    if not key:
        return None, None

    now = time.time()
    cached = KR_SEARCH_CACHE.get(key)
    if cached and now - cached[0] < KR_SEARCH_CACHE_TTL:
        return cached[1], cached[2]

    lock = _get_singleflight_lock(_ANALYSIS_CACHE_LOCKS, ("kr-search", key))
    with lock:
        now = time.time()
        cached = KR_SEARCH_CACHE.get(key)
        if cached and now - cached[0] < KR_SEARCH_CACHE_TTL:
            return cached[1], cached[2]
        try:
            url = f"https://ac.finance.naver.com/ac?q={urllib.parse.quote(key)}&q_enc=utf-8&st=1&r_lt=1&r_format=json&r_enc=utf-8"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                res_json = json.loads(resp.read().decode('utf-8'))
                items = res_json.get('items', [])
                if items and len(items[0]) > 0:
                    first = items[0][0]
                    code = first[0]
                    market = first[3].upper()
                    suffix = '.KS' if 'KOSPI' in market else '.KQ'
                    value = (f"{code}{suffix}", code)
                    KR_SEARCH_CACHE[key] = (now, value[0], value[1])
                    return value
        except Exception:
            pass

    # 실패 결과는 장시간 캐시하지 않는다. 외부 자동검색이 잠깐 실패해도 다음 조회에서 재시도한다.
    return None, None

def fetch_kr_stock_realtime(code_six):
    code_six = str(code_six or "").strip()
    now = time.time()
    cached = KR_QUOTE_CACHE.get(code_six)
    if cached and now - cached[0] < KR_QUOTE_CACHE_TTL:
        return cached[1]

    lock = _get_singleflight_lock(_ANALYSIS_CACHE_LOCKS, ("kr-quote", code_six))
    with lock:
        now = time.time()
        cached = KR_QUOTE_CACHE.get(code_six)
        if cached and now - cached[0] < KR_QUOTE_CACHE_TTL:
            return cached[1]
        try:
            url = f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code_six}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                'Referer': 'https://m.stock.naver.com/'
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                datas = data.get('datas', [])
                if datas:
                    item = datas[0]
                    cur_p = float(str(item.get('closePrice', 0)).replace(',', ''))
                    diff = float(str(item.get('compareToPreviousClosePrice', 0)).replace(',', ''))
                    ratio = float(str(item.get('fluctuationsRatio', 0)).replace(',', ''))
                    result = (cur_p, diff, ratio)
                    KR_QUOTE_CACHE[code_six] = (now, result)
                    return result
        except Exception as e:
            print("네이버 실시간 시세 조회 예외:", e)

    result = (None, None, None)
    KR_QUOTE_CACHE[code_six] = (now, result)
    return result

def fetch_krx_trend_and_supply(code_six):
    code_six = str(code_six or "").strip()
    now = time.time()
    cached = KR_TREND_CACHE.get(code_six)
    if cached and now - cached[0] < KR_TREND_CACHE_TTL:
        return cached[1]

    lock = _get_singleflight_lock(_ANALYSIS_CACHE_LOCKS, ("kr-trend", code_six))
    with lock:
        now = time.time()
        cached = KR_TREND_CACHE.get(code_six)
        if cached and now - cached[0] < KR_TREND_CACHE_TTL:
            return cached[1]
        try:
            url = f"https://m.stock.naver.com/api/stock/{code_six}/trend?page=1&pageSize=20"
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                'Referer': 'https://m.stock.naver.com/'
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data and isinstance(data, list):
                    prices = []
                    for row in data:
                        cp = row.get('closePrice')
                        if cp:
                            prices.append(float(str(cp).replace(',', '')))
                    ma20 = sum(prices) / len(prices) if prices else 0
                    resistance = max(prices) if prices else 0

                    sum_foreign = 0
                    sum_inst = 0
                    sum_indiv = 0
                    valid_days = 0

                    for row in data[:5]:
                        frgn = row.get('foreignerPureBuyQuant') or 0
                        insti = row.get('organPureBuyQuant') or row.get('institutionPureBuyQuant') or 0
                        indiv = row.get('individualPureBuyQuant') or 0

                        sum_foreign += int(str(frgn).replace(',', ''))
                        sum_inst += int(str(insti).replace(',', ''))
                        sum_indiv += int(str(indiv).replace(',', ''))
                        valid_days += 1

                    if sum_indiv == 0 and (sum_foreign != 0 or sum_inst != 0):
                        sum_indiv = -(sum_foreign + sum_inst)

                    result = (ma20, resistance, sum_foreign, sum_inst, sum_indiv, valid_days)
                    KR_TREND_CACHE[code_six] = (now, result)
                    return result
        except Exception as e:
            print("네이버 수급 집계 예외:", e)

    result = (0, 0, None, None, None, 0)
    KR_TREND_CACHE[code_six] = (now, result)
    return result

def _reanchor_volume_profile(profile, current_price):
    """캐시된 과거 매물대 구간을 새 현재가 기준으로 위/아래만 다시 잡는다."""
    if not profile:
        return None
    try:
        price = float(current_price) if current_price and float(current_price) > 0 else float(profile.get("current_price") or 0)
    except Exception:
        price = float(profile.get("current_price") or 0)
    if price <= 0:
        return profile

    zones = list(profile.get("zones") or [])
    above = sorted([z for z in zones if z.get("lower", 0) > price], key=lambda z: z.get("lower", 0))
    below = sorted([z for z in zones if z.get("upper", 0) < price], key=lambda z: z.get("upper", 0), reverse=True)
    inside = [z for z in zones if z.get("lower", 0) <= price <= z.get("upper", 0)]
    updated = dict(profile)
    updated["current_price"] = price
    updated["above"] = above[0] if above else None
    updated["below"] = below[0] if below else None
    updated["inside"] = inside[0] if inside else None
    return updated


def fetch_kr_historical_volume_profile(ticker_symbol, current_price=None):
    """국내 종목의 과거 6개월 일봉 OHLCV 기반 매물대. 과거 데이터는 10분 캐시."""
    symbol = str(ticker_symbol or "").strip()
    if not symbol:
        return None
    now = time.time()
    cached = KR_VOLUME_PROFILE_CACHE.get(symbol)
    if cached and now - cached[0] < KR_VOLUME_PROFILE_CACHE_TTL:
        return _reanchor_volume_profile(cached[1], current_price)

    lock = _get_singleflight_lock(_ANALYSIS_CACHE_LOCKS, ("kr-volume", symbol))
    with lock:
        now = time.time()
        cached = KR_VOLUME_PROFILE_CACHE.get(symbol)
        if cached and now - cached[0] < KR_VOLUME_PROFILE_CACHE_TTL:
            return _reanchor_volume_profile(cached[1], current_price)
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=6mo&interval=1d"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            result = (data.get("chart", {}).get("result") or [None])[0]
            if not result:
                return None
            quote = (result.get("indicators", {}).get("quote") or [{}])[0]
            highs = quote.get("high") or []
            lows = quote.get("low") or []
            closes = quote.get("close") or []
            volumes = quote.get("volume") or []
            profile_highs = highs[:-1] if len(highs) > 1 else highs
            profile_lows = lows[:-1] if len(lows) > 1 else lows
            profile_closes = closes[:-1] if len(closes) > 1 else closes
            profile_volumes = volumes[:-1] if len(volumes) > 1 else volumes
            profile = calculate_volume_profile_levels(
                profile_highs, profile_lows, profile_closes, profile_volumes, bins=24,
                current_price=None, state_key=symbol
            )
            KR_VOLUME_PROFILE_CACHE[symbol] = (now, profile)
            return _reanchor_volume_profile(profile, current_price)
        except Exception as e:
            print(f"[국내 매물대] {symbol} 계산 예외: {type(e).__name__}: {e}")
            KR_VOLUME_PROFILE_CACHE[symbol] = (now, None)
            return None

def fetch_yahoo_direct_v8(ticker_str):
    key = str(ticker_str or "").strip().upper()
    now = time.time()
    cached = US_YAHOO_CACHE.get(key)
    if cached and now - cached[0] < US_YAHOO_CACHE_TTL:
        return cached[1]

    lock = _get_singleflight_lock(_ANALYSIS_CACHE_LOCKS, ("us-yahoo", key))
    with lock:
        now = time.time()
        cached = US_YAHOO_CACHE.get(key)
        if cached and now - cached[0] < US_YAHOO_CACHE_TTL:
            return cached[1]
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(key)}?range=6mo&interval=1d"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36'
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            res = data.get('chart', {}).get('result', [])
            if not res:
                return None, None, None, None, None

            quotes = res[0].get('indicators', {}).get('quote', [{}])[0]
            raw_closes = quotes.get('close', [])
            raw_highs = quotes.get('high', [])
            raw_lows = quotes.get('low', [])
            raw_volumes = quotes.get('volume', [])

            rows = []
            for c, h, l, v in zip(raw_closes, raw_highs, raw_lows, raw_volumes):
                if c is None or h is None or l is None or v is None:
                    continue
                try:
                    c, h, l, v = float(c), float(h), float(l), float(v)
                    if all(math.isfinite(x) for x in (c, h, l, v)) and c > 0 and v > 0:
                        rows.append((c, h, l, v))
                except Exception:
                    continue

            if len(rows) < 2:
                return None, None, None, None, None

            closes = [r[0] for r in rows]
            highs = [r[1] for r in rows]
            lows = [r[2] for r in rows]
            volumes = [r[3] for r in rows]

            cur_p = closes[-1]
            prev_p = closes[-2]
            ma20 = sum(closes[-20:]) / min(20, len(closes))

            profile_highs = highs[:-1] if len(highs) > 1 else highs
            profile_lows = lows[:-1] if len(lows) > 1 else lows
            profile_closes = closes[:-1] if len(closes) > 1 else closes
            profile_volumes = volumes[:-1] if len(volumes) > 1 else volumes
            volume_profile = calculate_volume_profile_levels(
                profile_highs, profile_lows, profile_closes, profile_volumes, bins=24,
                current_price=cur_p, state_key=key
            )

            res_p = (
                volume_profile["above"]["center"]
                if volume_profile and volume_profile.get("above")
                else 0.0
            )

            result = (cur_p, prev_p, ma20, res_p, volume_profile)
            US_YAHOO_CACHE[key] = (now, result)
            return result

        except Exception as e:
            print("미국 야후 v8 예외:", e)
            result = (None, None, None, None, None)
            US_YAHOO_CACHE[key] = (now, result)
            return result

def fetch_us_options_volume(ticker_symbol):
    """CBOE 지연 옵션 거래량을 조회한다. 결과는 짧게 캐시한다."""
    key = str(ticker_symbol).upper().strip()
    now = datetime.datetime.now().timestamp()
    cached = OPTIONS_RESULT_CACHE.get(key)
    if cached and now - cached[0] < OPTIONS_CACHE_TTL:
        return cached[1], cached[2], cached[3]

    call_vol = 0
    put_vol = 0
    option_error = None
    try:
        cboe_url = (
            f"https://cdn.cboe.com/api/global/delayed_quotes/options/"
            f"{urllib.parse.quote(key)}.json"
        )
        req = urllib.request.Request(
            cboe_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/152.0.0.0 Safari/537.36",
                "Accept": "application/json,text/plain,*/*",
            }
        )
        # 기존 8초는 전체 화면을 붙잡는 시간이 너무 길어 4초로 제한한다.
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        rows = data.get("data") or []
        if isinstance(rows, dict):
            rows = [rows]

        for row in rows:
            if not isinstance(row, dict):
                continue
            options = row.get("options") or []
            if isinstance(options, dict):
                options = [options]

            for opt in options:
                if not isinstance(opt, dict):
                    continue
                contract = str(
                    opt.get("option")
                    or opt.get("contractSymbol")
                    or opt.get("symbol")
                    or ""
                ).upper()
                volume = opt.get("volume", 0)
                if isinstance(volume, str):
                    volume = volume.replace(",", "").strip()
                try:
                    volume = int(float(volume or 0))
                except Exception:
                    volume = 0

                cp_pos = -1
                if contract:
                    m = re.search(r"\d{6}([CP])", contract)
                    if m:
                        cp_pos = m.start(1)
                if cp_pos >= 0:
                    side = contract[cp_pos]
                else:
                    side = str(opt.get("type") or opt.get("optionType") or "").upper()

                if side in ("C", "CALL"):
                    call_vol += volume
                elif side in ("P", "PUT"):
                    put_vol += volume

        print(f"[미국 옵션] {key} 성공 / CBOE / CALL={call_vol} PUT={put_vol}")
    except urllib.error.HTTPError as e:
        option_error = e.code
        print(f"[미국 옵션] CBOE 실패 {key}: HTTP {e.code}")
    except Exception as e:
        option_error = type(e).__name__
        print(f"[미국 옵션] CBOE 실패 {key}: {type(e).__name__}: {e}")

    OPTIONS_RESULT_CACHE[key] = (now, call_vol, put_vol, option_error)
    return call_vol, put_vol, option_error


def build_us_options_content(ticker_symbol, call_vol, put_vol, option_error):
    if call_vol > 0:
        pc_ratio = put_vol / call_vol
        c_str = f"{call_vol/10000:.1f}만건" if call_vol >= 10000 else f"{call_vol:,}건"
        p_str = f"{put_vol/10000:.1f}만건" if put_vol >= 10000 else f"{put_vol:,}건"
        tag_line = f"#콜 {c_str}   #풋 {p_str}   #비율 {pc_ratio:.2f}"
        if pc_ratio <= 0.7:
            return (
                f"{tag_line}\n\nCBOE Options Volume\n\n"
                "현재 옵션 거래량이 상방 쪽으로 기울어 있어!\n"
                "콜옵션 거래량이 풋옵션보다 많아 상승 쪽 베팅이 상대적으로 강한 구간이야."
            )
        if pc_ratio >= 1.1:
            return (
                f"{tag_line}\n\nCBOE Options Volume\n\n"
                "현재 옵션 거래량이 하방 쪽으로 기울어 있어!\n"
                "풋옵션 거래량이 콜옵션을 넘어 하락 방어 수요가 상대적으로 강한 구간이야."
            )
        return (
            f"{tag_line}\n\nCBOE Options Volume\n\n"
            "현재 옵션 시장이 팽팽하게 눈치싸움 중이야.\n"
            "콜과 풋 거래량이 크게 벌어지지 않아 방향성을 조금 더 확인할 필요가 있어."
        )
    if option_error:
        return f"{ticker_symbol} 조회 실패 HTTP {option_error}"
    return f"{ticker_symbol} 조회 성공 거래량 0"


# -----------------------------------------------------------------------------
# 실시간 시장 일정 캘린더
# - 고정 날짜 목록을 사용하지 않는다.
# - Finnhub의 경제지표/실적 캘린더를 주기적으로 갱신한다.
# - 캐시가 있으면 /analyze에서 즉시 반환하고, 갱신은 백그라운드에서 수행한다.
# -----------------------------------------------------------------------------
CALENDAR_CACHE = {
    "expires_at": 0.0,
    "events": [],
    "loaded": False,
}
CALENDAR_LAST_ERROR = ""
CALENDAR_LAST_REFRESH_AT = 0.0
_CALENDAR_LOCK = threading.Lock()
_CALENDAR_REFRESHING = False
CALENDAR_CACHE_TTL = 1800  # 30분

CALENDAR_WATCH_SYMBOLS = [
    # 주요 지수 영향주 + AI/반도체 + 소비/금융 대형주.
    # 전체 실적 캘린더를 보여주지 않고, 이 목록의 실적만 '주요 실적'으로 표시한다.
    "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA",
    "AVGO", "AMD", "INTC", "MU", "ORCL", "ADBE", "NFLX", "CRM",
    "COST", "LLY", "NKE", "WMT", "HD", "LOW", "PEP", "KO", "MCD",
    "JPM", "BAC", "GS", "MS", "FDX", "UPS", "CTAS", "DRI"
]

# 경제지표는 '모든 일정'이 아니라 실제 시장 반응이 큰 핵심 발표만 표시한다.
# Employee Tenure, Employee Benefits, 국제수지 등은 캘린더 API에 있어도 화면에서는 제외한다.
CORE_ECONOMIC_KEYWORDS = (
    "fomc", "fed interest rate", "federal funds",
    "consumer price index", "cpi",
    "producer price index", "ppi",
    "employment situation", "nonfarm payroll", "non-farm payroll",
    "unemployment rate",
    "gross domestic product", "gdp",
    "personal income and outlays", "pce", "core pce",
    "retail sales",
    "ism manufacturing", "ism services", "ism non-manufacturing",
    "job openings and labor turnover", "jolts",
    "adp employment", "employment change"
)


def _calendar_week_window(now_kst):
    """현재/다음 거래주를 기준으로 월~일 날짜 범위를 반환한다."""
    base = now_kst.date()
    # 토/일이면 다음 월요일부터 한 주를 본다.
    if now_kst.weekday() >= 5:
        days_to_monday = 7 - now_kst.weekday()
        start = base + datetime.timedelta(days=days_to_monday)
    else:
        start = base - datetime.timedelta(days=now_kst.weekday())
    end = start + datetime.timedelta(days=6)
    return start, end


def _http_json(url, timeout=2.5):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "gaemiGTP/1.0 calendar"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def _parse_finnhub_datetime(value):
    """Finnhub economic-calendar 시간을 UTC 기준으로 읽어 KST로 변환한다."""
    if not value:
        return None
    text = str(value).strip()
    try:
        if text.endswith("Z"):
            dt = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        else:
            dt = datetime.datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
        kst = datetime.timezone(datetime.timedelta(hours=9))
        return dt.astimezone(kst)
    except Exception:
        return None


def _earnings_datetime_kst(date_text, hour):
    """Finnhub earnings hour(bmo/amc)를 뉴욕시간으로 해석해 KST로 변환한다."""
    try:
        from zoneinfo import ZoneInfo
        ny_tz = ZoneInfo("America/New_York")
        kst_tz = datetime.timezone(datetime.timedelta(hours=9))
        d = datetime.date.fromisoformat(str(date_text)[:10])
        if hour == "bmo":
            local_time = datetime.time(8, 30)
        elif hour == "amc":
            local_time = datetime.time(16, 5)
        else:
            local_time = datetime.time(12, 0)
        return datetime.datetime.combine(d, local_time, tzinfo=ny_tz).astimezone(kst_tz)
    except Exception:
        return None


def _format_kst_event_name(event):
    source = event.get("source")
    if source == "earnings":
        symbol = event.get("symbol", "")
        display = US_KOREAN_NAMES.get(symbol, symbol)
        return f"#{display} 실적 발표"
    return str(event.get("name") or "미국 경제지표 발표")


def _fetch_dynamic_calendar_events():
    if not FINNHUB_KEY:
        return []

    kst_tz = datetime.timezone(datetime.timedelta(hours=9))
    now_kst = datetime.datetime.now(kst_tz)
    start_date, end_date = _calendar_week_window(now_kst)
    from_s = start_date.isoformat()
    to_s = end_date.isoformat()

    base = "https://finnhub.io/api/v1"
    print(f"[시장 일정] 조회 범위 KST {from_s} ~ {to_s}")
    print(f"[시장 일정] FINNHUB_KEY 존재: {bool(FINNHUB_KEY)}")
    economic_url = (
        f"{base}/calendar/economic?from={urllib.parse.quote(from_s)}"
        f"&to={urllib.parse.quote(to_s)}&token={urllib.parse.quote(FINNHUB_KEY)}"
    )
    earnings_url = (
        f"{base}/calendar/earnings?from={urllib.parse.quote(from_s)}"
        f"&to={urllib.parse.quote(to_s)}&international=false"
        f"&token={urllib.parse.quote(FINNHUB_KEY)}"
    )

    events = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        econ_future = pool.submit(_http_json, economic_url, 2.5)
        earn_future = pool.submit(_http_json, earnings_url, 2.5)

        try:
            econ_payload = econ_future.result(timeout=3.0)
            print(f"[시장 일정] 경제 API 응답 키: {list(econ_payload.keys()) if isinstance(econ_payload, dict) else type(econ_payload).__name__}")
        except Exception as exc:
            print(f"[시장 일정] 경제 API 실패: {type(exc).__name__}: {exc}")
            econ_payload = {}
        try:
            earn_payload = earn_future.result(timeout=3.0)
            print(f"[시장 일정] 실적 API 응답 키: {list(earn_payload.keys()) if isinstance(earn_payload, dict) else type(earn_payload).__name__}")
        except Exception as exc:
            print(f"[시장 일정] 실적 API 실패: {type(exc).__name__}: {exc}")
            earn_payload = {}

    # 경제지표: 미국 + '핵심 이벤트'만 통과시킨다.
    economic_rows = econ_payload.get("economicCalendar", []) if isinstance(econ_payload, dict) else []
    print(f"[시장 일정] 경제 원본 건수: {len(economic_rows)}")
    economic_us = [r for r in economic_rows if str(r.get("country", "")).upper() == "US"]
    print(f"[시장 일정] 경제 US 건수: {len(economic_us)}")
    for row in economic_rows:
        if str(row.get("country", "")).upper() != "US":
            continue
        impact = str(row.get("impact", "")).lower()
        event_name = str(row.get("event") or "").strip()
        normalized = event_name.lower()
        if not event_name:
            continue
        # Finnhub의 impact가 high여도 화면에서는 시장 핵심 지표 whitelist를 한 번 더 적용한다.
        if not any(keyword in normalized for keyword in CORE_ECONOMIC_KEYWORDS):
            continue
        if impact not in {"high", "medium"}:
            # 일부 데이터는 impact가 비어 있으므로 핵심 키워드만으로도 최소한 통과시킨다.
            if impact not in {"", "low"}:
                continue
        dt = _parse_finnhub_datetime(row.get("time"))
        if not dt:
            continue
        events.append({
            "dt": dt,
            "name": event_name,
            "type": "economic",
            "impact": impact or "high",
            "source": "economic",
            "estimate": row.get("estimate"),
            "previous": row.get("prev") if row.get("prev") is not None else row.get("previous"),
        })

    # 실적: 시장에서 자주 보는 대형주 위주로 제한해 캘린더를 '핵심 일정' 수준으로 유지한다.
    earnings_rows = earn_payload.get("earningsCalendar", []) if isinstance(earn_payload, dict) else []
    print(f"[시장 일정] 실적 원본 건수: {len(earnings_rows)}")
    costco_rows = [r for r in earnings_rows if str(r.get("symbol") or "").upper() == "COST"]
    print(f"[시장 일정] COST 원본 건수: {len(costco_rows)}")
    if costco_rows:
        print(f"[시장 일정] COST 원본: {costco_rows[:3]}")
    watch = set(CALENDAR_WATCH_SYMBOLS)
    for row in earnings_rows:
        symbol = str(row.get("symbol") or "").upper()
        if symbol not in watch:
            continue
        dt = _earnings_datetime_kst(row.get("date"), str(row.get("hour") or "").lower())
        if not dt:
            continue
        events.append({
            "dt": dt,
            "name": "",
            "type": "earnings",
            "source": "earnings",
            "symbol": symbol,
            "hour": str(row.get("hour") or "").lower(),
            "eps_estimate": row.get("epsEstimate"),
            "revenue_estimate": row.get("revenueEstimate"),
        })

    # 중복 제거 및 시간순 정렬
    dedup = {}
    for ev in events:
        key = (
            ev.get("type"),
            ev.get("symbol") or ev.get("name"),
            ev["dt"].strftime("%Y-%m-%dT%H:%M")
        )
        dedup[key] = ev
    events = sorted(dedup.values(), key=lambda x: x["dt"])

    # 화면에는 '핵심 경제지표 + 주요 종목 실적'만 최대 6개까지 표시한다.
    # 중간급 잡일정이 화면을 채우지 않도록 선택 단계에서도 한 번 더 제한한다.
    core_economic = [e for e in events if e.get("type") == "economic" and e.get("impact") in {"high", "medium"}]
    earnings = [e for e in events if e.get("type") == "earnings"]
    selected = []
    print(f"[시장 일정] 핵심 경제 통과: {len(core_economic)}, 주요 실적 통과: {len(earnings)}, 전체 선택 후보: {len(core_economic) + len(earnings)}")
    print(f"[시장 일정] COST 필터 통과: {sum(1 for e in earnings if e.get('symbol') == 'COST')}")
    # 가장 가까운 일정부터. 같은 주에 실적과 핵심 지표가 겹치면 시간순으로 함께 보여준다.
    for ev in sorted(core_economic + earnings, key=lambda x: x["dt"]):
        if ev not in selected:
            selected.append(ev)
        if len(selected) >= 12:
            break
    print("[시장 일정] 최종 선택:", [(e.get("type"), e.get("symbol"), e.get("name"), e.get("dt").isoformat()) for e in selected])
    return selected


def _refresh_calendar_cache():
    global _CALENDAR_REFRESHING, CALENDAR_LAST_ERROR, CALENDAR_LAST_REFRESH_AT
    with _CALENDAR_LOCK:
        if _CALENDAR_REFRESHING:
            return
        _CALENDAR_REFRESHING = True

    try:
        events = _fetch_dynamic_calendar_events()
        with _CALENDAR_LOCK:
            # API 호출이 정상 완료됐으면 이벤트가 0건이어도 정상적인 '조용함'으로 간주한다.
            CALENDAR_CACHE["loaded"] = True
            CALENDAR_LAST_ERROR = ""
            CALENDAR_LAST_REFRESH_AT = time.time()
            CALENDAR_CACHE["events"] = events
            CALENDAR_CACHE["expires_at"] = time.time() + CALENDAR_CACHE_TTL
    except Exception as exc:
        # 실제 API 오류를 Render 로그에서 바로 볼 수 있게 남긴다.
        CALENDAR_LAST_ERROR = f"{type(exc).__name__}: {exc}"
        print(f"[시장 일정] refresh failed: {CALENDAR_LAST_ERROR}")
        with _CALENDAR_LOCK:
            CALENDAR_LAST_REFRESH_AT = time.time()
            # 실패했을 때는 기존 정상 캐시를 보존한다.
            if not CALENDAR_CACHE["events"]:
                CALENDAR_CACHE["expires_at"] = time.time() + 60
    finally:
        with _CALENDAR_LOCK:
            _CALENDAR_REFRESHING = False


def start_calendar_warmup():
    """서버 시작 시 일정 데이터를 백그라운드로 미리 받아 /analyze를 막지 않는다."""
    threading.Thread(target=_refresh_calendar_cache, daemon=True, name="calendar-warmup").start()


def _format_calendar_display_name(event):
    """화면용 일정명을 짧게 정리한다."""
    if event.get("type") == "earnings":
        symbol = event.get("symbol", "")
        display = US_KOREAN_NAMES.get(symbol, symbol)
        # '코스트코 COST' -> '코스트코'
        if display and symbol and display.endswith(f" {symbol}"):
            display = display[:-(len(symbol) + 1)]
        return f"#{display} 실적발표"

    raw = str(event.get("name") or "미국 경제지표 발표").strip()
    normalized = raw.lower()
    economic_map = [
        (("fomc", "federal funds", "fed interest rate"), "#미국 FOMC 기준금리 결정"),
        (("consumer price index", "cpi"), "#미국 CPI 소비자물가지수"),
        (("producer price index", "ppi"), "#미국 PPI 생산자물가지수"),
        (("employment situation", "nonfarm payroll", "non-farm payroll"), "#미국 고용보고서"),
        (("unemployment rate",), "#미국 실업률"),
        (("gross domestic product", "gdp"), "#미국 GDP"),
        (("personal income and outlays", "pce", "core pce"), "#미국 PCE 물가지수"),
        (("retail sales",), "#미국 소매판매"),
        (("ism manufacturing",), "#미국 ISM 제조업"),
        (("ism services", "ism non-manufacturing"), "#미국 ISM 서비스업"),
        (("job openings and labor turnover", "jolts"), "#미국 JOLTS 고용"),
        (("adp employment", "employment change"), "#미국 ADP 고용"),
    ]
    for keys, label in economic_map:
        if any(key in normalized for key in keys):
            return label
    return f"#미국 {raw}"


def get_live_calendar_data(stock_name, ticker_symbol):
    kst_tz = datetime.timezone(datetime.timedelta(hours=9))
    now_kst = datetime.datetime.now(kst_tz)

    with _CALENDAR_LOCK:
        events = list(CALENDAR_CACHE.get("events") or [])
        loaded = bool(CALENDAR_CACHE.get("loaded"))
        expired = time.time() >= float(CALENDAR_CACHE.get("expires_at", 0))
        refreshing = bool(_CALENDAR_REFRESHING)

    # 첫 요청에서 캐시가 아직 없으면 백그라운드 갱신을 최대 3.5초만 기다린다.
    if not events and (expired or not loaded):
        if not refreshing:
            threading.Thread(target=_refresh_calendar_cache, daemon=True, name="calendar-refresh").start()
        deadline = time.time() + 3.5
        while time.time() < deadline:
            with _CALENDAR_LOCK:
                events = list(CALENDAR_CACHE.get("events") or [])
                loaded = bool(CALENDAR_CACHE.get("loaded"))
                refreshing = bool(_CALENDAR_REFRESHING)
            if events or (loaded and not refreshing):
                break
            time.sleep(0.05)

    if expired and events:
        threading.Thread(target=_refresh_calendar_cache, daemon=True, name="calendar-refresh").start()

    weekdays = ['월', '화', '수', '목', '금', '토', '일']

    upcoming = [ev for ev in events if ev.get("dt") and ev["dt"] >= now_kst]
    upcoming.sort(key=lambda ev: ev["dt"])

    def event_time(ev):
        dt = ev["dt"]
        return dt.strftime(f"%m/%d({weekdays[dt.weekday()]}) %H:%M")

    # 오늘 밤은 KST 18:00~다음날 06:00 구간으로 판단한다.
    if now_kst.hour >= 18:
        tonight_start = now_kst
        tonight_end = now_kst.replace(hour=6, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
    elif now_kst.hour < 6:
        tonight_start = now_kst
        tonight_end = now_kst.replace(hour=6, minute=0, second=0, microsecond=0)
    else:
        tonight_start = now_kst.replace(hour=18, minute=0, second=0, microsecond=0)
        tonight_end = tonight_start + datetime.timedelta(days=1, hours=-12)

    tonight_events = [ev for ev in upcoming if tonight_start <= ev["dt"] < tonight_end]
    tonight_events.sort(key=lambda ev: ev["dt"])

    if tonight_events:
        tonight_parts = [f"{event_time(ev)} {_format_calendar_display_name(ev)}" for ev in tonight_events]
        tonight_card = "오늘밤 " + " · ".join(tonight_parts)
    else:
        tonight_card = "오늘밤 조용함"

    # 날짜별로 묶어서 같은 날짜의 일정은 한 줄에 이어 붙인다.
    grouped = {}
    for ev in upcoming:
        date_key = ev["dt"].date()
        grouped.setdefault(date_key, []).append(ev)

    # 오늘밤에 이미 보여준 날짜는 아래 목록에서 중복하지 않는다.
    tonight_dates = {ev["dt"].date() for ev in tonight_events}
    grouped_rows = []
    for date_key in sorted(grouped):
        if date_key in tonight_dates:
            continue
        day_events = grouped[date_key]
        day_events.sort(key=lambda ev: ev["dt"])
        parts = [f"{ev['dt'].strftime('%H:%M')} {_format_calendar_display_name(ev)}" for ev in day_events]
        first_dt = day_events[0]["dt"]
        date_label = first_dt.strftime(f"%m/%d({weekdays[first_dt.weekday()]})")
        grouped_rows.append(f"{date_label} " + " · ".join(parts))
        if len(grouped_rows) >= 7:
            break

    # 일정 자체가 아직 수신되지 않았거나 실패한 경우에도 오늘밤 한 줄은 보여주되,
    # 실재하지 않는 다음 일정을 임의로 만들지 않는다.
    if not events:
        return tonight_card

    if grouped_rows:
        schedule_block = "\n\n".join(grouped_rows)
        return f"{tonight_card}\n\n{schedule_block}"

    return tonight_card


def analyze_stock(raw_name='SK하이닉스'):
    raw_name = str(raw_name or 'SK하이닉스').strip()
    ticker_symbol = TICKERS.get(raw_name)
    clean_code = None

    try:
        if ticker_symbol:
            clean_code = ''.join(filter(str.isdigit, ticker_symbol))
        elif re.match(r'^\d{6}$', raw_name):
            clean_code = raw_name
            ticker_symbol = f"{clean_code}.KS"
        elif re.match(r'^[A-Za-z\-]+$', raw_name):
            ticker_symbol = raw_name.upper()
        else:
            ticker_symbol, clean_code = search_krx_code(raw_name)

        if not ticker_symbol:
            ticker_symbol = "000660.KS"
            clean_code = "000660"

        is_krw = ('-' not in ticker_symbol and ticker_symbol.endswith(('.KS', '.KQ'))) or (clean_code and len(clean_code) == 6)

        current_price = 0.0
        change_pct = 0.0
        ma20 = 0.0
        resistance_price = 0.0
        volume_profile = None
        supply_content = ""

        # 1~2. 외부 API는 한 요청 안에서 순차 처리한다.
        # 이전 구조는 여러 외부 API를 ThreadPoolExecutor에 동시에 넣은 뒤
        # timeout이 나도 실행 중인 작업이 남아 다음 요청과 겹칠 수 있었다.
        # Render/Gunicorn에서는 이 누적이 반복 검색 시 502로 이어질 수 있어
        # 요청마다 외부 작업이 남지 않도록 직접 호출한다.
        if is_krw and clean_code:
            try:
                cur_p, diff, ratio = fetch_kr_stock_realtime(clean_code)
            except Exception as e:
                print(f"[국내 시세] fail: {type(e).__name__}: {e}")
                cur_p, diff, ratio = 0.0, 0.0, 0.0

            try:
                ma20_val, res_val, f_5d, i_5d, ind_5d, v_days = fetch_krx_trend_and_supply(clean_code)
            except Exception as e:
                print(f"[국내 수급] fail: {type(e).__name__}: {e}")
                ma20_val, res_val, f_5d, i_5d, ind_5d, v_days = 0, 0, 0, 0, 0, 0

            try:
                news_list = fetch_realtime_news(raw_name, TICKERS)
            except Exception as e:
                print(f"[뉴스] fail: {type(e).__name__}: {e}")
                news_list = []

            try:
                kr_official_disclosures = fetch_kr_official_disclosures(clean_code)
            except Exception as e:
                print(f"[국내 공시] fail: {type(e).__name__}: {e}")
                kr_official_disclosures = []

            try:
                volume_profile = fetch_kr_historical_volume_profile(ticker_symbol, current_price=cur_p)
            except Exception as e:
                print(f"[매물대] fail: {type(e).__name__}: {e}")
                volume_profile = None

            kr_official_disclosures_block = format_kr_official_disclosures(clean_code, kr_official_disclosures)
            official_filings_block = ""

            # 실시간 시세가 없으면 임의의 가격/등락률을 만들지 않는다.
            current_price = float(cur_p) if cur_p and float(cur_p) > 0 else 0.0
            change_pct = float(ratio) if ratio is not None else 0.0
            ma20 = float(ma20_val) if ma20_val and float(ma20_val) > 0 else 0.0
            resistance_price = float(res_val) if res_val and float(res_val) > 0 else 0.0

            clean_price = round_krw_tick(current_price)
            clean_ma20 = round_krw_tick(ma20)
            clean_res = round_krw_tick(resistance_price)
            price_str = f"{clean_price:,}원"
            ma20_str = f"{clean_ma20:,}원"
            res_str = f"{clean_res:,}원"

            if f_5d is not None and i_5d is not None and v_days > 0:
                f_abs = format_shares(f_5d)
                i_abs = format_shares(i_5d)
                ind_abs = format_shares(ind_5d)
                tag_line = f"#외국인 {f_abs} #기관 {i_abs} #개인 {ind_abs}"

                if f_5d > 0 and i_5d > 0:
                    supply_content = f"{tag_line}\n\n최근 5일 동안 외인과 기관이 쌍끌이로 물량을 쓸어 담고 있어!\n메이저 세력이 바닥을 단단하게 다져놨으니 흔들려도 버티는 게 맞아."
                elif f_5d < 0 and i_5d < 0:
                    supply_content = f"{tag_line}\n\n최근 5일 동안 큰손들이 시장에서 발을 빼며 물량을 털어내고 있어.\n개미들만 물량을 떠안는 위험한 자리니까 절대 물타지 말고 조심해야 돼."
                elif f_5d > 0:
                    supply_content = f"{tag_line}\n\n최근 5일간 세력이 개미를 압도하는 완벽한 판세야.\n기관이 관망하는 사이 외국인이 지친 개미들 물량을 싹 쓸어 담았어.\n돈의 힘이 상방으로 쏠렸으니 단기 슈팅 흐름 기대해 봐도 좋아."
                elif i_5d > 0:
                    supply_content = f"{tag_line}\n\n최근 5일 동안 국내 기관들이 뚝심 있게 순매수하며 주가를 끌고 있어!\n토종 세력의 바닥 지지력이 살아있으니 20일선 지지 여부 보면서 따라가 보자."
                else:
                    supply_content = f"{tag_line}\n\n최근 5일간 세력들이 뚜렷한 방향 없이 팽팽하게 눈치싸움 중이야.\n무리하게 베팅하지 말고 기준선 지키는지 확인하면서 방향 잡힐 때까지 기다리자."

        # 2. 미국 주식
        else:
            try:
                cur_p, prev_p, ma20_val, res_val, volume_profile = fetch_yahoo_direct_v8(ticker_symbol)
            except Exception as e:
                print(f"[미국 시세] fail: {type(e).__name__}: {e}")
                cur_p, prev_p, ma20_val, res_val, volume_profile = 0, 0, 0, 0, None

            try:
                call_vol, put_vol, option_error = fetch_us_options_volume(ticker_symbol)
            except Exception as e:
                print(f"[미국 옵션] fail: {type(e).__name__}: {e}")
                call_vol, put_vol, option_error = 0, 0, str(e)

            try:
                news_list = fetch_realtime_news(raw_name, TICKERS)
            except Exception as e:
                print(f"[뉴스] fail: {type(e).__name__}: {e}")
                news_list = []

            try:
                us_filings_raw = fetch_us_official_filings(ticker_symbol)
            except Exception as e:
                print(f"[미국 공시] fail: {type(e).__name__}: {e}")
                us_filings_raw = []

            official_filings_block = format_us_official_filings(ticker_symbol, us_filings_raw)
            kr_official_disclosures_block = ""

            if cur_p and prev_p:
                current_price = cur_p
                change_pct = ((cur_p - prev_p) / prev_p) * 100
                ma20 = ma20_val or 0.0
                resistance_price = res_val or 0.0
            else:
                current_price = 0.0
                change_pct = 0.0
                ma20 = 0.0
                resistance_price = 0.0
                volume_profile = None
                print(f"[미국 주가] {ticker_symbol} 조회 실패 - 가짜 가격 사용 안 함")

            price_str = f"${current_price:,.2f}" if current_price > 0 else "시세 조회 실패"
            ma20_str = f"${ma20:,.2f}" if ma20 > 0 else "계산 대기"
            res_str = f"${resistance_price:,.2f}" if resistance_price > 0 else "계산 대기"
            supply_content = build_us_options_content(
                ticker_symbol, call_vol, put_vol, option_error
            )

        if not supply_content:
            supply_content = "거래소 수급 집계 대기\n최근 5일간의 거래소 수급 데이터를 수집하고 있어! 이럴 땐 세력 평단 대신 20일 이동평균선을 생존 지지선으로 잡는 게 안전해."

        # 3. 등락률 분기 (불필요한 멘트 삭제 완료)
        if change_pct >= 5.0:
            status_emoji, title_word = '🔥', '올랐어'
            intro_ment = f"오!! {raw_name} {change_pct:+.2f}% 상승중이야\n개미들아! 오늘 축제야? 수익 달달하겠다 나까지 심장이 다 뛰네 ㅋㅋㅋ"
            tags_str = f"#{raw_name}   #{change_pct:+.2f}%   #가즈아   #불기둥"
        elif 0.5 <= change_pct < 5.0:
            status_emoji, title_word = '🔥', '올랐어'
            intro_ment = f"스멀스멀 {change_pct:+.2f}% 우상향 중이야\n개미들아! 분위기 나쁘지 않은데? 이대로만 가자"
            tags_str = f"#{raw_name}   #{change_pct:+.2f}%   #우상향   #야금야금"
        elif -0.5 < change_pct < 0.5:
            status_emoji, title_word = '⚖️', '보합일까'
            intro_ment = f"하아.. {raw_name} {change_pct:+.2f}%로 완전 눈치싸움 중이네\n개미들아! 폭풍 전야처럼 조용한데?"
            tags_str = f"#{raw_name}   #{change_pct:+.2f}%   #눈치싸움   #방향탐색"
        elif -5.0 < change_pct <= -0.5:
            status_emoji, title_word = '❄️', '숨고르기일까'
            intro_ment = f"아이고 {raw_name} {change_pct:+.2f}% 파란불 켜져서 속 쓰리겠다\n개미들아! 물 한잔 마시고 차분하게 보자"
            tags_str = f"#{raw_name}   #{change_pct:+.2f}%   #숨고르기   #버텨보자"
        else:
            status_emoji, title_word = '❄️', '빠질까'
            intro_ment = f"헐... {raw_name} {change_pct:+.2f}% 무섭게 빠지네\n개미들아! 멘탈 꽉 잡아 지금 공포에 투매 동참하면 세력한테 바닥에서 물량 털리는 거야 ㅠㅠ"
            tags_str = f"#{raw_name}   #{change_pct:+.2f}%   #투매금지   #멘탈관리"

        news_lines = (
            "\n".join([f"📰 \"{item.get('title', '')}\"" for item in news_list])
            if news_list
            else "📰 현재 확인된 관련 뉴스를 가져오지 못했습니다."
        )


        # 첫 화면은 현재 주가를 가장 위에 배치한다.
        # 그 아래에는 기존의 친근한 말투를 다시 살리고,
        # 그 다음 자리에 향후 AI 분석 영역이 들어간다.
        # 뉴스와 공시는 기존처럼 한 칸(빈 줄) 간격을 유지한다.
        friendly_ment = (
            intro_ment.split("\n", 1)[1]
            if "\n" in intro_ment
            else intro_ment
        )

        # 뉴스/공시는 아래의 구조화된 클릭형 목록(news_items / disclosures / us_filings)에서
        # 한 번만 표시한다. 본문에 같은 내용을 다시 넣으면 화면에 중복 출력된다.
        first_content_parts = [
            intro_ment,
            f"현재 주가는 {price_str} 기록 중!",
            tags_str,
        ]

        sections = [
            {
                "title": f"{status_emoji} 그래서 오늘은 왜 {title_word}?",
                "content": "\n\n".join(first_content_parts),
                "tags": [f"#{raw_name}", f"#{change_pct:+.2f}%", "#실시간속보"]
            }
        ]

        sections.extend([
            {
                "title": "큰손들은 담고 있을까, 털고 있을까?",
                "content": supply_content
            },
            {
                "title": "여기 깨지면 큰일인데?",
                "content": (
                    (lambda vp_text: (
                        (lambda lines: (
                            (
                                (next((line for line in lines if line.startswith("악성 매물대")), "악성 매물대 계산 대기")
                                 + "\n\n니가 사면 하락하제?ㅋ\n과거 물린 형들 본전 탈출할 수 있는 구간이야!\n\n"
                                 + "#시체추가금지 #뇌동매수멈춰 #관망이답니다 #구경만해라\n\n"
                                 + next((line for line in lines if line.startswith("생존 매물대")), "생존 매물대 계산 대기")
                                 + "\n\n멘탈 단디 잡어ㅋ\n여기서 밀리면 실망 매물 나올 수 있는 구간이야!!\n\n"
                                 + "#주식차트 #지지라인 #뇌동매수금지 #주식경고 #리스크관리 #멘탈관리")
                            )
                        ))(vp_text.splitlines())
                        if vp_text else
                        "악성 매물대 계산 대기\n\n니가 사면 하락하제?ㅋ\n과거 물린 형들 본전 탈출할 수 있는 구간이야!\n\n"
                        "#시체추가금지 #뇌동매수멈춰 #관망이답니다 #구경만해라\n\n"
                        "생존 매물대 계산 대기\n\n여기 깨지면 으악 소리 나겠지?ㅋ\n실망 매물 나올 수 있는 구간이야!!\n\n"
                        "#주식차트 #지지라인 #뇌동매수금지 #주식경고 #리스크관리 #멘탈관리"
                    ))(format_volume_profile(volume_profile, is_usd=not is_krw))
                ),
            },
            {
                "title": "오늘 밤, 이번주 무슨 일이 있나?",
                "content": get_live_calendar_data(raw_name, ticker_symbol)
            }
        ])
        news_items = list(news_list) if isinstance(news_list, list) else []
        disclosures = []
        if is_krw and clean_code:
            for item in (kr_official_disclosures or []):
                report_title = str(item.get("report", "")).strip()
                if raw_name and raw_name not in report_title:
                    report_title = f"{raw_name} {report_title}"
                disclosures.append({
                    "title": report_title,
                    "source": "DART",
                    "date": item.get("date", ""),
                    "time": item.get("time", ""),
                    "time_zone": item.get("time_zone", ""),
                    "receipt_datetime": item.get("receipt_datetime", ""),
                    "link": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={item.get('receipt_no', '')}" if item.get("receipt_no") else "",
                })
        us_filings = []
        if not is_krw and ticker_symbol:
            for item in (us_filings_raw or []):
                us_filings.append({
                    "title": "내부자 거래" if str(item.get("form", "")).upper() == "4" else (item.get("description") or "SEC 공시"),
                    "source": "SEC",
                    "date": item.get("date", ""),
                    "time": item.get("time", ""),
                    "time_zone": "ET" if item.get("time") else "",
                    "acceptance_datetime": item.get("acceptance_datetime", ""),
                    "link": item.get("url", ""),
                    "form": item.get("form", ""),
                    "person": item.get("person", ""),
                    "officer_title": item.get("officer_title", ""),
                    "transaction_kind": item.get("transaction_kind", ""),
                    "transaction_summary": item.get("transaction_summary", ""),
                    "transaction_count": item.get("transaction_count", 0),
                    "price_range": item.get("price_range", ""),
                })
        return {
            "sections": sections,
            "news_items": news_items,
            "disclosures": disclosures,
            "us_filings": us_filings,
        }

    except Exception as e:
        print("전체 예외 안전 복구 가동:", e)
        return {
            "sections": [
                {
                    "title": "⚠️ 분석 데이터를 확인하지 못했어",
                    "content": f"{raw_name} 분석에 필요한 데이터를 가져오지 못했어. 잠시 후 다시 시도해줘."
                }
            ],
            "news_items": [],
            "disclosures": [],
            "us_filings": [],
            "ok": False
        }



