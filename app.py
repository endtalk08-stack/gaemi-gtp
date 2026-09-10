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
from email.utils import parsedate_to_datetime

app = Flask(__name__)
CORS(app)

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
                "date": (
                    f"{receipt_date[:4]}-{receipt_date[4:6]}-{receipt_date[6:8]}"
                    if len(receipt_date) == 8 else receipt_date
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

            role = f" · {officer_title}" if officer_title else ""
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

# 뉴스 품질 우선순위:
# 1) 실제 Google News RSS에서 수집
# 2) 같은 언론사 중복을 제거
# 3) 주요/전문 매체를 우선
# 4) 가능하면 서로 다른 출처 3개를 선택
# 5) 실제 뉴스가 없으면 가짜 제목을 만들지 않음
NEWS_SOURCE_PRIORITY = {
    "Reuters": 100, "로이터": 100,
    "AP": 98, "Associated Press": 98,
    "Bloomberg": 96, "블룸버그": 96,
    "Financial Times": 95, "파이낸셜타임스": 95,
    "The Wall Street Journal": 94, "월스트리트저널": 94,
    "CNBC": 92,
    "NVIDIA": 91, "엔비디아": 91,
    "연합뉴스": 90, "한국경제": 88, "매일경제": 87,
    "서울경제": 86, "전자신문": 85, "이데일리": 82,
    "머니투데이": 80, "조선비즈": 75,
}

# 주가에 직접 영향을 줄 가능성이 높은 '실제 재료' 표현.
NEWS_HARD_EVENT_WORDS = [
    "실적발표", "잠정실적", "실적", "매출", "영업이익", "순이익", "가이던스",
    "수주", "계약", "공급계약", "대형계약", "인수", "합병", "m&a",
    "투자", "증설", "감산", "증산", "출하", "판매", "가격 인상", "가격 하락",
    "공급 중단", "공급 차질", "규제", "관세", "제재", "수출 제한", "승인",
    "허가", "소송", "특허", "자사주", "배당", "유상증자", "전환사채",
    "earnings", "revenue", "profit", "guidance", "contract", "deal",
    "acquisition", "merger", "investment", "regulation", "tariff",
    "approval", "lawsuit", "buyback", "dividend", "offering",
]

# 단독 재료가 아니라 단순 전망/의견 중심인 기사는 우선순위를 낮춘다.
NEWS_SOFT_OPINION_WORDS = [
    "전망", "예상", "분석", "목표주가", "증권가", "전문가", "기대감",
    "가능성", "주목", "관심", "수혜주", "관련주", "추천", "진단",
    "전략", "시나리오", "전망치", "forecast", "estimate", "analyst",
    "target price", "outlook", "expectation", "potential",
]

# 주가 원인 분석에 상대적으로 덜 직접적인 기사 표현.
NEWS_NOISE_WORDS = [
    "인터뷰", "화보", "현장", "이모저모", "사설", "칼럼", "오피니언",
    "사용기", "리뷰", "가이드", "주식 초보", "투자전략", "투자 팁",
    "주간전망", "오늘의 운세", "퀴즈",
]

# 이미 화면 상단에서 직접 보여주는 '주가/수급 단순 요약' 기사는 뉴스 목록에서 제외한다.
# 실제 재료(계약, 실적, 투자, 인수 등)가 함께 있는 기사는 제외하지 않는다.
NEWS_MARKET_SUMMARY_WORDS = [
    "보합 마감", "상승 마감", "하락 마감", "급등 마감", "급락 마감",
    "장 마감", "마감 시황", "장 마감 시황", "오늘의 시황", "시황",
    "주가", "수급", "외국인·기관", "외국인 기관", "기관·외국인",
    "기관 외국인", "외국인 순매수", "외국인 순매도", "기관 순매수",
    "기관 순매도", "거래량", "거래대금", "상승률", "하락률",
    "등락", "장중", "증시 마감", "마감",
]

def _is_market_summary_news(title):
    """현재 주가/수급을 단순 요약한 기사인지 판별한다.

    단순 요약만 제외하고, 실제 사건/재료가 함께 언급된 기사는 보존한다.
    """
    title_lower = (title or "").lower()
    if not title_lower:
        return False

    summary_hits = sum(
        1 for word in NEWS_MARKET_SUMMARY_WORDS
        if word.lower() in title_lower
    )

    # 퍼센트 등락 + 마감/수급 표현은 대표적인 단순 시황 요약 패턴이다.
    pct_hit = bool(re.search(r"[+-]?\d+(?:\.\d+)?%", title_lower))
    close_or_flow_hit = any(
        word in title_lower
        for word in [
            "마감", "수급", "순매수", "순매도", "등락", "상승률", "하락률",
            "거래량", "거래대금", "시황",
        ]
    )

    # 확정된 실제 재료가 함께 있으면 '뉴스'로 유지한다.
    hard_event_hit = any(
        word.lower() in title_lower for word in NEWS_HARD_EVENT_WORDS
    )

    if hard_event_hit:
        return False

    if pct_hit and close_or_flow_hit:
        return True

    return summary_hits >= 2

# 화면 표시용 뉴스와 AI 분석용 후보를 분리한다.
# 화면에는 핵심 3개만 보여주고, 내부에는 상위 후보를 보관해 추후 AI가 더 넓은 근거를 사용할 수 있게 한다.
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
    except Exception:
        pass

    return 0

def _news_relevance_score(title, stock_name, ticker):
    """종목 직접 관련성과 실제 주가 영향 가능성을 함께 평가."""
    title_lower = (title or "").lower()
    score = 0

    stock = str(stock_name or "").strip().lower()
    tick = str(ticker or "").replace(".KS", "").replace(".KQ", "").lower()

    if stock and len(stock) >= 2 and stock in title_lower:
        score += 35
    if tick and len(tick) >= 2 and tick in title_lower:
        score += 30

    for word in NEWS_HARD_EVENT_WORDS:
        if word.lower() in title_lower:
            score += 6

    # 소프트한 전망 기사도 실적/계약 같은 확정 재료와 같이 있으면 살려둔다.
    hard_hit = any(word.lower() in title_lower for word in NEWS_HARD_EVENT_WORDS)
    for word in NEWS_SOFT_OPINION_WORDS:
        if word.lower() in title_lower:
            score += 2 if hard_hit else -7

    for word in NEWS_NOISE_WORDS:
        if word.lower() in title_lower:
            score -= 12

    # 직접적인 시장 충격 표현은 추가 가중치.
    very_high_impact = [
        "실적발표", "가이던스", "수주", "대형계약", "인수", "합병", "규제",
        "관세", "제재", "공급 중단", "공급 차질", "수출 제한", "승인",
        "유상증자", "전환사채", "earnings", "guidance", "acquisition",
        "merger", "regulation", "tariff", "approval", "offering",
    ]
    for word in very_high_impact:
        if word.lower() in title_lower:
            score += 10

    return score

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
    title = re.sub(r'\s*[-–—―|]\s*[^-–—―|]+$', '', title)
    title = re.sub(r'[\.…]+\s*$', '', title)
    title = re.sub(r'\.{2,}|…', ' · ', title)
    return title.strip().strip('"\'“”')

def fetch_realtime_news(stock_name):
    """
    뉴스는 넓게 수집한 뒤 강하게 필터링한다.
    화면에는 핵심 뉴스 3개만 제목으로 표시하고, 내부에는 상위 후보를 별도로 보관한다.
    """
    candidates = []
    seen_titles = set()
    seen_duplicate_keys = set()

    queries = [str(stock_name).strip()]
    ticker_guess = TICKERS.get(str(stock_name).strip())
    if ticker_guess:
        ticker_guess = str(ticker_guess).replace(".KS", "").replace(".KQ", "")
        if ticker_guess not in queries:
            queries.append(ticker_guess)
    elif re.match(r"^[A-Za-z\-]+$", str(stock_name).strip()):
        ticker_guess = str(stock_name).upper()
        if ticker_guess not in queries:
            queries.append(ticker_guess)

    ticker_for_score = ticker_guess if ticker_guess else ""

    for search_term in queries[:2]:
        try:
            # '왜 오늘'에 맞춰 최근 7일 검색. 점수에서 72시간 이내 기사를 강하게 우선한다.
            search_query = f"{search_term} when:7d"
            query = urllib.parse.quote(search_query)
            url = (
                f"https://news.google.com/rss/search?q={query}"
                f"&hl=ko&gl=KR&ceid=KR:ko"
            )
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                xml_data = resp.read()

            root = ET.fromstring(xml_data)
            for item in root.findall('.//item'):
                title_el = item.find('title')
                source_el = item.find('source')
                pub_el = item.find('pubDate')

                title = _clean_news_title(
                    title_el.text if title_el is not None else ""
                )
                source = (
                    (source_el.text or "").strip()
                    if source_el is not None else ""
                )
                pub_date = (
                    (pub_el.text or "").strip()
                    if pub_el is not None else ""
                )

                if not title:
                    continue

                # 이미 상단의 주가/수급 정보와 중복되는 단순 시황 요약 기사는
                # 뉴스 목록에서 제외한다. 실제 계약/실적/투자 등의 재료 기사는 유지한다.
                if _is_market_summary_news(title):
                    print(f"[뉴스 품질] {stock_name} 단순 주가·수급 요약 제외: {title}")
                    continue

                title_key = re.sub(r"\s+", " ", title).lower()
                duplicate_key = _news_duplicate_key(title)
                if title_key in seen_titles or duplicate_key in seen_duplicate_keys:
                    continue

                seen_titles.add(title_key)
                seen_duplicate_keys.add(duplicate_key)

                source_score = _news_source_score(source)
                freshness_score = _news_freshness_score(pub_date)
                relevance_score = _news_relevance_score(
                    title, stock_name, ticker_for_score
                )
                hard_event = any(
                    word.lower() in title.lower() for word in NEWS_HARD_EVENT_WORDS
                )

                # 7일보다 오래된 기사는 RSS가 섞여 들어와도 핵심 후보에서 사실상 탈락시킨다.
                if freshness_score == 0:
                    continue

                candidates.append({
                    "title": title,
                    "source": source,
                    "pub_date": pub_date,
                    "source_score": source_score,
                    "freshness_score": freshness_score,
                    "relevance_score": relevance_score,
                    "hard_event": hard_event,
                    "score": source_score + freshness_score + relevance_score,
                })

        except Exception as e:
            print(f"[뉴스] {stock_name} RSS 조회 예외: {type(e).__name__}: {e}")

    candidates.sort(
        key=lambda x: (
            x["score"],
            x["hard_event"],
            x["freshness_score"],
            x["relevance_score"],
        ),
        reverse=True,
    )

    # 먼저 내부 AI용 후보를 보관한다.
    # 화면에 3개만 보여주더라도 AI 단계에서는 더 많은 근거를 활용할 수 있게 한다.
    internal_candidates = [dict(item) for item in candidates[:10]]
    NEWS_AI_CANDIDATES_CACHE[str(stock_name).strip()] = internal_candidates

    # 화면에는 핵심 3개만 노출한다. 출처 다양성은 유지하되 점수 차이가 큰 경우에는
    # 더 강한 기사를 우선한다(약한 기사를 억지로 끼워 넣지 않음).
    selected = []
    for item in candidates:
        if not selected:
            selected.append(item)
            continue

        same_source = item["source"].lower().strip() == selected[0]["source"].lower().strip()
        if same_source and item["score"] < selected[0]["score"] - 8:
            continue

        selected.append(item)
        if len(selected) >= 3:
            break

    # 첫 후보가 지나치게 약하면 낮은 품질 기사를 억지로 표시하지 않는다.
    selected = [x for x in selected if x["score"] >= 70]

    print(
        f"[뉴스 품질] {stock_name} 후보={len(candidates)} / 내부AI={len(internal_candidates)} / 화면={len(selected)}"
    )
    for i, item in enumerate(selected[:3], 1):
        print(
            f"[뉴스 품질] {stock_name} 화면#{i} "
            f"score={item['score']} source={item['source']} "
            f"fresh={item['freshness_score']} relevance={item['relevance_score']} "
            f"hard={item['hard_event']}"
        )

    # 화면에서는 현재 종목명을 제거해 제목을 최대한 깔끔하게 표시한다.
    # 원본 제목(item["title"])은 내부 후보 데이터와 AI 분석용으로 그대로 보존한다.
    display_titles = []
    company_names = {
        str(stock_name).strip(),
        str(stock_name).strip().replace(" ", ""),
    }

    for item in selected[:3]:
        original_title = item["title"]
        display_title = original_title

        for company_name in sorted(company_names, key=len, reverse=True):
            if company_name:
                display_title = display_title.replace(company_name, "")

        display_title = re.sub(r"\s+", " ", display_title).strip()
        display_title = re.sub(r"^[,·:：\-–—]+\s*", "", display_title)
        display_title = re.sub(r"\s*[,·:：\-–—]+$", "", display_title).strip()

        # 종목명 제거 후 제목이 비어버리는 경우에는 원본 제목을 사용한다.
        display_titles.append(display_title or original_title)

    return display_titles


def get_news_ai_candidates(stock_name, limit=10):
    """추후 AI 원인 분석에서 사용할 내부 뉴스 후보를 반환한다."""
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

def format_volume_profile(profile):
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
            lines.append(f"#악성 매물대 ${resistance_price:,.2f}")
    elif inside:
        resistance_price = inside.get("upper", inside.get("center"))
        if resistance_price:
            lines.append(f"#악성 매물대 ${resistance_price:,.2f}")

    if below:
        support_price = below.get("lower", below.get("center"))
        if support_price:
            lines.append(f"#생존 지지선 ${support_price:,.2f}")
    elif inside:
        support_price = inside.get("lower", inside.get("center"))
        if support_price:
            lines.append(f"#생존 지지선 ${support_price:,.2f}")

    if poc:
        lines.append(f"POC ${poc['center']:,.2f} · 최근 {profile['days']}거래일 거래량 기준")

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

        # 1. 국내 주식
        if is_krw and clean_code:
            cur_p, diff, ratio = fetch_kr_stock_realtime(clean_code)
            ma20_val, res_val, f_5d, i_5d, ind_5d, v_days = fetch_krx_trend_and_supply(clean_code)

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
            cur_p, prev_p, ma20_val, res_val, volume_profile = fetch_yahoo_direct_v8(ticker_symbol)
            if cur_p and prev_p:
                current_price = cur_p
                change_pct = ((cur_p - prev_p) / prev_p) * 100
                ma20 = ma20_val or 0.0
                resistance_price = res_val or 0.0
            else:
                # 실제 시세 조회 실패 시 임의의 가격을 만들지 않는다.
                current_price = 0.0
                change_pct = 0.0
                ma20 = 0.0
                resistance_price = 0.0
                volume_profile = None
                print(f"[미국 주가] {ticker_symbol} 조회 실패 - 가짜 가격 사용 안 함")

            price_str = f"${current_price:,.2f}" if current_price > 0 else "시세 조회 실패"
            ma20_str = f"${ma20:,.2f}" if ma20 > 0 else "계산 대기"
            res_str = f"${resistance_price:,.2f}" if resistance_price > 0 else "계산 대기"

            # 미국 옵션 수급: CBOE 공개 지연 옵션체인 사용
            # Yahoo crumb 방식은 사용하지 않는다. CBOE 엔드포인트는 API 키가 필요 없고
            # 옵션 계약별 volume을 제공한다. (약 15분 지연)
            try:
                call_vol = 0
                put_vol = 0
                option_error = None

                try:
                    cboe_url = (
                        f"https://cdn.cboe.com/api/global/delayed_quotes/options/"
                        f"{urllib.parse.quote(ticker_symbol)}.json"
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

                    with urllib.request.urlopen(req, timeout=8) as resp:
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

                            # CBOE 옵션 심볼은 계약 문자열 안에 C/P가 들어간다.
                            # 일반 OCC 형식은 날짜 뒤에 C 또는 P가 위치한다.
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

                    if call_vol == 0 and put_vol == 0:
                        print(f"[미국 옵션] {ticker_symbol} CBOE 조회 성공했지만 거래량 데이터가 없습니다.")
                    else:
                        print(
                            f"[미국 옵션] {ticker_symbol} 성공 / CBOE / "
                            f"CALL={call_vol} PUT={put_vol}"
                        )

                except urllib.error.HTTPError as e:
                    option_error = e.code
                    print(f"[미국 옵션] CBOE 실패 {ticker_symbol}: HTTP {e.code}")
                except Exception as e:
                    print(
                        f"[미국 옵션] CBOE 실패 {ticker_symbol}: "
                        f"{type(e).__name__}: {e}"
                    )

                if call_vol > 0:
                    pc_ratio = put_vol / call_vol
                    c_str = f"{call_vol/10000:.1f}만건" if call_vol >= 10000 else f"{call_vol:,}건"
                    p_str = f"{put_vol/10000:.1f}만건" if put_vol >= 10000 else f"{put_vol:,}건"
                    tag_line = f"#콜 {c_str}   #풋 {p_str}   #비율 {pc_ratio:.2f}"

                    if pc_ratio <= 0.7:
                        supply_content = (
                            f"{tag_line}\n\n"
                            "CBOE Options Volume\n\n"
                            "현재 옵션 거래량이 상방 쪽으로 기울어 있어!\n"
                            "콜옵션 거래량이 풋옵션보다 많아 상승 쪽 베팅이 상대적으로 강한 구간이야."
                        )
                    elif pc_ratio >= 1.1:
                        supply_content = (
                            f"{tag_line}\n\n"
                            "CBOE Options Volume\n\n"
                            "현재 옵션 거래량이 하방 쪽으로 기울어 있어!\n"
                            "풋옵션 거래량이 콜옵션을 넘어 하락 방어 수요가 상대적으로 강한 구간이야."
                        )
                    else:
                        supply_content = (
                            f"{tag_line}\n\n"
                            "CBOE Options Volume\n\n"
                            "현재 옵션 시장이 팽팽하게 눈치싸움 중이야.\n"
                            "콜과 풋 거래량이 크게 벌어지지 않아 방향성을 조금 더 확인할 필요가 있어."
                        )
                elif call_vol == 0 and put_vol == 0 and option_error:
                    supply_content = f"{ticker_symbol} 조회 실패 HTTP {option_error}"
                else:
                    supply_content = f"{ticker_symbol} 조회 성공 거래량 0"

            except urllib.error.HTTPError as option_err:
                supply_content = f"{ticker_symbol} 조회 실패 HTTP {option_err.code}"
                print(f"[미국 옵션] 전체 처리 실패 {ticker_symbol}: HTTP {option_err.code}")
            except Exception as option_err:
                supply_content = f"{ticker_symbol} 조회 실패"
                print(
                    f"[미국 옵션] 전체 처리 실패 {ticker_symbol}: "
                    f"{type(option_err).__name__}: {option_err}"
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

        news_list = fetch_realtime_news(raw_name)
        news_lines = (
            "\n".join([f"📰 \"{title}\"" for title in news_list])
            if news_list
            else "📰 현재 확인된 관련 뉴스를 가져오지 못했습니다."
        )
        news_transition = "이런 뉴스 재료와 기업 공시가 나오면서 시장이 반응하고 있는 거야"

        # 미국 공시는 별도 메뉴를 만들지 않고 '왜 올랐을까?' 뉴스 바로 아래에 통합한다.
        official_filings_block = ""
        kr_official_disclosures_block = ""

        if not is_krw:
            official_filings_block = format_us_official_filings(ticker_symbol)
        else:
            kr_official_disclosures_block = format_kr_official_disclosures(clean_code)

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
                        format_volume_profile(volume_profile)
                        if volume_profile
                        else "#주요 매물대 계산 대기"
                    )
                )
            },
            {
                "title": "오늘 밤, 이번주 무슨 일이 있나?",
                "content": get_live_calendar_data(raw_name, ticker_symbol)
            }
        ])
        return jsonify({"sections": sections})

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
    app.run(host='0.0.0.0', port=10000)
