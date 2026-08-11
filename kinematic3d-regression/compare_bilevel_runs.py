#!/usr/bin/env python3
"""Compare two paired bilevel-planning regression result directories."""

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def _load_results(path: Path) -> dict[int, dict[str, str]]:
    """Load result rows keyed by evaluation episode."""
    with (path / "results.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return {int(row["eval_episode"]): row for row in rows}


def _load_trace(path: Path, episode: int) -> list[dict[str, Any]]:
    """Load one episode JSONL trace."""
    trace_path = path / "traces" / f"episode-{episode:03d}.jsonl"
    if not trace_path.exists():
        return []
    return [json.loads(line) for line in trace_path.read_text().splitlines()]


def _first_trace_difference(
    left: list[dict[str, Any]], right: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Describe the first action or state difference in two episode traces."""
    if not left or not right:
        return {"kind": "missing_trace"}
    if left[0]["state_hash"] != right[0]["state_hash"]:
        return {"kind": "reset_state", "step": -1}

    left_steps = left[1:]
    right_steps = right[1:]
    for step, (left_record, right_record) in enumerate(zip(left_steps, right_steps)):
        if left_record["action"] != right_record["action"]:
            return {
                "kind": "action",
                "step": step,
                "left_max_base_action_excess": left_record["max_base_action_excess"],
                "right_max_base_action_excess": right_record["max_base_action_excess"],
            }
        if left_record["state_hash_after"] != right_record["state_hash_after"]:
            return {
                "kind": "transition",
                "step": step,
                "left_max_base_action_excess": left_record["max_base_action_excess"],
                "right_max_base_action_excess": right_record["max_base_action_excess"],
            }
    if len(left_steps) != len(right_steps):
        return {"kind": "trace_length", "step": min(len(left_steps), len(right_steps))}
    return None


def compare_runs(left_dir: Path, right_dir: Path) -> dict[str, Any]:
    """Compare paired metrics and traces from two result directories."""
    left_results = _load_results(left_dir)
    right_results = _load_results(right_dir)
    if set(left_results) != set(right_results):
        raise ValueError("Evaluation episode sets differ")

    success_to_failure = 0
    failure_to_success = 0
    seed_mismatches: list[int] = []
    trace_differences: list[dict[str, Any]] = []
    for episode in sorted(left_results):
        left_row = left_results[episode]
        right_row = right_results[episode]
        if left_row["episode_seed"] != right_row["episode_seed"]:
            seed_mismatches.append(episode)
        left_success = left_row["success"].lower() == "true"
        right_success = right_row["success"].lower() == "true"
        success_to_failure += int(left_success and not right_success)
        failure_to_success += int(not left_success and right_success)

        difference = _first_trace_difference(
            _load_trace(left_dir, episode), _load_trace(right_dir, episode)
        )
        if difference is not None:
            difference["eval_episode"] = episode
            difference["episode_seed"] = int(left_row["episode_seed"])
            trace_differences.append(difference)

    return {
        "episodes": len(left_results),
        "seed_mismatches": seed_mismatches,
        "success_to_failure": success_to_failure,
        "failure_to_success": failure_to_success,
        "trace_differences": trace_differences,
    }


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("left_dir", type=Path)
    parser.add_argument("right_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    comparison = compare_runs(args.left_dir, args.right_dir)
    serialized = json.dumps(comparison, indent=2, sort_keys=True)
    if args.output is None:
        print(serialized)
    else:
        args.output.write_text(serialized + "\n", encoding="utf-8")


if __name__ == "__main__":
    _main()
