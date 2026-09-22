# enrich-bench

**Which in-silico filters actually enrich for real protein binders, and what does each one
cost?**

Status: work in progress. No results yet. Phase 0 of 6, infrastructure only.

## The question

De novo binder design pipelines produce thousands of candidate proteins and almost all of
them are wrong. The step that decides whether a campaign succeeds is not the generator, it is
the filter: the set of in-silico scores used to rank candidates before anyone spends money on
wet lab validation.

ipTM above 0.8. Interface PAE below some cutoff. ProteinMPNN log-likelihood. Design-to-refold
RMSD. Everyone uses these. Very little published work measures which of them enrich for
experimentally confirmed binders, by how much, with confidence intervals, or what each one
costs in GPU-seconds per design evaluated.

This repo measures that and publishes the numbers, including the ones that are
disappointing.

## Results

Not yet available. The table will report, for each filter, enrichment on a held-out set of
designs with known experimental outcomes, with bootstrapped confidence intervals, alongside
the compute it took to produce the score.

| Filter | EF at 1% | BEDROC (alpha=20) | AUC | GPU-sec per design | $ per 1,000 designs |
|---|---|---|---|---|---|
| _pending_ | | | | | |

Primary metric is enrichment factor at 1%: taking the top 1% of the ranked list, how many
times more true binders you get than random selection would give. BEDROC with alpha = 20 is
reported alongside it because plain AUC-ROC treats a hit at rank 10 and a hit at rank 9,000
as nearly equally good, which is not how anyone actually uses a ranked list.

## What counts as a positive

To be written in Phase 3, before any filter is scored.

The benchmark is conditional on this definition: binding at what affinity, measured by what
assay, at what threshold. There is no objectively correct answer, so the answer used here
will be stated explicitly and the sensitivity of the results to it will be reported.

## Leakage policy

To be written in Phase 3 as `LEAKAGE.md`.

Leakage is the most common reason published results in this field do not reproduce: a
benchmark structure that was in the PDB before a model's training cutoff. The policy will
state, per model used as a filter, its training data cutoff, whether any benchmark structure
could have been seen, and how the split handles it. Splitting is by sequence identity and not
only by date, because a close homolog in training is leakage even when the exact structure is
not.

## Reproducing this

Requires a [Modal](https://modal.com) account. All compute runs there.

```
git clone https://github.com/ninaphatak/enrich-bench
cd enrich-bench
uv sync
uv run modal token new

# short, cheap version to verify the pipeline works
uv run modal run pipelines/full_benchmark.py --pilot

# the full benchmark
uv run modal run pipelines/full_benchmark.py
```

Every job logs its GPU type, GPU-seconds, dollar cost, and the git sha that produced it, so
every number in the results table traces back to the code and the compute that made it.

See [CLAUDE.md](CLAUDE.md) for repo layout and conventions.

## Scope

This benchmark does not train models, does not include wet lab validation, and evaluates
filters against a single well characterized target. Those are deliberate limits, not
oversights. The claim is narrow on purpose: which in-silico filters enrich, and at what
compute cost.

## License

TBD.
