#!/usr/bin/env python
"""
Test script to verify the period determination and working hours calculation logic.
This ensures that multiple daily check-ins are properly categorized and hours calculated.
"""

import sys
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

# Add backend to path for imports
sys.path.insert(0, r"E:\IDVision\backend")

from services.payroll import (
    determine_period_type,
    get_zoneinfo,
    to_local,
    _late_minutes,
    _minutes_between,
    get_standard_daily_hours,
)
from models import AttendancePolicy


def test_determine_period_type():
    """Test that the period determination logic works correctly"""
    print("=" * 70)
    print("TEST 1: Period Type Determination")
    print("=" * 70)
    
    policy = AttendancePolicy(
        timezone="Asia/Ho_Chi_Minh",
        work_start_time=time(8, 0),
        break_start_time=time(12, 0),
        break_end_time=time(13, 0),
        work_end_time=time(17, 30),
        late_grace_minutes=5,
        hourly_wage=0.0,
    )
    
    tz = get_zoneinfo(policy.timezone)
    test_times = [
        ("08:15", "MORNING_START"),
        ("11:30", "MORNING_START"),
        ("12:05", "LUNCH_START"),
        ("12:30", "LUNCH_END"),
        ("13:05", "EVENING_END"),
        ("14:00", "EVENING_END"),
        ("17:35", "EVENING_END"),
    ]
    
    print(f"\nPolicy Settings:")
    print(f"  Work Start: {policy.work_start_time}")
    print(f"  Break Start: {policy.break_start_time}")
    print(f"  Break End: {policy.break_end_time}")
    print(f"  Work End: {policy.work_end_time}\n")
    
    all_passed = True
    for time_str, expected_period in test_times:
        hour, minute = map(int, time_str.split(":"))
        # Create UTC time by converting from local
        dt_local = datetime(2026, 5, 24, hour, minute, tzinfo=tz)
        dt_utc = dt_local.astimezone(ZoneInfo("UTC"))
        
        actual_period = determine_period_type(dt_utc, policy)
        status = "✓" if actual_period == expected_period else "✗"
        if actual_period != expected_period:
            all_passed = False
        
        print(f"  {status} {time_str} -> Expected: {expected_period:12} Got: {actual_period}")
    
    print(f"\nPeriod Type Test: {'PASSED' if all_passed else 'FAILED'}\n")
    return all_passed


def test_late_minutes_calculation():
    """Test that late minutes are calculated correctly"""
    print("=" * 70)
    print("TEST 2: Late Minutes Calculation")
    print("=" * 70)
    
    policy = AttendancePolicy(
        timezone="Asia/Ho_Chi_Minh",
        work_start_time=time(8, 0),
        break_start_time=time(12, 0),
        break_end_time=time(13, 0),
        work_end_time=time(17, 30),
        late_grace_minutes=5,
        hourly_wage=0.0,
    )
    
    tz = get_zoneinfo(policy.timezone)
    test_cases = [
        ("07:50", 0),      # Early - no late
        ("08:00", 0),      # On time - no late
        ("08:05", 5),      # 5 minutes late
        ("08:15", 15),     # 15 minutes late
    ]
    
    print(f"\nPolicy: Work starts at {policy.work_start_time}\n")
    
    all_passed = True
    for time_str, expected_late in test_cases:
        hour, minute = map(int, time_str.split(":"))
        dt_local = datetime(2026, 5, 24, hour, minute, tzinfo=tz)
        actual_late = _late_minutes(dt_local, policy)
        
        status = "✓" if actual_late == expected_late else "✗"
        if actual_late != expected_late:
            all_passed = False
        
        print(f"  {status} {time_str} -> Expected: {expected_late} min Got: {actual_late} min")
    
    print(f"\nLate Minutes Test: {'PASSED' if all_passed else 'FAILED'}\n")
    return all_passed


def test_standard_daily_hours():
    """Test that standard daily hours calculation is correct"""
    print("=" * 70)
    print("TEST 3: Standard Daily Hours Calculation")
    print("=" * 70)
    
    policy = AttendancePolicy(
        timezone="Asia/Ho_Chi_Minh",
        work_start_time=time(8, 0),
        break_start_time=time(12, 0),
        break_end_time=time(13, 0),
        work_end_time=time(17, 30),
        late_grace_minutes=5,
        hourly_wage=0.0,
    )
    
    # Total: 8:00 to 17:30 = 9.5 hours
    # Minus: 12:00 to 13:00 = 1 hour lunch break
    # Net: 8.5 hours
    standard_hours = get_standard_daily_hours(policy)
    expected = 8.5
    
    print(f"\nPolicy:")
    print(f"  Work Start: {policy.work_start_time}")
    print(f"  Break Start: {policy.break_start_time}")
    print(f"  Break End: {policy.break_end_time}")
    print(f"  Work End: {policy.work_end_time}")
    print(f"\nCalculation: (17:30 - 8:00) - (13:00 - 12:00) = 9.5 - 1.0 = 8.5 hours")
    print(f"Expected: {expected} hours")
    print(f"Got: {standard_hours} hours")
    
    passed = abs(standard_hours - expected) < 0.01
    print(f"\nStandard Daily Hours Test: {'PASSED' if passed else 'FAILED'}\n")
    return passed


def test_multi_checkin_hours_calculation():
    """Test the hour calculation for multi-check-in scenario from test_multi_checkin.py"""
    print("=" * 70)
    print("TEST 4: Multi-Check-in Hours Calculation")
    print("=" * 70)
    print("\nThis simulates the scenario:")
    print("  08:15 - MORNING_START (15 min late, grace=5, deduction=10 min)")
    print("  12:05 - LUNCH_START (actual end of morning shift)")
    print("  13:05 - EVENING_END (actual start of afternoon shift)")
    print("  17:35 - EVENING_END (actual end of work)")
    print("\nExpected:")
    print("  Morning: (12:05 - 08:15) - 10 min deduction = 230 - 10 = 220 min = 3.67 hours")
    print("  Afternoon: (17:35 - 13:05) = 270 min = 4.50 hours")
    print("  Total: 8.17 hours")
    
    policy = AttendancePolicy(
        timezone="Asia/Ho_Chi_Minh",
        work_start_time=time(8, 0),
        break_start_time=time(12, 0),
        break_end_time=time(13, 0),
        work_end_time=time(17, 30),
        late_grace_minutes=5,
        hourly_wage=0.0,
    )
    
    tz = get_zoneinfo(policy.timezone)
    
    # Parse the check-in times
    morning_start_local = datetime(2026, 5, 24, 8, 15, tzinfo=tz)
    lunch_start_local = datetime(2026, 5, 24, 12, 5, tzinfo=tz)
    lunch_end_local = datetime(2026, 5, 24, 13, 5, tzinfo=tz)
    evening_end_local = datetime(2026, 5, 24, 17, 35, tzinfo=tz)
    
    # Calculate morning shift
    morning_minutes = int((lunch_start_local - morning_start_local).total_seconds() // 60)
    late_minutes = _late_minutes(morning_start_local, policy)
    deduction_minutes = max(0, late_minutes - policy.late_grace_minutes)
    morning_minutes = max(0, morning_minutes - deduction_minutes)
    morning_hours = morning_minutes / 60.0
    
    # Calculate afternoon shift
    afternoon_minutes = int((evening_end_local - lunch_end_local).total_seconds() // 60)
    afternoon_hours = afternoon_minutes / 60.0
    
    total_hours = morning_hours + afternoon_hours
    
    print(f"\n\nActual Calculation:")
    print(f"  Morning shift: {morning_minutes} minutes = {morning_hours:.2f} hours")
    print(f"    (230 minutes - {deduction_minutes} min deduction for late)")
    print(f"  Afternoon shift: {afternoon_minutes} minutes = {afternoon_hours:.2f} hours")
    print(f"  Total: {total_hours:.2f} hours")
    
    expected_total = 8.17
    passed = abs(total_hours - expected_total) < 0.1
    print(f"\nMulti-Check-in Calculation Test: {'PASSED' if passed else 'FAILED'}\n")
    return passed


if __name__ == "__main__":
    print("\n")
    print("=" * 70)
    print("IDVision - Period Logic Tests")
    print("=" * 70)
    print()
    
    results = [
        test_determine_period_type(),
        test_late_minutes_calculation(),
        test_standard_daily_hours(),
        test_multi_checkin_hours_calculation(),
    ]
    
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"\nTests Passed: {passed}/{total}")
    print(f"Result: {'ALL TESTS PASSED' if all(results) else 'SOME TESTS FAILED'}\n")

