"""Exchange-local date filtering for official disclosure results; no persistence."""
import datetime as dt
import re
from zoneinfo import ZoneInfo


def _filing_timestamp(item, market, now):
    zone = ZoneInfo("Asia/Seoul" if market == "KR" else "America/New_York")
    if market == "US":
        raw = str(item.get("acceptance_datetime") or "").strip()
        if raw:
            try:
                value = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
                return value.replace(tzinfo=zone).astimezone(dt.timezone.utc) if value.tzinfo is None else value.astimezone(dt.timezone.utc)
            except ValueError:
                pass
        raw_date = str(item.get("date") or "")[:10]
    else:
        raw_date = str(item.get("receipt_datetime") or "").strip()[:8]
        if not re.fullmatch(r"\d{8}", raw_date):
            raw_date = str(item.get("date") or "").strip()
        if re.fullmatch(r"\d{8}", raw_date):
            raw_date = raw_date[:4] + "-" + raw_date[4:6] + "-" + raw_date[6:]
    try:
        local_date = dt.date.fromisoformat(raw_date)
    except ValueError:
        return None
    local_today = now.astimezone(zone).date()
    time_string = str(item.get("time") or "").strip()
    if re.fullmatch(r"\d{1,2}:\d{2}", time_string):
        hour, minute = map(int, time_string.split(":"))
        if hour < 24 and minute < 60:
            return dt.datetime.combine(local_date, dt.time(hour, minute), tzinfo=zone).astimezone(dt.timezone.utc)
    return dt.datetime.combine(local_date, dt.time.min, tzinfo=zone).astimezone(dt.timezone.utc) if local_date == local_today else None


def today_filings(filings, market, *, now=None):
    market = str(market).upper()
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now_requires_timezone")
    zone = ZoneInfo("Asia/Seoul" if market == "KR" else "America/New_York")
    today = now.astimezone(zone).date()
    result = []
    for item in filings or []:
        if not isinstance(item, dict):
            continue
        moment = _filing_timestamp(item, market, now)
        if moment is not None and moment.astimezone(zone).date() == today:
            result.append(item)
    return result
