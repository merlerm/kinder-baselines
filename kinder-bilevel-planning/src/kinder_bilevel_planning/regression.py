"""Utilities for paired environment-regression experiments."""

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from gymnasium.spaces import Space


def hash_observation(obs: Any) -> str:
    """Return a stable content hash for a vector observation."""
    obs_array = np.ascontiguousarray(np.asarray(obs))
    hasher = hashlib.sha256()
    hasher.update(str(obs_array.dtype).encode("utf-8"))
    hasher.update(str(obs_array.shape).encode("utf-8"))
    hasher.update(obs_array.tobytes())
    return hasher.hexdigest()


def get_action_excess(action_space: Space, action: np.ndarray) -> np.ndarray:
    """Return the coordinate-wise amount by which an action exceeds its box."""
    if not hasattr(action_space, "low") or not hasattr(action_space, "high"):
        return np.zeros_like(action, dtype=float)
    low = np.asarray(getattr(action_space, "low"))
    high = np.asarray(getattr(action_space, "high"))
    return np.maximum(np.maximum(low - action, action - high), 0.0)


def write_trace(trace_path: Path | None, records: list[dict[str, Any]]) -> None:
    """Write one episode trace when tracing is enabled."""
    if trace_path is None:
        return
    with trace_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, sort_keys=True))
            f.write("\n")
