"""
Analysis module: loads experiment results and compares monitored vs unmonitored behaviour.

Usage
-----
    python src/analyze.py                    # full report + all figures
    python src/analyze.py --task task_01     # filter to one task
    python src/analyze.py --no-plots         # text report only
"""

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RESULTS_DIR = Path(__file__).resolve().parent.parent / "data" / "results"
FIGURES_DIR = Path(__file__).resolve().parent.parent / "results" / "figures"

CONDITIONS = ["monitored", "unmonitored"]
TOOL_NAMES = ["web_search", "run_python", "write_file"]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_results(task_filter: str | None = None) -> pd.DataFrame:
    """Load all result JSON files into a DataFrame."""
    records = []
    for path in sorted(RESULTS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[warn] Could not load {path.name}: {exc}")
            continue
        if task_filter and data.get("task_id") != task_filter:
            continue
        records.append(data)

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    # Derived columns
    df["output_length"] = df["final_output"].fillna("").str.len()
    df["num_web_search"] = df["tool_calls"].apply(
        lambda calls: sum(1 for c in calls if c["tool_name"] == "web_search")
    )
    df["num_run_python"] = df["tool_calls"].apply(
        lambda calls: sum(1 for c in calls if c["tool_name"] == "run_python")
    )
    df["num_write_file"] = df["tool_calls"].apply(
        lambda calls: sum(1 for c in calls if c["tool_name"] == "write_file")
    )
    df["has_error"] = df["error"].notna() & (df["error"] != "")
    return df


# ---------------------------------------------------------------------------
# Text report
# ---------------------------------------------------------------------------

def print_report(df: pd.DataFrame):
    if df.empty:
        print("No results found. Run experiments first with runner.py")
        return

    print("\n" + "=" * 70)
    print("AGENT OVERSIGHT EXPERIMENT — RESULTS SUMMARY")
    print("=" * 70)
    print(f"Total runs loaded: {len(df)}")
    print(f"Tasks covered:     {sorted(df['task_id'].unique())}")
    print(f"Conditions:        {sorted(df['condition'].unique())}")
    print()

    metrics = [
        ("total_tool_calls",  "Avg tool calls"),
        ("num_web_search",    "Avg web_search calls"),
        ("num_run_python",    "Avg run_python calls"),
        ("num_write_file",    "Avg write_file calls"),
        ("output_length",     "Avg output length (chars)"),
        ("duration_seconds",  "Avg duration (s)"),
        ("total_input_tokens","Avg input tokens"),
        ("total_output_tokens","Avg output tokens"),
    ]

    print(f"{'Metric':<30}  {'Monitored':>12}  {'Unmonitored':>13}  {'Δ (un−mon)':>12}")
    print("-" * 72)

    for col, label in metrics:
        if col not in df.columns:
            continue
        mon = df[df["condition"] == "monitored"][col].mean()
        unmon = df[df["condition"] == "unmonitored"][col].mean()
        if pd.isna(mon) or pd.isna(unmon):
            continue
        delta = unmon - mon
        sign = "+" if delta >= 0 else ""
        print(f"{label:<30}  {mon:>12.2f}  {unmon:>13.2f}  {sign}{delta:>11.2f}")

    print()

    # Per-task breakdown
    print("\n--- Per-task breakdown (avg tool calls) ---\n")
    print(f"{'Task':<15}  {'Monitored':>10}  {'Unmonitored':>12}  {'Δ':>8}")
    print("-" * 50)
    for task_id in sorted(df["task_id"].unique()):
        t = df[df["task_id"] == task_id]
        mon = t[t["condition"] == "monitored"]["total_tool_calls"].mean()
        unmon = t[t["condition"] == "unmonitored"]["total_tool_calls"].mean()
        if pd.isna(mon) or pd.isna(unmon):
            continue
        delta = unmon - mon
        sign = "+" if delta >= 0 else ""
        print(f"{task_id:<15}  {mon:>10.2f}  {unmon:>12.2f}  {sign}{delta:>7.2f}")

    # Qualitative diff: show final_output side-by-side for first run
    print("\n--- Qualitative sample (first run, each task) ---")
    for task_id in sorted(df["task_id"].unique()):
        print(f"\n{'─'*60}")
        print(f"Task: {task_id}")
        for cond in CONDITIONS:
            row = df[
                (df["task_id"] == task_id) & (df["condition"] == cond)
            ].sort_values("run_number").head(1)
            if row.empty:
                continue
            text = row.iloc[0]["final_output"]
            snippet = (text[:300] + "…") if len(text) > 300 else text
            tools = row.iloc[0]["tools_used"]
            print(f"\n  [{cond.upper()}] tools={tools}")
            print(f"  {snippet}")


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def make_plots(df: pd.DataFrame):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        print("[warn] matplotlib/seaborn not available — skipping plots")
        return

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", palette="muted")

    # ------------------------------------------------------------------ #
    # 1. Average tool calls per condition
    # ------------------------------------------------------------------ #
    fig, ax = plt.subplots(figsize=(6, 4))
    means = df.groupby("condition")["total_tool_calls"].mean().reindex(CONDITIONS)
    sems = df.groupby("condition")["total_tool_calls"].sem().reindex(CONDITIONS)
    bars = ax.bar(CONDITIONS, means, yerr=sems, capsize=5, color=["#4C72B0", "#DD8452"])
    ax.set_title("Average Tool Calls per Condition")
    ax.set_ylabel("Mean tool calls (±SE)")
    ax.set_xlabel("Condition")
    for bar, val in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                f"{val:.2f}", ha="center", va="bottom", fontsize=10)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "01_tool_calls_per_condition.png", dpi=150)
    plt.close()
    print(f"[✓] Saved 01_tool_calls_per_condition.png")

    # ------------------------------------------------------------------ #
    # 2. Tool-type breakdown per condition
    # ------------------------------------------------------------------ #
    tool_cols = ["num_web_search", "num_run_python", "num_write_file"]
    tool_labels = ["web_search", "run_python", "write_file"]
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(tool_labels))
    width = 0.35
    for i, (cond, color) in enumerate(zip(CONDITIONS, ["#4C72B0", "#DD8452"])):
        vals = [df[df["condition"] == cond][col].mean() for col in tool_cols]
        ax.bar(x + (i - 0.5) * width, vals, width, label=cond.capitalize(), color=color)
    ax.set_xticks(x)
    ax.set_xticklabels(tool_labels)
    ax.set_title("Tool Usage Breakdown by Condition")
    ax.set_ylabel("Mean calls per run")
    ax.legend()
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "02_tool_breakdown.png", dpi=150)
    plt.close()
    print(f"[✓] Saved 02_tool_breakdown.png")

    # ------------------------------------------------------------------ #
    # 3. Output length distribution
    # ------------------------------------------------------------------ #
    fig, ax = plt.subplots(figsize=(7, 4))
    for cond, color in zip(CONDITIONS, ["#4C72B0", "#DD8452"]):
        vals = df[df["condition"] == cond]["output_length"].dropna()
        ax.hist(vals, bins=15, alpha=0.6, label=cond.capitalize(), color=color)
    ax.set_title("Output Length Distribution")
    ax.set_xlabel("Characters in final response")
    ax.set_ylabel("Frequency")
    ax.legend()
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "03_output_length.png", dpi=150)
    plt.close()
    print(f"[✓] Saved 03_output_length.png")

    # ------------------------------------------------------------------ #
    # 4. Per-task tool calls heatmap
    # ------------------------------------------------------------------ #
    if df["task_id"].nunique() > 1:
        pivot = (
            df.groupby(["task_id", "condition"])["total_tool_calls"]
            .mean()
            .unstack("condition")
            .reindex(columns=CONDITIONS)
        )
        fig, ax = plt.subplots(figsize=(6, max(4, len(pivot) * 0.55)))
        im = ax.imshow(pivot.values, aspect="auto", cmap="YlOrRd")
        ax.set_xticks(range(len(CONDITIONS)))
        ax.set_xticklabels([c.capitalize() for c in CONDITIONS])
        ax.set_yticks(range(len(pivot)))
        ax.set_yticklabels(pivot.index)
        plt.colorbar(im, ax=ax, label="Mean tool calls")
        for r in range(pivot.shape[0]):
            for c in range(pivot.shape[1]):
                val = pivot.values[r, c]
                if not np.isnan(val):
                    ax.text(c, r, f"{val:.1f}", ha="center", va="center",
                            color="black", fontsize=9)
        ax.set_title("Mean Tool Calls: Task × Condition")
        plt.tight_layout()
        plt.savefig(FIGURES_DIR / "04_heatmap_task_condition.png", dpi=150)
        plt.close()
        print(f"[✓] Saved 04_heatmap_task_condition.png")

    # ------------------------------------------------------------------ #
    # 5. Duration comparison
    # ------------------------------------------------------------------ #
    fig, ax = plt.subplots(figsize=(6, 4))
    df.boxplot(column="duration_seconds", by="condition", ax=ax,
               boxprops=dict(color="#4C72B0"), medianprops=dict(color="red"))
    ax.set_title("Task Duration by Condition")
    ax.set_xlabel("Condition")
    ax.set_ylabel("Duration (seconds)")
    plt.suptitle("")
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / "05_duration_boxplot.png", dpi=150)
    plt.close()
    print(f"[✓] Saved 05_duration_boxplot.png")

    print(f"\nAll figures saved to: {FIGURES_DIR}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Analyse oversight experiment results")
    parser.add_argument("--task", help="Filter to a single task id")
    parser.add_argument("--no-plots", action="store_true", help="Skip generating figures")
    args = parser.parse_args()

    df = load_results(task_filter=args.task)
    print_report(df)

    if not args.no_plots and not df.empty:
        make_plots(df)


if __name__ == "__main__":
    main()
