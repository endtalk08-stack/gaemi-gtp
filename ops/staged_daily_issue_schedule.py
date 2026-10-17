"""KST-visible daily US stock issue schedule. Staged, not activated."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
NEW_YORK = ZoneInfo("America/New_York")


def scheduled_kst_time(us_calendar_date):
    """US calendar date at 10:30 AM New York (one hour after regular open)."""
    eastern = datetime(us_calendar_date.year, us_calendar_date.month,
                       us_calendar_date.day, 10, 30, tzinfo=NEW_YORK)
    return eastern.astimezone(KST)


def due_run(now, completed_us_dates):
    """Return US calendar date to run once, or None.

    Check both today and yesterday in Korea so midnight winter runs are correct.
    Completed dates must be stored durably by production caller.
    """
    now_kst = now.astimezone(KST)
    completed = set(completed_us_dates)
    for offset in (1, 0):
        us_day = now_kst.date() - timedelta(days=offset)
        slot = scheduled_kst_time(us_day)
        if slot <= now_kst < slot + timedelta(minutes=30) and us_day.isoformat() not in completed:
            return us_day.isoformat()
    return None
