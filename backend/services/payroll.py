"""
IDVision — Attendance Policy and Payroll Utilities
Centralizes timezone handling, attendance status logic, and monthly payroll aggregation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models import AttendanceLog, AttendancePolicy

settings = get_settings()


@dataclass
class MonthStats:
    worked_days: int
    worked_hours: float


def _parse_hhmm(value: str) -> time:
    hour_str, minute_str = value.split(":")
    return time(hour=int(hour_str), minute=int(minute_str))


def _format_hhmm(value: time) -> str:
    return value.strftime("%H:%M")


def get_zoneinfo(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        return ZoneInfo("UTC")


async def get_or_create_policy(session: AsyncSession) -> AttendancePolicy:
    result = await session.execute(select(AttendancePolicy).limit(1))
    policy = result.scalar_one_or_none()
    if policy:
        return policy

    # Bootstrap a default policy from existing env settings for backward compatibility.
    policy = AttendancePolicy(
        timezone="Asia/Ho_Chi_Minh",
        work_start_time=time(settings.LATE_THRESHOLD_HOUR, settings.LATE_THRESHOLD_MINUTE),
        break_start_time=time(12, 0),
        break_end_time=time(13, 0),
        work_end_time=time(17, 30),
        late_grace_minutes=0,
        hourly_wage=0.0,
    )
    session.add(policy)
    await session.flush()
    return policy


def policy_to_response(policy: AttendancePolicy) -> dict:
    return {
        "timezone": policy.timezone,
        "work_start_time": _format_hhmm(policy.work_start_time),
        "break_start_time": _format_hhmm(policy.break_start_time),
        "break_end_time": _format_hhmm(policy.break_end_time),
        "work_end_time": _format_hhmm(policy.work_end_time),
        "late_grace_minutes": policy.late_grace_minutes,
        "hourly_wage": float(policy.hourly_wage),
    }


def update_policy_from_payload(policy: AttendancePolicy, payload: dict) -> None:
    policy.timezone = payload["timezone"]
    policy.work_start_time = _parse_hhmm(payload["work_start_time"])
    policy.break_start_time = _parse_hhmm(payload["break_start_time"])
    policy.break_end_time = _parse_hhmm(payload["break_end_time"])
    policy.work_end_time = _parse_hhmm(payload["work_end_time"])
    policy.late_grace_minutes = payload["late_grace_minutes"]
    policy.hourly_wage = payload["hourly_wage"]


def _minutes_between(start_time: time, end_time: time) -> int:
    start_minutes = start_time.hour * 60 + start_time.minute
    end_minutes = end_time.hour * 60 + end_time.minute
    return max(0, end_minutes - start_minutes)


def get_standard_daily_hours(policy: AttendancePolicy) -> float:
    total_minutes = _minutes_between(policy.work_start_time, policy.work_end_time)
    break_minutes = _minutes_between(policy.break_start_time, policy.break_end_time)
    working_minutes = max(0, total_minutes - break_minutes)
    return working_minutes / 60.0


def to_local(dt_utc: datetime, policy: AttendancePolicy) -> datetime:
    tz = get_zoneinfo(policy.timezone)
    return dt_utc.astimezone(tz)


def local_date_bounds_to_utc(target_date: date, policy: AttendancePolicy) -> tuple[datetime, datetime]:
    tz = get_zoneinfo(policy.timezone)
    start_local = datetime.combine(target_date, time.min).replace(tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def local_month_bounds_to_utc(month_str: str, policy: AttendancePolicy) -> tuple[datetime, datetime, str]:
    year, month = [int(v) for v in month_str.split("-")]
    first_day = date(year, month, 1)
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)

    start_utc, _ = local_date_bounds_to_utc(first_day, policy)
    end_utc, _ = local_date_bounds_to_utc(next_month, policy)
    return start_utc, end_utc, first_day.strftime("%Y-%m")


def _late_minutes(check_in_local: datetime, policy: AttendancePolicy) -> int:
    start_dt = check_in_local.replace(
        hour=policy.work_start_time.hour,
        minute=policy.work_start_time.minute,
        second=0,
        microsecond=0,
    )
    if check_in_local <= start_dt:
        return 0
    return int((check_in_local - start_dt).total_seconds() // 60)


def determine_status(check_in_utc: datetime, policy: AttendancePolicy) -> tuple[str, int]:
    check_in_local = to_local(check_in_utc, policy)
    late_minutes = _late_minutes(check_in_local, policy)
    return ("SUCCESS", 0) if late_minutes == 0 else ("LATE", late_minutes)


async def calculate_employee_month_stats(
    session: AsyncSession,
    employee_id: int,
    month_str: str,
    policy: AttendancePolicy,
) -> MonthStats:
    start_utc, end_utc, _ = local_month_bounds_to_utc(month_str, policy)

    stmt = (
        select(AttendanceLog)
        .where(
            and_(
                AttendanceLog.employee_id == employee_id,
                AttendanceLog.status.in_(["SUCCESS", "LATE"]),
                AttendanceLog.check_in_time >= start_utc,
                AttendanceLog.check_in_time < end_utc,
            )
        )
        .order_by(AttendanceLog.check_in_time.asc())
    )
    result = await session.execute(stmt)
    logs = result.scalars().all()

    first_log_by_day: dict[date, AttendanceLog] = {}
    for log in logs:
        local_day = to_local(log.check_in_time, policy).date()
        if local_day not in first_log_by_day:
            first_log_by_day[local_day] = log

    standard_daily_hours = get_standard_daily_hours(policy)
    total_hours = 0.0
    for log in first_log_by_day.values():
        local_time = to_local(log.check_in_time, policy)
        late_minutes = _late_minutes(local_time, policy)
        deduction_minutes = max(0, late_minutes - policy.late_grace_minutes)
        day_hours = max(0.0, standard_daily_hours - (deduction_minutes / 60.0))
        total_hours += day_hours

    return MonthStats(worked_days=len(first_log_by_day), worked_hours=round(total_hours, 2))

