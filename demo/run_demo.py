"""Interactive demo orchestrator for client presentation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "pipeline" / "scripts"
AUDIT_LOG = ROOT / "agent" / "audit" / "incidents.jsonl"

SCENARIOS = {
    "1": SCRIPTS / "inject_schema_drift.py",
    "2": SCRIPTS / "inject_divide_by_zero.py",
    "3": SCRIPTS / "inject_sql_syntax.py",
}


def run(cmd: list[str], check: bool = True) -> None:
    """Run a demo step from the repository root."""
    print(f"\n>> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=check)


def step(title: str) -> None:
    """Print a section banner so the live demo is easy to follow."""
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def print_mttr() -> None:
    """Show the last audit events written while the healer opened a pull request."""
    if not AUDIT_LOG.exists():
        print("No audit log yet.")
        return
    lines = AUDIT_LOG.read_text(encoding="utf-8").strip().splitlines()
    print(f"Audit events: {len(lines)}")
    for line in lines[-5:]:
        print(json.loads(line))


def main() -> None:
    """Reset the demo, inject one scenario, heal once, then wait for a manual merge."""
    parser = argparse.ArgumentParser(description="ETL Recovery Agent Demo")
    parser.add_argument("--scenario", choices=["1", "2", "3"], help="Failure scenario")
    parser.add_argument("--skip-baseline", action="store_true")
    args = parser.parse_args()

    py = sys.executable

    if not args.skip_baseline:
        step("1. Reset baseline and seed data")
        run([py, str(SCRIPTS / "reset_baseline.py")])

        step("2. Run baseline dbt pipeline (expect success)")
        run([py, str(SCRIPTS / "run_pipeline.py"), "--expect", "success"])

    if not args.scenario:
        print("\nPick a scenario: --scenario 1|2|3")
        print("  1 = schema drift (qty renamed)")
        print("  2 = divide by zero")
        print("  3 = SQL syntax error")
        return

    step(f"3. Inject scenario {args.scenario}")
    run([py, str(SCENARIOS[args.scenario])])

    step("4. Re-run dbt (expect failure)")
    run([py, str(SCRIPTS / "run_pipeline.py"), "--expect", "failed"], check=False)

    step("5. Start ETL Recovery Agent")
    run([py, "-m", "agent.main", "heal-once"], check=False)

    step("6. Human review — merge PR on GitHub, then press Enter")
    input("After merging PR, press Enter to re-run dbt...")

    step("7. Re-run dbt (expect success)")
    run([py, str(SCRIPTS / "run_pipeline.py"), "--expect", "success"])

    step("8. MTTR / audit summary")
    print_mttr()
    print("\nDemo complete.")


if __name__ == "__main__":
    main()
