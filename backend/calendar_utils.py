"""
Shop calendar helpers: conversion between CP-SAT integer "bucket" indices and
real calendar datetimes/shifts/days.

Bucket layout per day (BUCKETS_PER_DAY_WITH_OT = 72 buckets of 15 min each):
    buckets  0..31  -> Shift 1  (06:00 - 14:00)   regular time
    buckets 32..63  -> Shift 2  (14:00 - 22:00)   regular time
    buckets 64..71  -> Overtime (22:00 - 00:00)   overtime rate, shift "2" (OT)
Then the day rolls over (00:00-06:00 is never modelled - the shop is closed).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from config import (
    BUCKET_MINUTES,
    BUCKETS_PER_DAY,
    BUCKETS_PER_DAY_WITH_OT,
    BUCKETS_PER_SHIFT,
    HORIZON_DAYS,
    SCHEDULE_START_DT,
    TOTAL_BUCKETS_WITH_OT,
)

TOTAL_BUCKETS = TOTAL_BUCKETS_WITH_OT


def bucket_to_datetime(bucket: int) -> datetime:
    day_index = bucket // BUCKETS_PER_DAY_WITH_OT
    offset_in_day = bucket % BUCKETS_PER_DAY_WITH_OT
    day_start = SCHEDULE_START_DT + timedelta(days=day_index)
    return day_start + timedelta(minutes=offset_in_day * BUCKET_MINUTES)


def datetime_to_bucket(dt: datetime, round_up: bool = False) -> int:
    """Convert a real datetime back to the nearest bucket index. Clamped to
    the shop's working window for the given day (06:00-24:00)."""
    day_index = (dt.date() - SCHEDULE_START_DT.date()).days
    day_start = SCHEDULE_START_DT + timedelta(days=day_index)
    minutes_from_day_start = (dt - day_start).total_seconds() / 60.0
    if minutes_from_day_start < 0:
        minutes_from_day_start = 0
    offset = minutes_from_day_start / BUCKET_MINUTES
    offset_bucket = int(offset + (0.999 if round_up else 0))
    offset_bucket = max(0, min(BUCKETS_PER_DAY_WITH_OT, offset_bucket))
    return day_index * BUCKETS_PER_DAY_WITH_OT + offset_bucket


def day_index_of_bucket(bucket: int) -> int:
    return bucket // BUCKETS_PER_DAY_WITH_OT


def offset_in_day(bucket: int) -> int:
    return bucket % BUCKETS_PER_DAY_WITH_OT


def shift_of_bucket(bucket: int) -> int:
    off = offset_in_day(bucket)
    if off < BUCKETS_PER_SHIFT:
        return 1
    return 2  # covers shift 2 and its overtime extension


def is_overtime_bucket(bucket: int) -> bool:
    return offset_in_day(bucket) >= BUCKETS_PER_DAY


def buckets_for_day_shift(day_index: int, shift: int, include_overtime: bool = True) -> range:
    """Return the bucket range [start, end) for a given day+shift."""
    base = day_index * BUCKETS_PER_DAY_WITH_OT
    if shift == 1:
        return range(base, base + BUCKETS_PER_SHIFT)
    end = base + BUCKETS_PER_DAY_WITH_OT if include_overtime else base + BUCKETS_PER_DAY
    return range(base + BUCKETS_PER_SHIFT, end)


def date_of_day_index(day_index: int):
    return (SCHEDULE_START_DT + timedelta(days=day_index)).date()
