#!/usr/bin/env python
"""
Test script for multi-check-in per day feature.
This demonstrates how working hours are calculated with multiple check-ins.
"""

from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo


class MockPolicy:
    """Mock attendance policy for testing"""
    def __init__(self):
        self.timezone = "Asia/Ho_Chi_Minh"
        self.work_start_time = time(8, 0)
        self.break_start_time = time(12, 0)
        self.break_end_time = time(13, 0)
        self.work_end_time = time(17, 30)
        self.late_grace_minutes = 5


def get_zoneinfo(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        return ZoneInfo("UTC")


def to_local(dt_utc: datetime, policy: MockPolicy) -> datetime:
    tz = get_zoneinfo(policy.timezone)
    return dt_utc.astimezone(tz)


def _late_minutes(check_in_local: datetime, policy: MockPolicy) -> int:
    start_dt = check_in_local.replace(
        hour=policy.work_start_time.hour,
        minute=policy.work_start_time.minute,
        second=0,
        microsecond=0,
    )
    if check_in_local <= start_dt:
        return 0
    return int((check_in_local - start_dt).total_seconds() // 60)


def test_multi_checkin_scenario():
    """Test scenario with multiple check-ins throughout the day"""
    
    policy = MockPolicy()
    tz = get_zoneinfo(policy.timezone)
    today = date(2026, 5, 24)
    
    # Simulate check-ins throughout the day
    checkins = [
        ("08:15", "MORNING_START"),      # Morning start (late)
        ("08:20", "MORNING_START"),      # Duplicate - should be ignored
        ("12:05", "LUNCH_START"),        # Going to lunch
        ("13:05", "LUNCH_END"),          # Returning from lunch
        ("17:35", "EVENING_END"),        # Leaving
    ]
    
    print("=" * 60)
    print("Multi-Check-in Test Scenario")
    print("=" * 60)
    print(f"\nDate: {today}")
    print(f"Policy Settings:")
    print(f"  Work Start: {policy.work_start_time}")
    print(f"  Break Start: {policy.break_start_time}")
    print(f"  Break End: {policy.break_end_time}")
    print(f"  Work End: {policy.work_end_time}")
    print(f"  Late Grace: {policy.late_grace_minutes} minutes\n")
    
    # Parse check-ins
    periods = {}
    for time_str, period_type in checkins:
        hour, minute = map(int, time_str.split(":"))
        dt_local = datetime(2026, 5, 24, hour, minute, tzinfo=tz)
        
        if period_type not in periods:
            periods[period_type] = []
        periods[period_type].append(dt_local)
    
    # Print check-ins grouped by period
    print("Check-ins by Period:")
    print("-" * 60)
    for period_type in ["MORNING_START", "LUNCH_START", "LUNCH_END", "EVENING_END"]:
        if period_type in periods:
            times = [dt.strftime("%H:%M") for dt in periods[period_type]]
            print(f"{period_type:15} : {', '.join(times)}")
        else:
            print(f"{period_type:15} : (no check-in)")
    
    # Calculate working hours
    print("\n" + "=" * 60)
    print("Working Hours Calculation")
    print("=" * 60)
    
    morning_start = min(periods["MORNING_START"]) if "MORNING_START" in periods else None
    lunch_start = min(periods["LUNCH_START"]) if "LUNCH_START" in periods else None
    lunch_end = min(periods["LUNCH_END"]) if "LUNCH_END" in periods else None
    evening_end = max(periods["EVENING_END"]) if "EVENING_END" in periods else None
    
    if morning_start and evening_end:
        # Morning shift
        if lunch_start:
            morning_minutes = int((lunch_start - morning_start).total_seconds() // 60)
        else:
            lunch_start_policy = datetime.combine(today, policy.break_start_time).replace(tzinfo=tz)
            morning_minutes = int((lunch_start_policy - morning_start).total_seconds() // 60)
        
        late_minutes = _late_minutes(morning_start, policy)
        deduction_minutes = max(0, late_minutes - policy.late_grace_minutes)
        morning_minutes = max(0, morning_minutes - deduction_minutes)
        morning_hours = morning_minutes / 60.0
        
        # Afternoon shift
        if lunch_end and evening_end:
            afternoon_minutes = int((evening_end - lunch_end).total_seconds() // 60)
        else:
            lunch_end_policy = datetime.combine(today, policy.break_end_time).replace(tzinfo=tz)
            afternoon_minutes = int((evening_end - lunch_end_policy).total_seconds() // 60)
        
        afternoon_hours = afternoon_minutes / 60.0
        
        total_hours = morning_hours + afternoon_hours
        
        print(f"\nMorning Shift:")
        print(f"  Start Time: {morning_start.strftime('%H:%M')}")
        print(f"  End Time:   {lunch_start.strftime('%H:%M') if lunch_start else policy.break_start_time}")
        print(f"  Duration:   {morning_minutes} minutes")
        print(f"  Late Minutes: {late_minutes} (Grace: {policy.late_grace_minutes})")
        print(f"  Deduction: {deduction_minutes} minutes")
        print(f"  Working Hours: {morning_hours:.2f} hours\n")
        
        print(f"Afternoon Shift:")
        print(f"  Start Time: {lunch_end.strftime('%H:%M') if lunch_end else policy.break_end_time}")
        print(f"  End Time:   {evening_end.strftime('%H:%M')}")
        print(f"  Duration:   {afternoon_minutes} minutes")
        print(f"  Working Hours: {afternoon_hours:.2f} hours\n")
        
        print(f"Total Working Hours: {total_hours:.2f} hours")
        print(f"Worked Days: 1")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_multi_checkin_scenario()

