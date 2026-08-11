"""Evaluate domain-specific policies with regression instrumentation.

Mirrors the bilevel-planning regression runner: fixed outer seed generates the
episode-seed manifest, every step trace retains the raw action and state hashes,
and results.csv uses the shared paired-analysis schema.

Examples:
    python experiments/run_regression_eval.py env=base_motion3d seed=0 \
        validation_revision=A0 save_action_traces=True
"""

import logging
from pathlib import Path
from typing import Any

import hydra
import kinder
import numpy as np
import pandas as pd
from gymnasium.core import Env
from hydra.core.hydra_config import HydraConfig
from omegaconf import DictConfig, OmegaConf
from prpl_utils.utils import sample_seed_from_rng, timer

from kinder_ds_policies.policies import create_domain_specific_policy
from kinder_ds_policies.policies.base import PolicyFailure, StatefulPolicy
from kinder_ds_policies.regression import (
    get_action_excess,
    hash_observation,
    write_trace,
)


@hydra.main(version_base=None, config_name="config", config_path="conf/")
def _main(cfg: DictConfig) -> None:
    logging.info(f"Running seed={cfg.seed}, env={cfg.env.env_name}")

    kinder.register_all_environments()
    env = kinder.make(**cfg.env.make_kwargs, render_mode="rgb_array", use_gui=False)

    policy = create_domain_specific_policy(
        cfg.env.env_name,
        observation_space=env.observation_space,
        action_space=env.action_space,
        **cfg.env.policy_kwargs,
    )

    rng = np.random.default_rng(cfg.seed)
    configured_episode_seeds = cfg.get("eval_episode_seeds")
    if configured_episode_seeds is not None:
        episode_seeds = [int(s) for s in configured_episode_seeds]
        if len(episode_seeds) != cfg.num_eval_episodes:
            raise ValueError(
                "eval_episode_seeds must contain exactly num_eval_episodes seeds"
            )
    else:
        episode_seeds = [
            sample_seed_from_rng(rng) for _ in range(cfg.num_eval_episodes)
        ]

    current_dir = Path(HydraConfig.get().runtime.output_dir)
    trace_folder = Path(cfg.trace_folder)
    if cfg.save_action_traces:
        trace_folder.mkdir(parents=True, exist_ok=True)

    metrics: list[dict[str, float | bool | int | str]] = []
    for eval_episode in range(cfg.num_eval_episodes):
        logging.info(f"Starting evaluation episode {eval_episode}")
        episode_seed = episode_seeds[eval_episode]
        trace_path = (
            trace_folder / f"episode-{eval_episode:03d}.jsonl"
            if cfg.save_action_traces
            else None
        )
        try:
            episode_metrics = _run_single_episode_evaluation(
                policy,
                env,
                episode_seed,
                max_eval_steps=cfg.max_eval_steps,
                trace_path=trace_path,
            )
        except Exception as e:
            logging.error(
                f"Episode {eval_episode} failed with exception: {e}", exc_info=True
            )
            episode_metrics = {
                "success": False,
                "steps": 0,
                "planning_time": 0.0,
                "execution_time": 0.0,
                "env_step_time": 0.0,
                "reward": 0.0,
                "episode_seed": episode_seed,
                "actions_executed": 0,
                "out_of_space_actions": 0,
                "out_of_bounds_actions": 0,
                "max_action_excess": 0.0,
                "max_base_action_excess": 0.0,
                "failure_type": "exception",
                "error": str(e),
            }
        episode_metrics["eval_episode"] = eval_episode
        episode_metrics["validation_revision"] = cfg.validation_revision
        metrics.append(episode_metrics)

    df = pd.DataFrame(metrics)
    results_path = current_dir / "results.csv"
    df.to_csv(results_path, index=False)
    logging.info(f"Saved results to {results_path}")

    config_path = current_dir / "config.yaml"
    with config_path.open("w", encoding="utf-8") as f:
        OmegaConf.save(cfg, f)
    logging.info(f"Saved config to {config_path}")

    logging.info(f"Success rate: {df['success'].mean()}")


def _run_single_episode_evaluation(
    policy: StatefulPolicy,
    env: Env,
    episode_seed: int,
    max_eval_steps: int,
    trace_path: Path | None = None,
) -> dict[str, float | bool | int | str]:
    steps = 0
    success = False
    total_reward = 0.0
    policy.reset()
    obs, _ = env.reset(seed=episode_seed)
    execution_time = 0.0  # time spent computing policy actions
    env_step_time = 0.0  # time spent in env.step()
    actions_executed = 0
    out_of_space_actions = 0
    out_of_bounds_actions = 0
    max_action_excess = 0.0
    max_base_action_excess = 0.0
    trace_records: list[dict[str, Any]] = [
        {
            "event": "reset",
            "episode_seed": episode_seed,
            "state_hash": hash_observation(obs),
        }
    ]
    failure_type = "horizon_or_update_failure"
    for _ in range(max_eval_steps):
        policy_failed = False
        with timer() as result:
            try:
                action = policy(obs)
            except PolicyFailure:
                policy_failed = True
        execution_time += result["time"]
        if policy_failed:
            failure_type = "policy_failure"
            break

        action_array = np.asarray(action)
        action_in_space = bool(env.action_space.contains(action))
        action_excess = get_action_excess(env.action_space, action_array)
        base_action_excess = float(np.max(action_excess[:3]))
        current_max_action_excess = float(np.max(action_excess))
        if not action_in_space:
            out_of_space_actions += 1
        if current_max_action_excess > 0.0:
            out_of_bounds_actions += 1
        max_action_excess = max(max_action_excess, current_max_action_excess)
        max_base_action_excess = max(max_base_action_excess, base_action_excess)
        state_hash_before = hash_observation(obs)
        with timer() as result:
            obs, rew, done, truncated, _ = env.step(action)
        env_step_time += result["time"]
        actions_executed += 1
        trace_records.append(
            {
                "event": "step",
                "step": actions_executed - 1,
                "action": action_array.tolist(),
                "action_in_space": action_in_space,
                "max_action_excess": current_max_action_excess,
                "max_base_action_excess": base_action_excess,
                "state_hash_before": state_hash_before,
                "state_hash_after": hash_observation(obs),
                "reward": float(rew),
                "terminated": bool(done),
                "truncated": bool(truncated),
            }
        )
        total_reward += float(rew)
        assert not truncated
        steps += 1
        if done:
            success = True
            failure_type = ""
            break

    metrics: dict[str, float | bool | int | str] = {
        "success": success,
        "steps": steps,
        "planning_time": 0.0,
        "execution_time": execution_time,
        "env_step_time": env_step_time,
        "reward": total_reward,
        "episode_seed": episode_seed,
        "actions_executed": actions_executed,
        "out_of_space_actions": out_of_space_actions,
        "out_of_bounds_actions": out_of_bounds_actions,
        "max_action_excess": max_action_excess,
        "max_base_action_excess": max_base_action_excess,
        "failure_type": "" if success else failure_type,
    }
    write_trace(trace_path, trace_records)
    return metrics


if __name__ == "__main__":
    _main()
