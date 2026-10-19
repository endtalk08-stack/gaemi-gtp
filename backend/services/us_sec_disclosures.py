"""Read US SEC filings on demand for the central chat. No database writes."""
import datetime as dt
import json
import os
import re
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

from . import engine

SEC_AGENT = os.getenv("SEC_USER_AGENT", "").strip().strip("'\"")
FORMS_FINANCIAL = {"10-Q", "10-K"}
METRIC_TAGS = (
    ("매출", ("RevenueFromContractWithCustomerExcludingAssessedTax",
             "RevenueFromContractWithCustomerIncludingAssessedTax",
             "Revenues", "SalesRevenueNet", "SalesRevenueGoodsNet"), "USD"),
    ("영업이익", ("OperatingIncomeLoss",), "USD"),
    ("순이익", ("NetIncomeLoss", "ProfitLoss"), "USD"),
    ("희석 EPS", ("EarningsPerShareDiluted",), "USD/shares"),
)


class SecReadError(Exception):
    """SEC request failed. Do not mistake this for an empty filing list."""


def _json(url):
    headers = {"User-Agent": SEC_AGENT or "gaemiGTP/1.0 (SEC filings reader)",
               "Accept": "application/json"}
    try:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=7) as response:
            return json.load(response)
    except (OSError, ValueError, urllib.error.HTTPError) as exc:
        raise SecReadError(type(exc).__name__) from exc


def resolve_ticker(stock):
    value = str(stock or "").strip()
    symbol = str(engine.TICKERS.get(value, value)).upper()
    return symbol if symbol in engine.US_CIKS else ""


def _submissions(ticker):
    cik = str(engine.US_CIKS[ticker])
    response = _json(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json")
    return cik, (response.get("filings") or {}).get("recent") or {}


def _rows(ticker, recent, cik, limit=100):
    """List *all* SEC form types; do not drop 8-Ks that lack extracted details."""
    columns = ("form", "filingDate", "acceptanceDateTime", "accessionNumber",
               "primaryDocument", "primaryDocDescription")
    values = {name: list(recent.get(name) or []) for name in columns}
    rows = []
    for i, accession in enumerate(values["accessionNumber"][:limit]):
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", str(accession)):
            continue
        def at(key):
            return str(values[key][i] if i < len(values[key]) else "").strip()
        document = at("primaryDocument")
        path = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}"
        form = at("form")
        description = at("primaryDocDescription")
        rows.append({
            "ticker": ticker, "cik": cik, "accession": accession,
            "form": form, "date": at("filingDate"),
            "acceptance_datetime": at("acceptanceDateTime"),
            "title": description if description and description.lower() not in {"", "primary document"} else f"SEC {form} 공시",
            "description": description,
            "url": path + "/" + accession + "-index.htm",
            "original_document_url": path + "/" + document if document else "",
        })
    return rows


def list_today(stock, today=None):
    ticker = resolve_ticker(stock)
    if not ticker:
        raise ValueError("unsupported_stock")
    filing_day = today or dt.datetime.now(ZoneInfo("America/New_York")).date()
    cik, recent = _submissions(ticker)
    rows = _rows(ticker, recent, cik, limit=300)
    return {
        "ticker": ticker,
        "filing_date": filing_day.isoformat(),
        "time_zone": "America/New_York",
        "items": [row for row in rows if row["date"] == filing_day.isoformat()][:60],
    }


def _quarterly_units(fact, unit):
    return list((fact.get("units") or {}).get(unit) or [])


def _financial_metrics(companyfacts, accession, form):
    facts = (companyfacts.get("facts") or {}).get("us-gaap") or {}
    duration_min, duration_max = (60, 120) if form == "10-Q" else (280, 400)
    metrics = []
    for label, tags, unit in METRIC_TAGS:
        candidates = []
        for tag in tags:
            fact = facts.get(tag)
            if not fact:
                continue
            candidates = [entry for entry in _quarterly_units(fact, unit)
                          if entry.get("accn") == accession and entry.get("form") == form
                          and entry.get("start") and entry.get("end")
                          and isinstance(entry.get("val"), (float, int))]
            candidates = [entry for entry in candidates
                          if duration_min <= (dt.date.fromisoformat(entry["end"]) -
                                              dt.date.fromisoformat(entry["start"])).days <= duration_max]
            if candidates:
                break
        if not candidates:
            continue
        # Only use the reporting period belonging to this filing, never an
        # arbitrary newer value or year-to-date amount for a quarterly chart.
        current = max(candidates, key=lambda entry: (entry["end"], entry["start"]))
        period_days = (dt.date.fromisoformat(current["end"]) - dt.date.fromisoformat(current["start"])).days
        previous_rows = [entry for entry in _quarterly_units(fact, unit)
                         if entry.get("start") and entry.get("end")
                         and isinstance(entry.get("val"), (float, int))
                         and entry.get("filed", "") <= current.get("filed", "9999-12-31")]
        previous_rows = [entry for entry in previous_rows
                         if 350 <= (dt.date.fromisoformat(current["end"]) -
                                    dt.date.fromisoformat(entry["end"])).days <= 380
                         and abs((dt.date.fromisoformat(entry["end"]) -
                                  dt.date.fromisoformat(entry["start"])).days - period_days) <= 12]
        previous = max(previous_rows, key=lambda entry: entry.get("filed", "")) if previous_rows else None
        metrics.append({
            "label": label, "unit": unit, "current": current["val"],
            "previous": previous["val"] if previous else None,
            "period_end": current["end"],
            "previous_period_end": previous["end"] if previous else None,
        })
    return metrics


def detail(stock, accession):
    ticker = resolve_ticker(stock)
    if not ticker or not re.fullmatch(r"\d{10}-\d{2}-\d{6}", str(accession or "")):
        raise ValueError("invalid_filing")
    cik, recent = _submissions(ticker)
    row = next((item for item in _rows(ticker, recent, cik, limit=300)
                if item["accession"] == accession), None)
    if row is None:
        raise ValueError("filing_not_found")
    form = row["form"].upper()
    if form == "8-K":
        engine._enrich_us_8k_from_submission(row, ticker)
        row["detail_status"] = "ready" if row.get("key_points") or row.get("key_points_ko") else "partial"
    elif form == "4":
        engine._enrich_us_form4_from_submission(row, ticker)
        row["detail_status"] = "ready" if row.get("transactions") else "partial"
    elif form in FORMS_FINANCIAL:
        payload = _json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json")
        row["metrics"] = _financial_metrics(payload, accession, form)
        row["detail_status"] = "ready" if row["metrics"] else "partial"
    else:
        row["detail_status"] = "not_supported"
    return row
