"""Tests for Kinematic3D regression instrumentation."""

from pathlib import Path

import numpy as np
from gymnasium.spaces import Box

from kinder_ds_policies.regression import (
    get_action_excess,
    hash_observation,
    write_trace,
)


def test_observation_hash_is_content_sensitive() -> None:
    """Observation hashes are deterministic and distinguish content."""
    obs = np.array([1.0, 2.0], dtype=np.float32)
    assert hash_observation(obs) == hash_observation(obs.copy())
    assert hash_observation(obs) != hash_observation(obs + 1.0)


def test_action_excess_and_trace_writing(tmp_path: Path) -> None:
    """Action excess and JSONL traces preserve regression evidence."""
    action_space = Box(-0.2, 0.2, shape=(4,), dtype=np.float32)
    action = np.array([0.4, 0.0, 0.0, 0.0], dtype=np.float32)
    excess = get_action_excess(action_space, action)
    assert np.isclose(excess[0], 0.2)
    assert np.allclose(excess[1:], 0.0)

    trace_path = tmp_path / "trace.jsonl"
    write_trace(trace_path, [{"event": "reset"}, {"event": "step", "excess": 0.2}])
    assert trace_path.read_text().splitlines() == [
        '{"event": "reset"}',
        '{"event": "step", "excess": 0.2}',
    ]
