from datetime import date, datetime
from typing import Any

from app.untis.models import UntisPeriod

_DAY_NAMES = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]
_DAY_PREFIXES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_DAY_LABELS = [
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
]


def _format_time(t: int) -> str:
    return f"{t // 100:02d}:{t % 100:02d}"


def _date_int_to_date(d: int) -> date:
    return date(d // 10000, (d % 10000) // 100, d % 100)


def _convert_period(period: UntisPeriod) -> dict[str, Any]:
    subject_name = ""
    if period.subjects:
        el = period.subjects[0].element
        subject_name = el.long_name or el.name or ""
    elif period.lesson_text:
        subject_name = period.lesson_text

    return {
        "name": subject_name,
        "teachers": [t.element.name for t in period.teachers],
        "startTime": period.start_time,
        "endTime": period.end_time,
        "date": period.date,
        "class": period.classes[0].element.name if period.classes else "",
    }


def _make_free(start: int, end: int, date_int: int) -> dict[str, Any]:
    return {
        "name": "",
        "teachers": [],
        "startTime": start,
        "endTime": end,
        "date": date_int,
        "class": "",
    }


def _merge_continuous(lessons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not lessons:
        return []

    merged: list[dict[str, Any]] = []
    current = dict(lessons[0])

    for nxt in lessons[1:]:
        if current["endTime"] == nxt["startTime"] and current["date"] == nxt["date"] and current["name"] == nxt["name"]:
            all_teachers = current["teachers"] + nxt["teachers"]
            seen: set[str] = set()
            unique = []
            for t in all_teachers:
                if t not in seen:
                    seen.add(t)
                    unique.append(t)
            current = {**current, "endTime": nxt["endTime"], "teachers": unique}
        else:
            merged.append(current)
            current = dict(nxt)

    merged.append(current)
    return merged


def _insert_breaks(lessons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not lessons:
        return []

    by_date: dict[int, list[dict[str, Any]]] = {}
    for lesson in lessons:
        by_date.setdefault(lesson["date"], []).append(lesson)

    result: list[dict[str, Any]] = []

    for date_int, day_lessons in sorted(by_date.items()):
        sorted_day = sorted(day_lessons, key=lambda e: e["startTime"])

        if sorted_day[0]["startTime"] > 0:
            result.append(_make_free(0, sorted_day[0]["startTime"], date_int))

        for i, lesson in enumerate(sorted_day):
            result.append(lesson)
            if i < len(sorted_day) - 1:
                gap_start = lesson["endTime"]
                gap_end = sorted_day[i + 1]["startTime"]
                if gap_start != gap_end:
                    result.append(_make_free(gap_start, gap_end, date_int))

        last_end = sorted_day[-1]["endTime"]
        if last_end < 2359:
            result.append(_make_free(last_end, 2359, date_int))

    return sorted(result, key=lambda e: (e["date"], e["startTime"]))


def build_room_payload(periods: list[UntisPeriod], room_name: str, now: datetime | None = None) -> dict[str, Any]:
    if now is None:
        now = datetime.now()

    today_weekday = now.weekday()
    current_day = _DAY_NAMES[today_weekday]
    current_day_label = _DAY_LABELS[today_weekday]
    now_time_int = now.hour * 100 + now.minute
    cal_week = now.isocalendar().week

    days: dict[str, list[dict[str, Any]]] = {day: [] for day in _DAY_NAMES}

    if periods:
        converted = [_convert_period(p) for p in periods if p.start_time and p.end_time]
        converted.sort(key=lambda e: (e["date"], e["startTime"]))
        merged = _merge_continuous(converted)
        with_breaks = _insert_breaks(merged)

        for entry in with_breaks:
            weekday = _date_int_to_date(entry["date"]).weekday()
            day_name = _DAY_NAMES[weekday]
            prefix = _DAY_PREFIXES[weekday]
            slot_num = len(days[day_name]) + 1
            days[day_name].append(
                {
                    "id": f"{prefix}-{slot_num}",
                    "name": entry["name"],
                    "class": entry["class"],
                    "startTime": _format_time(entry["startTime"]),
                    "endTime": _format_time(entry["endTime"]),
                    "teachers": entry["teachers"],
                }
            )

        first_date = periods[0].date
        cal_week = _date_int_to_date(first_date).isocalendar().week

    current_lesson_id = _find_current_slot(days, current_day, now_time_int)

    return {
        "room": room_name,
        "calendarWeek": cal_week,
        "year": now.year,
        "day": current_day,
        "dayLabel": current_day_label,
        "currentLessonId": current_lesson_id,
        "fetchedAt": now.strftime("%Y-%m-%d %H:%M"),
        "days": days,
    }


def _find_current_slot(days: dict[str, list[dict[str, Any]]], current_day: str, now_time_int: int) -> str:
    slots = days.get(current_day, [])
    now_str = _format_time(now_time_int)

    for slot in slots:
        if slot["startTime"] <= now_str < slot["endTime"]:
            return slot["id"]

    return slots[-1]["id"] if slots else ""


def _find_current_slot_end(payload: dict[str, Any], now: datetime) -> int | None:
    day_name = _DAY_NAMES[now.weekday()]
    slots = payload.get("days", {}).get(day_name, [])
    now_str = _format_time(now.hour * 100 + now.minute)

    for slot in slots:
        if slot["startTime"] <= now_str < slot["endTime"]:
            h, m = map(int, slot["endTime"].split(":"))
            end_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
            return int((end_dt - now).total_seconds())

    return None


def _find_next_slot_start(payload: dict[str, Any], now: datetime) -> int | None:
    day_name = _DAY_NAMES[now.weekday()]
    slots = payload.get("days", {}).get(day_name, [])
    now_str = _format_time(now.hour * 100 + now.minute)

    for slot in slots:
        if slot["startTime"] > now_str:
            h, m = map(int, slot["startTime"].split(":"))
            start_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
            return int((start_dt - now).total_seconds())

    return None


def _find_nearest_boundary(payload: dict[str, Any], now: datetime) -> int | None:
    current_end = _find_current_slot_end(payload, now)
    if current_end is not None and current_end > 0:
        return current_end

    return _find_next_slot_start(payload, now)


def compute_slot_ttl(payload: dict[str, Any], now: datetime | None = None) -> int:
    current_time = datetime.now() if now is None else now

    secs = _find_nearest_boundary(payload, current_time)
    if secs is not None and secs > 0:
        return secs

    return 3600


def compute_next_wake_seconds(payloads: list[dict[str, Any]], now: datetime | None = None) -> int:
    current_time = datetime.now() if now is None else now

    earliest: int | None = None

    for payload in payloads:
        secs = _find_nearest_boundary(payload, current_time)
        if secs is not None and secs > 0:
            earliest = min(earliest, secs) if earliest is not None else secs

    if earliest is None:
        return 3600

    return max(earliest, 60)
