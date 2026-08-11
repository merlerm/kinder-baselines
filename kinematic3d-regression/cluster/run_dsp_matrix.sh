#!/usr/bin/env bash

set -euo pipefail

if [[ "$#" -ne 2 ]]; then
  echo "Usage: $0 <smoke|full> <max-concurrent-processes>" >&2
  exit 2
fi

MODE="$1"
MAX_JOBS="$2"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "$MODE" in
  smoke)
    EPISODES=2
    SEEDS=(0)
    ;;
  full)
    EPISODES=50
    SEEDS=(0 1 2 3 4)
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    exit 2
    ;;
esac

run_job() {
  "$SCRIPT_DIR/run_dsp_cpu.sh" "$1" "$2" "$3" "$EPISODES"
}
export -f run_job
export SCRIPT_DIR EPISODES

{
  for seed in "${SEEDS[@]}"; do
    printf '%s\0%s\0%s\0' A0 base_motion3d "$seed"
    printf '%s\0%s\0%s\0' A1 base_motion3d "$seed"
    printf '%s\0%s\0%s\0' A0 transport3d-o2 "$seed"
    printf '%s\0%s\0%s\0' A1 transport3d-o2 "$seed"
    printf '%s\0%s\0%s\0' A2 transport3d-o2 "$seed"
  done
} | xargs -0 -n 3 -P "$MAX_JOBS" bash -c 'run_job "$@"' _
