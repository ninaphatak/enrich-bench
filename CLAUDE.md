# CLAUDE.md

Instructions and conventions for this repository. Public and committed. Read this before
writing any code here.

## What this repo is

`enrich-bench` measures which in-silico filters actually enrich for experimentally
confirmed protein binders, and what each one costs in GPU-seconds per design evaluated.

De novo binder design pipelines produce thousands of candidates and almost all of them are
wrong. The step that decides whether a campaign succeeds is the filter cascade: the set of
scores used to rank candidates before anyone spends money on wet lab validation. Everyone
uses these filters. Very little published work measures which ones enrich, by how much, with
confidence intervals, at what compute cost. That measurement is the entire claim of this
repo.

Ground truth comes from published design campaigns that already have wet-lab outcomes. This
repo does not train models, does not run wet lab validation, does not ship a web UI, and
does not design binders against a novel target.

Primary outputs:

1. A benchmark that runs end to end on Modal with one command, with pinned dependencies and
   a cost report.
2. A results table: enrichment per filter on a held-out set, with bootstrapped confidence
   intervals, plus GPU-seconds per design evaluated.
3. A documented leakage policy, per model used as a filter.
4. A dynamics arm: whether short MD at the designed interface adds signal over static
   confidence metrics, and whether it is worth the compute.

## Status

Phase 0. Repo scaffolding and Modal infrastructure. No results yet.

## Repo layout

```
enrich-bench/
├── CLAUDE.md                 # this file: conventions, how to run
├── README.md                 # public face: what this is, results table
├── LEAKAGE.md                # per-model leakage policy (Phase 3)
├── pyproject.toml            # pinned deps, managed with uv
├── .claude/
│   ├── commands/             # custom slash commands
│   └── skills/               # project skills
├── infra/
│   ├── images.py             # every Modal Image definition, one place
│   ├── volumes.py            # named Volume handles
│   └── costs.py              # timing and pricing decorator
├── tools/                    # one module per model, each its own Modal app
│   ├── proteinmpnn.py
│   ├── af2_initial_guess.py
│   ├── boltz.py
│   ├── rfdiffusion.py
│   └── openmm_md.py
├── bench/
│   ├── datasets/             # ground truth assembly
│   ├── filters/              # the scored quantities under test
│   ├── metrics/              # EF, BEDROC, AUC, precision at k, bootstrap CIs
│   └── splits.py             # train/test splitting and leakage handling
├── pipelines/
│   ├── pilot_design.py       # pilot design round
│   └── full_benchmark.py     # the one-command entrypoint
├── notebooks/                # exploration only, never imported by anything
├── tests/
└── results/
    ├── figures/
    └── tables/
```

`notebooks/` is a dead end by design. If code in a notebook becomes useful, it moves into
`bench/` or `tools/` with a test before anything depends on it.

## Setup

Python 3.11. Dependencies managed with `uv`, all versions pinned.

```
uv sync
uv run modal token new     # once per machine
```

## How to run

```
uv run modal run infra/gpu_check.py              # smoke test: is a GPU reachable
uv run modal run pipelines/pilot_design.py --n 10
uv run modal run pipelines/full_benchmark.py --pilot
uv run modal run pipelines/full_benchmark.py     # the full thing
uv run pytest                                    # tests, all local, no GPU
```

Useful Modal CLI:

```
modal shell tools/af2_initial_guess.py::Folder   # interactive shell in the container
modal volume ls enrich-bench-data
modal volume get enrich-bench-data results/table.csv ./
modal app logs enrich-bench
```

`modal shell` is the best debugging tool in this repo. When a container misbehaves, open a
shell in it and inspect rather than guessing from logs.

## Coding conventions

- Python 3.11. Everything pinned. No unpinned dependency reaches a Modal image.
- **Every Modal function declares `gpu=`, `timeout=`, and `retries=` explicitly.** No
  defaults. A function without an explicit timeout can bill for a hung job indefinitely.
- **Every function that touches a structure takes and returns a path, not a parsed object.**
  Structures are too large to pass across function boundaries as objects.
- **All randomness takes an explicit seed argument.** No exceptions, including sampling
  temperature draws, bootstrap resampling, and train/test splits.
- **Anything in `bench/filters/` or `bench/metrics/` has a test in `tests/` before it is
  used to produce a number.** These are the scientific claims of the repo. A filter without
  a test does not get run.
- Parse structures with `gemmi`. Never hand-roll a PDB or mmCIF parser. Prefer mmCIF: the
  fixed-column PDB format breaks past 99,999 atoms or 62 chains.
- When reading a crystal structure, be explicit about asymmetric unit versus biological
  assembly. Using the wrong one produces a silently wrong interface.
- Any interface definition states its cutoff in the code and in the docstring, for example
  heavy atom pairs within 5 angstroms, or C-beta pairs within 8 angstroms. There is no
  default worth assuming.
- Type hints on every public function. Docstrings state units and direction, for example
  "lower is better, angstroms".

## Modal conventions

- **One image per tool.** Model dependencies are mutually incompatible in practice, so every
  tool in `tools/` gets its own image. Do not try to build one image that runs everything.
- **All image definitions live in `infra/images.py`.** Tools import from there. Images are
  cached by content hash, so a definition scattered across files means cache misses.
- Pin everything an image fetches. A `run_commands` that clones `main` instead of a pinned
  sha invalidates the build cache on every run.
- Install CUDA torch builds with an explicit `index_url`. Without it, pip installs a CPU-only
  wheel and `torch.cuda.is_available()` returns False on a GPU.
- **All Volume handles live in `infra/volumes.py`.** Three volumes: `enrich-bench-weights`,
  `enrich-bench-data`, `enrich-bench-results`.
- Model weights are downloaded once into the weights Volume and never re-downloaded per job.
- Container filesystems are ephemeral. Anything written outside a mounted Volume is gone when
  the container exits. Call `vol.commit()` after writing so other containers can see it, and
  `vol.reload()` to pick up writes made elsewhere.
- **Load weights in `@modal.enter()` on an `@app.cls`, not in the function body.** A class
  loads weights once per container and serves many calls. A plain function reloads them per
  call, which for a multi-GB model dominates the cost.
- Do not specify a region. Region pinning applies a billing multiplier and this workload does
  not need it.
- GPU functions are preemptible by default. For batch inference that is the right trade:
  keep preemptible and set `retries=`.
- Intermediates go to a Volume, not through return values. Return small dicts of scores and
  paths.
- Default to the cheapest GPU that does not OOM, and measure rather than assume. Record the
  GPU chosen and the measured peak memory next to the code that needs it.

## Cost accounting

Every remote call is wrapped in `with track_cost(...)` from `infra/costs.py`, in the local
entrypoint, which appends one row per job to a local `costs.csv`: timestamp, function name,
GPU type, GPU seconds, CPU seconds, estimated dollars, number of inputs, git sha, git dirty
flag, whether the job produces results, notes. The full schema is in the module docstring.
It runs on the laptop, not in the container, because a container's filesystem is discarded
when it exits.

A job marked `produces_results=True` refuses to start on an uncommitted working tree, so
every number in the results table traces to a commit.

Two reasons this is not optional. The headline metric of this benchmark is enrichment per
GPU-dollar, which cannot be reconstructed after the fact if `n_inputs` was never recorded.
And the git sha ties every result back to the code that produced it.

Hard rules:

- Never launch a `.map()` over more than 20 items without running 1 item first and measuring
  it.
- Every Modal function has an explicit `timeout=`.

## Reproducibility

The repo is done when a stranger can clone it, add a Modal token, run
`modal run pipelines/full_benchmark.py`, and reproduce the results table within noise.

That implies: pinned dependencies, seeds on all randomness, the leakage policy stated in
`LEAKAGE.md`, and a `--pilot` flag that runs a short, cheap version of the pipeline so the
plumbing can be verified before anyone spends real money.
