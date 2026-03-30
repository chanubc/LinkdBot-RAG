# Retrieval Benchmark Summary (2026-03-30)

## Context

This branch is a script-only benchmark branch. It is not intended to merge into `main`.

The goal of this document is to preserve the benchmark results and explain what
they actually mean, so future retrieval experiments can be compared against the
same baseline instead of redoing the setup from scratch.

Compared states:

- `before_branch`: `ef88190`
- `before_today`: `bc4a85f`
- `after_today`: current working tree measured on 2026-03-30

## What Was Measured

### Benchmark accuracy harness

Used `scripts/eval_retriever.py`.

Metrics:

- Top1 Accuracy
- MRR
- P@5
- Recall@5
- New-case top1 hit count

This is still a synthetic benchmark. It is useful for regression checks, but it
does not prove real-user retrieval quality by itself.

### Real-query sample accuracy

Used the same three real queries below with hand-labeled relevant URLs:

- `하나 증권 채용`
- `채용공고 링크 가져와`
- `스타트업 취업 전략`

Metrics:

- Top1 Accuracy
- MRR
- P@5
- Recall@5

This is more realistic than the synthetic harness, but it is still a very small
sample and not enough to claim broad accuracy improvement.

### Real latency

Used `scripts/profile_retriever_latency.py --real --user 8362770686`.

The branch was remeasured twice:

- comparative run: `--repeats 5`
- current rerun: `--repeats 10`

## Benchmark Accuracy Across Three States

| State | Top1 Accuracy | MRR | P@5 | Recall@5 | New cases |
| --- | ---: | ---: | ---: | ---: | --- |
| `before_branch` (`ef88190`) | 0.8571 | 0.9286 | 0.2429 | 1.0000 | 4/4 |
| `before_today` (`bc4a85f`) | 0.8571 | 0.9286 | 0.2429 | 1.0000 | 4/4 |
| `after_today` (working tree) | 0.8571 | 0.9286 | 0.2429 | 1.0000 | 4/4 |

### Interpretation

The benchmark accuracy did **not** change across these three states.

That does not contradict the older retrieval docs. The older document compared
`Dense` vs `PR#68` vs `Today`, which is a much broader historical comparison.
The 2026-03-30 comparison is narrower: it compares the branch base, the branch
before today's script work, and the branch after today's script work.

Today's work was mostly around orchestration and measurement support, not a new
ranking formula, so benchmark accuracy staying flat is expected.

## Real-query Sample Accuracy Across Three States

Relevant URLs were derived from the top results observed during the real query
benchmark pass, then held constant across the three compared states.

| State | Top1 Accuracy | MRR | P@5 | Recall@5 |
| --- | ---: | ---: | ---: | ---: |
| `before_branch` (`ef88190`) | 1.0000 | 1.0000 | 0.6000 | 1.0000 |
| `before_today` (`bc4a85f`) | 1.0000 | 1.0000 | 0.6000 | 1.0000 |
| `after_today` (working tree) | 1.0000 | 1.0000 | 0.6000 | 1.0000 |

### Interpretation

This sample also shows no accuracy separation across the three states.

That means the current three-query set is **not discriminative enough** to prove
that the branch changes accuracy in a meaningful way. It is still useful as a
smoke test, but it is not strong enough to decide product quality on its own.

## Real Latency Across Three States

### Comparative run (`--repeats 5`)

| Query | `before_branch` avg / p95 | `before_today` avg / p95 | `after_today` avg / p95 |
| --- | --- | --- | --- |
| `하나 증권 채용` | 362.75 / 430.91 ms | 478.39 / 947.15 ms | 540.94 / 1039.60 ms |
| `채용공고 링크 가져와` | 449.92 / 556.27 ms | 609.22 / 945.21 ms | 315.09 / 423.98 ms |
| `스타트업 취업 전략` | 715.71 / 776.46 ms | 769.64 / 1271.05 ms | 655.01 / 753.85 ms |

### Current rerun (`--repeats 10`, working tree only)

| Query | avg | p95 | results |
| --- | ---: | ---: | ---: |
| `하나 증권 채용` | 450.14 ms | 1618.08 ms | 5 |
| `채용공고 링크 가져와` | 349.07 ms | 423.96 ms | 5 |
| `스타트업 취업 전략` | 682.11 ms | 788.22 ms | 4 |

### Interpretation

Latency is mixed, not a clean win:

- `채용공고 링크 가져와` improved meaningfully.
- `스타트업 취업 전략` improved modestly.
- `하나 증권 채용` is still worse than the pre-branch baseline and has an ugly tail.

So the right summary is:

- accuracy: unchanged in the current benchmark sets
- latency: partially improved, but still query-sensitive

This is **not** enough evidence to say the original retrieval experiment
improved both latency and accuracy.

## Why The Branch Was Closed

The underlying CTE-first retrieval experiment did not produce a convincing
quality improvement relative to its cost:

- benchmark accuracy stayed flat in the current comparison
- the small real-query accuracy set also stayed flat
- latency improved for some queries but remained worse for others

That makes the experiment valuable mainly as a learning and measurement effort,
not as a product-ready retrieval improvement.

## What Was Worth Keeping

Even though the retrieval experiment itself was not kept, the benchmark tooling
was worth preserving:

- `scripts/eval_retriever.py`
- `scripts/profile_retriever_latency.py`
- `tests/test_eval_retriever_script.py`

These scripts give future retrieval experiments a repeatable way to answer:

- Did accuracy move?
- Did latency move?
- Did the measurement path itself break?

## Recommended Next Step

If retrieval accuracy needs to be revisited later, do not restart from the old
CTE-first idea.

Start with a better labeled real-query set first:

- 20 to 30 real queries
- a mix of exact-heavy, fallback-heavy, variant, and substring cases
- hand-labeled relevant URLs

Then use the benchmark scripts in this branch to compare any new hypothesis.
