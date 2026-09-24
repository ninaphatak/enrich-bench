"""Cost accounting. Every remote job appends one row to costs.csv at the repo root.

Usage, in a local entrypoint:

    with track_cost("check_gpu", gpu="T4", cpu_cores=0.125, n_inputs=1,
                    produces_results=False):
        check_gpu.remote()

Schema, in column order:

    timestamp         str    ISO 8601, UTC, when the job started
    function_name     str    the Modal function called
    gpu_type          str    as passed to gpu= on the function, or "none"
    gpu_seconds       float  seconds, wall clock around the call; 0 if gpu="none"
    cpu_seconds       float  physical core-seconds: wall clock times cpu_cores
    dollars_est       float  USD, rate card times seconds. Excludes memory, so it is
                             an estimate, not the bill
    n_inputs          int    count of items (designs, structures) the job evaluated
    git_sha           str    full 40 character hash of HEAD
    git_dirty         bool   True if the working tree had uncommitted changes
    produces_results  bool   True if this job's outputs feed the results table
    notes             str    free text; "FAILED: <exception>" is appended on error

A job that produces results refuses to start on a dirty tree, because its row would
name a commit that does not contain the code that ran. Other jobs run and record the
flag.

A row is written even when the job raises, including Ctrl-C, because a failed job
still costs money.

Timing is measured on the laptop around the call. It includes queueing, cold start,
and network round trip, and misses any idle time the container is billed for after
returning. So it is not the billed time; compare against the Modal dashboard. It is
WRONG for .map(): parallel containers overlap in wall time, so one wall-clock number
undercounts GPU seconds. Revisit before Phase 2.
"""

import csv
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COSTS_CSV = REPO_ROOT / "costs.csv"

COLUMNS = [
    "timestamp",
    "function_name",
    "gpu_type",
    "gpu_seconds",
    "cpu_seconds",
    "dollars_est",
    "n_inputs",
    "git_sha",
    "git_dirty",
    "produces_results",
    "notes",
]

# Modal rate card, USD per second. Keys match the strings passed to gpu=.
GPU_DOLLARS_PER_SEC = {
    "none": 0.0,
    "T4": 0.000164,
    "L4": 0.000222,
    "A10": 0.000306,
    "L40S": 0.000542,
    "A100-40GB": 0.000583,
    "A100-80GB": 0.000694,
    "H100": 0.001097,
}
CPU_DOLLARS_PER_CORE_SEC = 0.0000131


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def _check_header() -> None:
    """Fail before the job runs if costs.csv exists with a different schema."""
    if not COSTS_CSV.exists():
        return
    with COSTS_CSV.open(newline="") as f:
        header = next(csv.reader(f), None)
    if header != COLUMNS:
        raise RuntimeError(
            f"{COSTS_CSV} header {header} does not match schema {COLUMNS}. "
            "Rename the old file rather than mixing schemas."
        )


@contextmanager
def track_cost(
    function_name: str,
    *,
    gpu: str,
    cpu_cores: float,
    n_inputs: int,
    produces_results: bool,
    notes: str = "",
) -> Iterator[None]:
    """Time the enclosed remote call and append one row to costs.csv.

    gpu must match the function's gpu= argument, or "none" for CPU-only.
    cpu_cores must match the function's cpu= argument.
    n_inputs is the number of items evaluated, so dollars per item can be derived.
    produces_results=True refuses to run on an uncommitted working tree.
    """
    if gpu not in GPU_DOLLARS_PER_SEC:
        raise ValueError(f"gpu={gpu!r} not in rate card: {list(GPU_DOLLARS_PER_SEC)}")
    if n_inputs < 1:
        raise ValueError(f"n_inputs must be at least 1, got {n_inputs}")
    _check_header()

    sha = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    dirty = status != ""
    if produces_results and dirty:
        raise RuntimeError(
            "Refusing to run a result-producing job on a dirty tree. "
            f"Commit first. Uncommitted:\n{status}"
        )

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    t0 = time.perf_counter()
    try:
        yield
    except BaseException as e:
        notes = f"{notes} FAILED: {type(e).__name__}: {e}".strip()
        raise
    finally:
        wall = time.perf_counter() - t0
        gpu_seconds = 0.0 if gpu == "none" else wall
        cpu_seconds = wall * cpu_cores
        dollars = (
            gpu_seconds * GPU_DOLLARS_PER_SEC[gpu]
            + cpu_seconds * CPU_DOLLARS_PER_CORE_SEC
        )
        is_new = not COSTS_CSV.exists()
        with COSTS_CSV.open("a", newline="") as f:
            writer = csv.writer(f)
            if is_new:
                writer.writerow(COLUMNS)
            writer.writerow([
                started,
                function_name,
                gpu,
                f"{gpu_seconds:.3f}",
                f"{cpu_seconds:.3f}",
                f"{dollars:.6f}",
                n_inputs,
                sha,
                dirty,
                produces_results,
                notes,
            ])
