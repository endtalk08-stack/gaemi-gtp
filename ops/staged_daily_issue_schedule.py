"""Daily US stock issue analysis schedule, staging only.

No worker is wired to call this module yet.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
NEW_YORK = ZoneInfo("America/New_York")


def scheduled_kst_time(day):
    """US market-open + 60 minutes, converted to Korean local time."""
    eastern = datetime(day.year, day.month, day.day, 10, 30, tzinfo=NEW_YORK)
    return eastern.astimezone(KST)


def should_run(now, last_success_date):
    """A successful daily run prevents another call on its KST run date."""
    local = now.astimezone(KST)
    current_slot = scheduled_kst_time(local.date())
    if local < current_slot:
        return False
    return last_success_date != local.date().isoformat()
