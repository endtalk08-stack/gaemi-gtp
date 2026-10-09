"""SEC EDGAR submissions provider for US stock news analysis.

SEC's public data API does not require an API key. Automated requests should
identify the caller with SEC_USER_AGENT (for example: "gaemiGTP you@example.com").
"""

import datetime
import json
import os
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


def is_configured():
    return bool(SEC_USER_AGENT)


def _request_json(url, ttl):
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
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
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
