import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATA_DIR  # noqa: E402
from data.generator import generate_all  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def ensure_master_data():
    """Generate the dataset once for the whole test session if not present."""
    files = ["machines.json", "operators.json", "orders.json", "changeovers.json", "breakdowns.json"]
    if not all(os.path.exists(os.path.join(DATA_DIR, f)) for f in files):
        generate_all()


@pytest.fixture(scope="session")
def full_master_data():
    machines = json.load(open(os.path.join(DATA_DIR, "machines.json")))
    operators = json.load(open(os.path.join(DATA_DIR, "operators.json")))
    orders = json.load(open(os.path.join(DATA_DIR, "orders.json")))
    changeovers = json.load(open(os.path.join(DATA_DIR, "changeovers.json")))
    return machines, operators, orders, changeovers


@pytest.fixture(scope="session")
def small_master_data(full_master_data):
    """A small (fast-to-solve) slice of the dataset, used by scheduling and
    replanning tests that need CP-SAT to actually converge to OPTIMAL within
    a test suite's time budget - see docs/scheduling-algorithm.md 'Solver
    performance' for why the full 25-order model needs a longer budget."""
    machines, operators, orders, changeovers = full_master_data
    return machines, operators, orders[:6], changeovers
