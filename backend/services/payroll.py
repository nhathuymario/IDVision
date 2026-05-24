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


def determine_period_type(check_in_utc: datetime, policy: AttendancePolicy) -> str:
    """Determine which work period a check-in belongs to.
    
    Based on local time:
    - MORNING_START: work_start_time to break_start_time (8:00 to 12:00)
    - LUNCH_START: close to break_start_time (12:00)
    - LUNCH_END: close to break_end_time (13:00)
    - EVENING_END: break_end_time to work_end_time (13:00 to 17:30)
    
    Logic:
    - If check-in is between work_start and break_start, use MORNING_START
    - If check-in is between break_start and break_end (lunch period), use LUNCH_START/LUNCH_END
    - If check-in is between break_end and work_end, use EVENING_END
    - Default to MORNING_START for safety
    """
    check_in_local = to_local(check_in_utc, policy)
    check_in_time = check_in_local.time()
    
    # Check if in morning shift (before lunch)
    if check_in_time >= policy.work_start_time and check_in_time < policy.break_start_time:
        return "MORNING_START"
    
    # Check if in lunch period
    if check_in_time >= policy.break_start_time and check_in_time < policy.break_end_time:
        # Closer to break_start (within 50% of break duration) = LUNCH_START, otherwise LUNCH_END
        minutes_from_break_start = (
            (check_in_time.hour * 60 + check_in_time.minute) -
            (policy.break_start_time.hour * 60 + policy.break_start_time.minute)
        )
        break_duration_minutes = (
            (policy.break_end_time.hour * 60 + policy.break_end_time.minute) -
            (policy.break_start_time.hour * 60 + policy.break_start_time.minute)
        )
        if minutes_from_break_start < break_duration_minutes / 2:
            return "LUNCH_START"
        else:
            return "LUNCH_END"
    
    # Check if in afternoon shift (after lunch)
    if check_in_time >= policy.break_end_time and check_in_time <= policy.work_end_time:
        return "EVENING_END"
    
    # For very late check-ins after work_end_time, still count as EVENING_END
    if check_in_time > policy.work_end_time:
        return "EVENING_END"
    
    # Default for early check-ins (before work_start)
    return "MORNING_START"


async def calculate_employee_month_stats(
    session: AsyncSession,
    employee_id: int,
    month_str: str,
    policy: AttendancePolicy,
) -> MonthStats:
    """Calculate monthly working hours for an employee.
    
    Working hours logic:
    1. For each day, find the first check-in (MORNING_START) and last check-out (EVENING_END)
    2. Calculate: morning_hours (MORNING_START to LUNCH_START) + afternoon_hours (LUNCH_END to EVENING_END)
    3. Deduct late minutes from first check-in if applicable
    4. Multiple check-ins within same period don't affect total (first in/last out only)
    """
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

    # Group logs by day and period type
    # Structure: {date: {period_type: [logs]}}
    daily_logs: dict[date, dict[str, list[AttendanceLog]]] = {}
    for log in logs:
        local_day = to_local(log.check_in_time, policy).date()
        if local_day not in daily_logs:
            daily_logs[local_day] = {}
        period = log.period_type or "MORNING_START"
        if period not in daily_logs[local_day]:
            daily_logs[local_day][period] = []
        daily_logs[local_day][period].append(log)

    total_hours = 0.0
    worked_days = 0

    for day, periods in sorted(daily_logs.items()):
        # For each day, calculate working hours based on check-in/out times
        # We need at least one check-in to count as a worked day
        if "MORNING_START" not in periods and "LUNCH_END" not in periods:
            continue  # No valid check-in for this day

        worked_days += 1
        day_hours = await _calculate_daily_working_hours(
            periods=periods,
            policy=policy,
            day=day,
        )
        total_hours += day_hours

    return MonthStats(worked_days=worked_days, worked_hours=round(total_hours, 2))


async def _calculate_daily_working_hours(
    periods: dict[str, list[AttendanceLog]],
    policy: AttendancePolicy,
    day: date,
) -> float:
    """Calculate working hours for a single day.
    
    Takes first check-in from each period and calculates:
    morning_hours = (LUNCH_START - MORNING_START) actual time or policy time
    afternoon_hours = (EVENING_END - LUNCH_END) actual time or policy time
    
    Deducts late minutes from the morning shift only.
    Returns the total working hours for the day.
    """
    morning_start = None
    lunch_start = None
    lunch_end = None
    evening_end = None
    tz = get_zoneinfo(policy.timezone)

    # Get first log from each period (earliest check-in for that period)
    if "MORNING_START" in periods and periods["MORNING_START"]:
        logs_sorted = sorted(periods["MORNING_START"], key=lambda x: x.check_in_time)
        morning_start = to_local(logs_sorted[0].check_in_time, policy)

    if "LUNCH_START" in periods and periods["LUNCH_START"]:
        logs_sorted = sorted(periods["LUNCH_START"], key=lambda x: x.check_in_time)
        lunch_start = to_local(logs_sorted[0].check_in_time, policy)

    if "LUNCH_END" in periods and periods["LUNCH_END"]:
        logs_sorted = sorted(periods["LUNCH_END"], key=lambda x: x.check_in_time)
        lunch_end = to_local(logs_sorted[0].check_in_time, policy)

    if "EVENING_END" in periods and periods["EVENING_END"]:
        logs_sorted = sorted(periods["EVENING_END"], key=lambda x: x.check_in_time, reverse=True)
        evening_end = to_local(logs_sorted[0].check_in_time, policy)

    # If we don't have at least morning start, count zero hours
    if not morning_start:
        return 0.0

    # If we only have morning start but no evening end, assume employee just started work
    if not evening_end:
        return 0.0

    # Calculate morning shift hours (morning_start to lunch_start)
    morning_hours = 0.0
    if lunch_start:
        # Use actual lunch_start check-in time
        morning_minutes = int((lunch_start - morning_start).total_seconds() // 60)
        morning_minutes = max(0, morning_minutes)
    else:
        # No lunch_start check-in, use policy break_start_time
        lunch_start_time = datetime.combine(day, policy.break_start_time).replace(tzinfo=tz)
        morning_minutes = int((lunch_start_time - morning_start).total_seconds() // 60)
        morning_minutes = max(0, morning_minutes)

    # Apply late deduction only to morning shift
    late_minutes = _late_minutes(morning_start, policy)
    deduction_minutes = max(0, late_minutes - policy.late_grace_minutes)
    morning_minutes = max(0, morning_minutes - deduction_minutes)
    morning_hours = morning_minutes / 60.0

    # Calculate afternoon shift hours (lunch_end to evening_end)
    afternoon_hours = 0.0
    if lunch_end and evening_end:
        # Use actual lunch_end and evening_end check-in times
        afternoon_minutes = int((evening_end - lunch_end).total_seconds() // 60)
        afternoon_minutes = max(0, afternoon_minutes)
    elif evening_end:
        # No lunch_end recorded, use policy break_end_time
        lunch_end_time = datetime.combine(day, policy.break_end_time).replace(tzinfo=tz)
        afternoon_minutes = int((evening_end - lunch_end_time).total_seconds() // 60)
        afternoon_minutes = max(0, afternoon_minutes)
    else:
        afternoon_minutes = 0

    afternoon_hours = afternoon_minutes / 60.0

    total_daily_hours = morning_hours + afternoon_hours
    return round(total_daily_hours, 2)

