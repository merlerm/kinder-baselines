#!/usr/bin/env python3
"""Replay recorded regression traces with swept collision checking enabled.

Validates the PR #135 interpolated-path mechanism against real trajectories:
run inside a revision venv (A1 or later), this script rebuilds the environment
with ``max_collision_check_step`` set, resets with each recorded episode seed,
and replays the recorded raw actions.

Outcomes per episode:

- ``identical``: every replayed transition reproduces the recorded state hash.
  The swept check is behavior-preserving for this trajectory.
- ``swept_rejection``: an in-bound action whose recorded transition succeeded is
  rejected (state reverts) under interpolated checking. The original endpoint-only
  transition passed through an intermediate collision.
- ``clip_divergence``: replay diverged at a raw action outside the declared bound.
  Expected when replaying A0 traces (which executed unclipped) in an A1+ env.
- ``replay_mismatch``: a transition differs for an in-bound action without a
  rejection signature. Indicates nondeterminism or an environment bug; investigate.

Usage:
    python replay_swept_validation.py <result-dir> --env-id kinder/Transport3D-o2-v0 \
        --check-step 0.005 [--episodes success|all|0,3,7] [--output out.json]
"""

import argparse
import csv
import dataclasses
import json
from pathlib import Path

import numpy as np


def load_traces(result_dir: Path) -> dict[int, list[dict]]:
    """Load all episode traces keyed by eval episode index."""
    traces = {}
    for path in sorted((result_dir / "traces").glob("episode-*.jsonl")):
        episode = int(path.stem.split("-")[1])
        traces[episode] = [json.loads(line) for line in path.read_text().splitlines()]
    return traces


def select_episodes(result_dir: Path, mode: str) -> list[int]:
    """Resolve the requested episode subset from results.csv."""
    with (result_dir / "results.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if mode == "all":
        return [int(r["eval_episode"]) for r in rows]
    if mode == "success":
        return [int(r["eval_episode"]) for r in rows if r["success"] == "True"]
    return [int(part) for part in mode.split(",")]


def replay_episode(env, hash_observation, records: list[dict]) -> dict:
    """Replay one trace and classify the first divergence, if any."""
    reset = records[0]
    obs, _ = env.reset(seed=reset["episode_seed"])
    if hash_observation(obs) != reset["state_hash"]:
        return {"outcome": "reset_mismatch"}
    prev_hash = reset["state_hash"]
    for record in records[1:]:
        action = np.asarray(record["action"], dtype=np.float32)
        obs, _, _, _, _ = env.step(action)
        new_hash = hash_observation(obs)
        if new_hash == record["state_hash_after"]:
            prev_hash = new_hash
            continue
        if record["max_action_excess"] > 0.0:
            outcome = "clip_divergence"
        elif new_hash == prev_hash:
            outcome = "swept_rejection"
        else:
            outcome = "replay_mismatch"
        return {
            "outcome": outcome,
            "step": record["step"],
            "action": record["action"],
            "max_base_action_excess": record["max_base_action_excess"],
            "recorded_hash": record["state_hash_after"],
            "replayed_hash": new_hash,
        }
    return {"outcome": "identical", "steps_replayed": len(records) - 1}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_dir", type=Path)
    parser.add_argument("--env-id", required=True)
    parser.add_argument("--check-step", type=float, required=True)
    parser.add_argument("--episodes", default="all")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    import kinder
    from kinder_bilevel_planning.regression import hash_observation

    kinder.register_all_environments()
    probe = kinder.make(id=args.env_id).unwrapped
    # ConstantObjectKinDEREnv wraps the object-centric env that owns the config.
    probe_config = probe._object_centric_env.config  # pylint: disable=protected-access
    config = dataclasses.replace(
        probe_config, max_collision_check_step=args.check_step
    )
    probe.close()
    env = kinder.make(id=args.env_id, config=config)

    episodes = select_episodes(args.result_dir, args.episodes)
    traces = load_traces(args.result_dir)
    report = {
        "result_dir": str(args.result_dir),
        "env_id": args.env_id,
        "check_step": args.check_step,
        "episodes": {},
    }
    counts: dict[str, int] = {}
    for episode in episodes:
        result = replay_episode(env, hash_observation, traces[episode])
        report["episodes"][episode] = result
        counts[result["outcome"]] = counts.get(result["outcome"], 0) + 1
        print(f"episode {episode:03d}: {result['outcome']}")
    report["outcome_counts"] = counts

    serialized = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
