"""SEC EDGAR submissions provider for US stock news analysis.

SEC's public data API does not require an API key. Automated requests should
identify the caller with SEC_USER_AGENT (for example: "gaemiGTP you@example.com").
"""

import datetime
import json
import html
import os
import re
import urllib.error
import threading
import time
import urllib.request


REQUEST_TIMEOUT = 2.2
SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", "").strip().strip("'\"")
TICKER_DIRECTORY_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
IMPORTANT_FORMS = {
    "8-K", "10-Q", "10-K", "6-K", "20-F", "40-F",
    "DEF 14A", "4", "SC 13D", "SC 13G", "S-4",
}

_CACHE = {}
_CACHE_LOCK = threading.Lock()
_TICKER_TTL = 86400
_SUBMISSIONS_TTL = 180
_PANEL_SEC_FACTS_TTL = 900
_FORM4_CACHE_TTL = 3600
_FORM4_CACHE = {}
_SEC_INDEX_RE = re.compile(
    r"https://www\.sec\.gov/Archives/edgar/data/(?P<cik>\d{1,10})/"
    r"(?P<folder>\d{18})/(?P<accn>\d{10}-\d{2}-\d{6})-index\.htm"
)



def is_configured():
    return bool(SEC_USER_AGENT)


def _request_json(url, ttl, timeout=REQUEST_TIMEOUT):
    if not is_configured():
        return {}

    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(url)
        if cached and now - cached[0] <= ttl:
            return cached[1]

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": SEC_USER_AGENT,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"[provider:sec] failed url={url}: {type(exc).__name__}: {exc}")
        return {}

    with _CACHE_LOCK:
        _CACHE[url] = (now, payload)
    return payload


def _ticker_directory():
    payload = _request_json(TICKER_DIRECTORY_URL, _TICKER_TTL)
    directory = {}
    for row in (payload or {}).values():
        ticker = str((row or {}).get("ticker") or "").strip().upper()
        cik = (row or {}).get("cik_str")
        if not ticker or cik in (None, ""):
            continue
        try:
            directory[ticker] = int(cik)
        except (TypeError, ValueError):
            continue
    return directory


def _parse_datetime(value, fallback_date=""):
    raw = str(value or "").strip()
    if raw:
        try:
            dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt.astimezone(datetime.timezone.utc)
        except Exception:
            pass
    try:
        date = datetime.date.fromisoformat(str(fallback_date or "").strip())
        return datetime.datetime.combine(date, datetime.time.min, tzinfo=datetime.timezone.utc)
    except Exception:
        return None


def _normalize_recent_filings(payload, *, stock_name, ticker, cik, days=7, limit=10):
    recent = (((payload or {}).get("filings") or {}).get("recent") or {})
    forms = list(recent.get("form") or [])
    now = datetime.datetime.now(datetime.timezone.utc)
    rows = []

    def value(field, index):
        values = recent.get(field) or []
        return values[index] if index < len(values) else ""

    for index, form in enumerate(forms):
        form = str(form or "").strip()
        if form not in IMPORTANT_FORMS:
            continue

        filing_date = str(value("filingDate", index) or "").strip()
        accepted = _parse_datetime(value("acceptanceDateTime", index), filing_date)
        if accepted and now - accepted > datetime.timedelta(days=max(1, int(days))):
            continue

        accession = str(value("accessionNumber", index) or "").strip()
        primary_document = str(value("primaryDocument", index) or "").strip()
        description = str(value("primaryDocDescription", index) or "").strip()
        items = str(value("items", index) or "").strip()

        accession_path = accession.replace("-", "")
        if accession_path and primary_document:
            link = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                f"{accession_path}/{primary_document}"
            )
        else:
            link = f"https://www.sec.gov/edgar/browse/?CIK={int(cik)}"

        detail_parts = [f"{stock_name} filed Form {form} with the SEC."]
        if description:
            detail_parts.append(description)
        if items:
            detail_parts.append(f"Items: {items}")

        rows.append({
            "provider": "sec",
            "source_type": "sec_filing",
            "provider_stock": stock_name,
            "source": "SEC EDGAR",
            "source_quality": 100,
            "title": f"{stock_name} SEC {form} 공시",
            "description": " ".join(detail_parts),
            "summary": " ".join(detail_parts),
            "published_at": accepted.isoformat() if accepted else "",
            "link": link,
            "url": link,
            "category": "종목",
            "region": "미국",
            "sec_form": form,
            "sec_accession": accession,
            "sec_cik": int(cik),
            "ticker": ticker,
        })
        if len(rows) >= max(1, int(limit)):
            break

    rows.sort(key=lambda item: item.get("published_at") or "", reverse=True)
    return rows



def _panel_submission(index_url):
    """Verify SEC archival identity and find the form in SEC's own submissions."""
    match = _SEC_INDEX_RE.fullmatch(str(index_url or "").strip())
    if not match or match.group("folder") != match.group("accn").replace("-", ""):
        raise ValueError("invalid_sec_filing_url")
    cik, accession = int(match.group("cik")), match.group("accn")
    payload = _request_json(SUBMISSIONS_URL.format(cik=cik), _SUBMISSIONS_TTL)
    recent = ((payload.get("filings") or {}).get("recent") or {})
    accessions = recent.get("accessionNumber") or []
    try:
        index = accessions.index(accession)
    except ValueError:
        raise ValueError("sec_filing_not_found") from None
    def field(name):
        values = recent.get(name) or []
        return str(values[index] or "").strip() if index < len(values) else ""
    return cik, accession, field("form").upper(), field("primaryDocument")


def _panel_xml_value(xml, tag):
    """Read a scalar SEC XML field with optional namespace prefix."""
    pattern = rf"<(?:[A-Za-z0-9_.-]+:)?{re.escape(tag)}\b[^>]*>(.*?)</(?:[A-Za-z0-9_.-]+:)?{re.escape(tag)}>"
    match = re.search(pattern, xml, re.I | re.S)
    if not match:
        return ""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", match.group(1)))).strip()



def _panel_form4_from_xml(xml):
    """Extract each SEC Form 4 transaction exactly once from its XML table.

    Table I shares are actual common-stock transactions. Table II derivatives
    (including RSU awards) are distinct rights, not a second cash share sale.
    """
    person = _panel_xml_value(xml, "rptOwnerName")
    position = _panel_xml_value(xml, "officerTitle")
    if not position:
        for tag, label in (("isDirector", "Director"), ("isOfficer", "Officer"),
                           ("isTenPercentOwner", "10% Owner")):
            if _panel_xml_value(xml, tag).lower() in ("1", "true"):
                position = label
                break
    transactions = []
    for table_tag, derivative in (("nonDerivativeTransaction", False),
                                  ("derivativeTransaction", True)):
        matches = re.findall(
            rf"<(?:[A-Za-z0-9_.-]+:)?{table_tag}\b[^>]*>(.*?)"
            rf"</(?:[A-Za-z0-9_.-]+:)?{table_tag}>", xml, flags=re.I | re.S)
        for block in matches:
            code = _panel_xml_value(block, "transactionCode").upper()
            shares = _panel_xml_value(block, "transactionShares")
            if not (code or shares):
                continue
            transactions.append({
                "code": code,
                "shares": shares,
                "price": _panel_xml_value(block, "transactionPricePerShare"),
                "acquired_disposed": _panel_xml_value(block, "transactionAcquiredDisposedCode").upper(),
                "derivative": derivative,
                "security": _panel_xml_value(block, "securityTitle"),
            })
    return {"person": person, "officer_title": position, "transactions": transactions}


def enrich_form4_filing(filing, ticker_symbol):
    """One existing-provider Form 4/4A parser shared by the engine right panel.

    Returns original filing on network failure; never fabricates a trade.
    """
    accession = str(filing.get("accession") or "").strip()
    cik = str(filing.get("cik") or "").strip()
    original_url = str(filing.get("original_document_url") or "").strip()
    if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession) or not cik.isdigit():
        return filing
    cache_key = (int(cik), accession)
    now = time.time()
    with _CACHE_LOCK:
        cached = _FORM4_CACHE.get(cache_key)
    if cached and now - cached[0] < _FORM4_CACHE_TTL:
        filing.update(cached[1])
        return filing

    sec_root = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"
    candidates = [sec_root + accession + ".txt"]
    if original_url.startswith(sec_root) and re.fullmatch(
        r"[A-Za-z0-9_.-]{1,180}", original_url[len(sec_root):]):
        candidates.append(original_url)
    headers = {"User-Agent": SEC_USER_AGENT or os.environ.get("SEC_USER_AGENT", "gaemiGTP/1.0"),
               "Accept": "text/xml,application/xml,text/plain,*/*"}
    parsed = {}
    for url in candidates:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=6) as response:
                raw = response.read(2_000_000).decode("utf-8", errors="ignore")
            parsed = _panel_form4_from_xml(raw)
            # The submission TXT often carries both tables; keep it authoritative.
            if parsed["transactions"]:
                break
        except (OSError, urllib.error.HTTPError, ValueError) as exc:
            print(f"[provider:sec] Form 4 document fallback: {ticker_symbol} {type(exc).__name__}")
    if not parsed.get("person") and not parsed.get("transactions"):
        return filing

    transactions = parsed.get("transactions") or []
    code_labels = {
        "P": "내부자 매수", "S": "내부자 매도", "A": "내부자 취득",
        "D": "회사로 반환", "F": "세금·행사가격 지급",
        "M": "옵션·파생상품 행사", "G": "주식 증여",
        "V": "자발적 신고", "J": "기타 거래",
    }
    ordinary = [tx for tx in transactions if not tx["derivative"]]
    derivative = [tx for tx in transactions if tx["derivative"]]
    counters = {}
    for tx in ordinary:
        code = tx["code"]
        if code:
            counters[code] = counters.get(code, 0) + 1
    priority = ("P", "S", "A", "G", "F", "M", "D", "C", "J", "V")
    ordered = sorted(counters, key=lambda code: priority.index(code) if code in priority else len(priority))
    summary_parts = [f"{code_labels.get(code, '내부자 거래')} {counters[code]}건" for code in ordered]
    if derivative:
        summary_parts.append(f"RSU·옵션 등 파생증권 {len(derivative)}건")
    summary = " · ".join(summary_parts) or "내부자 거래"
    detail = {
        "person": parsed.get("person") or filing.get("person", ""),
        "officer_title": parsed.get("officer_title") or filing.get("officer_title", ""),
        "transactions": ordinary,
        "derivative_transactions": derivative,
        "transaction_kind": code_labels.get(ordered[0], "파생증권 변동" if derivative else "내부자 거래") if ordered else ("파생증권 변동" if derivative else "내부자 거래"),
        "transaction_summary": summary,
        "transaction_count": len(transactions),
        "price_range": "",
    }
    representative = ordinary[0] if ordinary else (derivative[0] if derivative else None)
    if representative:
        detail["transaction_code"] = representative["code"]
        if ordinary:
            detail["shares"] = representative["shares"]
            detail["price"] = representative["price"]
    filing.update(detail)
    with _CACHE_LOCK:
        _FORM4_CACHE[cache_key] = (time.time(), detail)
    return filing



def _panel_form144_fields(xml):
    """Use only values directly present in Form 144; planned sale is not an executed trade."""
    result = []
    person = _panel_xml_value(xml, "nameOfPersonForWhoseAccountTheSecuritiesAreToBeSold")
    if person:
        result.append({"label": "매도 예정자", "value": person})
    blocks = re.findall(
        r"<(?:[A-Za-z0-9_.-]+:)?securitiesInformation\b[^>]*>(.*?)"
        r"</(?:[A-Za-z0-9_.-]+:)?securitiesInformation>",
        xml, re.I | re.S,
    )
    for block in blocks[:8]:
        for label, tag in (
            ("증권 종류", "securitiesClassTitle"),
            ("매도 예정 주식 수", "noOfUnitsSold"),
            ("예상 시장가치(USD)", "aggregateMarketValue"),
            ("매도 예정일", "approxSaleDate"),
        ):
            value = _panel_xml_value(block, tag)
            if value:
                result.append({"label": label, "value": value})
    return result


def _panel_filing_metrics(facts, accession, form):
    us_gaap = ((facts.get("facts") or {}).get("us-gaap") or {})
    days_min, days_max = (60, 120) if form == "10-Q" else (280, 400)
    metrics = []
    tags_by_label = (
        ("매출", ("RevenueFromContractWithCustomerExcludingAssessedTax",
                 "RevenueFromContractWithCustomerIncludingAssessedTax",
                 "Revenues", "SalesRevenueNet"), "USD"),
        ("영업이익", ("OperatingIncomeLoss",), "USD"),
        ("순이익", ("NetIncomeLoss", "ProfitLoss"), "USD"),
        ("희석 EPS", ("EarningsPerShareDiluted",), "USD/shares"),
    )
    for label, tags, unit in tags_by_label:
        for tag in tags:
            points = ((us_gaap.get(tag) or {}).get("units") or {}).get(unit) or []
            candidates = []
            for point in points:
                if point.get("accn") != accession or point.get("form") != form:
                    continue
                if not isinstance(point.get("val"), (int, float)):
                    continue
                try:
                    length = (datetime.date.fromisoformat(point["end"]) -
                              datetime.date.fromisoformat(point["start"])).days
                except (KeyError, ValueError, TypeError):
                    continue
                if days_min <= length <= days_max:
                    candidates.append(point)
            if candidates:
                latest = max(candidates, key=lambda v: (v["end"], v["start"]))
                metrics.append({"label": label, "value": latest["val"],
                                "unit": unit, "period_end": latest["end"]})
                break
    return metrics


def fetch_panel_missing_detail(index_url):
    """Read-only missing Form 144/10-Q/10-K detail, for existing right-panel rows.

    Does not collect or replace the existing 30-day list in engine.py.
    SEC canonical index URL is validated before any outbound request.
    """
    result = {"status": "unavailable", "fields": [], "metrics": []}
    if not is_configured():
        return result
    cik, accession, form, document = _panel_submission(index_url)
    result["form"] = form
    if form not in {"144", "10-Q", "10-K"}:
        result["status"] = "existing_renderer"
        return result

    if form == "144":
        # SEC supplies the primary document name in its verified submission feed.
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,180}", document or ""):
            return result
        url = (f"https://www.sec.gov/Archives/edgar/data/"
               f"{cik}/{accession.replace('-', '')}/{document}")
        req = urllib.request.Request(
            url, headers={"User-Agent": SEC_USER_AGENT, "Accept": "text/xml,application/xml,*/*"})
        try:
            with urllib.request.urlopen(req, timeout=7) as resp:
                xml = resp.read(1_500_000).decode("utf-8", errors="ignore")
            result["fields"] = _panel_form144_fields(xml)
        except (OSError, urllib.error.HTTPError) as exc:
            print(f"[provider:sec] Form 144 detail unavailable: {type(exc).__name__}")
    else:
        # Reuse the existing SEC JSON request/cache layer, not another collector.
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
        facts = _request_json(url, _PANEL_SEC_FACTS_TTL, timeout=10)
        if facts:
            result["metrics"] = _panel_filing_metrics(facts, accession, form)
    if result["fields"] or result["metrics"]:
        result["status"] = "ready"
    return result

def fetch_recent_filings(stock_name, ticker, limit=10, days=7):
    if not is_configured():
        return []

    ticker = str(ticker or "").strip().upper()
    if not ticker:
        return []

    cik = _ticker_directory().get(ticker)
    if not cik:
        return []

    payload = _request_json(
        SUBMISSIONS_URL.format(cik=cik),
        _SUBMISSIONS_TTL,
    )
    if not payload:
        return []

    return _normalize_recent_filings(
        payload,
        stock_name=stock_name,
        ticker=ticker,
        cik=cik,
        days=days,
        limit=limit,
    )
