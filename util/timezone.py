from datetime import datetime, time
from zoneinfo import ZoneInfo

STOCKHOLM = ZoneInfo("Europe/Stockholm")


def stockholm_now() -> datetime:
    return datetime.now(STOCKHOLM)


def stockholm_time(hour: int, minute: int = 0) -> time:
    return time(hour, minute, tzinfo=STOCKHOLM)
