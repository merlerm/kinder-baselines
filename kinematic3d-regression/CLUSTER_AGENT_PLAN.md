# Cluster agent experiment plan

## Your role

You are running a merge-gating regression study for a stack of Kinematic3D environment
fixes in `kindergarden`. Your job is to produce paired evidence about how existing KinDER
baselines behave before and after each change. You are not developing new environment
dynamics, changing rewards, tuning methods to recover scores, or opening upstream pull
requests.

Run every environment episode on the cluster. Small import, syntax, and static checks may
run elsewhere, but no experiment rollout should load the researcher's laptop.

## Scientific purpose

Generated policies exposed invalid but visually successful behavior in Obstruction3D and
Packing3D. The fixes also introduce a shared mobile-base action clipping rule that could
affect older Kinematic3D results. Before merging, we need to answer four separate
questions:

1. Does shared action clipping change any baseline trajectory that already respects the
   declared action space?
2. Does the Transport3D reset fix change only seeds whose old initial state overlaps the
   table?
3. Do the Obstruction3D fixes reject shortcut trajectories while retaining feasible,
   collision-valid solutions?
4. Do the Packing3D fixes reject shortcut trajectories while supporting every part shape
   and correct terminal seating?

The first cluster batch addresses questions 1 and 2 with bilevel planning. Later batches
cover the other released baselines and the environment-specific capability checks.

## Fixed environment revisions

Do not substitute newer branch tips or floating Git refs.

| Label | Commit | Meaning |
| --- | --- | --- |
| `A0` | `421609e` | Maintained upstream code before this fix stack |
| `A1` | `4e9a443` | Shared Kinematic3D base-action clipping and optional motion validation |
| `A2` | `9bf8d0f` | Transport3D reset validity |
| `A3` | `486f303` | Obstruction3D goal and motion validity |
| `A4` | `8486999` | Packing3D geometry, motion, and state validity |

Published paper numbers are broad sanity checks, not exact reproduction targets. Use the
maintained baseline implementation on this fork branch for every revision and keep it
fixed while changing only `kindergarden`.

## Non-negotiable constraints

- Work from `merlerm/kinder-baselines`, branch
  `validation/kinematic3d-regression`, commit `1969ae8` or a documented descendant.
- Do not push experiment branches to the Princeton upstream repository.
- Do not open a pull request for this validation infrastructure.
- Do not edit kindergarden environment code during an experiment batch.
- Do not add dense rewards or reward wrappers.
- Use identical outer seeds and episode seeds across paired revisions.
- Preserve raw actions before the environment clips or rejects them.
- Never average away Transport seeds whose old reset is invalid. Report them separately.
- Never overwrite a completed result directory. Move a partial directory aside with a
  timestamp and explain why before rerunning.
- Do not weaken SSH host-key checking, share credentials, or print tokens in logs.
- Do not launch the full matrix until the smoke gate below passes.

## Output contract

Store all durable results under one explicit cluster path:

```bash
export KINDER_REGRESSION_ROOT=/cluster/storage/path/kinder-regression
```

The root must have enough capacity for five Python environments, five kindergarden
worktrees, action traces, later checkpoints, and logs. Record the actual path in your
report. Do not use a broad home-directory path by accident.

The BP runner writes:

```text
$KINDER_REGRESSION_ROOT/
├── manifests/
│   ├── kinder-baselines-revision.txt
│   └── bilevel-A*-pip-freeze.txt
├── source/kindergarden/
├── worktrees/kindergarden-A*/
├── venvs/bilevel-A*/
└── results/bilevel/<revision>/<environment>/seed-<outer-seed>/
    ├── results.csv
    ├── config.yaml
    ├── run_experiment.log
    └── traces/episode-*.jsonl
```

Every result row must include:

- `validation_revision`;
- outer seed in the resolved config;
- exact `episode_seed`;
- success, steps, return, and failure class;
- planning, policy, and environment-step time;
- action count;
- action-space and numerical-bound violation counts; and
- maximum total and mobile-base action excess.

Each step trace must retain the raw action and state hashes before and after the step.

## Phase 0: cluster preflight

Before installing anything, record:

```bash
hostname
date --iso-8601=seconds
nproc
free -h
df -h "$KINDER_REGRESSION_ROOT"
python3 --version
git --version
```

Then verify:

1. The checkout is the fork branch and the working tree is clean.
2. Commit `1969ae8` is an ancestor of `HEAD`.
3. Python is at least 3.10 and can create virtual environments.
4. The node can reach GitHub and PyPI during setup, or the necessary package cache is
   already present.
5. Other users are not relying on all CPU cores. Begin with one concurrent process.

Stop and report if any condition fails. Do not silently change versions or installation
methods to get past a failure.

## Phase 1: install the paired BP environments

From the fork checkout root:

```bash
bash kinematic3d-regression/cluster/setup_bilevel_envs.sh
```

The script creates detached worktrees and a separate virtual environment for A0-A4.
After it finishes, verify each environment imports kindergarden from its matching
worktree, not from a global installation:

```bash
for label in A0 A1 A2 A3 A4; do
  "$KINDER_REGRESSION_ROOT/venvs/bilevel-$label/bin/python" -c \
    'import kinder; print(kinder.__file__)'
done
```

Also inspect the recorded baseline revision and dependency manifests. Stop if any
worktree SHA differs from the fixed table above.

## Phase 2: run the BP smoke matrix

Run five jobs sequentially, two episodes per job:

```bash
bash kinematic3d-regression/cluster/run_bilevel_matrix.sh smoke 1
```

This produces ten total episodes:

- BaseMotion3D: A0 and A1, outer seed 0;
- Transport3D-o2: A0, A1, and A2, outer seed 0.

Do not increase concurrency during the first smoke. Monitor process memory, CPU load, and
whether PyBullet clients are released between episodes.

### Smoke integrity checks

Confirm all five `results.csv` files exist and each contains exactly two rows. Then check:

1. No row has `failure_type=exception` because of setup, imports, serialization, or
   missing files.
2. Paired rows have identical `episode_seed` values.
3. A0 and A1 reset hashes match for both environments.
4. BaseMotion A0/A1 trajectories are identical until an action with positive
   `max_base_action_excess`, if one exists.
5. Transport A0/A1 trajectories obey the same rule.
6. A1/A2 Transport reset differences are permitted only when the A1 reset overlaps the
   table. A two-episode smoke may contain no such seed.
7. Trace files contain a reset record plus one record per executed action.
8. `out_of_space_actions` can include a dtype or shape mismatch. Use
   `out_of_bounds_actions` and `max_base_action_excess` to decide whether the numerical
   base bound was exceeded.

Use the comparator for the first four paired checks:

```bash
python kinematic3d-regression/compare_bilevel_runs.py \
  "$KINDER_REGRESSION_ROOT/results/bilevel/A0/base_motion3d/seed-0" \
  "$KINDER_REGRESSION_ROOT/results/bilevel/A1/base_motion3d/seed-0"

python kinematic3d-regression/compare_bilevel_runs.py \
  "$KINDER_REGRESSION_ROOT/results/bilevel/A0/transport3d-o2/seed-0" \
  "$KINDER_REGRESSION_ROOT/results/bilevel/A1/transport3d-o2/seed-0"

python kinematic3d-regression/compare_bilevel_runs.py \
  "$KINDER_REGRESSION_ROOT/results/bilevel/A1/transport3d-o2/seed-0" \
  "$KINDER_REGRESSION_ROOT/results/bilevel/A2/transport3d-o2/seed-0"
```

### Smoke report and gate

Write `smoke-report.md` under `$KINDER_REGRESSION_ROOT/results/bilevel/` containing:

- host, time, checkout commit, and storage root;
- exact commands;
- whether all five jobs completed;
- a five-row success/steps/timing table;
- action-bound violations by cell;
- the comparator summaries;
- every exception or suspicious divergence; and
- a clear recommendation: `proceed`, `repair harness`, or `investigate baseline`.

Proceed only if seed pairing is exact, imports are correct, traces are complete, and every
A0/A1 divergence is explained by a numerically out-of-bound base command. A smoke success
rate is not itself a gate because there are only two episodes.

## Phase 3: run the full BP matrix

After the smoke report says `proceed`, choose conservative concurrency based on observed
memory and shared load. Start with two processes unless the node owner has approved more:

```bash
bash kinematic3d-regression/cluster/run_bilevel_matrix.sh full 2
```

The full matrix has 25 jobs and 1,250 episodes:

| Environment | Revisions | Outer seeds | Episodes per seed | Total |
| --- | --- | ---: | ---: | ---: |
| BaseMotion3D | A0, A1 | 5 | 50 | 500 |
| Transport3D-o2 | A0, A1, A2 | 5 | 50 | 750 |

The historical BP success rates, approximately 1.00 on BaseMotion3D and 0.46 on
Transport3D, are rough A0 checks. Small drift is acceptable. Stop before interpreting
revision deltas if A0 is qualitatively different, such as BaseMotion no longer being
nearly solved or Transport collapsing because of installation errors.

Monitor disk use while traces accumulate. Reducing concurrency is always acceptable;
changing seeds, timeouts, planner hyperparameters, or environment commits is not.

## Phase 4: analyze the BP results

For every outer seed, run three comparisons:

1. BaseMotion A0 versus A1;
2. Transport A0 versus A1; and
3. Transport A1 versus A2.

Aggregate episode-level results, retaining paired rows. Report:

- success rate and raw success count per cell;
- success-to-failure and failure-to-success flips;
- successful-episode action count and sparse return;
- planning, policy, environment-step, and wall time;
- number and fraction of actions numerically outside the declared bounds;
- maximum mobile-base excess;
- number and kind of first trace differences; and
- all failure classes.

### A0 versus A1 interpretation

An in-bound action must produce the same transition. Classify each first divergence as:

- `expected_clip`: the raw mobile-base action exceeds its bound at the divergent step;
- `method_action_difference`: actions differ before environment states diverge;
- `unexpected_transition`: the same in-bound action produces different next-state hashes;
- `reset_difference`: initial hashes differ; or
- `missing_or_failed_trace`.

The merge gate for the shared PR is zero unexplained deterministic success regressions
and zero `unexpected_transition` or `reset_difference` cases.

### A1 versus A2 Transport interpretation

First split seeds by whether the A1 initial state overlaps the table. For common-valid
seeds, A1 and A2 reset states and subsequent paired behavior should be identical until a
method action differs. For repaired seeds, the A2 initial state is intentionally different.
Report performance on the common-valid subset and corrected full distribution separately.

Do not call a score increase or decrease a policy regression when the underlying initial
state changed from invalid to valid.

## Phase 5: package the BP evidence

Produce:

```text
$KINDER_REGRESSION_ROOT/results/bilevel/
├── smoke-report.md
├── full-summary.md
├── episode-results.csv
├── paired-flips.csv
├── first-divergences.json
└── run-manifest.md
```

`run-manifest.md` must include host information, source commits, dependency manifests,
commands, concurrency, start/end times, output paths, and any moved partial directories.
Do not delete raw per-run outputs after aggregation.

Conclude separately for:

- PR #135 shared action clipping: `pass`, `investigate`, or `block`;
- PR #136 Transport resets: `pass`, `investigate`, or `block`.

Do not make a conclusion about Obstruction3D or Packing3D from this BP batch.

## Later baseline batches

Do not begin these until BP passes its smoke gate and its full jobs are stable. Each batch
must reuse the same A0-A4 labels, seed manifest, output fields, and paired-analysis rules.

### CPU and planner batch

1. Domain-specific policies on BaseMotion3D A0/A1 and Transport3D A0/A1/A2.
2. Ground-truth MPC on the same cells.
3. MBRL with the released world-model checkpoints on the same cells.
4. Frozen PPO and SAC checkpoint evaluation on the same cells.
5. Bilevel planning on KinematicShelf3D and PrplLab3D for A0/A1.

The current branch does not yet provide all of these runners. Add them as separate,
reviewable commits on the fork. Do not improvise a result from a training script when an
evaluation-only loader is required.

### API planner batch

Run LLMPlan, VLMPlan, LLMCon, and VLMCon on BaseMotion3D and Transport3D. Generate each
high-level plan once for an exact initial observation and replay it across compatible
revisions so model sampling noise is not attributed to the environment.

Preserve prompts and raw outputs. These jobs need network/API access but not a GPU.

### Accelerator batch

- DP and DPES use their Python 3.9, PyTorch 1.12.1, CUDA 11.6 environment.
- VLA uses a separate OpenPI JAX/CUDA12 or TPU environment.
- Download only BaseMotion3D and Transport3D checkpoints and record checksums.
- Never combine the two incompatible software environments merely for convenience.

### Corrected-environment capability batch

- Obstruction3D A2/A3: old shortcut policy, repaired policy, adversarial fast policy, and
  qualified skill-planner paths across o0-o4.
- Packing3D A3/A4: old shortcut policy, repaired policy, adversarial fast policy, and the
  forked PDDLStream planner across p1-p3.
- Independently replay every successful corrected trajectory at 1 mm resolution and
  verify no intermediate collision.
- Check analytic full containment or seating for every terminal state and every part
  shape.

Old shortcut policies are expected to fail under corrected semantics. That is not a
regression if the trace shows rejection for the intended collision or goal reason.

## When to stop and ask for help

Stop the current batch and report before spending more compute if:

- a revision SHA or imported kindergarden path is wrong;
- paired episode seeds differ;
- A0/A1 reset states differ;
- the same in-bound action yields different A0/A1 next states;
- result directories are partial or traces are missing;
- A0 performance is qualitatively inconsistent with the maintained baseline;
- dependencies require changing the fixed baseline code or environment commits;
- the cluster is under load or another user needs the resources;
- credentials, host keys, checkpoint provenance, or API access are uncertain; or
- a later baseline has no released implementation or compatible checkpoint.

Report evidence, not only the symptom: exact command, revision, episode seed, first
divergent step, raw action, hashes, error log, and relevant output path.

