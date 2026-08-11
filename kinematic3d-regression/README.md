# Kinematic3D regression campaign

This directory contains experiment infrastructure for comparing the maintained
pre-change KinDER revision with the Kinematic3D pull request stack. It does not modify
environment behavior.

An autonomous cluster worker should read
[`CLUSTER_AGENT_PLAN.md`](CLUSTER_AGENT_PLAN.md) before setup. It defines the scientific
purpose, constraints, smoke and full gates, interpretation rules, outputs, and later
baseline batches.

## Revisions

| Label | Kindergarden commit | Scope |
| --- | --- | --- |
| `A0` | `421609e` | Maintained upstream main before the stack |
| `A1` | `4e9a443` | Shared Kinematic3D motion validity |
| `A2` | `9bf8d0f` | Transport3D reset validity |
| `A3` | `486f303` | Obstruction3D goal and motion validity |
| `A4` | `8486999` | Packing3D geometry and state validity |

The first batch runs bilevel planning on the only two Kinematic3D environments in the
KinDER paper:

- BaseMotion3D on A0 and A1;
- Transport3D-o2 on A0, A1, and A2.

Each revision has an isolated virtual environment and detached kindergarden worktree.
The current `kinder-baselines` checkout is installed into every environment, so the
baseline implementation remains fixed while only kindergarden changes.

## Cluster setup

From the repository root on the cluster:

```bash
export KINDER_REGRESSION_ROOT=/path/with/adequate/storage/kinder-regression
bash kinematic3d-regression/cluster/setup_bilevel_envs.sh
```

This creates the source checkout, five kindergarden worktrees, five Python environments,
and dependency manifests under `KINDER_REGRESSION_ROOT`. It never changes the active
checkout of either repository.

Run the two-episode smoke matrix with one process at a time:

```bash
bash kinematic3d-regression/cluster/run_bilevel_matrix.sh smoke 1
```

After inspecting the smoke outputs, run the full five-seed, 50-episode matrix. The second
argument controls concurrent processes:

```bash
bash kinematic3d-regression/cluster/run_bilevel_matrix.sh full 4
```

Results are written below:

```text
$KINDER_REGRESSION_ROOT/results/bilevel/<revision>/<environment>/seed-<seed>/
```

Each run contains `results.csv`, the resolved Hydra configuration, logs, and one JSONL
action trace per episode. The result table records the exact episode seed, raw action
space violations, numerical bound violations, maximum base-action excess,
policy/planning/environment time, and a failure class.

Completed result directories are not overwritten. Move an unwanted directory aside
before intentionally rerunning it.

## Pairing

The outer method seeds are `0, 1, 2, 3, 4`. Each runner uses a dedicated RNG to generate
50 episode seeds, so the episode manifest is identical across environment revisions.
The exact generated seeds are recorded in every output row.

The primary A0/A1 test is transition identity for in-space actions. A trajectory may
diverge only after a raw mobile-base command exceeds the declared action bound. The
A1/A2 Transport comparison is split later into common-valid reset seeds and seeds whose
A1 state overlaps the table.

Compare one paired outer-seed result after both jobs finish:

```bash
python kinematic3d-regression/compare_bilevel_runs.py \
  "$KINDER_REGRESSION_ROOT/results/bilevel/A0/base_motion3d/seed-0" \
  "$KINDER_REGRESSION_ROOT/results/bilevel/A1/base_motion3d/seed-0"
```
