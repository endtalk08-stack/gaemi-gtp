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
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

from .news_result import get_shared_stock_news_result
from .disclosure_scoring import score_disclosures
from .stock_analysis import fetch_stock_price_result
from ..providers.market_price import fetch_news_price_reaction

from .market_levels import (
    calculate_volume_profile_levels,
    format_volume_profile,
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
    '알파벳': 'GOOGL',
    '구글': 'GOOGL',
    '메타': 'META',
    '브로드컴': 'AVGO',
    '버크셔 해서웨이': 'BRK.B',
    '일라이 릴리': 'LLY',
    'AMD': 'AMD',
    '마이크론 테크놀로지': 'MU',
    '퀄컴': 'QCOM',
    'TSMC': 'TSM',
    'ASML': 'ASML',
    '팔란티어': 'PLTR',
    '로빈후드': 'HOOD',
    '록히드마틴': 'LMT',
    '엑슨모빌': 'XOM',
    '스페이스X': 'SPCX',
    '샌디스크': 'SNDK',
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
    "AVGO": "0001730168",
    "BRK.B": "0001067983",
    "AMD": "0000002488",
    "MU": "0000723125",
    "QCOM": "0000804328",
    "TSM": "0001046179",
    "ASML": "0000937966",
    "PLTR": "0001321655",
    "HOOD": "0001783879",
    "LMT": "0000936468",
    "XOM": "0000034088",
    "SPCX": "0001181412",
    "SNDK": "0002023554",
}

US_FILING_CACHE = {}
US_FORM4_DETAIL_CACHE = {}
US_FORM4_DETAIL_CACHE_TTL = 3600
US_8K_DETAIL_CACHE = {}
US_8K_DETAIL_CACHE_TTL = 3600

# 국내 기업 공식 공시(OpenDART)
# 인증키가 없으면 공시 기능만 건너뛰고 기존 화면/기능은 그대로 동작한다.
OPENDART_API_KEY = (
    os.environ.get("OPENDART_API_KEY", "").strip()
    or os.environ.get("DART_API_KEY", "").strip()
)
# Only the 20 supported Korean news-universe stocks; no full DART corpCode ZIP at runtime.
# Source: Korean listed-company DART/KRX identifier crosswalk (snapshot 2026-10-04).
DART_STOCK_CORP_CODES = {
    "005930": "00126380",  # 삼성전자
    "000660": "00164779",  # SK하이닉스
    "373220": "01515323",  # LG에너지솔루션
    "207940": "00877059",  # 삼성바이오로직스
    "005380": "00164742",  # 현대자동차
    "000270": "00106641",  # 기아
    "012450": "00126566",  # 한화에어로스페이스
    "105560": "00688996",  # KB금융
    "035420": "00266961",  # NAVER
    "034020": "00159616",  # 두산에너빌리티
    "068270": "00413046",  # 셀트리온
    "006400": "00126362",  # 삼성SDI
    "012330": "00164788",  # 현대모비스
    "055550": "00382199",  # 신한지주
    "005490": "00155319",  # POSCO홀딩스
    "051910": "00356361",  # LG화학
    "329180": "01390344",  # HD현대중공업
    "028260": "00149655",  # 삼성물산
    "035720": "00258801",  # 카카오
    "015760": "00159193",  # 한국전력공사
}
DART_DISCLOSURE_CACHE = {}
DART_EXECUTIVE_SHAREHOLDING_CACHE = {}
DART_EXECUTIVE_SHAREHOLDING_CACHE_TTL = 3600
DART_MAJOR_SHAREHOLDER_CHANGE_CACHE = {}
DART_MAJOR_SHAREHOLDER_CHANGE_CACHE_TTL = 3600
DART_EARNINGS_DETAIL_CACHE = {}
DART_EARNINGS_DETAIL_CACHE_TTL = 3600
DART_SUPPLY_CONTRACT_DETAIL_CACHE = {}
DART_SUPPLY_CONTRACT_DETAIL_CACHE_TTL = 3600
DART_FINANCING_DETAIL_CACHE = {}
DART_FINANCING_DETAIL_CACHE_TTL = 3600
DART_TREASURY_STOCK_DETAIL_CACHE = {}
DART_TREASURY_STOCK_DETAIL_CACHE_TTL = 3600
DART_DIVIDEND_DETAIL_CACHE = {}
DART_DIVIDEND_DETAIL_CACHE_TTL = 3600
DART_CORPORATE_ACTION_DETAIL_CACHE = {}
DART_CORPORATE_ACTION_DETAIL_CACHE_TTL = 3600
# 같은 종목을 동시에 여러 사용자가 조회해도 DART/SEC 외부 요청이 중복되지 않도록
# 종목별 단일 비행(single-flight) 락을 사용한다. 서로 다른 종목은 동시에 처리한다.
_DART_SINGLEFLIGHT_LOCKS = {}
_SEC_SINGLEFLIGHT_LOCKS = {}
_SINGLEFLIGHT_LOCK_GUARD = threading.Lock()
DART_RECEIPT_TIME_CACHE = {}

def _get_singleflight_lock(lock_map, key):
    with _SINGLEFLIGHT_LOCK_GUARD:
        lock = lock_map.get(key)
        if lock is None:
            lock = threading.Lock()
            lock_map[key] = lock
        return lock




# 실시간 데이터는 아주 짧게, 과거 계산 데이터는 길게 캐시한다.
# 캐시는 정확도를 떨어뜨리는 것이 아니라 같은 순간의 중복 외부 호출을 줄이는 용도다.
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

def fetch_dart_corp_code(stock_code):
    """Return the preverified DART code for the selected Korean stock only."""
    stock_code = str(stock_code or "").strip()
    if not OPENDART_API_KEY or not stock_code:
        return ""
    return DART_STOCK_CORP_CODES.get(stock_code, "")


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


def fetch_dart_executive_shareholdings(stock_code):
    """OpenDART 임원·주요주주 소유보고(elestock) 원천 데이터를 조회한다."""
    if not OPENDART_API_KEY or not stock_code:
        return []

    stock_code = str(stock_code).strip()
    now_ts = datetime.datetime.now().timestamp()
    cached = DART_EXECUTIVE_SHAREHOLDING_CACHE.get(stock_code)
    if cached and now_ts - cached[0] < DART_EXECUTIVE_SHAREHOLDING_CACHE_TTL:
        return cached[1]

    lock = _get_singleflight_lock(_DART_SINGLEFLIGHT_LOCKS, ("elestock", stock_code))
    with lock:
        now_ts = datetime.datetime.now().timestamp()
        cached = DART_EXECUTIVE_SHAREHOLDING_CACHE.get(stock_code)
        if cached and now_ts - cached[0] < DART_EXECUTIVE_SHAREHOLDING_CACHE_TTL:
            return cached[1]

        # 상세 전용 요청에서도 전체 corpCode.xml 맵을 다시 만들지 않는다.
        # 현재 프로세스 메모리의 corp_code만 재사용한다.
        corp_code = fetch_dart_corp_code(stock_code)
        if not corp_code:
            return []

        try:
            params = urllib.parse.urlencode({
                "crtfc_key": OPENDART_API_KEY,
                "corp_code": corp_code,
            })
            url = f"https://opendart.fss.or.kr/api/elestock.json?{params}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            status = str(data.get("status", ""))
            if status not in ("000", ""):
                print(
                    f"[국내 공시 상세] {stock_code} DART 응답 "
                    f"status={status} message={data.get('message', '')}"
                )
                return []

            items = data.get("list", []) or []
            DART_EXECUTIVE_SHAREHOLDING_CACHE[stock_code] = (now_ts, items)
            return items
        except urllib.error.HTTPError as e:
            print(f"[국내 공시 상세] {stock_code} DART 실패: HTTP {e.code}")
        except Exception as e:
            print(f"[국내 공시 상세] {stock_code} DART 실패: {type(e).__name__}: {e}")
        return []


def _attach_dart_executive_shareholding_details(stock_code, disclosures):
    """목록 공시의 접수번호와 elestock 상세 원천을 정확히 일치시켜 붙인다."""
    if not disclosures:
        return disclosures

    target_receipt_nos = {
        str(item.get("receipt_no") or "").strip()
        for item in disclosures
        if "임원" in str(item.get("report") or "")
        and "주요주주" in str(item.get("report") or "")
        and str(item.get("receipt_no") or "").strip()
    }
    if not target_receipt_nos:
        return disclosures

    details = fetch_dart_executive_shareholdings(stock_code)
    details_by_receipt = {}
    for detail in details:
        receipt_no = str(detail.get("rcept_no") or "").strip()
        if receipt_no in target_receipt_nos:
            details_by_receipt.setdefault(receipt_no, []).append(detail)

    for item in disclosures:
        receipt_no = str(item.get("receipt_no") or "").strip()
        matched = details_by_receipt.get(receipt_no, [])
        if not matched:
            continue

        item["executive_shareholdings"] = matched
        share_delta = 0
        has_delta = False
        for detail in matched:
            raw_delta = str(detail.get("sp_stock_lmp_irds_cnt") or "").replace(",", "").strip()
            try:
                share_delta += int(raw_delta)
                has_delta = True
            except (TypeError, ValueError):
                continue
        if has_delta:
            item["shareholding_change"] = (
                "지분증가" if share_delta > 0
                else "지분감소" if share_delta < 0
                else "지분변동없음"
            )
            item["shareholding_delta"] = share_delta

    return disclosures


def _clean_dart_cell_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


class _DartTableHTMLParser(HTMLParser):
    """정상 XML이 아닌 DART 원문에서도 표 행/셀 텍스트만 읽는다."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._row = None
        self._cell_parts = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell_parts = []

    def handle_data(self, data):
        if self._cell_parts is not None:
            self._cell_parts.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("td", "th") and self._cell_parts is not None:
            text_value = _clean_dart_cell_text(" ".join(self._cell_parts))
            if text_value and self._row is not None:
                self._row.append(text_value)
            self._cell_parts = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
            self._cell_parts = None


def _dart_document_rows(receipt_no):
    """OpenDART 원본 문서를 표의 행/셀 단위 텍스트로 읽는다."""
    receipt_no = str(receipt_no or "").strip()
    if not receipt_no or not OPENDART_API_KEY:
        return []
    params = urllib.parse.urlencode({"crtfc_key": OPENDART_API_KEY, "rcept_no": receipt_no})
    url = f"https://opendart.fss.or.kr/api/document.xml?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=3) as resp:
        payload = resp.read()
    rows = []
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        for name in zf.namelist():
            if not name.lower().endswith((".xml", ".html", ".htm")):
                continue
            raw = zf.read(name)
            try:
                root = ET.fromstring(raw)
            except Exception:
                parser = _DartTableHTMLParser()
                parser.feed(raw.decode("utf-8", errors="ignore"))
                rows.extend(parser.rows)
                continue
            for tr in root.iter():
                if str(tr.tag).split("}")[-1].upper() != "TR":
                    continue
                cells = []
                for child in list(tr):
                    tag = str(child.tag).split("}")[-1].upper()
                    if tag not in ("TD", "TH"):
                        continue
                    text_value = _clean_dart_cell_text(" ".join(child.itertext()))
                    if text_value:
                        cells.append(text_value)
                if cells:
                    rows.append(cells)
    return rows


def _parse_number_text(value, as_float=False):
    text_value = str(value or "").replace(",", "").replace("%", "").strip()
    if not text_value or text_value in ("-", "해당없음"):
        return None
    try:
        return float(text_value) if as_float else int(float(text_value))
    except (TypeError, ValueError):
        return None


def fetch_dart_major_shareholder_change(receipt_no):
    """최대주주등소유주식변동신고 원본에서 화면에 필요한 핵심값만 가공한다."""
    receipt_no = str(receipt_no or "").strip()
    if not receipt_no:
        return {}
    now_ts = datetime.datetime.now().timestamp()
    cached = DART_MAJOR_SHAREHOLDER_CHANGE_CACHE.get(receipt_no)
    if cached and now_ts - cached[0] < DART_MAJOR_SHAREHOLDER_CHANGE_CACHE_TTL:
        return cached[1]

    lock = _get_singleflight_lock(_DART_SINGLEFLIGHT_LOCKS, ("major-holder-change", receipt_no))
    with lock:
        now_ts = datetime.datetime.now().timestamp()
        cached = DART_MAJOR_SHAREHOLDER_CHANGE_CACHE.get(receipt_no)
        if cached and now_ts - cached[0] < DART_MAJOR_SHAREHOLDER_CHANGE_CACHE_TTL:
            return cached[1]
        try:
            rows = _dart_document_rows(receipt_no)
            if not rows:
                return {}

            summary = {}
            detail_changes = []
            section = ""
            current_person = {}
            for cells in rows:
                first_cell = cells[0] if cells else ""
                if first_cell in ("직전보고서제출일", "이번보고서제출일", "증감", "합계"):
                    section = "summary"
                elif "성명" in cells:
                    section = "details"

                if section == "summary":
                    if cells[0] in ("직전보고서제출일", "이번보고서제출일", "증감"):
                        label = cells[0]
                        nums = []
                        for value in cells[1:]:
                            parsed = _parse_number_text(value, as_float=True)
                            if parsed is not None:
                                nums.append(parsed)
                        if len(nums) >= 2:
                            shares = int(nums[-2])
                            rate = float(nums[-1])
                            if label == "직전보고서제출일":
                                summary["previous_shares"] = shares
                                summary["previous_rate"] = rate
                            elif label == "이번보고서제출일":
                                summary["current_shares"] = shares
                                summary["current_rate"] = rate
                            else:
                                summary["share_delta"] = shares
                                summary["rate_delta"] = rate

                elif section == "details":
                    if "성명" in cells:
                        try:
                            idx = cells.index("성명")
                            current_person["name"] = cells[idx + 1]
                        except Exception:
                            pass
                    if "최대주주 및 발행회사와의 관계" in cells:
                        try:
                            idx = cells.index("최대주주 및 발행회사와의 관계")
                            current_person["relation"] = cells[idx + 1]
                        except Exception:
                            pass
                    date_index = next((i for i, value in enumerate(cells) if re.match(r"^\d{4}-\d{2}-\d{2}$", value)), None)
                    if date_index is not None and len(cells) >= date_index + 6:
                        before = _parse_number_text(cells[date_index + 3])
                        delta = _parse_number_text(cells[date_index + 4])
                        after = _parse_number_text(cells[date_index + 5])
                        if delta is not None:
                            detail_changes.append({
                                "name": current_person.get("name", ""),
                                "relation": current_person.get("relation", ""),
                                "date": cells[date_index],
                                "reason": cells[date_index + 1],
                                "stock_type": cells[date_index + 2],
                                "before_shares": before,
                                "share_delta": delta,
                                "after_shares": after,
                            })

            if "share_delta" not in summary and "previous_shares" in summary and "current_shares" in summary:
                summary["share_delta"] = summary["current_shares"] - summary["previous_shares"]
            if "rate_delta" not in summary and "previous_rate" in summary and "current_rate" in summary:
                summary["rate_delta"] = round(summary["current_rate"] - summary["previous_rate"], 4)

            # 같은 사람/법인의 여러 거래는 화면에 한 줄만 보이도록 순변동으로 합친다.
            grouped_changes = {}
            for change in detail_changes:
                key = (
                    change.get("name", ""),
                    change.get("relation", ""),
                )
                grouped = grouped_changes.get(key)
                if grouped is None:
                    grouped_changes[key] = dict(change)
                    continue
                grouped["share_delta"] = (grouped.get("share_delta") or 0) + (change.get("share_delta") or 0)
                grouped["after_shares"] = change.get("after_shares")
                grouped["date"] = change.get("date") or grouped.get("date", "")
                if change.get("reason") != grouped.get("reason"):
                    grouped["reason"] = "순변동"
            detail_changes = list(grouped_changes.values())

            if not summary and not detail_changes:
                return {}
            result = {**summary, "detail_changes": detail_changes}
            DART_MAJOR_SHAREHOLDER_CHANGE_CACHE[receipt_no] = (now_ts, result)
            return result
        except Exception as e:
            print(f"[국내 공시 상세] 최대주주 변동 {receipt_no} 실패: {type(e).__name__}: {e}")
            return {}


def _attach_dart_major_shareholder_change_details(disclosures, max_detail_fetches=2):
    """최대주주 변동 상세는 일부만 조회해 /analyze 전체 응답을 지연시키지 않는다."""
    detail_fetches = 0
    for item in disclosures or []:
        report = str(item.get("report") or "")
        receipt_no = str(item.get("receipt_no") or "").strip()
        if "최대주주등소유주식변동신고" not in report or not receipt_no:
            continue
        if detail_fetches >= max_detail_fetches:
            print(f"[국내 공시 상세] 요청당 최대 {max_detail_fetches}건까지만 조회")
            break
        detail_fetches += 1
        detail = fetch_dart_major_shareholder_change(receipt_no)
        if not detail:
            continue
        item["major_shareholder_change"] = detail
        delta = detail.get("share_delta")
        if isinstance(delta, (int, float)):
            item["shareholding_change"] = (
                "지분증가" if delta > 0
                else "지분감소" if delta < 0
                else "지분변동없음"
            )
            item["shareholding_delta"] = int(delta)
    return disclosures



def _is_dart_earnings_report(report_name):
    text = str(report_name or "").replace(" ", "")
    return any(keyword in text for keyword in (
        "잠정실적", "매출액또는손익구조", "영업(잠정)실적", "연결재무제표기준영업(잠정)실적",
    ))


def _dart_earnings_header_map(rows):
    """실적 표의 헤더를 읽어 현재/전기/전년동기 열 위치를 찾는다."""
    header_map = {}
    for cells in rows:
        normalized = [_clean_dart_cell_text(value).replace(" ", "") for value in cells]
        if not normalized:
            continue
        for index, value in enumerate(normalized):
            if index == 0:
                continue
            if any(token in value for token in ("당기실적", "당분기", "당기", "금기", "이번분기", "이번연도")):
                header_map.setdefault("current", index)
            elif any(token in value for token in ("전기실적", "전분기", "전기", "직전분기")):
                header_map.setdefault("previous", index)
            elif any(token in value for token in ("전년동기", "전년", "전년도")):
                header_map.setdefault("year_ago", index)
        if "current" in header_map and ("previous" in header_map or "year_ago" in header_map):
            break
    return header_map


def fetch_dart_earnings_detail(receipt_no):
    """실적 DART 원문에서 표 헤더 기준으로 매출/영업이익/순이익 핵심값만 추출한다."""
    receipt_no = str(receipt_no or "").strip()
    if not receipt_no:
        return {}
    now_ts = datetime.datetime.now().timestamp()
    cached = DART_EARNINGS_DETAIL_CACHE.get(receipt_no)
    if cached and now_ts - cached[0] < DART_EARNINGS_DETAIL_CACHE_TTL:
        return cached[1]

    lock = _get_singleflight_lock(_DART_SINGLEFLIGHT_LOCKS, ("earnings-detail", receipt_no))
    with lock:
        now_ts = datetime.datetime.now().timestamp()
        cached = DART_EARNINGS_DETAIL_CACHE.get(receipt_no)
        if cached and now_ts - cached[0] < DART_EARNINGS_DETAIL_CACHE_TTL:
            return cached[1]
        try:
            rows = _dart_document_rows(receipt_no)
            if not rows:
                return {}

            aliases = (
                ("revenue", "매출액", ("매출액", "매출")),
                ("operating_profit", "영업이익", ("영업이익", "영업손익")),
                ("net_income", "당기순이익", ("당기순이익", "당기순손익", "분기순이익", "분기순손익")),
            )
            header_map = _dart_earnings_header_map(rows)
            metrics = []
            seen = set()
            for cells in rows:
                if not cells:
                    continue
                label_text = _clean_dart_cell_text(cells[0]).replace(" ", "")
                matched = next((
                    (key, label) for key, label, names in aliases
                    if any(name.replace(" ", "") in label_text for name in names)
                ), None)
                if not matched or matched[0] in seen:
                    continue

                key, label = matched
                metric = {"key": key, "label": label}

                def value_at(column_name):
                    index = header_map.get(column_name)
                    if index is None or index >= len(cells):
                        return None
                    return _parse_number_text(cells[index])

                current = value_at("current")
                previous = value_at("previous")
                year_ago = value_at("year_ago")

                # 헤더를 식별하지 못한 예외 표만 기존 순서 기반 fallback을 사용한다.
                if current is None and not header_map:
                    numeric_values = [
                        parsed for parsed in (_parse_number_text(value) for value in cells[1:])
                        if parsed is not None
                    ]
                    if numeric_values:
                        current = numeric_values[0]
                        previous = numeric_values[1] if len(numeric_values) >= 2 else None

                if current is None:
                    continue

                metric["current"] = current
                if previous is not None:
                    metric["previous"] = previous
                    if previous != 0:
                        metric["change_rate"] = round((current - previous) / abs(previous) * 100, 2)
                if year_ago is not None:
                    metric["year_ago"] = year_ago
                    if year_ago != 0:
                        metric["year_over_year_rate"] = round((current - year_ago) / abs(year_ago) * 100, 2)

                metrics.append(metric)
                seen.add(key)

            result = {"metrics": metrics} if metrics else {}
            DART_EARNINGS_DETAIL_CACHE[receipt_no] = (now_ts, result)
            return result
        except Exception as e:
            print(f"[국내 공시 상세] 실적 {receipt_no} 실패: {type(e).__name__}: {e}")
            return {}



def _is_dart_supply_contract_report(report_name):
    text = str(report_name or "").replace(" ", "")
    return any(keyword in text for keyword in (
        "단일판매ㆍ공급계약", "단일판매·공급계약", "단일판매공급계약", "공급계약체결", "수주계약",
    ))


def _dart_contract_value_after_label(cells, labels, numeric=False):
    normalized = [_clean_dart_cell_text(value).strip() for value in cells]
    for index, value in enumerate(normalized):
        compact = value.replace(" ", "")
        if not any(label.replace(" ", "") in compact for label in labels):
            continue
        for candidate in normalized[index + 1:]:
            if not candidate:
                continue
            if numeric:
                parsed = _parse_number_text(candidate, as_float=True)
                if parsed is not None:
                    return parsed
            else:
                return candidate
    return None


def fetch_dart_supply_contract_detail(receipt_no):
    """단일판매·공급계약 공시에서 계약 핵심값만 추출한다."""
    receipt_no = str(receipt_no or "").strip()
    if not receipt_no:
        return {}
    now_ts = datetime.datetime.now().timestamp()
    cached = DART_SUPPLY_CONTRACT_DETAIL_CACHE.get(receipt_no)
    if cached and now_ts - cached[0] < DART_SUPPLY_CONTRACT_DETAIL_CACHE_TTL:
        return cached[1]

    lock = _get_singleflight_lock(_DART_SINGLEFLIGHT_LOCKS, ("supply-contract", receipt_no))
    with lock:
        now_ts = datetime.datetime.now().timestamp()
        cached = DART_SUPPLY_CONTRACT_DETAIL_CACHE.get(receipt_no)
        if cached and now_ts - cached[0] < DART_SUPPLY_CONTRACT_DETAIL_CACHE_TTL:
            return cached[1]
        try:
            rows = _dart_document_rows(receipt_no)
            if not rows:
                return {}

            detail = {}
            for cells in rows:
                if "contract_amount" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, ("계약금액", "계약금액(원)", "계약금액(백만원)"), numeric=True
                    )
                    if value is not None:
                        detail["contract_amount"] = value
                if "sales_ratio" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, ("매출액대비", "최근매출액대비", "매출액 대비"), numeric=True
                    )
                    if value is not None:
                        detail["sales_ratio"] = value
                if "counterparty" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, ("계약상대", "계약상대방", "수요기관", "발주처")
                    )
                    if value:
                        detail["counterparty"] = value
                if "contract_name" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, ("계약내용", "판매ㆍ공급계약내용", "판매·공급계약내용", "공사명", "수주내용")
                    )
                    if value:
                        detail["contract_name"] = value
                if "start_date" not in detail:
                    value = _dart_contract_value_after_label(cells, ("계약기간시작", "시작일", "계약시작일"))
                    if value:
                        detail["start_date"] = value
                if "end_date" not in detail:
                    value = _dart_contract_value_after_label(cells, ("계약기간종료", "종료일", "계약종료일"))
                    if value:
                        detail["end_date"] = value

            # 계약금액/매출비중/상대방/내용 중 실제로 잡힌 값만 화면에 넘긴다.
            result = detail if detail else {}
            DART_SUPPLY_CONTRACT_DETAIL_CACHE[receipt_no] = (now_ts, result)
            return result
        except Exception as e:
            print(f"[국내 공시 상세] 공급계약 {receipt_no} 실패: {type(e).__name__}: {e}")
            return {}



def _dart_financing_kind(report_name):
    text = str(report_name or "").replace(" ", "")
    if "유상증자" in text:
        return "유상증자"
    if "전환사채" in text:
        return "전환사채"
    if "신주인수권부사채" in text:
        return "신주인수권부사채"
    if "교환사채" in text:
        return "교환사채"
    return ""


def fetch_dart_financing_detail(receipt_no, report_name=""):
    """증자·CB/BW/EB 공시에서 자금조달 핵심값만 추출한다."""
    receipt_no = str(receipt_no or "").strip()
    kind = _dart_financing_kind(report_name)
    if not receipt_no or not kind:
        return {}
    now_ts = datetime.datetime.now().timestamp()
    cache_key = (receipt_no, kind)
    cached = DART_FINANCING_DETAIL_CACHE.get(cache_key)
    if cached and now_ts - cached[0] < DART_FINANCING_DETAIL_CACHE_TTL:
        return cached[1]

    lock = _get_singleflight_lock(_DART_SINGLEFLIGHT_LOCKS, ("financing-detail", receipt_no, kind))
    with lock:
        now_ts = datetime.datetime.now().timestamp()
        cached = DART_FINANCING_DETAIL_CACHE.get(cache_key)
        if cached and now_ts - cached[0] < DART_FINANCING_DETAIL_CACHE_TTL:
            return cached[1]
        try:
            rows = _dart_document_rows(receipt_no)
            if not rows:
                return {}

            detail = {"kind": kind}
            for cells in rows:
                if "amount" not in detail:
                    labels = (
                        ("자금조달의목적", "조달금액", "발행총액", "사채의권면(전자등록)총액", "사채의권면총액")
                        if kind != "유상증자"
                        else ("신주의종류와수", "자금조달의목적", "시설자금", "영업양수자금", "운영자금", "채무상환자금", "타법인증권취득자금")
                    )
                    value = _dart_contract_value_after_label(cells, labels, numeric=True)
                    if value is not None:
                        detail["amount"] = value

                if "issue_price" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, ("신주발행가액", "발행가액", "전환가액", "행사가액", "교환가액"), numeric=True
                    )
                    if value is not None:
                        detail["issue_price"] = value

                if "new_shares" not in detail and kind == "유상증자":
                    value = _dart_contract_value_after_label(
                        cells, ("신주의종류와수", "보통주식", "기타주식"), numeric=True
                    )
                    if value is not None:
                        detail["new_shares"] = value

                if "method" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, ("증자방식", "발행방법", "사채의종류", "배정방법")
                    )
                    if value:
                        detail["method"] = value

                if "purpose" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, ("자금조달의목적", "자금의사용목적", "사용목적")
                    )
                    if value and _parse_number_text(value) is None:
                        detail["purpose"] = value

                if "maturity_date" not in detail and kind != "유상증자":
                    value = _dart_contract_value_after_label(cells, ("사채만기일", "만기일"))
                    if value:
                        detail["maturity_date"] = value

                if "conversion_start" not in detail and kind in ("전환사채", "신주인수권부사채", "교환사채"):
                    value = _dart_contract_value_after_label(
                        cells, ("전환청구기간시작일", "권리행사기간시작일", "교환청구기간시작일")
                    )
                    if value:
                        detail["conversion_start"] = value

            result = detail if len(detail) > 1 else {}
            DART_FINANCING_DETAIL_CACHE[cache_key] = (now_ts, result)
            return result
        except Exception as e:
            print(f"[국내 공시 상세] 자금조달 {receipt_no} 실패: {type(e).__name__}: {e}")
            return {}



def _dart_treasury_stock_kind(report_name):
    text = str(report_name or "").replace(" ", "")
    if "자기주식" not in text and "자사주" not in text:
        return ""
    if "취득" in text:
        return "자기주식취득"
    if "처분" in text:
        return "자기주식처분"
    return ""


def fetch_dart_treasury_stock_detail(receipt_no, report_name=""):
    """자기주식 취득·처분 공시에서 주식수/금액/가격/목적 핵심값만 추출한다."""
    receipt_no = str(receipt_no or "").strip()
    kind = _dart_treasury_stock_kind(report_name)
    if not receipt_no or not kind:
        return {}
    now_ts = datetime.datetime.now().timestamp()
    cache_key = (receipt_no, kind)
    cached = DART_TREASURY_STOCK_DETAIL_CACHE.get(cache_key)
    if cached and now_ts - cached[0] < DART_TREASURY_STOCK_DETAIL_CACHE_TTL:
        return cached[1]

    lock = _get_singleflight_lock(_DART_SINGLEFLIGHT_LOCKS, ("treasury-stock", receipt_no, kind))
    with lock:
        now_ts = datetime.datetime.now().timestamp()
        cached = DART_TREASURY_STOCK_DETAIL_CACHE.get(cache_key)
        if cached and now_ts - cached[0] < DART_TREASURY_STOCK_DETAIL_CACHE_TTL:
            return cached[1]
        try:
            rows = _dart_document_rows(receipt_no)
            if not rows:
                return {}

            action = "취득" if kind == "자기주식취득" else "처분"
            detail = {"kind": kind}
            for cells in rows:
                if "shares" not in detail:
                    value = _dart_contract_value_after_label(
                        cells,
                        (f"{action}예정주식", f"{action}예정주식수", f"{action}주식수", "보통주식"),
                        numeric=True,
                    )
                    if value is not None:
                        detail["shares"] = value

                if "amount" not in detail:
                    value = _dart_contract_value_after_label(
                        cells,
                        (f"{action}예정금액", f"{action}금액", "예정금액"),
                        numeric=True,
                    )
                    if value is not None:
                        detail["amount"] = value

                if "price" not in detail:
                    value = _dart_contract_value_after_label(
                        cells,
                        (f"1주당{action}가액", f"1주당{action}가격", f"{action}가격", "1주당가액"),
                        numeric=True,
                    )
                    if value is not None:
                        detail["price"] = value

                if "purpose" not in detail:
                    value = _dart_contract_value_after_label(
                        cells,
                        (f"{action}목적", "목적", "자기주식취득목적", "자기주식처분목적"),
                    )
                    if value and _parse_number_text(value) is None:
                        detail["purpose"] = value

                if "method" not in detail:
                    value = _dart_contract_value_after_label(
                        cells,
                        (f"{action}방법", "취득방법", "처분방법"),
                    )
                    if value:
                        detail["method"] = value

                if "start_date" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, (f"{action}예정기간시작일", "예정기간시작일", "시작일")
                    )
                    if value:
                        detail["start_date"] = value
                if "end_date" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, (f"{action}예정기간종료일", "예정기간종료일", "종료일")
                    )
                    if value:
                        detail["end_date"] = value

            result = detail if len(detail) > 1 else {}
            DART_TREASURY_STOCK_DETAIL_CACHE[cache_key] = (now_ts, result)
            return result
        except Exception as e:
            print(f"[국내 공시 상세] 자기주식 {receipt_no} 실패: {type(e).__name__}: {e}")
            return {}



def _is_dart_dividend_report(report_name):
    text = str(report_name or "").replace(" ", "")
    return any(keyword in text for keyword in (
        "현금ㆍ현물배당결정", "현금·현물배당결정", "배당결정", "주식배당결정",
    ))


def fetch_dart_dividend_detail(receipt_no):
    """배당 결정 공시에서 주당배당금/배당률/총액/기준일 핵심값만 추출한다."""
    receipt_no = str(receipt_no or "").strip()
    if not receipt_no:
        return {}
    now_ts = datetime.datetime.now().timestamp()
    cached = DART_DIVIDEND_DETAIL_CACHE.get(receipt_no)
    if cached and now_ts - cached[0] < DART_DIVIDEND_DETAIL_CACHE_TTL:
        return cached[1]

    lock = _get_singleflight_lock(_DART_SINGLEFLIGHT_LOCKS, ("dividend-detail", receipt_no))
    with lock:
        now_ts = datetime.datetime.now().timestamp()
        cached = DART_DIVIDEND_DETAIL_CACHE.get(receipt_no)
        if cached and now_ts - cached[0] < DART_DIVIDEND_DETAIL_CACHE_TTL:
            return cached[1]
        try:
            rows = _dart_document_rows(receipt_no)
            if not rows:
                return {}

            detail = {}
            for cells in rows:
                if "dividend_per_share" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, ("1주당배당금", "주당배당금", "1주당 현금배당금"), numeric=True
                    )
                    if value is not None:
                        detail["dividend_per_share"] = value
                if "dividend_rate" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, ("시가배당율", "시가배당률", "배당률"), numeric=True
                    )
                    if value is not None:
                        detail["dividend_rate"] = value
                if "total_amount" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, ("배당금총액", "배당금 총액", "현금배당금총액"), numeric=True
                    )
                    if value is not None:
                        detail["total_amount"] = value
                if "record_date" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, ("배당기준일", "기준일")
                    )
                    if value:
                        detail["record_date"] = value
                if "payment_date" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, ("배당금지급예정일", "지급예정일", "지급일")
                    )
                    if value:
                        detail["payment_date"] = value

            result = detail if detail else {}
            DART_DIVIDEND_DETAIL_CACHE[receipt_no] = (now_ts, result)
            return result
        except Exception as e:
            print(f"[국내 공시 상세] 배당 {receipt_no} 실패: {type(e).__name__}: {e}")
            return {}



def _dart_corporate_action_kind(report_name):
    text = str(report_name or "").replace(" ", "")
    if "합병" in text:
        return "합병"
    if "분할" in text:
        return "분할"
    if "영업양수" in text:
        return "영업양수"
    if "영업양도" in text:
        return "영업양도"
    if "타법인주식및출자증권취득" in text or "타법인주식취득" in text:
        return "타법인지분취득"
    if "타법인주식및출자증권처분" in text or "타법인주식처분" in text:
        return "타법인지분처분"
    return ""


def fetch_dart_corporate_action_detail(receipt_no, report_name=""):
    """합병·분할·영업양수도·타법인지분 공시에서 투자 핵심값만 추출한다."""
    receipt_no = str(receipt_no or "").strip()
    kind = _dart_corporate_action_kind(report_name)
    if not receipt_no or not kind:
        return {}
    now_ts = datetime.datetime.now().timestamp()
    cache_key = (receipt_no, kind)
    cached = DART_CORPORATE_ACTION_DETAIL_CACHE.get(cache_key)
    if cached and now_ts - cached[0] < DART_CORPORATE_ACTION_DETAIL_CACHE_TTL:
        return cached[1]

    lock = _get_singleflight_lock(_DART_SINGLEFLIGHT_LOCKS, ("corporate-action", receipt_no, kind))
    with lock:
        now_ts = datetime.datetime.now().timestamp()
        cached = DART_CORPORATE_ACTION_DETAIL_CACHE.get(cache_key)
        if cached and now_ts - cached[0] < DART_CORPORATE_ACTION_DETAIL_CACHE_TTL:
            return cached[1]
        try:
            rows = _dart_document_rows(receipt_no)
            if not rows:
                return {}

            detail = {"kind": kind}
            for cells in rows:
                if "counterparty" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, ("상대회사", "상대방", "양수회사", "양도회사", "피합병회사", "합병상대회사", "발행회사")
                    )
                    if value:
                        detail["counterparty"] = value
                if "amount" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, ("양수금액", "양도금액", "취득금액", "처분금액", "거래금액"), numeric=True
                    )
                    if value is not None:
                        detail["amount"] = value
                if "equity_ratio" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, ("취득후지분비율", "처분후지분비율", "지분비율", "소유비율"), numeric=True
                    )
                    if value is not None:
                        detail["equity_ratio"] = value
                if "shares" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, ("취득주식수", "처분주식수", "주식수"), numeric=True
                    )
                    if value is not None:
                        detail["shares"] = value
                if "ratio" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, ("자기자본대비", "총자산대비", "최근사업연도말자산총액대비"), numeric=True
                    )
                    if value is not None:
                        detail["ratio"] = value
                if "purpose" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, ("취득목적", "처분목적", "합병목적", "분할목적", "양수목적", "양도목적")
                    )
                    if value and _parse_number_text(value) is None:
                        detail["purpose"] = value
                if "effective_date" not in detail:
                    value = _dart_contract_value_after_label(
                        cells, ("합병기일", "분할기일", "양수예정일자", "양도예정일자", "취득예정일자", "처분예정일자")
                    )
                    if value:
                        detail["effective_date"] = value

            result = detail if len(detail) > 1 else {}
            DART_CORPORATE_ACTION_DETAIL_CACHE[cache_key] = (now_ts, result)
            return result
        except Exception as e:
            print(f"[국내 공시 상세] 기업행위 {receipt_no} 실패: {type(e).__name__}: {e}")
            return {}


def fetch_dart_disclosure_detail(stock_code, receipt_no, report_name=""):
    """선택된 DART 공시 한 건의 기존 상세 파서를 필요할 때만 실행한다."""
    stock_code = str(stock_code or "").strip()
    receipt_no = str(receipt_no or "").strip()
    report_name = str(report_name or "").strip()
    if not stock_code or not receipt_no:
        return {}

    item = {
        "report": report_name,
        "receipt_no": receipt_no,
    }
    disclosures = [item]

    # 기존에 구현된 상세 파서를 재사용한다. /analyze에서는 호출하지 않는다.
    if "최대주주등소유주식변동신고" in report_name:
        _attach_dart_major_shareholder_change_details(disclosures, max_detail_fetches=1)

    if "임원" in report_name and "주요주주" in report_name:
        _attach_dart_executive_shareholding_details(stock_code, disclosures)

    if _is_dart_earnings_report(report_name):
        item["earnings_detail"] = fetch_dart_earnings_detail(receipt_no)

    if _is_dart_supply_contract_report(report_name):
        item["supply_contract_detail"] = fetch_dart_supply_contract_detail(receipt_no)

    if _dart_financing_kind(report_name):
        item["financing_detail"] = fetch_dart_financing_detail(receipt_no, report_name)

    if _dart_treasury_stock_kind(report_name):
        item["treasury_stock_detail"] = fetch_dart_treasury_stock_detail(receipt_no, report_name)

    if _is_dart_dividend_report(report_name):
        item["dividend_detail"] = fetch_dart_dividend_detail(receipt_no)

    if _dart_corporate_action_kind(report_name):
        item["corporate_action_detail"] = fetch_dart_corporate_action_detail(receipt_no, report_name)

    detail = disclosures[0]
    return {
        "receipt_no": receipt_no,
        "executive_shareholdings": detail.get("executive_shareholdings", []),
        "major_shareholder_change": detail.get("major_shareholder_change", {}),
        "earnings_detail": detail.get("earnings_detail", {}),
        "supply_contract_detail": detail.get("supply_contract_detail", {}),
        "financing_detail": detail.get("financing_detail", {}),
        "treasury_stock_detail": detail.get("treasury_stock_detail", {}),
        "dividend_detail": detail.get("dividend_detail", {}),
        "corporate_action_detail": detail.get("corporate_action_detail", {}),
        "shareholding_change": detail.get("shareholding_change", ""),
        "shareholding_delta": detail.get("shareholding_delta"),
    }


def _fetch_kr_official_disclosures_uncached(stock_code, days=7, max_results=3):
    """OpenDART에서 국내 기업의 최근 공시를 코드로 조회한다."""
    if not OPENDART_API_KEY or not stock_code:
        return []

    stock_code = str(stock_code).strip()
    cache_key = (stock_code, days, max_results)
    cached = DART_DISCLOSURE_CACHE.get(cache_key)
    now_ts = datetime.datetime.now().timestamp()
    if cached and now_ts - cached[0] < 300:
        return cached[1]

    # 사용자 분석 요청에서 corpCode.xml 전체 다운로드/파싱을 절대 수행하지 않는다.
    # 미리 저장된 단일 corp_code가 없으면 공시만 건너뛰고 분석 응답을 계속한다.
    corp_code = fetch_dart_corp_code(stock_code)
    if not corp_code:
        print(f"[국내 공시] {stock_code} corp_code cache miss - analyze에서는 전체 XML 파싱 생략")
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

        # 국내 공시는 최신 접수일이 항상 위에 오도록 정렬한다.
        # 같은 날에는 최신 접수번호를 우선한다.
        results.sort(
            key=lambda x: (x["receipt_datetime"], x["receipt_no"]),
            reverse=True,
        )
        results = results[:max_results]

        # /analyze 핵심 응답에서는 DART 목록 API의 결과만 사용한다.
        # 접수시간 보강은 각 공시 원문 HTML을 다시 조회해야 하며, 표시용 메타데이터 때문에
        # 최대 3개의 추가 외부 요청을 기다리면 Gunicorn worker timeout 위험이 커진다.
        # 원문 접수시간은 공시 상세 전용 경로에서 필요할 때 조회한다.

        print(f"[국내 공시] {stock_code} 성공 / 선택={len(results)}")
        DART_DISCLOSURE_CACHE[cache_key] = (now_ts, results)
        return results

    except urllib.error.HTTPError as e:
        print(f"[국내 공시] {stock_code} DART 실패: HTTP {e.code}")
    except Exception as e:
        print(f"[국내 공시] {stock_code} DART 실패: {type(e).__name__}: {e}")

    DART_DISCLOSURE_CACHE[cache_key] = (now_ts, [])
    return []


def fetch_kr_official_disclosures(stock_code, days=7, max_results=3):
    """DART 조회를 종목별로 단일화해 동시 요청 중복을 막는다."""
    if not OPENDART_API_KEY or not stock_code:
        return []
    stock_code = str(stock_code).strip()
    cache_key = (stock_code, days, max_results)
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
        return _fetch_kr_official_disclosures_uncached(stock_code, days, max_results)


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

    now_ts = datetime.datetime.now().timestamp()
    cached = US_FORM4_DETAIL_CACHE.get(accession)
    if cached and now_ts - cached[0] < US_FORM4_DETAIL_CACHE_TTL:
        filing.update(cached[1])
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
        detail_fields = {
            key: filing.get(key)
            for key in (
                "person", "officer_title", "transactions", "transaction_code",
                "shares", "price", "transaction_kind", "transaction_summary",
                "transaction_count", "price_range",
            )
            if key in filing
        }
        US_FORM4_DETAIL_CACHE[accession] = (datetime.datetime.now().timestamp(), detail_fields)
        return filing
    except Exception as detail_err:
        print(f"[미국 공시] {ticker_symbol} Form 4 원문 보강 실패: {type(detail_err).__name__}: {detail_err}")
        return filing


SEC_8K_DISPLAY_ITEMS = {
    "1.01": ("중요 계약·협약", ["주요계약", "계약체결"]),
    "1.02": ("중요 계약 종료", ["계약종료", "주요계약"]),
    "1.03": ("파산·법정관리", ["파산", "법정관리"]),
    "2.01": ("인수·매각", ["인수합병", "자산양수도"]),
    "2.02": ("실적 발표", ["실적발표", "경영성과"]),
    "2.03": ("중요 차입·채무", ["자금조달", "차입"]),
    "2.04": ("채무 관련 중요 변화", ["채무", "재무위험"]),
    "2.05": ("구조조정", ["구조조정", "사업재편"]),
    "2.06": ("대규모 손상차손", ["손상차손", "자산가치"]),
    "3.01": ("상장 유지 관련 사항", ["상장규정", "상장유지"]),
    "3.02": ("미등록 주식 발행", ["주식발행", "자금조달"]),
    "4.01": ("회계법인 변경", ["회계법인변경", "감사"]),
    "4.02": ("재무제표 신뢰 철회", ["재무제표", "회계이슈"]),
    "5.01": ("회사 지배권 변경", ["지배권변경", "경영권"]),
    "5.02": ("주요 경영진 변경", ["임원변경", "경영진"]),
}

SEC_8K_CONDITIONAL_ITEMS = {
    "5.03": ("정관·회계연도 변경", ["정관변경"]),
    "5.07": ("주주총회 투표 결과", ["주주총회"]),
    "7.01": ("중요 정보 공개", ["중요정보"]),
    "8.01": ("기타 주요 사항", ["기타주요사항"]),
}

SEC_8K_CONDITIONAL_MATERIAL_WORDS = [
    "agreement", "contract", "acquisition", "merger", "sale", "financing",
    "credit", "loan", "debt", "earnings", "revenue", "guidance", "dividend",
    "repurchase", "restructuring", "impairment", "bankruptcy", "litigation",
    "investigation", "regulatory", "chief executive", "chief financial",
    "director", "officer", "resign", "appoint", "shareholder", "vote",
]


def _plain_text_from_html(value):
    text = re.sub(r"(?is)<script\b.*?</script>|<style\b.*?</style>", " ", str(value or ""))
    text = re.sub(r"(?i)<br\s*/?>|</p\s*>|</div\s*>|</tr\s*>|</li\s*>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text).replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def _extract_8k_item_sections(text):
    """8-K 본문에서 Item 번호와 각 Item 구간을 분리한다."""
    matches = list(re.finditer(r"(?im)\bItem\s+([1-9]\.\d{2})\b", text or ""))
    sections = []
    seen = set()
    for index, match in enumerate(matches):
        item_no = match.group(1)
        if item_no in seen:
            continue
        seen.add(item_no)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((item_no, (text[match.end():end] or "").strip()))
    return sections


def _extract_8k_key_points(section_text, max_points=3):
    """8-K Item 본문에서 화면에 보여줄 핵심 문장을 최대 3개만 고른다."""
    text = re.sub(r"(?im)^Item\s+[1-9]\.\d{2}\b[^\n]*", " ", str(section_text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9$])", text)
    skip_starts = (
        "the information contained in this current report",
        "the information in this item",
        "the foregoing",
        "the description above",
        "reference is made",
        "incorporated herein by reference",
    )
    signal_words = (
        "$", "%", "million", "billion", "revenue", "earnings", "income", "sales",
        "deliveries", "production", "guidance", "agreement", "contract", "credit",
        "loan", "debt", "acquisition", "merger", "purchase", "sale", "appoint",
        "resign", "chief executive", "chief financial", "director", "restructur",
        "impairment", "bankruptcy", "investigation", "dividend", "repurchase",
    )

    ranked = []
    for index, sentence in enumerate(sentences):
        sentence = sentence.strip(" -•\t\r\n")
        if len(sentence) < 35 or len(sentence) > 420:
            continue
        lowered = sentence.lower()
        if lowered.startswith(skip_starts):
            continue
        score = sum(2 for word in signal_words if word in lowered)
        if re.search(r"\d", sentence):
            score += 2
        if "$" in sentence or "%" in sentence:
            score += 2
        if score <= 0:
            continue
        ranked.append((score, index, sentence))

    ranked.sort(key=lambda row: (-row[0], row[1]))
    selected = []
    for _, index, sentence in ranked:
        normalized = sentence[:300].strip()
        if normalized and normalized not in [point[1] for point in selected]:
            selected.append((index, normalized))
        if len(selected) >= max_points:
            break
    selected.sort(key=lambda point: point[0])
    return [point[1] for point in selected]


def _format_sec_amount_ko(raw_amount):
    """SEC 영문 금액 표기를 화면용 한글 금액으로 바꾼다."""
    value = str(raw_amount or "").strip().replace(",", "")
    match = re.match(r"\$?([0-9]+(?:\.[0-9]+)?)\s*(billion|million)?", value, re.I)
    if not match:
        return value
    number = float(match.group(1))
    unit = (match.group(2) or "").lower()
    if unit == "billion":
        eok = number * 10
        return f"{eok:g}억 달러"
    if unit == "million":
        eok = number / 10
        return f"{eok:g}억 달러"
    return f"$" + f"{number:g}"


def _summarize_8k_key_points_ko(key_points):
    """8-K 핵심문장에서 확인 가능한 사실만 짧은 한국어 문장으로 가공한다."""
    summaries = []
    for point in key_points or []:
        text = re.sub(r"\s+", " ", str(point or "")).strip()
        lowered = text.lower()
        summary = ""

        if "press release" in lowered and ("exhibit 99.1" in lowered or "exhibit99.1" in lowered):
            summary = "실적 관련 보도자료 공개 · Exhibit 99.1 첨부"
        elif "revolving credit" in lowered and ("increase" in lowered or "additional" in lowered):
            amounts = re.findall(r"\$[0-9]+(?:\.[0-9]+)?\s*(?:billion|million)", text, re.I)
            if len(amounts) >= 2:
                summary = "회전신용 한도 최대 " + _format_sec_amount_ko(amounts[0]) + " 추가 확대 가능 · 총 한도 최대 " + _format_sec_amount_ko(amounts[-1])
            elif amounts:
                summary = "회전신용 한도 " + _format_sec_amount_ko(amounts[0]) + " 규모 변경"
        elif "liquidity" in lowered and ("maintain" in lowered or "minimum" in lowered or "at least" in lowered):
            amounts = re.findall(r"\$[0-9]+(?:\.[0-9]+)?\s*(?:billion|million)", text, re.I)
            if amounts:
                summary = "최소 " + _format_sec_amount_ko(amounts[0]) + " 유동성 유지 조건"
        elif "revolving credit agreement" in lowered and ("mature" in lowered or "maturity" in lowered):
            amounts = re.findall(r"\$[0-9]+(?:\.[0-9]+)?\s*(?:billion|million)", text, re.I)
            date_match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})", text, re.I)
            date_text = ""
            if date_match:
                month_map = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}
                month = month_map.get(date_match.group(1).lower())
                if month:
                    date_text = f"{date_match.group(3)}-{month:02d}-{int(date_match.group(2)):02d} 만기"
            parts = []
            if amounts:
                parts.append("기존 회전신용 계약 한도 " + _format_sec_amount_ko(amounts[0]))
            if date_text:
                parts.append(date_text)
            summary = " · ".join(parts)

        if summary and summary not in summaries:
            summaries.append(summary)
        if len(summaries) >= 3:
            break
    return summaries


def _extract_8k_exhibit_99_1_points(index_html, filing, max_points=4):
    """같은 8-K 제출 건의 Exhibit 99.1에서 화면용 핵심 숫자 문장만 뽑는다."""
    accession = str(filing.get("accession") or "").strip()
    cik = str(filing.get("cik") or "").strip()
    if not accession or not cik:
        return []

    candidates = []
    for match in re.finditer(r'(?is)<tr[^>]*>(.*?)</tr>', str(index_html or "")):
        row_html = match.group(1)
        row_text = _plain_text_from_html(row_html)
        if not re.search(r"(?i)(?:EX-?99\.1|Exhibit\s+99\.1)", row_text):
            continue
        href_match = re.search(r'(?i)href=["\']([^"\']+)["\']', row_html)
        if href_match:
            candidates.append(href_match.group(1))

    if not candidates:
        return []

    clean_accession = accession.replace("-", "")
    href = candidates[0]
    if href.startswith("http://") or href.startswith("https://"):
        exhibit_url = href
    elif href.startswith("/"):
        exhibit_url = "https://www.sec.gov" + href
    else:
        exhibit_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{clean_accession}/{href}"

    req = urllib.request.Request(
        exhibit_url,
        headers={
            "User-Agent": os.environ.get("SEC_USER_AGENT", "gaemiGTP/1.0"),
            "Accept": "text/html,application/xhtml+xml,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        exhibit_text = _plain_text_from_html(resp.read().decode("utf-8", errors="ignore"))

    sentences = re.split(r"(?<=[.!?])\s+|\n+", exhibit_text)
    signal_words = (
        "production", "produced", "deliveries", "delivered", "revenue", "revenues",
        "operating income", "net income", "earnings", "eps", "earnings per share",
        "free cash flow", "cash flow", "guidance", "outlook", "margin",
    )
    ranked = []
    for index, sentence in enumerate(sentences):
        sentence = re.sub(r"\s+", " ", sentence).strip(" -•\t\r\n")
        if len(sentence) < 20 or len(sentence) > 420:
            continue
        lowered = sentence.lower()
        signal_count = sum(1 for word in signal_words if word in lowered)
        if signal_count <= 0 or not re.search(r"\d", sentence):
            continue
        score = signal_count * 3
        if "$" in sentence or "%" in sentence:
            score += 2
        if re.search(r"\b\d{1,3}(?:,\d{3})+\b", sentence):
            score += 2
        ranked.append((score, index, sentence))

    ranked.sort(key=lambda row: (-row[0], row[1]))
    selected = []
    seen = set()
    for _, index, sentence in ranked:
        normalized = sentence[:320].strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            selected.append((index, normalized))
        if len(selected) >= max_points:
            break
    selected.sort(key=lambda row: row[0])
    return [sentence for _, sentence in selected]



def _summarize_8k_exhibit_points_ko(points):
    """Exhibit 99.1 핵심문장을 패널용 짧은 한국어 결과로 가공한다."""
    summaries = []
    for point in points or []:
        text = re.sub(r"\s+", " ", str(point or "")).strip()
        lowered = text.lower()

        production = re.search(r"produced\s+(?:over\s+)?([0-9,]+)\s+vehicles?", text, re.I)
        deliveries = re.search(r"delivered\s+(?:over\s+)?([0-9,]+)\s+vehicles?", text, re.I)
        storage = re.search(r"deployed\s+([0-9]+(?:\.[0-9]+)?)\s*GWh", text, re.I)
        if production or deliveries or storage:
            if production:
                summaries.append("생산량 · " + production.group(1) + "대 이상")
            if deliveries:
                summaries.append("인도량 · " + deliveries.group(1) + "대 이상")
            if storage:
                summaries.append("에너지 저장 · " + storage.group(1) + " GWh")
            continue

        if ("net income" in lowered or "cash flow" in lowered) and "announce" in lowered and "q3" in lowered:
            summaries.append("재무실적 · Q3 실적 발표 시 공개")

    unique = []
    for summary in summaries:
        if summary not in unique:
            unique.append(summary)
        if len(unique) >= 4:
            break
    return unique

def _enrich_us_8k_from_submission(filing, ticker_symbol):
    """SEC 8-K 원문에서 표시할 사건만 골라 Item/제목/해시태그 재료를 붙인다."""
    filing_url = str(filing.get("original_document_url") or "").strip()
    accession = str(filing.get("accession") or "").strip()
    if not filing_url or not accession:
        filing["display_8k"] = False
        return filing

    now_ts = datetime.datetime.now().timestamp()
    cached = US_8K_DETAIL_CACHE.get(accession)
    if cached and now_ts - cached[0] < US_8K_DETAIL_CACHE_TTL:
        filing.update(cached[1])
        return filing

    detail = {"display_8k": False}
    try:
        req = urllib.request.Request(
            filing_url,
            headers={
                "User-Agent": os.environ.get("SEC_USER_AGENT", "gaemiGTP/1.0"),
                "Accept": "text/html,application/xhtml+xml,*/*",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            document_text = _plain_text_from_html(resp.read().decode("utf-8", errors="ignore"))

        exhibit_points = []
        try:
            filing_page_url = str(filing.get("url") or "").strip()
            if filing_page_url:
                index_req = urllib.request.Request(
                    filing_page_url,
                    headers={
                        "User-Agent": os.environ.get("SEC_USER_AGENT", "gaemiGTP/1.0"),
                        "Accept": "text/html,application/xhtml+xml,*/*",
                    },
                )
                with urllib.request.urlopen(index_req, timeout=5) as index_resp:
                    index_html = index_resp.read().decode("utf-8", errors="ignore")
                exhibit_points = _extract_8k_exhibit_99_1_points(index_html, filing)
        except Exception as exhibit_err:
            print(f"[미국 공시] {ticker_symbol} Exhibit 99.1 보강 실패: {type(exhibit_err).__name__}: {exhibit_err}")

        item_sections = _extract_8k_item_sections(document_text)
        selected = []
        for item_no, section_text in item_sections:
            if item_no in SEC_8K_DISPLAY_ITEMS:
                selected.append((item_no, SEC_8K_DISPLAY_ITEMS[item_no]))
                continue
            if item_no in SEC_8K_CONDITIONAL_ITEMS:
                material_text = section_text.lower()
                if any(word in material_text for word in SEC_8K_CONDITIONAL_MATERIAL_WORDS):
                    selected.append((item_no, SEC_8K_CONDITIONAL_ITEMS[item_no]))

        if selected:
            item_numbers = [item_no for item_no, _ in selected]
            labels = []
            keywords = []
            selected_sections = []
            section_map = {item_no: section_text for item_no, section_text in item_sections}
            for item_no, (label, item_keywords) in selected:
                if label not in labels:
                    labels.append(label)
                for keyword in item_keywords:
                    if keyword not in keywords:
                        keywords.append(keyword)
                if section_map.get(item_no):
                    selected_sections.append(section_map[item_no])

            key_points = _extract_8k_key_points(" ".join(selected_sections), max_points=3)
            key_points_ko = _summarize_8k_key_points_ko(key_points)
            if exhibit_points and any(item_no == "2.02" for item_no in item_numbers):
                key_points = exhibit_points[:3]
                exhibit_points_ko = _summarize_8k_exhibit_points_ko(exhibit_points)
                key_points_ko = exhibit_points_ko or exhibit_points[:3]
            detail = {
                "display_8k": True,
                "item": item_numbers[0],
                "items": item_numbers,
                "event_title": labels[0] if len(labels) == 1 else " · ".join(labels[:2]),
                "keywords": keywords[:3],
                "key_points": key_points,
                "key_points_ko": key_points_ko,
            }
    except Exception as detail_err:
        print(f"[미국 공시] {ticker_symbol} 8-K 원문 보강 실패: {type(detail_err).__name__}: {detail_err}")

    US_8K_DETAIL_CACHE[accession] = (datetime.datetime.now().timestamp(), detail)
    filing.update(detail)
    return filing


def _fetch_us_official_filings_uncached(ticker_symbol, days=7, max_results=3):
    """SEC 공식 제출자료 중 최근 주요 공시를 수집한다. AI/웹검색 없이 코드로만 수집."""
    ticker_symbol = ticker_symbol.upper()
    cik = US_CIKS.get(ticker_symbol)
    cache_key = (ticker_symbol, days, max_results)
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

            # Form 4와 8-K 원문 보강은 서로 독립적으로 처리한다.
            if form == "4" and filing_url:
                filing["_needs_form4_enrichment"] = True
            elif form == "8-K" and filing_url:
                filing["_needs_8k_enrichment"] = True

            results.append(filing)

            if len(results) >= max_results:
                break

        # 조회한 기간 안의 Form 4는 기존 방식 그대로 상세 보강한다.
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

        # 8-K는 원문 Item을 확인한 뒤 의미 있는 사건이 있는 공시만 남긴다.
        eight_k_targets = [f for f in results if f.get("_needs_8k_enrichment")]
        if eight_k_targets:
            with ThreadPoolExecutor(max_workers=min(3, len(eight_k_targets))) as enrich_executor:
                future_map = {
                    enrich_executor.submit(_enrich_us_8k_from_submission, filing, ticker_symbol): filing
                    for filing in eight_k_targets
                }
                for future, filing in future_map.items():
                    try:
                        enriched = future.result()
                        filing.update(enriched)
                    except Exception as enrich_err:
                        print(f"[미국 공시] {ticker_symbol} 8-K 병렬 보강 실패: {type(enrich_err).__name__}: {enrich_err}")
                    filing.pop("_needs_8k_enrichment", None)

        results = [
            filing for filing in results
            if str(filing.get("form", "")).upper() != "8-K" or filing.get("display_8k")
        ]

        US_FILING_CACHE[cache_key] = (datetime.datetime.now().timestamp(), results)
        return results
    except urllib.error.HTTPError as e:
        print(f"[미국 공시] {ticker_symbol} SEC 실패: HTTP {e.code}")
    except Exception as e:
        print(f"[미국 공시] {ticker_symbol} SEC 실패: {type(e).__name__}: {e}")
    US_FILING_CACHE[cache_key] = (datetime.datetime.now().timestamp(), [])
    return []

def fetch_us_official_filings(ticker_symbol, days=7, max_results=3):
    """SEC 조회를 종목별로 단일화해 동시 요청 중복을 막는다."""
    ticker_symbol = str(ticker_symbol or "").upper().strip()
    if not ticker_symbol or ticker_symbol not in US_CIKS:
        return []
    cache_key = (ticker_symbol, days, max_results)
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
        return _fetch_us_official_filings_uncached(ticker_symbol, days, max_results)


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
            event_title = str(item.get("event_title", "")).strip()
            lines.append(f"📌 {display_date} · {'기업 주요 공시' if form == '8-K' else form}")
            lines.append(f"📰 {event_title or desc or '주요 내용 발표'}")
            if form == "8-K":
                for point in (item.get("key_points_ko") or [])[:3]:
                    lines.append(f"• {point}")

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





# -----------------------------------------------------------------------------
# 실시간 시장 일정 캘린더
# - 고정 날짜 목록을 사용하지 않는다.
# - 공식 미국 경제일정(BLS/BEA/Fed/Census) + Finnhub 주요 실적 캘린더를 주기적으로 갱신한다.
# - 프로세스 메모리 캐시만 사용하며, 갱신은 백그라운드에서 수행한다.
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

def _calendar_events_to_json(events):
    payload = []
    for ev in events or []:
        row = dict(ev)
        dt = row.get("dt")
        if isinstance(dt, datetime.datetime):
            row["dt"] = dt.isoformat()
        payload.append(row)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _calendar_events_from_json(raw):
    try:
        rows = json.loads(raw or "[]")
        out = []
        for row in rows if isinstance(rows, list) else []:
            row = dict(row)
            dt = row.get("dt")
            if isinstance(dt, str):
                parsed = datetime.datetime.fromisoformat(dt)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=datetime.timezone.utc)
                row["dt"] = parsed.astimezone(datetime.timezone(datetime.timedelta(hours=9)))
            if isinstance(row.get("dt"), datetime.datetime):
                out.append(row)
        return out
    except Exception as exc:
        print(f"[시장 일정] persistent cache decode fail: {type(exc).__name__}: {exc}")
        return []


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


def _http_text(url, timeout=5.0):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "gaemiGTP/1.0 calendar"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_ics_datetime(line):
    """ICS DTSTART 파서. TZID가 있으면 해당 시간대, Z면 UTC로 해석한다."""
    try:
        if ":" not in line:
            return None
        key, value = line.split(":", 1)
        value = value.strip()
        params = {}
        if ";" in key:
            parts = key.split(";")
            key = parts[0]
            for item in parts[1:]:
                if "=" in item:
                    k, v = item.split("=", 1)
                    params[k.upper()] = v
        tz_name = params.get("TZID")
        if value.endswith("Z"):
            tzinfo = datetime.timezone.utc
            value = value[:-1]
        elif tz_name:
            try:
                tzinfo = ZoneInfo(tz_name)
            except Exception:
                tzinfo = datetime.timezone.utc
        else:
            tzinfo = datetime.timezone.utc
        if len(value) == 8:
            return datetime.datetime.strptime(value, "%Y%m%d").replace(tzinfo=tzinfo)
        if len(value) >= 15:
            return datetime.datetime.strptime(value[:15], "%Y%m%dT%H%M%S").replace(tzinfo=tzinfo)
        return None
    except Exception:
        return None


def _parse_bls_ics_events(start_date, end_date):
    """BLS 공식 ICS에서 핵심 고용/CPI/PPI/JOLTS 일정을 읽는다."""
    url = "https://www.bls.gov/schedule/news_release/bls.ics"
    raw = _http_text(url, timeout=6.0)
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    # RFC5545 line folding 해제
    unfolded = []
    for line in lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)

    allowed = (
        "consumer price index",
        "producer price index",
        "employment situation",
        "job openings and labor turnover",
    )
    kst = datetime.timezone(datetime.timedelta(hours=9))
    events = []
    block = []
    inside = False
    for line in unfolded:
        line = line.strip()
        if line == "BEGIN:VEVENT":
            inside = True
            block = []
            continue
        if line == "END:VEVENT":
            if inside:
                fields = {"SUMMARY": "", "DTSTART": ""}
                for item in block:
                    if item.startswith("SUMMARY:"):
                        fields["SUMMARY"] = item.split(":", 1)[1].strip()
                    elif item.startswith("DTSTART"):
                        fields["DTSTART"] = item
                summary = fields["SUMMARY"]
                if summary and any(k in summary.lower() for k in allowed):
                    dt = _parse_ics_datetime(fields["DTSTART"])
                    if dt:
                        dt = dt.astimezone(kst)
                        if start_date <= dt.date() <= end_date:
                            if "consumer price index" in summary.lower():
                                label = "#미국 CPI 소비자물가지수"
                            elif "producer price index" in summary.lower():
                                label = "#미국 PPI 생산자물가지수"
                            elif "employment situation" in summary.lower():
                                label = "#미국 고용보고서"
                            else:
                                label = "#미국 JOLTS 고용"
                            events.append({
                                "dt": dt,
                                "name": label,
                                "type": "economic",
                                "impact": "high",
                                "source": "BLS",
                            })
            inside = False
            block = []
            continue
        if inside:
            block.append(line)
    return events


class _TableParser(HTMLParser):
    """작은 HTML 표 파싱용 표준 라이브러리 파서."""
    def __init__(self):
        super().__init__()
        self.rows = []
        self._row = None
        self._cell = []
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._in_cell = True
            self._cell = []

    def handle_data(self, data):
        if self._in_cell:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self._in_cell and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = []
            self._in_cell = False
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                self.rows.append(self._row)
            self._row = None


def _parse_bea_schedule_events(start_date, end_date):
    """BEA 공식 Release Schedule에서 GDP/PCE만 선택한다."""
    html_text = _http_text("https://www.bea.gov/news/schedule", timeout=6.0)
    parser = _TableParser()
    parser.feed(html_text)
    kst = datetime.timezone(datetime.timedelta(hours=9))
    et_tz = ZoneInfo("America/New_York")
    events = []
    now_year = start_date.year
    for row in parser.rows:
        if len(row) < 3:
            continue
        date_text, time_text = row[0].strip(), row[1].strip()
        title = " ".join(row[2:]).strip()
        lower = title.lower()
        if not any(k in lower for k in ("gross domestic product", "personal income and outlays")):
            continue
        m = re.match(r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})$", date_text, re.I)
        if not m:
            continue
        try:
            d = datetime.date(now_year, datetime.datetime.strptime(m.group(1)[:3], "%b").month, int(m.group(2)))
            tm = re.match(r"^(\d{1,2}):(\d{2})\s*(AM|PM)$", time_text, re.I)
            if not tm:
                continue
            hour = int(tm.group(1)) % 12 + (12 if tm.group(3).lower() == "pm" else 0)
            minute = int(tm.group(2))
            dt = datetime.datetime.combine(d, datetime.time(hour, minute), tzinfo=et_tz).astimezone(kst)
            if start_date <= dt.date() <= end_date:
                label = "#미국 GDP" if "gross domestic product" in lower else "#미국 PCE 물가지수"
                events.append({
                    "dt": dt,
                    "name": label,
                    "type": "economic",
                    "impact": "high",
                    "source": "BEA",
                })
        except Exception:
            continue
    return events


def _parse_fomc_events(start_date, end_date):
    """Fed 공식 FOMC 일정에서 각 회의 둘째 날 14:00 ET 정책결정 시점을 잡는다."""
    html_text = _http_text("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", timeout=6.0)
    text = re.sub(r"<[^>]+>", " ", html_text)
    text = re.sub(r"\s+", " ", text)
    year = str(start_date.year)
    marker = f"{year} FOMC Meetings"
    idx = text.find(marker)
    if idx < 0:
        return []
    chunk = text[idx:]
    next_year = chunk.find(str(start_date.year + 1))
    if next_year > 0:
        chunk = chunk[:next_year]
    month_map = {m: i for i, m in enumerate(("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), 1)}
    et_tz = ZoneInfo("America/New_York")
    kst = datetime.timezone(datetime.timedelta(hours=9))
    events = []
    for month, d1, d2 in re.findall(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})-(\d{1,2})", chunk):
        try:
            d = datetime.date(int(year), month_map[month], int(d2))
            dt = datetime.datetime.combine(d, datetime.time(14, 0), tzinfo=et_tz).astimezone(kst)
            if start_date <= dt.date() <= end_date:
                events.append({
                    "dt": dt,
                    "name": "#미국 FOMC 기준금리 결정",
                    "type": "economic",
                    "impact": "high",
                    "source": "Federal Reserve",
                })
        except Exception:
            continue
    return events


def _parse_census_events(start_date, end_date):
    """미국 Census 경제지표 일정에서 소매판매만 선택한다."""
    html_text = _http_text("https://www.census.gov/economic-indicators/calendar-listview.html", timeout=6.0)
    parser = _TableParser()
    parser.feed(html_text)
    kst = datetime.timezone(datetime.timedelta(hours=9))
    et_tz = ZoneInfo("America/New_York")
    events = []
    for row in parser.rows:
        if len(row) < 3:
            continue
        title = row[0]
        if "Advance Monthly Sales for Retail and Food Services" not in title:
            continue
        date_text = row[1]
        time_text = row[2]
        m = re.match(r"^(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})$", date_text, re.I)
        if not m:
            continue
        try:
            month = datetime.datetime.strptime(m.group(1)[:3], "%b").month
            d = datetime.date(int(m.group(3)), month, int(m.group(2)))
            tm = re.match(r"^(\d{1,2}):(\d{2})\s*(AM|PM)$", time_text, re.I)
            if not tm:
                continue
            hour = int(tm.group(1)) % 12 + (12 if tm.group(3).lower() == "pm" else 0)
            minute = int(tm.group(2))
            dt = datetime.datetime.combine(d, datetime.time(hour, minute), tzinfo=et_tz).astimezone(kst)
            if start_date <= dt.date() <= end_date:
                events.append({
                    "dt": dt,
                    "name": "#미국 소매판매",
                    "type": "economic",
                    "impact": "high",
                    "source": "U.S. Census Bureau",
                })
        except Exception:
            continue
    return events


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


FINANCE_CALENDAR_BASE_URL = "https://www.financecalendar.com/wp-json/fc/v1"

# Finance Calendar의 단일 경제일정 피드에서 가져올 핵심 일정만 통과시킨다.
# 사용자가 요청한 시장 영향도가 높은 미국 일정만 표시한다.
# 공식 연준 일정의 FOMC 정책결정일(각 회의 둘째 날).
# Finance Calendar의 일반 /calendar 피드는 "federal funds" 같은 유사 문자열도
# 포함할 수 있어, FOMC는 공식 날짜와 함께 한 번 더 검증한다.
OFFICIAL_FOMC_DECISION_DATES = {
    2026: {
        datetime.date(2026, 1, 28), datetime.date(2026, 3, 18),
        datetime.date(2026, 4, 29), datetime.date(2026, 6, 17),
        datetime.date(2026, 7, 29), datetime.date(2026, 9, 16),
        datetime.date(2026, 10, 28), datetime.date(2026, 12, 9),
    },
    2027: {
        datetime.date(2027, 1, 27), datetime.date(2027, 3, 17),
        datetime.date(2027, 4, 28), datetime.date(2027, 6, 9),
        datetime.date(2027, 7, 28), datetime.date(2027, 9, 15),
        datetime.date(2027, 10, 27), datetime.date(2027, 12, 8),
    },
}


def _is_official_fomc_decision(dt):
    """FOMC는 미국 동부시간(ET) 기준 공식 결정일의 14:00 전후 1건만 허용."""
    try:
        from zoneinfo import ZoneInfo
        et = dt.astimezone(ZoneInfo("America/New_York"))
        official_dates = OFFICIAL_FOMC_DECISION_DATES.get(et.year, set())
        if et.date() not in official_dates:
            return False
        # 연준 정책성명은 통상 14:00 ET. 회의/기자회견 등 다른 FOMC 행은 제외한다.
        return 13 * 60 + 30 <= et.hour * 60 + et.minute <= 14 * 60 + 30
    except Exception:
        return False

def _fomc_canonical_key(dt):
    """FOMC 중복 제거용: ET 공식 결정 날짜만 키로 사용."""
    try:
        from zoneinfo import ZoneInfo
        return dt.astimezone(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return dt.date().isoformat()


CORE_ECONOMIC_EVENT_RULES = (
    (("consumer price index", "cpi"), "#미국 CPI 소비자물가지수"),
    (("producer price index", "ppi"), "#미국 PPI 생산자물가지수"),
    (("employment situation", "nonfarm payroll", "non-farm payroll", "jobs report"), "#미국 고용보고서"),
    (("initial jobless claims", "initial claims", "jobless claims", "weekly unemployment claims"), "#미국 신규실업수당청구건수"),
    (("personal income and outlays", "pce", "personal consumption expenditures"), "#미국 PCE 물가지수"),
    (("gross domestic product", "gdp"), "#미국 GDP"),
    (("fomc", "federal funds", "fed interest rate", "rate decision"), "#미국 FOMC 기준금리 결정"),
    (("ism manufacturing", "manufacturing pmi"), "#미국 ISM 제조업 PMI"),
    (("ism services", "ism non-manufacturing", "services pmi"), "#미국 ISM 서비스업 PMI"),
    (("retail sales", "advance retail sales"), "#미국 소매판매"),
    (("new home sales", "new residential sales"), "#미국 신규주택판매"),
    (("housing starts", "housing start"), "#미국 주택착공"),
    (("building permits", "building permit"), "#미국 건축허가"),
    (("jolts", "job openings and labor turnover"), "#미국 JOLTS 고용"),
    (("adp employment", "adp nonfarm employment", "employment change"), "#미국 ADP 고용"),
    (("crude oil", "crude oil inventories", "crude oil stocks", "weekly petroleum status", "eia petroleum"), "#미국 원유재고"),
)


def _parse_financecalendar_datetime(row):
    """Finance Calendar JSON의 UTC 시간을 KST datetime으로 변환한다."""
    try:
        value = row.get("time_utc") or row.get("datetime_utc") or row.get("datetime")
        if value:
            text_value = str(value).strip()
            if text_value.endswith("Z"):
                dt = datetime.datetime.fromisoformat(text_value[:-1] + "+00:00")
            else:
                dt = datetime.datetime.fromisoformat(text_value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
            kst = datetime.timezone(datetime.timedelta(hours=9))
            return dt.astimezone(kst)

        date_text = str(row.get("date") or "").strip()
        time_text = str(row.get("time_et") or row.get("time") or "").strip()
        if date_text and time_text:
            from zoneinfo import ZoneInfo
            et = ZoneInfo("America/New_York")
            kst = datetime.timezone(datetime.timedelta(hours=9))
            base_date = datetime.date.fromisoformat(date_text[:10])
            m = re.match(r"^(\d{1,2}):(\d{2})\s*(AM|PM)$", time_text, re.I)
            if m:
                hour = int(m.group(1)) % 12 + (12 if m.group(3).upper() == "PM" else 0)
                minute = int(m.group(2))
            else:
                m24 = re.match(r"^(\d{1,2}):(\d{2})$", time_text)
                if not m24:
                    return None
                hour, minute = int(m24.group(1)), int(m24.group(2))
            return datetime.datetime.combine(base_date, datetime.time(hour, minute), tzinfo=et).astimezone(kst)
    except Exception:
        return None
    return None


def _match_core_economic_event(row):
    raw = " ".join(str(row.get(k) or "") for k in ("name", "title", "event", "series", "category")).strip()
    normalized = raw.lower()

    # FOMC는 일반 키워드 매칭을 사용하지 않는다.
    # "federal funds" / "rate decision"가 다른 금리 관련 일정까지 잡는 것을 막고,
    # Finance Calendar의 series/title이 실제 FOMC 결정인 경우만 통과시킨다.
    series = str(row.get("series") or "").strip().lower()
    title = str(row.get("title") or row.get("name") or row.get("event") or "").strip().lower()
    is_fomc = (
        series == "fomc"
        or "fomc rate decision" in title
        or title == "fomc decision"
        or title.startswith("fomc decision ")
    )
    if is_fomc:
        return "#미국 FOMC 기준금리 결정"

    # FOMC 관련 문자열인데 공식 FOMC 결정이 아닌 경우는 버린다.
    if "fomc" in normalized or "federal funds" in normalized or "fed interest rate" in normalized:
        return None

    for keywords, label in CORE_ECONOMIC_EVENT_RULES:
        # FOMC 규칙은 위에서 별도 처리했으므로 여기서는 건너뛴다.
        if label == "#미국 FOMC 기준금리 결정":
            continue
        if any(keyword in normalized for keyword in keywords):
            return label
    return None


def _fetch_dynamic_calendar_events():
    """경제일정 1곳 + 실적 1곳만 조회한다.

    경제일정은 Finance Calendar의 통합 피드를 한 번 호출하고,
    실적은 기존 Finnhub earnings 캘린더만 유지한다.
    /analyze가 호출될 때마다 API를 호출하지 않고 캐시에 저장한다.
    """
    kst_tz = datetime.timezone(datetime.timedelta(hours=9))
    now_kst = datetime.datetime.now(kst_tz)
    start_date, end_date = _calendar_week_window(now_kst)

    economic_events = []
    finance_url = (
        f"{FINANCE_CALENDAR_BASE_URL}/calendar"
        f"?from={urllib.parse.quote(start_date.isoformat())}"
        f"&to={urllib.parse.quote(end_date.isoformat())}"
        f"&limit=500"
    )
    try:
        payload = _http_json(finance_url, 6.0)
        rows = payload.get("events", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            rows = []
        print(f"[시장 일정] FinanceCalendar 원본: {len(rows)}건")
        for row in rows:
            if not isinstance(row, dict):
                continue
            country = str(row.get("country") or row.get("country_name") or "").lower()
            if country and country not in {"united states", "us", "usa", "u.s.", "u.s.a."}:
                continue
            label = _match_core_economic_event(row)
            if not label:
                continue
            dt = _parse_financecalendar_datetime(row)
            if not dt:
                continue
            if not (start_date <= dt.date() <= end_date):
                continue
            if label == "#미국 FOMC 기준금리 결정" and not _is_official_fomc_decision(dt):
                print(f"[시장 일정] FOMC 비공식/중복 일정 제외: {dt.isoformat()} / {row.get('title') or row.get('name') or ''}")
                continue
            economic_events.append({
                "dt": dt,
                "name": label,
                "type": "economic",
                "impact": str(row.get("impact") or "high").lower(),
                "original_title": row.get("title") or row.get("name") or row.get("event") or "",
            })
        print(f"[시장 일정] FinanceCalendar 핵심 통과: {len(economic_events)}건")
    except Exception as exc:
        print(f"[시장 일정] FinanceCalendar 실패: {type(exc).__name__}: {exc}")

    # 실적은 Finnhub earnings API 1곳만 유지한다.
    earnings_events = []
    if FINNHUB_KEY:
        earnings_url = (
            "https://finnhub.io/api/v1/calendar/earnings"
            f"?from={urllib.parse.quote(start_date.isoformat())}"
            f"&to={urllib.parse.quote(end_date.isoformat())}"
            f"&international=false&token={urllib.parse.quote(FINNHUB_KEY)}"
        )
        try:
            earn_payload = _http_json(earnings_url, 3.0)
            earnings_rows = earn_payload.get("earningsCalendar", []) if isinstance(earn_payload, dict) else []
            print(f"[시장 일정] 실적 원본 건수: {len(earnings_rows)}")
            watch = set(CALENDAR_WATCH_SYMBOLS)
            for row in earnings_rows:
                symbol = str(row.get("symbol") or "").upper()
                if symbol not in watch:
                    continue
                dt = _earnings_datetime_kst(row.get("date"), str(row.get("hour") or "").lower())
                if not dt:
                    continue
                earnings_events.append({
                    "dt": dt,
                    "name": "",
                    "type": "earnings",
                    "source": "earnings",
                    "symbol": symbol,
                    "hour": str(row.get("hour") or "").lower(),
                    "eps_estimate": row.get("epsEstimate"),
                    "revenue_estimate": row.get("revenueEstimate"),
                })
            print(f"[시장 일정] 주요 실적 통과: {len(earnings_events)}건")
        except Exception as exc:
            print(f"[시장 일정] 실적 API 실패: {type(exc).__name__}: {exc}")
    else:
        print("[시장 일정] FINNHUB_KEY 없음 - 실적 캘린더 생략")

    events = economic_events + earnings_events
    dedup = {}
    for ev in events:
        if ev.get("name") == "#미국 FOMC 기준금리 결정":
            key = ("economic", "#미국 FOMC 기준금리 결정", _fomc_canonical_key(ev["dt"]))
        else:
            key = (
                ev.get("type"),
                ev.get("symbol") or ev.get("name"),
                ev["dt"].strftime("%Y-%m-%dT%H:%M")
            )
        dedup[key] = ev
    events = sorted(dedup.values(), key=lambda x: x["dt"])

    # 너무 먼 일정까지 늘리지 않고, 사용자가 보는 다음 5개 날짜 안에서 핵심 일정만 최대 20개 유지
    selected = [e for e in events if e.get("type") in {"economic", "earnings"}][:20]
    print(f"[시장 일정] 경제 {len(economic_events)} + 실적 {len(earnings_events)} -> 최종 {len(selected)}건")
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
    """서버 시작 시 시장 일정은 외부 원본에서 받아 프로세스 메모리에만 보관한다."""
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
    # 기존 캐시에 남아 있을 수 있는 "#미국 " 접두사도 화면에서는 제거한다.
    raw = re.sub(r"^#?\s*미국\s*", "", raw).strip()
    normalized = raw.lower()
    economic_map = [
        (("fomc", "federal funds", "fed interest rate"), "#FOMC 기준금리 결정"),
        (("consumer price index", "cpi"), "#CPI 소비자물가지수"),
        (("producer price index", "ppi"), "#PPI 생산자물가지수"),
        (("employment situation", "nonfarm payroll", "non-farm payroll"), "#고용보고서"),
        (("unemployment rate",), "#실업률"),
        (("gross domestic product", "gdp"), "#GDP"),
        (("personal income and outlays", "pce", "core pce"), "#PCE 물가지수"),
        (("retail sales",), "#소매판매"),
        (("ism manufacturing",), "#ISM 제조업"),
        (("ism services", "ism non-manufacturing"), "#ISM 서비스업"),
        (("job openings and labor turnover", "jolts"), "#JOLTS 고용"),
        (("adp employment", "employment change"), "#ADP 고용"),
    ]
    for keys, label in economic_map:
        if any(key in normalized for key in keys):
            return label
    return f"#{raw}"


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


def _attach_news_price_reactions(news_result):
    """Attach up to three post-news price reactions per central issue brief."""
    if not isinstance(news_result, dict):
        return news_result

    briefs = news_result.get("issue_briefs") or []
    if not briefs:
        return news_result

    requests_by_brief = [[] for _ in briefs]
    unique_requests = {}
    for brief_index, brief in enumerate(briefs):
        published_at = str(brief.get("reaction_at") or "").strip()
        if not published_at:
            continue
        for stock_name in (brief.get("stock_names") or [])[:3]:
            name = str(stock_name or "").strip()
            ticker = TICKERS.get(name)
            if not name or not ticker:
                continue
            cache_key = (ticker, published_at)
            requests_by_brief[brief_index].append((name, cache_key))
            unique_requests.setdefault(cache_key, (ticker, published_at))

    reaction_cache = {}
    if unique_requests:
        with ThreadPoolExecutor(max_workers=min(3, len(unique_requests))) as pool:
            futures = {
                cache_key: pool.submit(fetch_news_price_reaction, ticker, published_at)
                for cache_key, (ticker, published_at) in unique_requests.items()
            }
            for cache_key, future in futures.items():
                try:
                    reaction_cache[cache_key] = future.result()
                except Exception as exc:
                    ticker, _ = unique_requests[cache_key]
                    print(f"[뉴스 반응] {ticker} 계산 예외: {type(exc).__name__}: {exc}")
                    reaction_cache[cache_key] = None

    for brief, requests in zip(briefs, requests_by_brief):
        reactions = []
        for name, cache_key in requests:
            reaction = reaction_cache.get(cache_key)
            if not reaction or reaction.get("status") != "ready":
                continue
            low_pct = reaction.get("low_pct")
            high_pct = reaction.get("high_pct")
            if not all(
                isinstance(value, (int, float)) and math.isfinite(value)
                for value in (low_pct, high_pct)
            ):
                continue

            reaction_item = {
                "name": name,
                "low_pct": low_pct,
                "high_pct": high_pct,
            }
            close_pct = reaction.get("close_pct")
            if isinstance(close_pct, (int, float)) and math.isfinite(close_pct):
                reaction_item["close_pct"] = close_pct

            # Keep the old field in the shared result for compatibility with
            # any non-central consumers, but the central row no longer renders it.
            change_pct = reaction.get("change_pct")
            if isinstance(change_pct, (int, float)) and math.isfinite(change_pct):
                reaction_item["change_pct"] = change_pct

            reactions.append(reaction_item)
        # No waiting/error placeholder: unavailable reaction data stays invisible.
        brief["stock_reactions"] = reactions

    return news_result


def analyze_stock(raw_name='SK하이닉스', ticker_symbol_override=None, news_name_override=None):
    raw_name = str(raw_name or 'SK하이닉스').strip()
    ticker_symbol = ticker_symbol_override or TICKERS.get(raw_name)
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
            return {
                "sections": [
                    {
                        "id": "analysis-error",
                        "title": "종목을 찾을 수 없습니다.",
                        "content": f"{raw_name} 종목을 확인하지 못했습니다. 종목명이나 티커를 다시 확인해주세요."
                    }
                ],
                "paired_news_items": [],
                "storyboard_news_items": [],
                "issue_briefs": [],
                "keyword_storyboard": [],
                "disclosures": [],
                "us_filings": [],
                "ok": False,
            }

        is_krw = ('-' not in ticker_symbol and ticker_symbol.endswith(('.KS', '.KQ'))) or (clean_code and len(clean_code) == 6)

        current_price = 0.0
        change_pct = 0.0
        volume_profile = None

        # 1~2. 외부 API는 한 요청 안에서 순차 처리한다.
        # 이전 구조는 여러 외부 API를 ThreadPoolExecutor에 동시에 넣은 뒤
        # timeout이 나도 실행 중인 작업이 남아 다음 요청과 겹칠 수 있었다.
        # Render/Gunicorn에서는 이 누적이 반복 검색 시 502로 이어질 수 있어
        # 요청마다 외부 작업이 남지 않도록 직접 호출한다.
        if is_krw and clean_code:
            analyze_started = time.monotonic()
            def _trace_stage(stage, started):
                print(f"[analyze trace] stock={raw_name} stage={stage} elapsed={time.monotonic() - started:.2f}s total={time.monotonic() - analyze_started:.2f}s", flush=True)

            stage_started = time.monotonic()
            print(f"[analyze trace] stock={raw_name} stage=realtime start", flush=True)
            price_result = fetch_stock_price_result(
                is_krw=True,
                ticker_symbol=ticker_symbol,
                clean_code=clean_code,
            )
            cur_p = price_result["current_price"]
            _trace_stage("realtime done", stage_started)

            stage_started = time.monotonic()
            print(f"[analyze trace] stock={raw_name} stage=news start", flush=True)
            news_result = get_shared_stock_news_result(
                raw_name,
                market="국내",
                limit=50,
            )
            news_result = _attach_news_price_reactions(news_result)
            _trace_stage("news done", stage_started)

            stage_started = time.monotonic()
            print(f"[analyze trace] stock={raw_name} stage=dart start", flush=True)
            try:
                kr_official_disclosures = fetch_kr_official_disclosures(clean_code, days=30, max_results=30)
                # DART 임원·주요주주 상세(elestock)도 외부 API 호출이라 지연 시
                # /analyze 전체 worker를 막을 수 있다. 핵심 응답에서는 공시 목록을
                # 우선 반환하고 상세 조회는 공시 전용 경로에서 처리한다.
                # DART 원문 document.xml 전체 파싱은 큰 공시에서 Gunicorn worker를
                # 장시간 점유할 수 있다. /analyze 핵심 응답에서는 원문 상세를 동기
                # 파싱하지 않고 목록/구조화 공시 결과를 우선 반환한다.
            except Exception as e:
                print(f"[국내 공시] fail: {type(e).__name__}: {e}")
                kr_official_disclosures = []
            _trace_stage("dart done", stage_started)

            stage_started = time.monotonic()
            print(f"[analyze trace] stock={raw_name} stage=volume_profile start", flush=True)
            try:
                volume_profile = fetch_kr_historical_volume_profile(ticker_symbol, current_price=cur_p)
            except Exception as e:
                print(f"[매물대] fail: {type(e).__name__}: {e}")
                volume_profile = None
            _trace_stage("volume_profile done", stage_started)

            kr_official_disclosures_block = format_kr_official_disclosures(clean_code, kr_official_disclosures)
            official_filings_block = ""

            # 현재가 원천만 stock_analysis 결과를 사용한다.
            current_price = price_result["current_price"]
            change_pct = price_result["change_pct"]
            price_str = price_result["price_text"]

        # 2. 미국 주식
        else:
            price_result = fetch_stock_price_result(
                is_krw=False,
                ticker_symbol=ticker_symbol,
            )
            cur_p = price_result["current_price"]

            try:
                _, _, _, _, volume_profile = fetch_yahoo_direct_v8(ticker_symbol)
            except Exception as e:
                print(f"[미국 시세] fail: {type(e).__name__}: {e}")
                volume_profile = None

            news_result = get_shared_stock_news_result(
                news_name_override or raw_name,
                market="미국",
                limit=50,
            )
            news_result = _attach_news_price_reactions(news_result)

            try:
                us_filings_raw = fetch_us_official_filings(ticker_symbol, days=30, max_results=30)
            except Exception as e:
                print(f"[미국 공시] fail: {type(e).__name__}: {e}")
                us_filings_raw = []

            official_filings_block = format_us_official_filings(ticker_symbol, us_filings_raw)
            kr_official_disclosures_block = ""

            current_price = price_result["current_price"]
            change_pct = price_result["change_pct"]
            if current_price <= 0:
                volume_profile = None
                print(f"[미국 주가] {ticker_symbol} 조회 실패 - 가짜 가격 사용 안 함")

            price_str = price_result["price_text"]
        # 3. 등락률 분기 (불필요한 멘트 삭제 완료)
        if change_pct >= 5.0:
            status_emoji, title_word = '🔥', '올랐어'
            intro_ment = f"오!! {raw_name} 상승중이야"
        elif 0.5 <= change_pct < 5.0:
            status_emoji, title_word = '🔥', '올랐어'
            intro_ment = "스멀스멀 우상향 중이야"
        elif -0.5 < change_pct < 0.5:
            status_emoji, title_word = '⚖️', '보합일까'
            intro_ment = f"하아.. {raw_name} 완전 눈치싸움 중이네"
        elif -5.0 < change_pct <= -0.5:
            status_emoji, title_word = '❄️', '숨고르기일까'
            intro_ment = f"아이고 {raw_name} 파란불 켜져서 속 쓰리겠다"
        else:
            status_emoji, title_word = '❄️', '빠질까'
            intro_ment = f"헐... {raw_name} 무섭게 빠지네"


        # 왼쪽 사이드바에 현재가/등락률이 있으므로 본문에서는 중복하지 않는다.
        # 본문 멘트는 유지하고 퍼센트는 기술지표(고가/저가/이평선)에만 표시한다.
        # 뉴스와 공시는 기존처럼 한 칸(빈 줄) 간격을 유지한다.
        # 뉴스/공시는 아래의 구조화된 클릭형 목록(paired_news_items / disclosures / us_filings)에서
        # 한 번만 표시한다. 본문에 같은 내용을 다시 넣으면 화면에 중복 출력된다.
        price_tags = list(price_result.get("price_tags") or [])
        tags_str = "   ".join(price_tags)

        first_content_parts = [intro_ment]
        price_metrics_text = str(price_result.get("first_reply_metrics_text") or "").strip()
        if price_metrics_text:
            first_content_parts.append(price_metrics_text)
        first_content_parts.append(tags_str)

        sections = [
            {
                "id": "why-up",
                "title": f"{status_emoji} 오늘은 왜 {title_word}?",
                "content": "\n\n".join(first_content_parts),
                "tags": [f"#{raw_name}", "#실시간속보"]
            }
        ]

        sections.extend([
            {
                "id": "levels",
                "title": "여기 깨지면 큰일인데?",
                "content": (
                    (lambda vp_text: (
                        (lambda lines: (
                            (
                                (next((line for line in lines if line.startswith("악성 매물대")), "악성 매물대 계산 대기")
                                 + "\n\n니가 사면 하락하제?\n과거 물린 형들 본전 탈출할 수 있는 구간이야!\n\n"
                                 + "#시체추가금지 #뇌동매수멈춰 #관망이답니다 #구경만해라\n\n"
                                 + next((line for line in lines if line.startswith("생존 매물대")), "생존 매물대 계산 대기")
                                 + "\n\n여기 깨지면 으악 소리 나겠지?\n여기서 밀리면 실망 매물 나올 수 있는 구간이야!!\n\n"
                                 + "#지지라인 #뇌동매수금지 #주식경고 #리스크관리 #멘탈관리")
                            )
                        ))(vp_text.splitlines())
                        if vp_text else
                        "악성 매물대 계산 대기\n\n니가 사면 하락하제?\n과거 물린 형들 본전 탈출할 수 있는 구간이야!\n\n"
                        "#시체추가금지 #뇌동매수멈춰 #관망이답니다 #구경만해라\n\n"
                        "생존 매물대 계산 대기\n\n여기 깨지면 으악 소리 나겠지?\n실망 매물 나올 수 있는 구간이야!!\n\n"
                        "#지지라인 #뇌동매수금지 #주식경고 #리스크관리 #멘탈관리"
                    ))(format_volume_profile(volume_profile, is_usd=not is_krw))
                ),
            },
            {
                "id": "calendar",
                "title": "오늘 밤, 이번주 무슨 일이 있어?",
                "content": get_live_calendar_data(raw_name, ticker_symbol)
            }
        ])
        disclosures = []
        if is_krw and clean_code:
            for item in score_disclosures(kr_official_disclosures or []):
                report_title = str(item.get("report", "")).strip()
                if raw_name and raw_name not in report_title:
                    report_title = f"{raw_name} {report_title}"
                disclosures.append({
                    "title": report_title,
                    "source": "DART",
                    "receipt_no": item.get("receipt_no", ""),
                    "stock_code": clean_code,
                    "report": item.get("report", ""),
                    "date": item.get("date", ""),
                    "time": item.get("time", ""),
                    "time_zone": item.get("time_zone", ""),
                    "receipt_datetime": item.get("receipt_datetime", ""),
                    "link": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={item.get('receipt_no', '')}" if item.get("receipt_no") else "",
                    "keywords": (
                        item.get("keywords", [])
                        + ([f"#{item.get('shareholding_change')}"] if item.get("shareholding_change") else [])
                    ),
                    "executive_shareholdings": item.get("executive_shareholdings", []),
                    "shareholding_change": item.get("shareholding_change", ""),
                    "shareholding_delta": item.get("shareholding_delta"),
                    "major_shareholder_change": item.get("major_shareholder_change", {}),
                })
        us_filings = []
        if not is_krw and ticker_symbol:
            for item in score_disclosures(us_filings_raw or []):
                us_filings.append({
                    "title": (
                        item.get("transaction_summary")
                        or item.get("transaction_kind")
                        or "내부자 거래"
                    ) if str(item.get("form", "")).upper() == "4" else (
                        item.get("event_title")
                        or item.get("description")
                        or "SEC 공시"
                    ),
                    "source": "SEC",
                    "date": item.get("date", ""),
                    "time": item.get("time", ""),
                    "time_zone": "ET" if item.get("time") else "",
                    "acceptance_datetime": item.get("acceptance_datetime", ""),
                    "link": item.get("url", ""),
                    "keywords": item.get("keywords", []),
                    "form": item.get("form", ""),
                    "item": item.get("item", ""),
                    "items": item.get("items", []),
                    "event_title": item.get("event_title", ""),
                    "key_points": item.get("key_points", []),
                    "key_points_ko": item.get("key_points_ko", []),
                    "person": item.get("person", ""),
                    "officer_title": item.get("officer_title", ""),
                    "transaction_kind": item.get("transaction_kind", ""),
                    "transaction_summary": item.get("transaction_summary", ""),
                    "transaction_count": item.get("transaction_count", 0),
                    "transactions": item.get("transactions", []),
                    "price_range": item.get("price_range", ""),
                })
        week_52 = (price_result.get("indicators") or {}).get("week_52") or {}
        current_quote = float(price_result.get("current_price") or 0)
        previous_high = float(week_52.get("high") or 0)
        price_snapshot = {
            "current": current_quote,
            "currency": "KRW" if is_krw else "USD",
            "change_pct": price_result.get("change_pct"),
            "change_pct_basis": "현재 표시가격의 직전 종가 대비 등락률",
            "previous_trading_day": price_result.get("previous_trading_day"),
            "week_52_high": previous_high,
        }
        if current_quote > 0 and previous_high > 0 and math.isfinite(current_quote) and math.isfinite(previous_high):
            price_snapshot["rise_to_52w_high_pct"] = round(
                max(0.0, (previous_high - current_quote) / current_quote * 100), 2
            )
        return {
            "sections": sections,
            "price_snapshot": price_snapshot,
            "paired_news_items": news_result.get("paired_news_items", []),
            "panel_news_items": news_result.get("panel_news_items", news_result.get("paired_news_items", [])),
            "storyboard_news_items": news_result.get("storyboard_news_items", []),
            "issue_briefs": news_result.get("issue_briefs", []),
            "keyword_storyboard": news_result.get("keyword_storyboard", []),
            "disclosures": disclosures,
            "us_filings": us_filings,
        }

    except Exception as e:
        print("전체 예외 안전 복구 가동:", e)
        return {
            "sections": [
                {
                    "id": "analysis-error",
                    "title": "⚠️ 분석 데이터를 확인하지 못했어",
                    "content": f"{raw_name} 분석에 필요한 데이터를 가져오지 못했어. 잠시 후 다시 시도해줘."
                }
            ],
            "paired_news_items": [],
            "storyboard_news_items": [],
            "issue_briefs": [],
            "keyword_storyboard": [],
            "disclosures": [],
            "us_filings": [],
            "ok": False
        }

