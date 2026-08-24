"""Quick manual smoke test: generate data (if missing) and solve one strategy."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATA_DIR
from data.generator import generate_all
from scheduler.solver import solve_schedule, SchedulingError


def load_or_generate():
    files = ["machines.json", "operators.json", "orders.json", "changeovers.json"]
    if not all(os.path.exists(os.path.join(DATA_DIR, f)) for f in files):
        generate_all()
    machines = json.load(open(os.path.join(DATA_DIR, "machines.json")))
    operators = json.load(open(os.path.join(DATA_DIR, "operators.json")))
    orders = json.load(open(os.path.join(DATA_DIR, "orders.json")))
    changeovers = json.load(open(os.path.join(DATA_DIR, "changeovers.json")))
    return machines, operators, orders, changeovers


if __name__ == "__main__":
    strategy = sys.argv[1] if len(sys.argv) > 1 else "cheapest"
    machines, operators, orders, changeovers = load_or_generate()
    print(f"Solving strategy={strategy} with {len(machines)} machines, {len(operators)} operators, "
          f"{len(orders)} orders, {sum(len(o['routing']) for o in orders)} operations...")
    t0 = time.time()
    try:
        result = solve_schedule(machines, operators, orders, changeovers, strategy=strategy, time_limit_seconds=60)
    except SchedulingError as e:
        print("SCHEDULING ERROR:", e.to_dict())
        sys.exit(1)
    print(f"Done in {time.time()-t0:.1f}s wall / solver status={result['solver_status']} "
          f"solver_time={result['solver_wall_time_seconds']}s")
    print("Metrics:", json.dumps(result["metrics"], indent=2)[:1500])
    print("Cost breakdown:", json.dumps(result["cost_breakdown"], indent=2))
    print("Num scheduled operations:", len(result["operations"]))
    print("Sample operation:", json.dumps(result["operations"][0], indent=2))
