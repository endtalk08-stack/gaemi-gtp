"""Strict one-stock, one-provider-request SEC/DART snapshot collector (DigitalOcean).

Never invoked automatically. Execution requires BOTH explicit --confirm-single
and GAEMI_MANUAL_DISCLOSURE_OK=YES. Importing/CLI dry-run sends zero requests.
Does not run enrichment, pagination, retries, bulk discovery or scheduling.
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo
from .disclosure_universe import disclosure_identity

DAYS = 30
MAX_RESPONSE_BYTES = 8_000_000


class IncompleteDisclosureWindow(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _get_json_once(url, headers):
    """Exactly one GET; no retries, no redirects, no next-page requests."""
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, headers=headers)
    with opener.open(req, timeout=10) as resp:
        data = resp.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("disclosure_response_too_large")
    return json.loads(data)


def _collect_kr(symbol, corp_code, now):
    today = now.astimezone(ZoneInfo("Asia/Seoul")).date()
    cutoff = today - dt.timedelta(days=DAYS)
    params = urllib.parse.urlencode({
        "crtfc_key": os.environ["OPENDART_API_KEY"],
        "corp_code": corp_code,
        "bgn_de": cutoff.strftime("%Y%m%d"),
        "end_de": today.strftime("%Y%m%d"),
        "page_no": 1,
        "page_count": 100,
    })
    data = _get_json_once(
        "https://opendart.fss.or.kr/api/list.json?" + params,
        {"User-Agent": "gaemiGTP disclosure one-stock manual verification",
         "Accept": "application/json"},
    )
    status = str(data.get("status", ""))
    if status == "013":  # OpenDART: no filings for this window
        return []
    if status != "000":
        raise RuntimeError("dart_provider_status_" + status[:6])
    if int(data.get("total_page", 1)) > 1:
        raise IncompleteDisclosureWindow("dart_multi_page_refused_no_partial_save")
    results = []
    for item in data.get("list", []):
        receipt = str(item.get("rcept_dt", ""))
        report = str(item.get("report_nm", "")).strip()
        receipt_no = str(item.get("rcept_no", ""))
        if not (len(receipt) == 8 and receipt.isdigit() and report and receipt_no):
            continue
        receipt_date = dt.datetime.strptime(receipt, "%Y%m%d").date()
        if receipt_date < cutoff or receipt_date > today:
            continue
        results.append({
            "date": f"{receipt_date.month}/{receipt_date.day}",
            "report": report, "receipt_no": receipt_no,
            "time": "", "time_zone": "",
            "receipt_datetime": receipt,
            "score": 0,
        })
    return sorted(results, key=lambda x: (x["receipt_datetime"], x["receipt_no"]), reverse=True)


def _collect_us(symbol, cik, now):
    today = now.astimezone(ZoneInfo("America/New_York")).date()
    cutoff = today - dt.timedelta(days=DAYS)
    user_agent = os.environ["SEC_USER_AGENT"].strip()
    if "@" not in user_agent:
        raise ValueError("sec_user_agent_must_identify_contact")
    data = _get_json_once(
        "https://data.sec.gov/submissions/CIK" + cik + ".json",
        {"User-Agent": user_agent, "Accept": "application/json"},
    )
    company_cik = data.get("cik")
    if company_cik is not None and str(company_cik).zfill(10) != cik:
        raise ValueError("sec_cik_mismatch")
    recent = data.get("filings", {}).get("recent", {})
    dates = recent.get("filingDate", [])
    if not isinstance(dates, list) or not dates:
        raise IncompleteDisclosureWindow("sec_no_filing_dates_refused")
    parsed_dates = [dt.date.fromisoformat(str(d)) for d in dates]
    if min(parsed_dates) > cutoff:
        raise IncompleteDisclosureWindow("sec_recent_window_incomplete_no_partial_save")
    results = []
    for i, when in enumerate(parsed_dates):
        if not (cutoff <= when <= today):
            continue
        try:
            form = str(recent["form"][i])
            accession = str(recent["accessionNumber"][i])
            doc = str(recent["primaryDocument"][i])
        except (KeyError, IndexError, TypeError):
            raise IncompleteDisclosureWindow("sec_column_mismatch_no_partial_save")
        if not (form and accession):
            continue
        clean = accession.replace("-", "")
        base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{clean}/"
        descs = recent.get("primaryDocDescription", [])
        accepted = recent.get("acceptanceDateTime", [])
        description = descs[i] if i < len(descs) else ""
        acceptance_datetime = accepted[i] if i < len(accepted) else ""
        tm = str(acceptance_datetime).split("T", 1)
        results.append({
            "date": when.isoformat(), "form": form,
            "description": str(description or "SEC 공식 공시"),
            "time": tm[1][:5] if len(tm) > 1 else "",
            "acceptance_datetime": acceptance_datetime,
            "url": base + accession + "-index.htm",
            "original_document_url": base + urllib.parse.quote(doc) if doc else "",
            "accession": accession, "cik": cik,
        })
    return results


def collect_once(market, symbol, now=None):
    """At most one provider HTTP request for ONE fixed-universe stock."""
    market, symbol, name, identity = disclosure_identity(market, symbol)
    database_url = os.environ.get("NEWS_DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("news_database_missing")
    if market == "KR" and not os.environ.get("OPENDART_API_KEY"):
        raise RuntimeError("dart_key_missing")
    if market == "US" and not os.environ.get("SEC_USER_AGENT"):
        raise RuntimeError("sec_user_agent_missing")
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now_requires_timezone")
    records = (_collect_kr(symbol, identity, now) if market == "KR"
               else _collect_us(symbol, identity, now))
    import psycopg
    from psycopg.types.json import Jsonb
    with psycopg.connect(database_url, connect_timeout=4) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO public.disclosure_snapshots(market,symbol,filings,fetched_at)
                   VALUES (%s,%s,%s,now())
                   ON CONFLICT (market,symbol) DO UPDATE
                   SET filings=EXCLUDED.filings, fetched_at=EXCLUDED.fetched_at""",
                (market, symbol, Jsonb(records)),
            )
    return {"market": market, "symbol": symbol, "company": name,
            "filing_count": len(records), "provider_requests": 1}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Single-ticker disclosure manual collector, zero HTTP by default")
    parser.add_argument("--market", required=True, choices=("KR", "US"))
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--confirm-single", action="store_true")
    args = parser.parse_args(argv)
    try:
        market, symbol, name, _ = disclosure_identity(args.market, args.symbol)
        if not (args.confirm_single and os.environ.get("GAEMI_MANUAL_DISCLOSURE_OK") == "YES"):
            print(json.dumps({"market": market, "symbol": symbol, "company": name,
                              "mode": "DRY_RUN_NO_PROVIDER_REQUEST", "required_approval": True},
                             ensure_ascii=False))
            return 0
        print(json.dumps(collect_once(market, symbol), ensure_ascii=False))
        return 0
    except Exception as exc:
        print("disclosure_manual_error=" + type(exc).__name__, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
