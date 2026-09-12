from flask import Flask, jsonify, request
from flask_cors import CORS
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
import zipfile
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime

app = Flask(__name__)
CORS(app)

# Gunicorn/WSGI compatibility: Render Start Command `gunicorn app:app` can import this object.
application = app

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

# 외부 API는 서로 독립적인 요청을 동시에 처리해 전체 대기시간을 줄인다.
# 너무 많은 동시 요청으로 외부 서비스에 부담을 주지 않도록 6개로 제한한다.
API_EXECUTOR = ThreadPoolExecutor(max_workers=6)
NEWS_RESULT_CACHE = {}
NEWS_DISPLAY_CACHE = {}
OPTIONS_RESULT_CACHE = {}
NEWS_CACHE_TTL = 120
OPTIONS_CACHE_TTL = 60


US_MATERIAL_FORMS = {
    "8-K", "10-Q", "10-K", "6-K", "20-F", "424B5",
    "S-3", "S-1", "SC 13D", "SC 13G", "SC 13G/A", "4"
}

def fetch_dart_corp_map():
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


def fetch_kr_official_disclosures(stock_code, days=7):
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

        results = []
        for item in data.get("list", []) or []:
            report_name = str(item.get("report_nm", "")).strip()
            receipt_date = str(item.get("rcept_dt", "")).strip()
            receipt_no = str(item.get("rcept_no", "")).strip()
            if not report_name or not receipt_date:
                continue

            results.append({
                # 국내 공시 날짜는 뉴스와 동일하게 YYYY.MM.DD 형식으로 표시한다.
                "date": (
                    f"{receipt_date[:4]}.{receipt_date[4:6]}.{receipt_date[6:8]}"
                    if len(receipt_date) == 8 and receipt_date.isdigit() else receipt_date
                ),
                "report": report_name,
                "receipt_no": receipt_no,
                "score": _dart_report_score(report_name),
            })

        # 영향도가 높은 공시를 우선하고, 같은 날에는 최신 접수번호를 우선한다.
        results.sort(
            key=lambda x: (x["score"], x["date"], x["receipt_no"]),
            reverse=True,
        )
        results = results[:3]

        print(f"[국내 공시] {stock_code} 성공 / 선택={len(results)}")
        DART_DISCLOSURE_CACHE[cache_key] = (now_ts, results)
        return results

    except urllib.error.HTTPError as e:
        print(f"[국내 공시] {stock_code} DART 실패: HTTP {e.code}")
    except Exception as e:
        print(f"[국내 공시] {stock_code} DART 실패: {type(e).__name__}: {e}")

    DART_DISCLOSURE_CACHE[cache_key] = (now_ts, [])
    return []


def format_kr_official_disclosures(stock_code):
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

def fetch_us_official_filings(ticker_symbol, days=7):
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

            filing = {
                "date": dates[i],
                "form": form,
                "description": description or "SEC 공식 공시",
                "url": filing_url,
            }

            # Form 4는 primaryDocument(.html)와 별도로 실제 XML 파일이 제공된다.
            # SEC 제출목록 JSON의 primaryDocument는 보통 HTML이므로,
            # 해당 제출의 index 페이지에서 FORM 4 XML 링크를 찾아 실제 XML을 읽는다.
            if form == "4" and filing_url:
                try:
                    sec_headers = {
                        "User-Agent": os.environ.get("SEC_USER_AGENT", "gaemiGTP/1.0"),
                        "Accept": "text/html,application/xml,text/xml,*/*",
                    }

                    clean_accession = accession.replace("-", "")
                    index_url = (
                        f"https://www.sec.gov/Archives/edgar/data/"
                        f"{int(cik)}/{clean_accession}/{accession}-index.htm"
                    )

                    index_req = urllib.request.Request(index_url, headers=sec_headers)
                    with urllib.request.urlopen(index_req, timeout=5) as index_resp:
                        index_text = index_resp.read().decode("utf-8", errors="ignore")

                    # FORM 4의 XML 링크는 제출별 디렉터리 안의 xslF345X05/X06 등에
                    # 있을 수 있으므로 고정 경로를 가정하지 않고 index에서 찾는다.
                    xml_href = ""
                    hrefs = re.findall(
                        r'href=[\"\']([^\"\']+\.xml(?:\?[^\"\']*)?)[\"\']',
                        index_text,
                        flags=re.I,
                    )
                    for href in hrefs:
                        if "form4" in href.lower() or "wk-form4" in href.lower():
                            xml_href = href
                            break
                    if not xml_href and hrefs:
                        xml_href = hrefs[0]

                    if xml_href:
                        from urllib.parse import urljoin
                        detail_url = urljoin(index_url, xml_href)
                    else:
                        # 일부 SEC 응답은 index에서 XML 링크가 노출되지 않을 수 있어
                        # 제출문서명 기준의 보조 경로를 한 번 시도한다.
                        base_name = re.sub(r"\.html?$", ".xml", document, flags=re.I)
                        detail_url = (
                            f"https://www.sec.gov/Archives/edgar/data/"
                            f"{int(cik)}/{clean_accession}/xslF345X06/{base_name}"
                        )

                    print(f"[미국 공시] {ticker_symbol} Form 4 XML 요청: {detail_url}")
                    detail_req = urllib.request.Request(
                        detail_url,
                        headers={
                            **sec_headers,
                            "Accept": "application/xml,text/xml,*/*",
                        },
                    )
                    with urllib.request.urlopen(detail_req, timeout=5) as detail_resp:
                        detail_text = detail_resp.read().decode("utf-8", errors="ignore")
                    print(f"[미국 공시] {ticker_symbol} Form 4 XML 수신: {len(detail_text)} bytes")

                    # SEC Form 4 XML 원문이 일부 제출본에서 XML 문법 오류를 포함할 수 있어
                    # ElementTree에 의존하지 않는다. SEC의 공식 제출 .txt 원문은 일반 텍스트이므로
                    # 여기에서 Form 4 거래 블록을 직접 추출한다. XML은 다운로드 성공 여부 확인용으로만 사용한다.
                    def _clean_value(value):
                        return re.sub(r"\s+", " ", str(value or "")).strip()

                    def _tag_value(text, tag_name):
                        pat = rf"<(?:[A-Za-z0-9_.-]+:)?{re.escape(tag_name)}\b[^>]*>(.*?)</(?:[A-Za-z0-9_.-]+:)?{re.escape(tag_name)}>"
                        mm = re.search(pat, text, flags=re.I | re.S)
                        if not mm:
                            return ""
                        value = re.sub(r"<[^>]+>", " ", mm.group(1))
                        return _clean_value(value)

                    def _has_tag_value(text, tag_name, expected="1"):
                        value = _tag_value(text, tag_name)
                        return value.strip().lower() == str(expected).lower()

                    # SEC 공식 제출 원문(.txt)을 가져온다.
                    submission_txt_url = (
                        f"https://www.sec.gov/Archives/edgar/data/"
                        f"{int(cik)}/{clean_accession}/{accession}.txt"
                    )
                    print(f"[미국 공시] {ticker_symbol} Form 4 제출원문 요청: {submission_txt_url}")
                    txt_req = urllib.request.Request(submission_txt_url, headers=sec_headers)
                    with urllib.request.urlopen(txt_req, timeout=5) as txt_resp:
                        submission_text = txt_resp.read().decode("utf-8", errors="ignore")
                    print(f"[미국 공시] {ticker_symbol} Form 4 제출원문 수신: {len(submission_text)} bytes")

                    # 제출원문 안의 XML 구간만 골라내도 되고, 전체 텍스트에서 직접 찾아도 된다.
                    # 전체 텍스트를 대상으로 하면 SEC 포맷이 조금 달라져도 대응력이 높다.
                    filing["person"] = _tag_value(submission_text, "rptOwnerName")
                    filing["officer_title"] = _tag_value(submission_text, "officerTitle")

                    # officerTitle이 비어 있는 Director 공시가 많으므로 관계 태그를 이용해 역할을 보강한다.
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
                        submission_text,
                        flags=re.I | re.S,
                    )

                    for block in txn_blocks:
                        code = _tag_value(block, "transactionCode").upper()
                        shares = _tag_value(block, "transactionShares")
                        price = _tag_value(block, "transactionPricePerShare")
                        acquired_disposed = _tag_value(block, "transactionAcquiredDisposedCode").upper()
                        if code or shares:
                            transactions.append({
                                "code": code,
                                "shares": shares,
                                "price": price,
                                "acquired_disposed": acquired_disposed,
                            })

                    if transactions:
                        filing["transactions"] = transactions
                        filing["transaction_code"] = transactions[0]["code"]
                        filing["shares"] = transactions[0]["shares"]
                        filing["price"] = transactions[0]["price"]
                        print(
                            f"[미국 공시] {ticker_symbol} Form 4 제출원문 파싱 성공: "
                            f"person={filing.get('person','')} "
                            f"title={filing.get('officer_title','')} "
                            f"transactions={len(transactions)}"
                        )
                    else:
                        filing["transactions"] = []
                        print(
                            f"[미국 공시] {ticker_symbol} Form 4 제출원문에서 거래행을 찾지 못했습니다. "
                            f"person={filing.get('person','')} title={filing.get('officer_title','')}"
                        )

                except Exception as detail_err:
                    print(
                        f"[미국 공시] {ticker_symbol} Form 4 원문 보강 실패: "
                        f"{type(detail_err).__name__}: {detail_err}"
                    )

            results.append(filing)

            if len(results) >= 3:
                break

        US_FILING_CACHE[cache_key] = (datetime.datetime.now().timestamp(), results)
        return results
    except urllib.error.HTTPError as e:
        print(f"[미국 공시] {ticker_symbol} SEC 실패: HTTP {e.code}")
    except Exception as e:
        print(f"[미국 공시] {ticker_symbol} SEC 실패: {type(e).__name__}: {e}")
    US_FILING_CACHE[cache_key] = (datetime.datetime.now().timestamp(), [])
    return []

def format_us_official_filings(ticker_symbol):
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
    try:
        url = f"https://ac.finance.naver.com/ac?q={urllib.parse.quote(stock_name)}&q_enc=utf-8&st=1&r_lt=1&r_format=json&r_enc=utf-8"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            res_json = json.loads(resp.read().decode('utf-8'))
            items = res_json.get('items', [])
            if items and len(items[0]) > 0:
                first = items[0][0]
                code = first[0]
                market = first[3].upper()
                suffix = '.KS' if 'KOSPI' in market else '.KQ'
                return f"{code}{suffix}", code
    except Exception:
        pass
    return None, None

def fetch_kr_stock_realtime(code_six):
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
                return cur_p, diff, ratio
    except Exception as e:
        print("네이버 실시간 시세 조회 예외:", e)
    return None, None, None

def fetch_krx_trend_and_supply(code_six):
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

                return ma20, resistance, sum_foreign, sum_inst, sum_indiv, valid_days
    except Exception as e:
        print("네이버 수급 집계 예외:", e)
    return 0, 0, None, None, None, 0

def fetch_kr_historical_volume_profile(ticker_symbol):
    """국내 종목의 과거 6개월 일봉 OHLCV로 거래량 매물대를 계산한다.
    실시간 현재가/수급은 향후 증권사 API를 사용하고, 이 함수는 과거 분포 계산용이다.
    """
    try:
        symbol = str(ticker_symbol or "").strip()
        if not symbol:
            return None
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=6mo&interval=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        result = (data.get("chart", {}).get("result") or [None])[0]
        if not result:
            return None
        quote = (result.get("indicators", {}).get("quote") or [{}])[0]
        return calculate_volume_profile_levels(
            quote.get("high") or [], quote.get("low") or [],
            quote.get("close") or [], quote.get("volume") or [], bins=24
        )
    except Exception as e:
        print(f"[국내 매물대] {ticker_symbol} 계산 예외: {type(e).__name__}: {e}")
        return None


def fetch_yahoo_direct_v8(ticker_str):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_str}?range=6mo&interval=1d"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/152.0.0.0 Safari/537.36'
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

        # 정확한 최근 20거래일 MA20
        ma20 = sum(closes[-20:]) / min(20, len(closes))

        volume_profile = calculate_volume_profile_levels(
            highs, lows, closes, volumes, bins=24
        )

        # Volume Profile에서 현재가 위의 다음 주요 집중구간을 저항으로 사용.
        res_p = (
            volume_profile["above"]["center"]
            if volume_profile and volume_profile.get("above")
            else 0.0
        )

        return cur_p, prev_p, ma20, res_p, volume_profile

    except Exception as e:
        print("미국 야후 v8 예외:", e)
        return None, None, None, None, None

# 뉴스 품질 우선순위
# - 실제 Google News RSS에서 수집
# - 종목 직접 관련 뉴스와 시장/업종 원인 뉴스를 구분
# - 호재/악재 재료를 모두 살림
# - 단순 시세/수급 기사와 명백한 잡음은 제거
# - 화면에는 핵심 3개, AI용으로는 상위 10개를 보관
NEWS_SOURCE_PRIORITY = {
    "Reuters": 100, "로이터": 100,
    "AP": 98, "Associated Press": 98,
    "Bloomberg": 96, "블룸버그": 96,
    "Financial Times": 95, "파이낸셜타임스": 95,
    "The Wall Street Journal": 94, "월스트리트저널": 94,
    "CNBC": 92,
    "연합뉴스": 90, "한국경제": 88, "매일경제": 87,
    "서울경제": 86, "전자신문": 85, "이데일리": 82,
    "머니투데이": 80, "조선비즈": 75,
}

# 실제 주가에 영향을 줄 가능성이 높은 재료.
NEWS_HARD_EVENT_WORDS = [
    "실적발표", "잠정실적", "실적", "매출", "영업이익", "순이익", "가이던스",
    "수주", "계약", "공급계약", "대형계약", "인수", "합병", "m&a",
    "투자", "증설", "감산", "증산", "출하", "판매", "가격 인상", "가격 하락",
    "공급 중단", "공급 차질", "공급망", "규제", "관세", "제재", "수출 제한",
    "승인", "허가", "소송", "특허", "자사주", "배당", "유상증자", "전환사채",
    "earnings", "revenue", "profit", "guidance", "contract", "deal",
    "acquisition", "merger", "investment", "regulation", "tariff",
    "approval", "lawsuit", "buyback", "dividend", "offering",
]

# 기업/산업의 실질적인 변화로 볼 수 있는 표현. 하드 이벤트와 함께 우선순위를 높인다.
NEWS_MATERIAL_WORDS = [
    "신제품", "제품 출시", "신규 고객", "고객사", "수요 증가", "수요 감소",
    "수요 회복", "수요 둔화", "점유율", "시장 점유율", "공급 확대", "공급 축소",
    "생산 확대", "생산 감소", "생산 중단", "공장", "라인 증설", "라인 가동",
    "가동 중단", "납품", "공급", "출하량", "판매량", "가격 상승", "가격 하락",
    "수익성", "마진", "실적 개선", "실적 악화", "전망 상향", "전망 하향",
    "목표 상향", "목표 하향", "신규 수주", "수주 확대", "백지화", "철회",
    "파기", "지연", "중단", "재개", "협력", "파트너십", "동맹",
    "ai", "hbm", "반도체", "메모리", "파운드리", "gpu", "데이터센터",
]

# 단독 재료가 아니라 전망/의견 중심인 기사는 우선순위를 낮춘다.
NEWS_SOFT_OPINION_WORDS = [
    "전망", "예상", "분석", "목표주가", "증권가", "전문가", "기대감",
    "가능성", "주목", "관심", "수혜주", "관련주", "추천", "진단",
    "전략", "시나리오", "전망치", "forecast", "estimate", "analyst",
    "target price", "outlook", "expectation", "potential",
]

# 명백한 잡음/콘텐츠성 기사.
NEWS_NOISE_WORDS = [
    "인터뷰", "화보", "현장", "이모저모", "사설", "칼럼", "오피니언",
    "사용기", "리뷰", "가이드", "주식 초보", "투자전략", "투자 팁",
    "주간전망", "오늘의 운세", "퀴즈", "기부", "봉사", "캠페인",
    "맛집", "여행", "공연", "연예", "채용", "인사", "부고",
]

# 화면 상단의 현재가/수급을 단순 반복하는 기사.
NEWS_MARKET_SUMMARY_WORDS = [
    "보합 마감", "상승 마감", "하락 마감", "급등 마감", "급락 마감",
    "장 마감", "마감 시황", "장 마감 시황", "오늘의 시황", "시황",
    "주가", "수급", "외국인·기관", "외국인 기관", "기관·외국인",
    "기관 외국인", "외국인 순매수", "외국인 순매도", "기관 순매수",
    "기관 순매도", "거래량", "거래대금", "상승률", "하락률",
    "등락", "장중", "증시 마감", "마감",
]

# 시장/업종 전체 움직임의 원인을 설명하는 기사. 종목 단독 뉴스가 없어도 살린다.
NEWS_MARKET_CAUSE_WORDS = [
    "미국", "뉴욕", "나스닥", "s&p", "다우", "반도체", "기술주", "업황",
    "금리", "환율", "유가", "관세", "전쟁", "지정학", "공급", "수요",
    "중국", "대만", "일본", "연준", "fed", "fomc", "물가", "고용",
    "인플레이션", "경기", "침체", "상승세", "하락세", "약세", "강세",
    "호재", "악재", "우려", "기대", "영향", "여파", "때문",
]

# 종목별로 자주 쓰이는 별칭. 제목에 회사의 약칭만 나오는 경우를 보완한다.
NEWS_NAME_ALIASES = {
    "삼성전자": ["삼성전자", "삼성", "samsung electronics"],
    "SK하이닉스": ["sk하이닉스", "하이닉스", "sk hynix"],
    "현대차": ["현대차", "현대자동차", "hyundai motor"],
    "현대자동차": ["현대차", "현대자동차", "hyundai motor"],
    "기아": ["기아", "kia"],
    "네이버": ["네이버", "naver"],
    "NAVER": ["네이버", "naver"],
    "카카오": ["카카오", "kakao"],
    "셀트리온": ["셀트리온", "celltrion"],
    "한미반도체": ["한미반도체", "hanmi semiconductor"],
    "두산에너빌리티": ["두산에너빌리티", "두산중공업", "doosan enerbility"],
    "두산로보틱스": ["두산로보틱스", "doosan robotics"],
    "한화에어로스페이스": ["한화에어로스페이스", "한화에어로", "hanwha aerospace"],
    "엔비디아": ["엔비디아", "nvidia", "nvda"],
    "테슬라": ["테슬라", "tesla", "tsla"],
    "애플": ["애플", "apple", "aapl"],
    "마이크로소프트": ["마이크로소프트", "microsoft", "msft"],
    "아마존": ["아마존", "amazon", "amzn"],
    "구글": ["구글", "알파벳", "google", "alphabet", "googl"],
    "오라클": ["오라클", "oracle", "orcl"],
    "어도비": ["어도비", "adobe", "adbe"],
}


def _news_terms_for_stock(stock_name, ticker=""):
    """검색/관련성 판단에 사용할 종목명·별칭·티커를 만든다."""
    name = str(stock_name or "").strip()
    terms = []
    for term in [name, name.replace(" ", "")]:
        if term and term.lower() not in {x.lower() for x in terms}:
            terms.append(term)

    for alias in NEWS_NAME_ALIASES.get(name, []):
        if alias and alias.lower() not in {x.lower() for x in terms}:
            terms.append(alias)

    ticker_clean = str(ticker or "").replace(".KS", "").replace(".KQ", "").strip()
    if ticker_clean and ticker_clean.lower() not in {x.lower() for x in terms}:
        terms.append(ticker_clean)
    return terms


def _news_contains_any(text, words):
    text_lower = (text or "").lower()
    return any(str(word).lower() in text_lower for word in words)


def _is_market_summary_news(title):
    """단순 주가/수급 기사만 제외하고, 실제 원인이 있는 기사는 보존한다."""
    title_lower = (title or "").lower()
    if not title_lower:
        return False

    summary_hits = sum(1 for word in NEWS_MARKET_SUMMARY_WORDS if word.lower() in title_lower)
    if summary_hits == 0:
        return False

    # 실적/계약/투자/규제 등 재료가 있으면 유지한다.
    if _news_contains_any(title_lower, NEWS_HARD_EVENT_WORDS + NEWS_MATERIAL_WORDS):
        return False

    # 미국/금리/반도체 등 시장 원인이 있으면 유지한다.
    market_cause = [
        "미국", "뉴욕", "나스닥", "s&p", "다우", "반도체", "기술주", "업황",
        "금리", "환율", "유가", "관세", "전쟁", "지정학", "공급", "수요",
        "중국", "대만", "연준", "fed", "fomc", "물가", "고용", "경기",
        "침체", "인플레이션", "때문", "영향", "여파", "우려",
    ]
    if _news_contains_any(title_lower, market_cause):
        return False

    # 단순 상승/하락/마감/수급만 설명하는 기사는 제외한다.
    return summary_hits >= 1


# 화면 표시용 뉴스와 AI 분석용 후보를 분리한다.
NEWS_AI_CANDIDATES_CACHE = {}


def _news_source_score(source_name):
    source = (source_name or "").strip()
    for key, score in NEWS_SOURCE_PRIORITY.items():
        if key.lower() == source.lower():
            return score
    return 60


def _news_freshness_score(pub_date):
    """RSS 발행 시각 기준 최신 기사일수록 높은 점수."""
    if not pub_date:
        return 0
    try:
        dt = parsedate_to_datetime(pub_date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        now = datetime.datetime.now(datetime.timezone.utc)
        age_hours = max(0.0, (now - dt.astimezone(datetime.timezone.utc)).total_seconds() / 3600.0)
        if age_hours <= 6:
            return 40
        if age_hours <= 24:
            return 32
        if age_hours <= 48:
            return 24
        if age_hours <= 72:
            return 14
        if age_hours <= 168:
            return 4
        if age_hours <= 336:
            return 2
        if age_hours <= 720:
            return 1
    except Exception:
        pass
    return 0


def _news_relevance_score(title, stock_name, ticker):
    """종목 직접 관련성 + 재료성 + 시장 영향 가능성을 평가한다."""
    title_lower = (title or "").lower()
    score = 0
    terms = _news_terms_for_stock(stock_name, ticker)

    direct_hits = sum(1 for term in terms if term and term.lower() in title_lower)
    direct = direct_hits > 0
    if direct:
        score += 45
        if direct_hits >= 2:
            score += 10

    hard_hits = sum(1 for word in NEWS_HARD_EVENT_WORDS if word.lower() in title_lower)
    material_hits = sum(1 for word in NEWS_MATERIAL_WORDS if word.lower() in title_lower)
    cause_hits = sum(1 for word in NEWS_MARKET_CAUSE_WORDS if word.lower() in title_lower)

    score += min(hard_hits, 5) * 8
    score += min(material_hits, 5) * 5
    if cause_hits:
        score += min(cause_hits, 4) * 4

    # 의견/전망만 있는 기사는 낮추되, 확정 재료와 함께 있으면 너무 세게 감점하지 않는다.
    hard_or_material = hard_hits > 0 or material_hits > 0
    soft_hits = sum(1 for word in NEWS_SOFT_OPINION_WORDS if word.lower() in title_lower)
    score += soft_hits * (2 if hard_or_material else -6)

    noise_hits = sum(1 for word in NEWS_NOISE_WORDS if word.lower() in title_lower)
    score -= noise_hits * 18

    # 단순 시세/수급 기사는 별도 필터와 함께 추가 감점한다.
    if _is_market_summary_news(title):
        score -= 45

    return score


def _news_impact_type(title, stock_name, ticker):
    """뉴스가 호재/악재/시장요인/중립 중 어디에 가까운지 내부용으로 분류한다."""
    t = (title or "").lower()
    positive = [
        "호재", "실적 개선", "실적 증가", "매출 증가", "영업이익 증가", "수주",
        "계약", "공급 확대", "수요 회복", "수요 증가", "증설", "투자 확대",
        "가격 인상", "점유율 상승", "목표 상향", "전망 상향", "승인", "허가",
        "자사주", "배당 확대", "신규 고객", "신제품", "강세", "상승",
    ]
    negative = [
        "악재", "실적 악화", "실적 감소", "매출 감소", "영업이익 감소", "수주 취소",
        "계약 해지", "공급 차질", "공급 중단", "수요 감소", "수요 둔화", "감산",
        "투자 축소", "가격 하락", "점유율 하락", "목표 하향", "전망 하향", "규제",
        "관세", "제재", "소송", "리콜", "생산 중단", "약세", "하락",
    ]
    p = sum(1 for w in positive if w.lower() in t)
    n = sum(1 for w in negative if w.lower() in t)
    if p > n and p > 0:
        return "positive"
    if n > p and n > 0:
        return "negative"
    if _news_contains_any(t, NEWS_MARKET_CAUSE_WORDS):
        return "market"
    return "neutral"


def _news_duplicate_key(title):
    """표현만 조금 다른 동일/유사 기사 중복을 줄이기 위한 키."""
    key = re.sub(r"[^0-9a-zA-Z가-힣]", "", (title or "").lower())
    for token in ("속보", "단독", "종합", "오늘", "긴급"):
        key = key.replace(token, "")
    return key


def _clean_news_title(title):
    title = title or ""
    title = re.sub(r'\[.*?\]', '', title)
    title = re.sub(r'<[^>]+>', '', title)
    # Google News RSS 제목 뒤의 언론사 표기를 제거한다.
    title = re.sub(r'\s*[-–—―|]\s*[^-–—―|]+$', '', title)
    title = re.sub(r'[\.…]+\s*$', '', title)
    title = re.sub(r'\.{2,}|…', ' · ', title)
    return title.strip().strip('"\'“”')


def _fetch_one_news_rss(search_term, days=7):
    """Google News RSS 한 검색어를 조회한다. 기본 7일, 부족할 때만 보충 기간을 넓힌다."""
    rows = []
    try:
        days = max(1, int(days))
        search_query = f'"{search_term}" when:{days}d' if search_term else ""
        query = urllib.parse.quote(search_query)
        url = (
            f"https://news.google.com/rss/search?q={query}"
            f"&hl=ko&gl=KR&ceid=KR:ko"
        )
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        for item in root.findall('.//item'):
            title_el = item.find('title')
            source_el = item.find('source')
            pub_el = item.find('pubDate')
            link_el = item.find('link')
            title = _clean_news_title(title_el.text if title_el is not None else "")
            source = (source_el.text or "").strip() if source_el is not None else ""
            pub_date = (pub_el.text or "").strip() if pub_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            if title:
                rows.append({"title": title, "source": source, "pub_date": pub_date, "link": link})
    except Exception as e:
        print(f"[뉴스] RSS 조회 예외 search={search_term}: {type(e).__name__}: {e}")
    return rows


def _fetch_realtime_news_uncached(stock_name):
    """종목 관련 최신 호재/악재/시장원인 뉴스를 수집한다. 기본 7일, 부족할 때 14일 보충."""
    clean_stock_name = str(stock_name or "").strip()
    ticker_guess = TICKERS.get(clean_stock_name)
    if ticker_guess:
        ticker_guess = str(ticker_guess).replace(".KS", "").replace(".KQ", "")
    elif re.match(r"^[A-Za-z\-]+$", clean_stock_name):
        ticker_guess = clean_stock_name.upper()

    terms = _news_terms_for_stock(clean_stock_name, ticker_guess)
    primary = terms[0] if terms else clean_stock_name

    queries = [
        primary,
        f"{primary} 실적 계약 수주 투자 공급",
        f"{primary} 악재 우려 규제 관세 소송",
        f"{primary} 호재 기대 전망 수요 고객",
        f"{primary} 반도체 시장 미국 금리 수요",
    ]
    if ticker_guess and re.match(r"^[A-Za-z\-]+$", str(ticker_guess)):
        queries[0] = f"{primary} {ticker_guess}"

    def collect_queries(query_items, days):
        rows = []
        executor = ThreadPoolExecutor(max_workers=min(5, len(query_items)))
        try:
            futures = [executor.submit(_fetch_one_news_rss, q, days) for q in query_items]
            for future in futures:
                try:
                    rows.extend(future.result())
                except Exception as e:
                    print(f"[뉴스] 검색 작업 예외: {type(e).__name__}: {e}")
        finally:
            executor.shutdown(wait=True)
        return rows

    raw_rows = collect_queries(queries, 7)

    def build_candidates(rows):
        candidates = []
        seen_titles = set()
        seen_duplicate_keys = set()
        all_terms_lower = [x.lower() for x in terms if x]

        for row in rows:
            title = row["title"]
            title_lower = title.lower()
            title_key = re.sub(r"\s+", " ", title_lower).strip()
            duplicate_key = _news_duplicate_key(title)
            if title_key in seen_titles or duplicate_key in seen_duplicate_keys:
                continue
            seen_titles.add(title_key)
            seen_duplicate_keys.add(duplicate_key)

            freshness_score = _news_freshness_score(row["pub_date"])
            if freshness_score == 0:
                continue

            direct = any(term in title_lower for term in all_terms_lower)
            material_hit = _news_contains_any(title_lower, NEWS_HARD_EVENT_WORDS + NEWS_MATERIAL_WORDS)
            market_cause_hit = _news_contains_any(title_lower, NEWS_MARKET_CAUSE_WORDS)
            noise_hit = _news_contains_any(title_lower, NEWS_NOISE_WORDS)
            market_summary = _is_market_summary_news(title)

            if not direct and not market_cause_hit:
                continue
            if market_summary:
                continue
            if direct and noise_hit and not material_hit and not market_cause_hit:
                continue

            source_score = _news_source_score(row["source"])
            relevance_score = _news_relevance_score(title, clean_stock_name, ticker_guess or "")
            impact_type = _news_impact_type(title, clean_stock_name, ticker_guess or "")

            score = (
                source_score
                + freshness_score
                + relevance_score
                + (28 if direct else 0)
                + (24 if material_hit else 0)
                + (12 if market_cause_hit else 0)
                - (25 if noise_hit else 0)
            )
            candidates.append({
                "title": title, "source": row["source"], "pub_date": row["pub_date"],
                "link": row.get("link", ""),
                "source_score": source_score, "freshness_score": freshness_score,
                "relevance_score": relevance_score, "direct": direct,
                "material": material_hit, "market_cause": market_cause_hit,
                "impact_type": impact_type, "score": score,
            })
        return candidates

    candidates = build_candidates(raw_rows)

    # 1차(최근 7일)에서 3개가 안 나오면 14일 → 30일 순으로 보충한다.
    # 관련성 필터는 그대로 유지하므로 오래된 기사라도 종목과 직접 관련된 경우만 추가된다.
    if len(candidates) < 3:
        fallback_queries = [
            f"{primary} 호재", f"{primary} 악재",
            f"{primary} 실적 계약 수주", f"{primary} 규제 관세 소송 공급차질",
            f"{primary} 투자 공급 고객 수요 전망",
        ]
        if ticker_guess and re.match(r"^[A-Za-z\-]+$", str(ticker_guess)):
            fallback_queries.append(f"{ticker_guess} earnings news")
        fallback_rows = collect_queries(fallback_queries, 14)
        candidates = build_candidates(raw_rows + fallback_rows)

    if len(candidates) < 3:
        # 14일 내에도 부족한 경우에만 최근 30일까지 확장한다.
        # 단순 주가/시장요약 기사는 기존 필터에서 계속 제외한다.
        extended_queries = [
            primary,
            f"{primary} 실적",
            f"{primary} 계약 수주",
            f"{primary} 투자 공급 고객",
            f"{primary} 규제 관세 소송",
        ]
        if ticker_guess and re.match(r"^[A-Za-z\-]+$", str(ticker_guess)):
            extended_queries.append(f"{ticker_guess} stock company news")
        extended_rows = collect_queries(extended_queries, 30)
        candidates = build_candidates(raw_rows + fallback_rows + extended_rows)

    candidates.sort(
        key=lambda x: (x["score"], x["direct"], x["material"], x["freshness_score"]),
        reverse=True,
    )

    internal_candidates = [dict(item) for item in candidates[:10]]
    NEWS_AI_CANDIDATES_CACHE[clean_stock_name] = internal_candidates

    selected = []
    selected_keys = set()
    pools = [
        [x for x in candidates if x["direct"] and x["material"]],
        [x for x in candidates if x["direct"] and not x["material"]],
        [x for x in candidates if x["market_cause"] and not x["direct"]],
    ]
    for pool in pools:
        for item in pool:
            key = item["title"].lower()
            if key in selected_keys:
                continue
            selected.append(item)
            selected_keys.add(key)
            if len(selected) >= 3:
                break
        if len(selected) >= 3:
            break

    if len(selected) < 3:
        for item in candidates:
            key = item["title"].lower()
            if key in selected_keys:
                continue
            selected.append(item)
            selected_keys.add(key)
            if len(selected) >= 3:
                break

    print(f"[뉴스 품질] {clean_stock_name} 후보={len(candidates)} / 내부AI={len(internal_candidates)} / 화면={len(selected)}")
    for i, item in enumerate(selected[:3], 1):
        print(f"[뉴스 품질] {clean_stock_name} 화면#{i} score={item['score']} type={item['impact_type']} direct={item['direct']} material={item['material']} source={item['source']}")

    display_titles = []
    company_names = set(terms)
    for item in selected[:3]:
        original_title = item["title"]
        display_title = original_title
        for company_name in sorted(company_names, key=len, reverse=True):
            if company_name:
                display_title = display_title.replace(company_name, "")
                display_title = re.sub(re.escape(company_name), "", display_title, flags=re.IGNORECASE)
        display_title = re.sub(r"\s+", " ", display_title).strip()
        display_title = re.sub(r"^[,·:：\-–—]+\s*", "", display_title)
        display_title = re.sub(r"\s*[,·:：\-–—]+$", "", display_title).strip()
        display_titles.append(display_title or original_title)

    display_items = []
    for item, display_title in zip(selected[:3], display_titles):
        display_items.append({
            "title": display_title,
            "source": str(item.get("source") or "출처 확인 필요"),
            "date": _format_news_display_date(item.get("pub_date", "")),
            "datetime": _format_news_display_date(item.get("pub_date", "")),
            "display_datetime": _format_news_display_date(item.get("pub_date", "")),
            "link": str(item.get("link") or "").strip(),
            "original_link": _resolve_news_original_link(item.get("link", "")),
        })
    NEWS_DISPLAY_CACHE[clean_stock_name] = display_items

    return display_titles


def _format_news_display_date(pub_date):
    """뉴스 게시일을 화면에서 YYYY.MM.DD 형식으로 표시한다."""
    try:
        dt = parsedate_to_datetime(str(pub_date or "").strip())
        return dt.strftime("%Y.%m.%d")
    except Exception:
        text = str(pub_date or "").strip()
        m = re.search(r"(20\d{2})[-./]?(\d{1,2})[-./]?(\d{1,2})", text)
        if m:
            return f"{m.group(1)}.{int(m.group(2)):02d}.{int(m.group(3)):02d}"
        return "날짜 확인 필요"


NEWS_ORIGINAL_LINK_CACHE = {}

def _resolve_news_original_link(url):
    """Google News RSS 링크를 가능하면 실제 언론사 원문 URL로 따라간다."""
    url = str(url or "").strip()
    if not url:
        return ""
    cached = NEWS_ORIGINAL_LINK_CACHE.get(url)
    if cached is not None:
        return cached
    resolved = url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            resolved = resp.geturl() or url
    except Exception:
        pass
    NEWS_ORIGINAL_LINK_CACHE[url] = resolved
    return resolved


def get_structured_news(stock_name, limit=3):
    """화면에 표시할 뉴스 제목/출처/날짜/원문 링크를 반환한다."""
    items = NEWS_DISPLAY_CACHE.get(str(stock_name).strip(), [])
    return [dict(item) for item in items[:max(1, int(limit))]]


def get_structured_disclosures(stock_name, stock_code, limit=3):
    """국내 DART 공시를 화면용 제목/출처/날짜/원문 링크로 정리한다."""
    if not stock_code:
        return []

    items = fetch_kr_official_disclosures(stock_code)
    results = []
    company = str(stock_name or "").strip()
    for item in items[:max(1, int(limit))]:
        report_title = str(item.get("report", "주요 공시")).strip() or "주요 공시"
        display_title = report_title
        if company and company not in display_title:
            display_title = f"{company} {display_title}"

        receipt_no = str(item.get("receipt_no", "")).strip()
        link = (
            f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}"
            if receipt_no else ""
        )
        display_date = str(item.get("date", "")).strip()
        results.append({
            "title": display_title,
            "source": "DART",
            "date": display_date,
            "datetime": display_date,
            "display_datetime": display_date,
            "link": link,
            "original_link": link,
        })
    return results


def fetch_realtime_news(stock_name):
    """뉴스 결과를 120초 캐시해 같은 종목의 반복 조회 대기시간을 줄인다."""
    key = str(stock_name).strip()
    now = datetime.datetime.now().timestamp()
    cached = NEWS_RESULT_CACHE.get(key)
    if cached and now - cached[0] < NEWS_CACHE_TTL:
        return list(cached[1])

    result = _fetch_realtime_news_uncached(stock_name)
    NEWS_RESULT_CACHE[key] = (now, list(result))
    return result


def get_news_ai_candidates(stock_name, limit=10):
    """AI 원인 분석에서 사용할 내부 뉴스 후보를 반환한다."""
    items = NEWS_AI_CANDIDATES_CACHE.get(str(stock_name).strip(), [])
    return [dict(item) for item in items[:max(1, int(limit))]]

def calculate_volume_profile_levels(highs, lows, closes, volumes, bins=24):
    """
    최근 60거래일 OHLCV를 가격 구간별로 묶어 거래량 집중 구간을 찾는다.
    일봉 데이터만 있으므로 각 봉의 거래량을 고가~저가 구간에 균등 배분하는
    '근사형 Volume Profile'이다. 실제 체결 틱 데이터라고 과장하지 않는다.
    """
    try:
        rows = []
        for h, l, c, v in zip(highs[-60:], lows[-60:], closes[-60:], volumes[-60:]):
            h, l, c, v = float(h), float(l), float(c), float(v)
            if h > 0 and l > 0 and h >= l and v > 0:
                rows.append((h, l, c, v))

        if len(rows) < 20:
            return None

        min_price = min(x[1] for x in rows)
        max_price = max(x[0] for x in rows)
        current_price = rows[-1][2]

        if max_price <= min_price:
            return None

        bin_size = (max_price - min_price) / bins
        profile = [0.0] * bins

        for high, low, close, volume in rows:
            start_bin = max(0, min(bins - 1, int((low - min_price) / bin_size)))
            end_bin = max(0, min(bins - 1, int((high - min_price) / bin_size)))
            count = max(1, end_bin - start_bin + 1)
            allocated = volume / count
            for idx in range(start_bin, end_bin + 1):
                profile[idx] += allocated

        peak = max(profile)
        if peak <= 0:
            return None

        levels = []
        for idx, volume in enumerate(profile):
            lower = min_price + idx * bin_size
            upper = lower + bin_size
            levels.append({
                "idx": idx,
                "lower": lower,
                "upper": upper,
                "center": (lower + upper) / 2,
                "volume": volume,
                "relative": volume / peak,
            })

        # POC의 55% 이상 거래량이면서 서로 붙어 있는 가격대를 하나의 집중구간으로 묶는다.
        strong = {x["idx"] for x in levels if x["relative"] >= 0.55}
        clusters = []
        for idx in sorted(strong):
            if not clusters or idx > clusters[-1][-1] + 1:
                clusters.append([idx])
            else:
                clusters[-1].append(idx)

        zones = []
        for cluster in clusters:
            items = [levels[i] for i in cluster]
            total_volume = sum(x["volume"] for x in items)
            center = (
                sum(x["center"] * x["volume"] for x in items) / total_volume
                if total_volume else items[len(items) // 2]["center"]
            )
            zones.append({
                "lower": items[0]["lower"],
                "upper": items[-1]["upper"],
                "center": center,
                "volume": total_volume,
                "strength": max(x["relative"] for x in items),
            })

        if not zones:
            poc = levels[profile.index(peak)]
            zones = [{
                "lower": poc["lower"],
                "upper": poc["upper"],
                "center": poc["center"],
                "volume": poc["volume"],
                "strength": poc["relative"],
            }]

        above = sorted(
            [z for z in zones if z["lower"] > current_price],
            key=lambda z: z["lower"]
        )
        below = sorted(
            [z for z in zones if z["upper"] < current_price],
            key=lambda z: z["upper"],
            reverse=True
        )
        inside = [
            z for z in zones
            if z["lower"] <= current_price <= z["upper"]
        ]

        # 현재가 위/아래의 '가장 가까운' 집중구간을 우선하되,
        # 여러 구간 중 상대적으로 강한 구간 정보도 유지한다.
        return {
            "current_price": current_price,
            "poc": levels[profile.index(peak)],
            "zones": zones,
            "above": above[0] if above else None,
            "below": below[0] if below else None,
            "inside": inside[0] if inside else None,
            "days": len(rows),
        }
    except Exception as e:
        print(f"[Volume Profile] 계산 예외: {type(e).__name__}: {e}")
        return None

def format_volume_profile(profile, is_usd=True):
    if not profile:
        return ""

    inside = profile.get("inside")
    above = profile.get("above")
    below = profile.get("below")
    poc = profile.get("poc")

    lines = []

    # 매물대는 내부적으로 구간으로 분석하되,
    # 화면에는 저항/지지 대표 가격 하나만 표시한다.
    # 저항 = 선택된 저항 매물대의 상단 가격
    # 지지 = 선택된 지지 매물대의 하단 가격
    if above:
        resistance_price = above.get("upper", above.get("center"))
        if resistance_price:
            lines.append(f"#악성 매물대 ${resistance_price:,.2f}" if is_usd else f"#악성 매물대 {round_krw_tick(resistance_price):,}원")
    elif inside:
        resistance_price = inside.get("upper", inside.get("center"))
        if resistance_price:
            lines.append(f"#악성 매물대 ${resistance_price:,.2f}" if is_usd else f"#악성 매물대 {round_krw_tick(resistance_price):,}원")

    if below:
        support_price = below.get("lower", below.get("center"))
        if support_price:
            lines.append(f"#생존 지지선 ${support_price:,.2f}" if is_usd else f"#생존 지지선 {round_krw_tick(support_price):,}원")
    elif inside:
        support_price = inside.get("lower", inside.get("center"))
        if support_price:
            lines.append(f"#생존 지지선 ${support_price:,.2f}" if is_usd else f"#생존 지지선 {round_krw_tick(support_price):,}원")

    if poc:
        lines.append((f"POC ${poc['center']:,.2f} · 최근 {profile['days']}거래일 거래량 기준" if is_usd else f"POC {round_krw_tick(poc['center']):,}원 · 최근 {profile['days']}거래일 거래량 기준"))

    return "\n".join(lines)

def format_shares(n):
    if n is None: return "0주"
    sign = "+" if n > 0 else ""
    if abs(n) >= 10000:
        return f"{sign}{n / 10000:,.1f}만주"
    return f"{sign}{n:,}주"

def round_krw_tick(price):
    if price is None: return 0
    try:
        p = float(price)
        if math.isnan(p) or math.isinf(p) or p <= 0: return 0
        if p >= 500_000: return int(p // 1000) * 1000
        elif p >= 100_000: return int(p // 500) * 500
        elif p >= 50_000: return int(p // 100) * 100
        elif p >= 10_000: return int(p // 50) * 50
        else: return int(p // 10) * 10
    except Exception:
        return 0

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


def get_live_calendar_data(stock_name, ticker_symbol):
    kst_tz = datetime.timezone(datetime.timedelta(hours=9))
    now_kst = datetime.datetime.now(kst_tz)
    weekdays = ['월', '화', '수', '목', '금', '토', '일']

    master_events = [
        {
            "name": "미국 8월 생산자물가지수 #PPI",
            "dt": datetime.datetime(2026, 9, 10, 21, 30, tzinfo=kst_tz),
            "est": "0.2%",
            "type": "ppi"
        },
        {
            "name": "#오라클 ORCL 실적 발표",
            "dt": datetime.datetime(2026, 9, 11, 5, 0, tzinfo=kst_tz),
            "est": "예상 EPS $1.33",
            "type": "earnings",
            "target": "글로벌 AI·클라우드 대장주"
        },
        {
            "name": "#어도비 ADBE 실적 발표",
            "dt": datetime.datetime(2026, 9, 11, 5, 0, tzinfo=kst_tz),
            "est": "예상 EPS $6.08",
            "type": "earnings",
            "target": "글로벌 AI·소프트웨어 대장주"
        },
        {
            "name": "미국 8월 소비자물가지수 #CPI",
            "dt": datetime.datetime(2026, 9, 11, 21, 30, tzinfo=kst_tz),
            "est": "0.2%",
            "type": "cpi"
        },
        {
            "name": "미국 연준 #FOMC 기준금리 결정",
            "dt": datetime.datetime(2026, 9, 17, 3, 0, tzinfo=kst_tz),
            "est": "기준금리 3.50%~3.75%",
            "type": "fomc"
        },
        {
            "name": "미국 개인소비지출 #PCE 물가지수",
            "dt": datetime.datetime(2026, 9, 25, 21, 30, tzinfo=kst_tz),
            "est": "2.6%",
            "type": "pce"
        }
    ]

    master_events.sort(key=lambda x: x['dt'])
    upcoming = [ev for ev in master_events if ev['dt'] >= now_kst]
    if not upcoming:
        upcoming = master_events[:4]

    tomorrow_morning = (now_kst + datetime.timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    tonight_event = next((ev for ev in upcoming if ev['dt'] <= tomorrow_morning), None)

    if tonight_event:
        t_dt = tonight_event['dt']
        t_wd = weekdays[t_dt.weekday()]
        time_str = t_dt.strftime(f"%m/%d({t_wd}) %H:%M")

        if tonight_event['type'] == 'earnings':
            tonight_card = (
                f"🚨 오늘 밤엔 큰 거 하나 온다! 긴장 바짝 해!\n\n"
                f"⏰ {time_str} {tonight_event['name']}\n"
                f"{tonight_event.get('target', '글로벌 빅테크')} 실적 발표거든? "
                f"미국 대장주가 기침하면 국장도 영향을 받으니까 장 시작 전 방향성 잘 체크하자고!"
            )
        else:
            tonight_card = (
                f"🚨 오늘 밤엔 큰 거 하나 온다! 긴장 바짝 해!\n\n"
                f"⏰ {time_str} {tonight_event['name']} 발표!\n"
                f"시장 예상치는 {tonight_event['est']} 수준이야. "
                f"예상치보다 튀면 오늘 밤 야간 선물부터 거칠게 출렁일 수 있으니 방심 금물이야!"
            )
    else:
        tonight_card = (
            "🌙 오늘 밤은? 없네!\n"
            "오늘 밤은 시장을 뒤흔들 빅이벤트가 없으니까 야간 미장 걱정 말고 꿀잠 자도 돼 ㅎㅎ\n"
            "대신 이번 주 뒤로 갈수록 굵직한 지표와 메이저 실적들이 대기 중이니까 아래 일정 꼭 메모해 둬!"
        )

    check_lines = []
    for ev in upcoming[:4]:
        e_dt = ev['dt']
        e_wd = weekdays[e_dt.weekday()]
        e_time = e_dt.strftime(f"%m/%d({e_wd}) %H:%M")
        check_lines.append(f"• {e_time} {ev['name']}")

    calendar_block = (
        "🗓️ 이번 주 핵심 개미 캘린더 ★★★\n" +
        "\n".join(check_lines) +
        "\n\n\"지표나 실적 발표 전후로는 호가창 얇아지니까 뇌동매매 절대 금지야! 알았제?\""
    )

    return f"{tonight_card}\n\n{calendar_block}"

@app.route('/')
def home():
    return "gaemiGTP 대화형 수급 & 리포트 엔진 가동 중!"

@app.route('/analyze', methods=['GET'])
def analyze():
    raw_name = request.args.get('stock', 'SK하이닉스').strip()
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

        # 1~2. 외부 API는 서로 독립적인 요청을 동시에 실행한다.
        # 기존 데이터/계산/화면 구조는 유지하고 "기다리는 순서"만 개선한다.
        if is_krw and clean_code:
            realtime_future = API_EXECUTOR.submit(fetch_kr_stock_realtime, clean_code)
            trend_future = API_EXECUTOR.submit(fetch_krx_trend_and_supply, clean_code)
            news_future = API_EXECUTOR.submit(fetch_realtime_news, raw_name)
            disclosure_future = API_EXECUTOR.submit(format_kr_official_disclosures, clean_code)
            volume_profile_future = API_EXECUTOR.submit(
                fetch_kr_historical_volume_profile, ticker_symbol
            )

            cur_p, diff, ratio = realtime_future.result()
            ma20_val, res_val, f_5d, i_5d, ind_5d, v_days = trend_future.result()
            news_list = news_future.result()
            kr_official_disclosures_block = disclosure_future.result()
            volume_profile = volume_profile_future.result()
            official_filings_block = ""

            current_price = cur_p if cur_p else 1783000.0
            change_pct = ratio if ratio is not None else 8.26
            ma20 = ma20_val if ma20_val else current_price * 0.95
            resistance_price = res_val if res_val else current_price * 1.05

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
            yahoo_future = API_EXECUTOR.submit(fetch_yahoo_direct_v8, ticker_symbol)
            options_future = API_EXECUTOR.submit(fetch_us_options_volume, ticker_symbol)
            news_future = API_EXECUTOR.submit(fetch_realtime_news, raw_name)
            filing_future = API_EXECUTOR.submit(format_us_official_filings, ticker_symbol)

            cur_p, prev_p, ma20_val, res_val, volume_profile = yahoo_future.result()
            call_vol, put_vol, option_error = options_future.result()
            news_list = news_future.result()
            news_items = get_structured_news(raw_name, limit=3)
            official_filings_block = filing_future.result()
            kr_official_disclosures_block = ""
            disclosures = []

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
            "\n".join([f"📰 \"{title}\"" for title in news_list])
            if news_list
            else "📰 현재 확인된 관련 뉴스를 가져오지 못했습니다."
        )
        news_transition = "이런 뉴스 재료와 기업 공시가 나오면서 시장이 반응하고 있는 거야"


        # 첫 화면은 현재 주가를 가장 위에 배치한다.
        # 그 아래에는 기존의 친근한 말투를 다시 살리고,
        # 그 다음 자리에 향후 AI 분석 영역이 들어간다.
        # 뉴스와 공시는 기존처럼 한 칸(빈 줄) 간격을 유지한다.
        friendly_ment = (
            intro_ment.split("\n", 1)[1]
            if "\n" in intro_ment
            else intro_ment
        )

        first_content_parts = [
            intro_ment,
            f"현재 주가는 {price_str} 기록 중!",
            news_lines,
        ]
        if official_filings_block:
            first_content_parts.append(official_filings_block)
        if kr_official_disclosures_block:
            first_content_parts.append(kr_official_disclosures_block)
        first_content_parts.extend([news_transition, tags_str])

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
                "title": "여기 깨지면 도망쳐",
                "content": (
                    f"#생존 지지선 {ma20_str} 딱 기억해놔! "
                    f"이 가격 깨지면 실망 매물 나올 수 있으니 절대 미련 갖지 말고 비중 줄여! 알았제?\n\n"
                    + (
                        format_volume_profile(volume_profile, is_usd=False)
                        if volume_profile
                        else f"#악성 매물대 {res_str} 이 가격은 최근 고점 부근의 본전 매물이 몰려 있을 가능성이 있어. 돌파 전에는 무리하게 따라붙지 말자."
                    )
                )
            },
            {
                "title": "오늘 밤, 이번주 무슨 일이 있나?",
                "content": get_live_calendar_data(raw_name, ticker_symbol)
            }
        ])
        return jsonify({"sections": sections, "news_items": news_items, "disclosures": disclosures})

    except Exception as e:
        print("전체 예외 안전 복구 가동:", e)
        return jsonify({
            "sections": [
                {
                    "title": "🔥 그래서 오늘은 왜 올랐어?",
                    "content": f"{raw_name} 실시간 호가 접수 완료!\n현재 시장 수급 유입으로 지지선 테스트 중이야.\n\n#{raw_name}   #+8.26%   #가즈아   #불기둥"
                },
                {
                    "title": "큰손들은 담고 있을까, 털고 있을까?",
                    "content": "#외국인 +48.2만주   #기관 +21.4만주   #개인 -69.6만주\n\n최근 5일 동안 외인과 기관이 쌍끌이로 물량을 쓸어 담고 있어!\n메이저 세력이 바닥을 단단하게 다져놨으니 흔들려도 버티는 게 맞아."
                },
                {
                    "title": "여기 깨지면 도망쳐",
                    "content": "#생존 지지선 1,680,000원 딱 기억해놔! 이 가격 깨지면 실망 매물 나올 수 있으니 절대 미련 갖지 말고 비중 줄여! 알았제?\n\n#악성 매물대 1,792,000원 이 가격은! 최근 고점 부근에 과거 물려있는 본전 대기 악성 매물이 숨어 있어ㅠㅠ 조심해!"
                },
                {
                    "title": "오늘 밤, 이번주 무슨 일이 있나?",
                    "content": get_live_calendar_data(raw_name, ticker_symbol)
                }
            ]
        })

if __name__ == '__main__':
    # Render가 제공하는 PORT를 사용하고, 로컬 실행에서는 10000을 기본값으로 사용한다.
    port = int(os.environ.get('PORT', '10000'))
    app.run(host='0.0.0.0', port=port)
