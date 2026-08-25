"""
Central configuration and shop-calendar constants for the Machine Shop Scheduler.

Every "magic number" that the project spec does NOT pin down (shift
timings, bucket granularity, cost rates, etc.) lives here, in one place, so it
can be audited and is never duplicated/hardcoded inside business logic.
See docs/trade-off-memo.md and pdf report section "Assumptions" for the
rationale behind each value below.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# Environment / paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.environ.get("DATABASE_URL", os.path.join(BASE_DIR, "shop.db"))
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
FLASK_ENV = os.environ.get("FLASK_ENV", "development")
RANDOM_SEED = int(os.environ.get("DATA_SEED", "42"))

# ---------------------------------------------------------------------------
# Shop calendar (ASSUMPTION - not specified exactly by the project)
# ---------------------------------------------------------------------------
SHIFT_DEFINITIONS = {
    1: {"label": "Shift 1", "start_hour": 6, "end_hour": 14},   # 06:00-14:00
    2: {"label": "Shift 2", "start_hour": 14, "end_hour": 22},  # 14:00-22:00
}
SHIFT_HOURS = 8
WORKING_HOURS_PER_DAY = 16  # 06:00 -> 22:00, both shifts, contiguous
NON_WORKING_HOURS_PER_DAY = 24 - WORKING_HOURS_PER_DAY  # 22:00 -> 06:00 next day

# Discrete time-bucket granularity used by the CP-SAT model.
# 15 minutes keeps the horizon at a computationally manageable 896 buckets
# instead of 1344 (if we modelled the idle overnight hours) or ~20k (minutes).
BUCKET_MINUTES = 30
BUCKETS_PER_HOUR = 60 // BUCKET_MINUTES
BUCKETS_PER_SHIFT = SHIFT_HOURS * BUCKETS_PER_HOUR          # 32
BUCKETS_PER_DAY = WORKING_HOURS_PER_DAY * BUCKETS_PER_HOUR  # 64

# Planning horizon.
HORIZON_DAYS = 14
TOTAL_BUCKETS = HORIZON_DAYS * BUCKETS_PER_DAY  # 896

# Overtime: any work scheduled past a shift's normal end (i.e. the shop asks
# an operator to stay) is billed at the machine/operator overtime rate.
# We model overtime as *extra buckets appended after shift 2* (22:00-24:00,
# 2 hours per day max) that the solver may use only at overtime cost.
OVERTIME_HOURS_PER_DAY = 2
BUCKETS_PER_OVERTIME = OVERTIME_HOURS_PER_DAY * BUCKETS_PER_HOUR
BUCKETS_PER_DAY_WITH_OT = BUCKETS_PER_DAY + BUCKETS_PER_OVERTIME  # 72
TOTAL_BUCKETS_WITH_OT = HORIZON_DAYS * BUCKETS_PER_DAY_WITH_OT

# Reference start of the plan (Monday 06:00). Set at import time; the data
# generator and API both use this so all dates line up.
SCHEDULE_START_DATE = date(2026, 8, 24)  # Monday
SCHEDULE_START_DT = datetime.combine(SCHEDULE_START_DATE, datetime.min.time()) + timedelta(hours=6)

# ---------------------------------------------------------------------------
# Cost assumptions (ASSUMPTION - documented in pdf report, Section "Assumptions")
# ---------------------------------------------------------------------------
OVERTIME_COST_MULTIPLIER = 1.75      # applied on top of machine hourly_cost/operator rate
GENERATOR_COST_MULTIPLIER = 3.0      # diesel generator vs grid electricity
INSPECTION_FAIL_RATE_RANGE = (0.02, 0.05)  # 2-5% assumed inspection failure rate
REWORK_TIME_FRACTION = 0.6           # rework takes ~60% of the original op time

# Part families used to build the sequence-dependent changeover matrix.
PART_FAMILIES = ["Shaft", "Flange", "Housing", "Bracket", "Gear", "Pin"]

# Changeover minutes: ~20 min within-family, up to 3h cross-family.
CHANGEOVER_SAME_FAMILY_MIN = 15
CHANGEOVER_SAME_FAMILY_MAX = 25
CHANGEOVER_DIFFERENT_FAMILY_MIN = 45
CHANGEOVER_DIFFERENT_FAMILY_MAX = 180

MACHINE_TYPES = ["CNC Lathe", "Milling", "Drilling", "Grinding", "Inspection"]

OPERATION_TYPES = ["Turning", "Milling", "Drilling", "Grinding", "Inspection", "Deburring"]

# Maps an operation type to the machine types capable of performing it.
OPERATION_TO_MACHINE_TYPES = {
    "Turning": ["CNC Lathe"],
    "Milling": ["Milling"],
    "Drilling": ["Drilling"],
    "Grinding": ["Grinding"],
    "Deburring": ["Milling", "Drilling"],
    "Inspection": ["Inspection"],
}

CUSTOMER_TIERS = ["Tier-1", "Tier-2", "Tier-3"]

# A single scheduled operation must fit inside one operator's continuous
# shift-availability window (a shift cannot be "handed off" mid-operation in
# this model - see docs/scheduling-algorithm.md "Batch splitting"). Any
# operation whose raw duration would exceed this many buckets is split by the
# data generator into several parallel/sequential sub-batches of the same
# operation_type, so large lots (up to 5000pc) remain schedulable.
MAX_SINGLE_OPERATION_BUCKETS = 15  # 7.5 hours at 30-min buckets

