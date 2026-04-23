from datetime import date, datetime

from app import Settings


def now() -> datetime:
    return datetime.now(Settings.timezone_info)


def today() -> date:
    return now().date()
