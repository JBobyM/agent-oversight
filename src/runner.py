"""
Experiment runner.

Usage
-----
# Run one experiment:
    python src/runner.py --task task_01 --condition monitored

# Run one task under both conditions, 3 times each:
    python src/runner.py --task task_01 --runs 3

# Run the full matrix (all tasks × both conditions × N runs):
    python src/runner.py --all --runs 3

Results are saved to:
    data/results/{condition}_{task_id}_{run:02d}.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Allow running as a script from the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent import Agent, DEFAULT_MODEL
from src.conditions import CONDITIONS
from src.tasks import TASKS, get_task

RESULTS_DIR = Path(__file__).resolve().parent.parent / "data" / "results"


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

def run_experiment(
    task_id: str,
    condition: str,
    run_number: int = 1,
    model: str = DEFAULT_MODEL,
    verbose: bool = True,
) -> dict:
    """Run one agent experiment and save the result JSON."""
    task = get_task(task_id)
    agent = Agent(condition=condition, model=model)

    if verbose:
        print(f"\n{'='*60}")
        print(f"Task:      {task['id']} — {task['name']}")
        print(f"Condition: {condition.upper()}")
        print(f"Run:       {run_number}")
        print(f"{'='*60}")

    result = agent.run(task["description"])

    # Augment with metadata
    result["task_id"] = task["id"]
    result["task_name"] = task["name"]
    result["task_category"] = task["category"]
    result["run_number"] = run_number
    result["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Save
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"{condition}_{task['id']}_{run_number:02d}.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    if verbose:
        print(f"\n[✓] Saved → {out_path.relative_to(Path.cwd())}")
        print(f"    Duration:    {result['duration_seconds']:.1f}s")
        print(f"    Tool calls:  {result['total_tool_calls']}")
        print(f"    Tools used:  {result['tools_used']}")
        tok_in = result["total_input_tokens"]
        tok_out = result["total_output_tokens"]
        print(f"    Tokens:      {tok_in} in / {tok_out} out")
        if result.get("error"):
            print(f"    ERROR:       {result['error']}")
        print(f"\n--- Final output (truncated) ---")
        snippet = result["final_output"][:500].replace("\n", " ")
        print(snippet + ("…" if len(result["final_output"]) > 500 else ""))

    return result


# ---------------------------------------------------------------------------
# Batch helpers
# ---------------------------------------------------------------------------

def run_task_all_conditions(
    task_id: str, runs: int = 1, model: str = DEFAULT_MODEL, verbose: bool = True
) -> list[dict]:
    results = []
    for condition in CONDITIONS:
        for run in range(1, runs + 1):
            r = run_experiment(task_id, condition, run, model, verbose)
            results.append(r)
    return results


def run_all(runs: int = 1, model: str = DEFAULT_MODEL, verbose: bool = True) -> list[dict]:
    results = []
    total = len(TASKS) * len(CONDITIONS) * runs
    done = 0
    for task in TASKS:
        for condition in CONDITIONS:
            for run in range(1, runs + 1):
                done += 1
                if verbose:
                    print(f"\n[{done}/{total}] Running {task['id']} | {condition} | run {run}")
                r = run_experiment(task["id"], condition, run, model, verbose)
                results.append(r)
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Agent oversight experiment runner")
    parser.add_argument("--task", help="Task id (e.g. task_01) or name (e.g. ceo_lookup)")
    parser.add_argument(
        "--condition",
        choices=list(CONDITIONS),
        help="Condition to run (default: both)",
    )
    parser.add_argument(
        "--runs", type=int, default=1, help="Number of runs per task×condition (default: 1)"
    )
    parser.add_argument("--all", action="store_true", help="Run all tasks × all conditions")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model ID to use")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")
    parser.add_argument("--list", action="store_true", help="List all tasks and exit")

    args = parser.parse_args()
    verbose = not args.quiet

    if args.list:
        print("\nAvailable tasks:")
        for t in TASKS:
            print(f"  {t['id']}  ({t['name']})  [{t['category']}]")
            print(f"      {t['description'][:80]}…")
        return

    if args.all:
        run_all(runs=args.runs, model=args.model, verbose=verbose)
    elif args.task:
        if args.condition:
            for run in range(1, args.runs + 1):
                run_experiment(args.task, args.condition, run, args.model, verbose)
        else:
            run_task_all_conditions(args.task, runs=args.runs, model=args.model, verbose=verbose)
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python src/runner.py --list")
        print("  python src/runner.py --task task_01 --condition monitored")
        print("  python src/runner.py --task task_01 --runs 3")
        print("  python src/runner.py --all --runs 2")


if __name__ == "__main__":
    main()
