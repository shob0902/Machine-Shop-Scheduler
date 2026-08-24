"""Loads (and lazily regenerates) the shop's master data JSON files."""
from __future__ import annotations

import json
import os

from config import DATA_DIR
from data.generator import generate_all

_FILES = ["machines.json", "operators.json", "orders.json", "changeovers.json", "breakdowns.json"]


def ensure_data_exists() -> None:
    if not all(os.path.exists(os.path.join(DATA_DIR, f)) for f in _FILES):
        generate_all()


def _load(fname: str):
    ensure_data_exists()
    with open(os.path.join(DATA_DIR, fname), encoding="utf-8") as f:
        return json.load(f)


def load_machines() -> list:
    return _load("machines.json")


def load_operators() -> list:
    return _load("operators.json")


def load_orders() -> list:
    return _load("orders.json")


def load_changeovers() -> dict:
    return _load("changeovers.json")


def load_breakdowns() -> list:
    return _load("breakdowns.json")


def load_all() -> tuple:
    return load_machines(), load_operators(), load_orders(), load_changeovers()


def regenerate(num_orders: int = 25) -> dict:
    return generate_all(num_orders=num_orders)
