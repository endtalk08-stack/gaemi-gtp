"""Independent DigitalOcean US macro/earnings calendar collector.

No Neon calls, no AI, no worker restart. Writes one atomic local snapshot.
Run: python -m backend.us_market_calendar --output /run/gaemi-gateway/us-market-calendar.json
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib import error, parse, request
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
KST = ZoneInfo("Asia/Seoul")
UTC = dt.timezone.utc
ECONOMIC_URL = "https://www.financecalendar.com/wp-json/fc/v1/calendar"
EARNINGS_URL = "https://finnhub.io/api/v1/calendar/earnings"
SOURCE_CREDIT = "https://www.financecalendar.com"
DEFAULT_OUTPUT = "/run/gaemi-gateway/us-market-calendar.json"

# Only relevant US macro announcements, no unrelated schedule/title matches.
ECONOMIC_LABELS = (
    (("fomc", "fed rate decision"), "FOMC 기준금리 결정"),
    (("consumer price index", "us-cpi", " cpi"), "CPI 소비자물가지수"),
    (("producer price index", "us-ppi", " ppi"), "PPI 생산자물가지수"),
    (("nonfarm payroll", "employment situation", "jobs report"), "고용보고서"),
    (("unemployment rate",), "실업률"),
    (("personal consumption expenditures", "personal income and outlays", "core pce", " pce"), "PCE 물가지수"),
    (("gross domestic product", " gdp", "us-gdp"), "GDP"),
    (("retail sales",), "소매판매"),
    (("initial jobless claims", "weekly unemployment claims"), "신규실업수당 청구"),
    (("ism manufacturing", "manufacturing pmi"), "ISM 제조업"),
    (("ism services", "services pmi"), "ISM 서비스업"),
    (("jolts", "job openings and labor turnover"), "JOLTS 구인"),
    (("adp employment", "adp nonfarm"), "ADP 고용"),
    (("durable goods orders",), "내구재 주문"),
    (("consumer confidence",), "소비자신뢰지수"),
    (("new home sales",), "신규주택판매"),
    (("crude oil inventories", "eia petroleum"), "원유재고"),
)
# Market-moving US earnings; do not restrict collection to this list.
FOCUS_SYMBOLS = {
    "NVDA", "MSFT", "AAPL", "AMZN", "GOOGL", "GOOG", "META", "TSLA",
    "AMD", "AVGO", "MU", "INTC", "ORCL", "NFLX", "CRM", "ADBE",
    "JPM", "BAC", "GS", "COST", "LLY", "WMT", "NKE", "HD", "KO",
    "GEV", "ADP", "APH", "VRT", "SNDK",
}


def nullable(value):
    if value is None or value == "" or value == "-":
        return None
    return value


def fetch_json(url, params, timeout=12):
    uri = url + "?" + parse.urlencode(params)
    req = request.Request(uri, headers={"User-Agent": "gaemiGTP-calendar/1.0", "Accept": "application/json"})
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except error.HTTPError as exc:
        raise RuntimeError("http_{}".format(exc.code)) from None
    except error.URLError:
        raise RuntimeError("network_unavailable") from None
    except (ValueError, UnicodeError, json.JSONDecodeError):
        raise RuntimeError("invalid_json") from None


def parse_economic_time(row):
    """Return an exact UTC instant only when upstream supplies trustworthy time."""
    for field in ("time_utc", "datetime_utc", "datetime"):
        value = row.get(field)
        if not value:
            continue
        try:
            parsed_time = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed_time.tzinfo is not None:
                return parsed_time.astimezone(UTC)
        except ValueError:
            pass
    d = str(row.get("date") or "")[:10]
    t = str(row.get("time_et") or "").strip()
    if not d or not t:
        return None
    match = re.fullmatch(r"(\d{1,2}):(\d{2})\s*(AM|PM)", t, re.IGNORECASE)
    try:
        if match:
            h = int(match.group(1)) % 12 + (12 if match.group(3).upper() == "PM" else 0)
            m = int(match.group(2))
            return dt.datetime.combine(dt.date.fromisoformat(d), dt.time(h, m), ET).astimezone(UTC)
        match = re.fullmatch(r"(\d{1,2}):(\d{2})", t)
        if match:
            return dt.datetime.combine(dt.date.fromisoformat(d), dt.time(int(match.group(1)), int(match.group(2))), ET).astimezone(UTC)
    except ValueError:
        return None
    return None


def economic_label(row):
    text = " ".join(str(row.get(field) or "") for field in ("series", "title", "name", "event")).lower()
    for patterns, label in ECONOMIC_LABELS:
        if any(pattern in text for pattern in patterns):
            return label
    return None


def fetch_economic(start, end):
    payload = fetch_json(ECONOMIC_URL, {
        "country": "US", "from": start.isoformat(), "to": end.isoformat(), "limit": 500,
    })
    rows = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError("unexpected_economic_schema")
    results = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        country = str(row.get("country") or "").lower()
        if country and country not in {"us", "usa", "united states", "u.s.", "u.s.a."}:
            continue
        label = economic_label(row)
        if not label:
            continue
        instant = parse_economic_time(row)
        publisher_date = str(row.get("date") or "")[:10]
        if not publisher_date and instant:
            publisher_date = instant.astimezone(ET).date().isoformat()
        if not publisher_date:
            continue
        results.append({
            "type": "economic", "name": label, "symbol": None,
            "date_et": publisher_date, "time_kst": instant.astimezone(KST).isoformat() if instant else None,
            "timing": "exact" if instant else "date_only",
            "consensus": nullable(row.get("consensus")),
            "previous": nullable(row.get("prior") if row.get("prior") is not None else row.get("previous")),
            "actual": nullable(row.get("actual")),
            "eps_estimate": None, "revenue_estimate": None,
            "eps_actual": None, "revenue_actual": None,
            "source": "Finance Calendar", "source_url": nullable(row.get("url")),
            "focus": True,
        })
    return results


def fetch_earnings(start, end, api_key):
    if not api_key:
        raise RuntimeError("missing_finnhub_key")
    payload = fetch_json(EARNINGS_URL, {
        "from": start.isoformat(), "to": end.isoformat(),
        "international": "false", "token": api_key,
    })
    rows = payload.get("earningsCalendar") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError("unexpected_earnings_schema")
    results = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        date_et = str(row.get("date") or "")[:10]
        if not symbol or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_et):
            continue
        session = str(row.get("hour") or "").lower()
        # Finnhub bmo/amc are broad windows, not exact publication timestamps.
        timing = {"bmo": "before_market_open", "amc": "after_market_close"}.get(session, "unknown")
        results.append({
            "type": "earnings", "name": symbol + " 실적 발표", "symbol": symbol,
            "date_et": date_et, "time_kst": None, "timing": timing,
            "consensus": None, "previous": None, "actual": None,
            "eps_estimate": nullable(row.get("epsEstimate")),
            "revenue_estimate": nullable(row.get("revenueEstimate")),
            "eps_actual": nullable(row.get("epsActual")),
            "revenue_actual": nullable(row.get("revenueActual")),
            "source": "Finnhub", "source_url": None, "focus": symbol in FOCUS_SYMBOLS,
        })
    return results


def write_atomic(path, data):
    output = Path(path)
    if not output.parent.is_dir():
        raise RuntimeError("output_directory_missing")
    fd, name = tempfile.mkstemp(prefix=".us-calendar-", dir=str(output.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, output)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def collect(output):
    now = dt.datetime.now(UTC)
    us_today = now.astimezone(ET).date()
    start, end = us_today - dt.timedelta(days=1), us_today + dt.timedelta(days=7)
    statuses, events = {}, []
    for source, collector in (
        ("economic", lambda: fetch_economic(start, end)),
        ("earnings", lambda: fetch_earnings(start, end, os.environ.get("FINNHUB_API_KEY", "").strip())),
    ):
        try:
            rows = collector()
            events.extend(rows)
            statuses[source] = {"ok": True, "count": len(rows)}
        except Exception as exc:
            # Do not expose credential-bearing request URLs or environment values.
            code = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
            statuses[source] = {"ok": False, "error": code}
    if not any(item["ok"] for item in statuses.values()):
        print("CALENDAR_FETCH_FAILED " + json.dumps(statuses, ensure_ascii=False))
        return 1
    unique = {}
    for item in events:
        key = (item["type"], item["symbol"] or item["name"], item["date_et"], item["timing"])
        unique[key] = item
    events = sorted(unique.values(), key=lambda x: (x["date_et"], x["time_kst"] or "", x["type"], x["name"]))
    snapshot = {
        "schema": 1, "fetched_at_utc": now.isoformat(),
        "window_et": {"from": start.isoformat(), "to": end.isoformat()},
        "status": "ok" if all(x["ok"] for x in statuses.values()) else "partial",
        "sources": statuses, "count": len(events), "events": events,
        "attribution": {"economic": SOURCE_CREDIT, "earnings": "Finnhub"},
    }
    write_atomic(output, snapshot)
    counts = {"economic": sum(e["type"] == "economic" for e in events),
              "earnings": sum(e["type"] == "earnings" for e in events)}
    print("CALENDAR_SNAPSHOT_OK " + json.dumps({
        "output": output, "status": snapshot["status"], "count": len(events),
        "by_type": counts, "sources": statuses,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect US economic releases and company earnings to a local JSON snapshot")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        sys.exit(collect(args.output))
    except Exception as exc:
        print("CALENDAR_WRITE_FAILED " + type(exc).__name__)
        sys.exit(1)
