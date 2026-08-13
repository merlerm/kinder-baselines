#!/usr/bin/env bash

set -euo pipefail

if [[ "$#" -lt 4 ]]; then
  echo "Usage: $0 <A0..A4> <agent-config> <env-id> <seed> [extra hydra overrides...]" >&2
  echo "Example: $0 A0 ppo_basemotion3d kinder/BaseMotion3D-v0 301 max_episode_steps=100" >&2
  exit 2
fi

LABEL="$1"
AGENT_CONFIG="$2"
ENV_ID="$3"
SEED="$4"
shift 4

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGRESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BASELINES_DIR="$(cd "$REGRESSION_DIR/.." && pwd)"
source "$REGRESSION_DIR/revisions.sh"
get_kindergarden_revision "$LABEL" >/dev/null

if [[ -z "${KINDER_REGRESSION_ROOT:-}" ]]; then
  echo "Set KINDER_REGRESSION_ROOT to the cluster regression root." >&2
  exit 2
fi

VENV="$KINDER_REGRESSION_ROOT/venvs/rl-$LABEL"
if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Missing $VENV. Run setup_rl_envs.sh first." >&2
  exit 2
fi

ENV_NAME="${ENV_ID##*/}"
OUTPUT_DIR="$KINDER_REGRESSION_ROOT/results/rl/$LABEL/$AGENT_CONFIG/$ENV_NAME/seed-$SEED"
if [[ -f "$OUTPUT_DIR/outputs/.completed" ]]; then
  echo "Completed result already exists: $OUTPUT_DIR"
  exit 0
fi
if [[ -d "$OUTPUT_DIR" ]]; then
  echo "Partial output exists at $OUTPUT_DIR; move it aside before rerunning." >&2
  exit 2
fi

mkdir -p "$OUTPUT_DIR"
export MPLCONFIGDIR="$KINDER_REGRESSION_ROOT/cache/matplotlib"
export XDG_CACHE_HOME="$KINDER_REGRESSION_ROOT/cache/xdg"
mkdir -p "$MPLCONFIGDIR" "$XDG_CACHE_HOME"

# Torch/numpy default to one thread pool per core; cap them so concurrent
# training runs on a shared node do not oversubscribe the machine.
export OMP_NUM_THREADS="${KINDER_RL_THREADS:-4}"
export MKL_NUM_THREADS="${KINDER_RL_THREADS:-4}"
export OPENBLAS_NUM_THREADS="${KINDER_RL_THREADS:-4}"

# kinder-rl writes outputs/ and runs/ relative to the working directory.
cd "$OUTPUT_DIR"
"$VENV/bin/python" "$BASELINES_DIR/kinder-rl/experiments/run_experiment.py" \
  "agent=$AGENT_CONFIG" \
  "env_id=$ENV_ID" \
  "seed=$SEED" \
  "$@"
touch "$OUTPUT_DIR/outputs/.completed"
