"""Named Modal Volume handles. The only place volume names are spelled.

- enrich-bench-weights: model weights, downloaded once and never per job.
- enrich-bench-data: input structures, ground truth datasets, and pipeline
  intermediates (backbones, sequences, refolds).
- enrich-bench-results: final score tables and figures.

Writers must call .commit() so other containers see their files. Long-lived
readers must call .reload() to see files committed after they mounted.
"""

import modal

data = modal.Volume.from_name("enrich-bench-data", create_if_missing=True)
weights = modal.Volume.from_name("enrich-bench-weights", create_if_missing=True)
results = modal.Volume.from_name("enrich-bench-results", create_if_missing=True)