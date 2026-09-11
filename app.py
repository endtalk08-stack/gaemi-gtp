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
                    f"{int(receipt_date[4:6])}/{int(receipt_date[6:8])}"
                    if len(receipt_date) == 8 and receipt_date.isdigit() else receipt_date
                ),
                "report": report_name,
                "receipt_no": receipt_no,
                "score": _dart_report_score(report_name),
            })

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
    """SEC 공식 제출자료 중 최근 주요 공시를 수집한다."""
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
                "User-Agent": os.environ.get("SEC_USER_AGENT", "gaemiGTP/1.0 (contact@example.com)"),
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

        sec_headers = {
            "User-Agent": os.environ.get("SEC_USER_AGENT", "gaemiGTP/1.0 (contact@example.com)"),
            "Accept": "text/html,application/xml,text/xml,*/*",
        }

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

            if form == "4" and filing_url:
                try:
                    index_url = (
                        f"https://www.sec.gov/Archives/edgar/data/"
                        f"{int(cik)}/{clean_accession}/{accession}-index.htm"
                    )

                    index_req = urllib.request.Request(index_url, headers=sec_headers)
                    with urllib.request.urlopen(index_req, timeout=5) as index_resp:
                        index_text = index_resp.read().decode("utf-8", errors="ignore")

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
                        detail_url = urllib.parse.urljoin(index_url, xml_href)
                    else:
                        base_name = re.sub(r"\.html?$", ".xml", document, flags=re.I)
                        detail_url = (
                            f"https://www.sec.gov/Archives/edgar/data/"
                            f"{int(cik)}/{clean_accession}/xslF345X06/{base_name}"
                        )

                    submission_txt_url = (
                        f"https://www.sec.gov/Archives/edgar/data/"
                        f"{int(cik)}/{clean_accession}/{accession}.txt"
                    )
                    txt_req = urllib.request.Request(submission_txt_url, headers=sec_headers)
                    with urllib.request.urlopen(txt_req, timeout=5) as txt_resp:
                        submission_text = txt_resp.read().decode("utf-8", errors="ignore")

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

                except Exception as detail_err:
                    print(f"[미국 공시] {ticker_symbol} Form 4 원문 파싱 실패: {detail_err}")

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
        "P": "내부자 매수", "S": "내부자 매도", "A": "주식 취득",
        "D": "회사로 반환", "F": "세금·행사가격 지급", "M": "옵션·파생상품 행사",
        "G": "주식 증여", "C": "전환 거래", "J": "기타 거래", "V": "자발적 신고",
    }

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

            if not code_counts:
                code = str(item.get("transaction_code", "")).upper().strip()
                if code:
                    code_counts[code] = 1

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

def calculate_volume_profile_levels(highs, lows, closes, volumes, bins=24):
    """Volume Profile 매물대 구간을 구간 분할하여 분석한다."""
    if not closes or not highs or not lows or not volumes:
        return None

    min_price = min(lows)
    max_price = max(highs)
    if min_price == max_price:
        return None

    bin_size = (max_price - min_price) / bins
    profile = [0.0] * bins

    for h, l, v in zip(highs, lows, volumes):
        if h == l:
            idx = min(int((h - min_price) / bin_size), bins - 1)
            profile[idx] += v
        else:
            step = (h - l) / 5
            for i in range(5):
                p = l + step * i
                idx = min(int((p - min_price) / bin_size), bins - 1)
                profile[idx] += v / 5

    current_price = closes[-1]
    above_bins = []

    for i in range(bins):
        bin_center = min_price + bin_size * (i + 0.5)
        if bin_center > current_price:
            above_bins.append((bin_center, profile[i]))

    if above_bins:
        max_above = max(above_bins, key=lambda x: x[1])
        return {"above": {"center": max_above[0], "volume": max_above[1]}}

    return {"above": {"center": max_price, "volume": 0.0}}

def fetch_yahoo_direct_v8(ticker_str):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_str}?range=6mo&interval=1d"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36'
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

        volume_profile = calculate_volume_profile_levels(
            highs, lows, closes, volumes, bins=24
        )

        res_p = (
            volume_profile["above"]["center"]
            if volume_profile and volume_profile.get("above")
            else 0.0
        )

        return cur_p, prev_p, ma20, res_p, volume_profile

    except Exception as e:
        print("미국 야후 v8 예외:", e)
        return None, None, None, None, None

# 뉴스 필터링용 키워드 정의
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

NEWS_SOFT_OPINION_WORDS = [
    "전망", "예상", "분석", "목표주가", "증권가", "전문가", "기대감",
    "가능성", "주목", "관심", "수혜주", "관련주", "추천", "진단",
    "전략", "시나리오", "전망치", "forecast", "estimate", "analyst",
    "target price"
]

def fetch_google_news_rss(query):
    """Google News RSS에서 기사 수집 및 우선순위 정렬"""
    try:
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            xml_bytes = resp.read()

        root = ET.fromstring(xml_bytes)
        articles = []

        for item in root.findall(".//item"):
            title = item.findtext("title") or ""
            link = item.findtext("link") or ""
            pub_date = item.findtext("pubDate") or ""
            source = item.find("source").text if item.find("source") is not None else ""

            score = NEWS_SOURCE_PRIORITY.get(source, 50)
            title_lower = title.lower()

            if any(word in title_lower for word in NEWS_HARD_EVENT_WORDS):
                score += 30
            if any(word in title_lower for word in NEWS_SOFT_OPINION_WORDS):
                score -= 10

            articles.append({
                "title": title,
                "link": link,
                "source": source,
                "pub_date": pub_date,
                "score": score
            })

        articles.sort(key=lambda x: x["score"], reverse=True)
        return articles[:3]
    except Exception as e:
        print(f"뉴스 수집 에러: {e}")
        return []

# --- Flask Route Handlers ---

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "message": "Stock Information Backend API is Running."
    })

@app.route('/api/stock', methods=['GET'])
def get_stock_info():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({"error": "검색할 종목명을 입력하세요 (쿼리 파라미터 'q')"}), 400

    # 1. 티커 변환 확인
    ticker = TICKERS.get(query)
    code_six = None

    if not ticker:
        # 네이버 금융 자동완성 검색 시도 (국내)
        ticker, code_six = search_krx_code(query)

    if not ticker:
        # 미국 종목 단독 심볼 검색 예외 처리
        ticker = query.upper()

    result = {
        "query": query,
        "ticker": ticker,
        "type": "US" if not ticker.endswith(('.KS', '.KQ')) and not code_six else "KR"
    }

    # 2. 국내/해외별 데이터 조회
    if result["type"] == "KR":
        if not code_six:
            code_six = ticker.split('.')[0]

        cur_p, diff, ratio = fetch_kr_stock_realtime(code_six)
        ma20, resistance, sum_foreign, sum_inst, sum_indiv, days = fetch_krx_trend_and_supply(code_six)
        disclosures = fetch_kr_official_disclosures(code_six)

        result["price"] = {"current": cur_p, "change": diff, "ratio": ratio}
        result["technical"] = {"ma20": ma20, "resistance": resistance}
        result["supply_5d"] = {
            "foreign": sum_foreign,
            "institution": sum_inst,
            "individual": sum_indiv,
            "valid_days": days
        }
        result["disclosures"] = disclosures
    else:
        cur_p, prev_p, ma20, res_p, volume_profile = fetch_yahoo_direct_v8(ticker)
        filings = fetch_us_official_filings(ticker)

        result["price"] = {
            "current": cur_p,
            "previous": prev_p,
            "change": round(cur_p - prev_p, 2) if cur_p and prev_p else None
        }
        result["technical"] = {"ma20": ma20, "resistance": res_p}
        result["filings"] = filings

    # 3. 뉴스 수집
    result["news"] = fetch_google_news_rss(query)

    return jsonify(result)

if __name__ == '__main__':
    # 로컬 개발 환경 실행
    app.run(host='0.0.0.0', port=5000, debug=True)
