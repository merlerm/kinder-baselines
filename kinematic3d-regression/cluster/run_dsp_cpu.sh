#!/usr/bin/env bash

set -euo pipefail

if [[ "$#" -ne 4 ]]; then
  echo "Usage: $0 <A0..A4> <env-config> <outer-seed> <num-episodes>" >&2
  exit 2
fi

LABEL="$1"
ENV_CONFIG="$2"
OUTER_SEED="$3"
NUM_EPISODES="$4"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGRESSION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BASELINES_DIR="$(cd "$REGRESSION_DIR/.." && pwd)"
source "$REGRESSION_DIR/revisions.sh"
get_kindergarden_revision "$LABEL" >/dev/null

if [[ -z "${KINDER_REGRESSION_ROOT:-}" ]]; then
  echo "Set KINDER_REGRESSION_ROOT to the cluster regression root." >&2
  exit 2
fi

VENV="$KINDER_REGRESSION_ROOT/venvs/dsp-$LABEL"
if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Missing $VENV. Run setup_dsp_envs.sh first." >&2
  exit 2
fi

OUTPUT_DIR="$KINDER_REGRESSION_ROOT/results/dsp/$LABEL/$ENV_CONFIG/seed-$OUTER_SEED"
if [[ -f "$OUTPUT_DIR/results.csv" ]]; then
  echo "Completed result already exists: $OUTPUT_DIR/results.csv"
  exit 0
fi
if [[ -d "$OUTPUT_DIR" ]]; then
  echo "Partial output exists at $OUTPUT_DIR; move it aside before rerunning." >&2
  exit 2
fi

mkdir -p "$OUTPUT_DIR"
# The compiled IKFast extension links against MKL; resolve it from the pinned
# copy under the regression root so runs do not depend on shell profiles.
if [[ -d "$KINDER_REGRESSION_ROOT/lib" ]]; then
  export LD_LIBRARY_PATH="$KINDER_REGRESSION_ROOT/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  # Sequential threading avoids the Intel OpenMP dependency and thread
  # oversubscription across concurrent jobs.
  export MKL_THREADING_LAYER=SEQUENTIAL
fi
export MPLCONFIGDIR="$KINDER_REGRESSION_ROOT/cache/matplotlib"
export XDG_CACHE_HOME="$KINDER_REGRESSION_ROOT/cache/xdg"
mkdir -p "$MPLCONFIGDIR" "$XDG_CACHE_HOME"

cd "$BASELINES_DIR/kinder-ds-policies"
exec "$VENV/bin/python" experiments/run_regression_eval.py \
  "env=$ENV_CONFIG" \
  "seed=$OUTER_SEED" \
  "num_eval_episodes=$NUM_EPISODES" \
  "validation_revision=$LABEL" \
  "save_action_traces=True" \
  "hydra.run.dir=$OUTPUT_DIR"
