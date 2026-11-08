"""SwarmOS command-line entry point."""

import argparse
import json
from pathlib import Path
import sys

from .controller import run_swarm001
from .run_history import RunHistory


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SwarmOS autonomous coding workflow"
    )
    parser.add_argument(
        "command",
        choices=["demo", "inspect", "list"],
        help="Command to execute"
    )
    parser.add_argument(
        "--output",
        default="evidence/demo",
        help="Directory for run evidence"
    )
    parser.add_argument(
        "--database",
        default=".swarmos/runs.sqlite3",
        help="SQLite path for persistent run history",
    )
    parser.add_argument("--run-id", help="Run ID for inspect")

    args = parser.parse_args()

    if args.command == "demo":
        output = Path(args.output)
        output.mkdir(parents=True, exist_ok=True)
        try:
            with RunHistory(args.database) as history:
                run = history.start()
                result = run_swarm001(
                    output / "fixture",
                    Path(__file__).parent.parent / "tests" /
                    "test_swarm001_acceptance.py",
                )
                history.finish(run, result)
        except Exception as error:
            print(f"Persistence failure: {error}", file=sys.stderr)
            return 1
        evidence = {
            "termination": result.termination.value,
            "completed": result.completed,
            "patches_attempted": result.patches_attempted,
            "message": result.message,
            "diff": result.diff,
            "steps": [
                {
                    "number": step.number,
                    "role": step.role.value,
                    "tool": step.tool,
                    "result": step.result,
                }
                for step in result.steps
            ],
        }
        summary_path = output / "run-summary.json"
        diff_path = output / "swarm001.diff"
        if summary_path.exists():
            summary_path = output / f"run-summary-{run.id}.json"
        if diff_path.exists():
            diff_path = output / f"swarm001-{run.id}.diff"
        summary_path.write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
        )
        diff_path.write_text(result.diff, encoding="utf-8")
        print("SwarmOS bounded demo completed.")
        print(f"Evidence directory: {output}")
        print(f"Run ID: {run.id}")
        print(f"Termination: {result.termination.value}")
        print(
            f"Steps: {len(result.steps)}; patches: {result.patches_attempted}")
        return 0 if result.completed else 1
    if args.command == "inspect":
        if not args.run_id:
            print("--run-id is required for inspect", file=sys.stderr)
            return 2
        try:
            with RunHistory(args.database) as history:
                run, tasks, events = history.get(args.run_id)
        except KeyError as error:
            print(str(error), file=sys.stderr)
            return 2
        except Exception as error:
            print(f"Persistence failure: {error}", file=sys.stderr)
            return 1
        print(f"Run: {run.id}")
        print(f"Status: {run.status}")
        print(f"Started: {run.started_at}")
        print(f"Finished: {run.finished_at}")
        for event in events:
            print(f"{event.kind}: {event.payload}")
        return 0
    if args.command == "list":
        try:
            with RunHistory(args.database) as history:
                for run in history.recent():
                    print(f"{run.id} {run.status} {run.started_at}")
        except Exception as error:
            print(f"Persistence failure: {error}", file=sys.stderr)
            return 1
        return 0


if __name__ == "__main__":
    sys.exit(main())
