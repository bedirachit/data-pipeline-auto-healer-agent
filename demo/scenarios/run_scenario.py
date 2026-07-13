"""Per-scenario demo entrypoints."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "pipeline" / "scripts"

SCENARIOS = {
    "1": ("schema_drift", SCRIPTS / "inject_schema_drift.py"),
    "2": ("divide_by_zero", SCRIPTS / "inject_divide_by_zero.py"),
    "3": ("sql_syntax", SCRIPTS / "inject_sql_syntax.py"),
}


def run(script: Path) -> None:
    subprocess.run([sys.executable, str(script)], check=True, cwd=ROOT)


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in SCENARIOS:
        print("Usage: python demo/scenarios/run_scenario.py [1|2|3]")
        sys.exit(1)

    key = sys.argv[1]
    name, inject_script = SCENARIOS[key]
    print(f"=== Scenario {key}: {name} ===")

    run(SCRIPTS / "reset_baseline.py")
    run(SCRIPTS / "run_pipeline.py")
    run(inject_script)
    run(SCRIPTS / "run_pipeline.py")
    print("Failure injected and dbt re-run. Start agent: python -m agent.main heal-once")


if __name__ == "__main__":
    main()
