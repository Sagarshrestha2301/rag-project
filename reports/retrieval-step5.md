# Step 5 retrieval: what was measured (2026-11-16)

Two retrievers were built and scored on the same 30 questions with the same scorer
(`eval/score.py`) and the same page-level definition of a hit.

| retriever | recall@5 | recall@10 | recall@30 | MRR |
|---|---|---|---|---|
| page BM25 (`ui/retrieval.py`) — **in use** | **25/26** | 25/26 | 25/26 | **0.885** |
| chunk BM25 alone (page and dense at 0) | 18/26 | 24/26 | 26/26 | 0.394 |
| chunk BM25 + chunk bge, no page list | 18/26 | 25/26 | 26/26 | 0.449 |
| + page BM25 in the fusion, weights in the code | 18/26 | 25/26 | 26/26 | 0.464 |
| + page BM25, best of 79 weight combinations (3 / 0.5 / 0) | 23/26 | 25/26 | 26/26 | 0.432 |

**Corrected 2026-11-16.** This table first quoted `chunk BM25 + chunk bge` at 24/26 with
MRR 0.832 and `best of 24 weight combinations` at 24/26 with MRR 0.486. Neither number
reproduces, and neither had an artifact behind it: they came from a shell session. The
same scorer over **79 saved configurations** (`eval/run_sweep.py`,
`eval/runs/2026-11-16-sweep/`) gives the rows above instead — the best fusion is 23/26 at
MRR 0.432, and the best MRR any fusion reaches is 0.500 at 22/26. The decision does not
change; it gets stronger, because no fusion gets near the baseline. See PROPOSED D-057.

Runs: `eval/runs/2026-11-15-2026-11-14-97docs` (baseline),
`eval/runs/2026-11-16-hybrid-bge` (the fusion), `eval/runs/2026-11-16-sweep/` (each list
alone and 79 weight combinations, the ablation table above). Reproduce with
`.venv\Scripts\python.exe evalun_hybrid.py --label hybrid-bge`.

## What this says

- **The page baseline is strong on this eval set and this corpus.** 25 of 26 answerable
  questions have their gold page at rank 1. That is not luck: the questions quote exact
  strings (`540 mm`, a station name, a year), which BM25 over whole pages matches
  directly, and a page keeps terms together that chunking separates (q010 asks about
  "the correlation coefficient for equation (2)"; the phrase is on one page and in no
  single chunk).
- **The chunk fusion is not a plumbing bug.** Driving the same code path with the page
  list alone reproduces 25/26 and MRR 0.885 exactly, so the loss comes from fusing
  chunk-granularity lists into a page-granularity metric.
- **The dense side does add recall at the tail**: recall@30 goes 25 -> 26, and the one
  question the baseline misses entirely (q015) is found at rank 9-15 by the fusion. That
  is the case chunk + dense retrieval exists for; it is not enough to accept a
  seven-question loss at rank 5.
- **Rejected, not deleted.** `retrieval/hybrid.py` stays as evidence, with a
  `TODO(step-05)` naming the next honest attempt: a cross-encoder reranker over the
  baseline's top 30 pages, where the candidate set is unchanged and recall cannot fall.
  Re-tuning RRF weights on these 26 questions would be fitting the test set.

## What is not measured

- **Answer quality.** No generation was run for these runs, so citation accuracy, numeric
  exact match and not-found behaviour are unchanged from the last recorded oracle run;
  nothing here claims an improvement in answers.
- **A larger corpus.** 851 pages fit page-level BM25 comfortably. At 100k pages the
  page-level list is 100k documents per query and the chunk list is ~380k; the trade-off
  will look different, and that is where a reranker becomes necessary rather than nice.
