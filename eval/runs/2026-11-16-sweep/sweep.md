# Step 5 ablation: one list at a time, then the fusion

- Corpus: 3226 chunks; page index over 851 pages
- Questions: 30 (26 answerable)
- 79 configurations scored in 31.8 s, one dense encode per question
- Weights are RRF multipliers: `weight / (60 + rank)` per list, fused per page

## Each signal alone

| weights | recall@5 | recall@10 | recall@30 | MRR |
|---|---|---|---|---|
| page 1 / chunk 0 / dense 0 | 25/26 | 25/26 | 25/26 | 0.885 |
| page 0 / chunk 1 / dense 0 | 18/26 | 24/26 | 26/26 | 0.394 |
| page 0 / chunk 0 / dense 1 | 16/26 | 22/26 | 26/26 | 0.422 |

## Best 10 of 79 configurations

| weights | recall@5 | recall@10 | recall@30 | MRR |
|---|---|---|---|---|
| page 1 / chunk 0 / dense 0 | 25/26 | 25/26 | 25/26 | 0.885 |
| page 0.5 / chunk 0 / dense 0 | 25/26 | 25/26 | 25/26 | 0.885 |
| page 2 / chunk 0 / dense 0 | 25/26 | 25/26 | 25/26 | 0.885 |
| page 3 / chunk 0 / dense 0 | 25/26 | 25/26 | 25/26 | 0.885 |
| page 3 / chunk 0.5 / dense 0 | 23/26 | 25/26 | 26/26 | 0.432 |
| page 3 / chunk 0.5 / dense 0.5 | 22/26 | 25/26 | 26/26 | 0.500 |
| page 2 / chunk 0.5 / dense 0 | 22/26 | 25/26 | 26/26 | 0.420 |
| page 3 / chunk 1 / dense 0 | 22/26 | 24/26 | 26/26 | 0.418 |
| page 2 / chunk 0.5 / dense 0.5 | 21/26 | 25/26 | 26/26 | 0.490 |
| page 3 / chunk 2 / dense 0.5 | 21/26 | 25/26 | 26/26 | 0.446 |

## The configuration in the code

| page 1 / chunk 1 / dense 0.7 | 18/26 | 25/26 | 26/26 | 0.464 |

That is rank 36 of 79 by recall@5, then MRR.

## Against the page-level BM25 baseline

Baseline (`eval\runs\2026-11-15-2026-11-14-97docs`): recall@5 25/26, recall@10 25/26, recall@30 25/26, MRR 0.885.

**No configuration beats the baseline.** The measured decision is to keep page-level BM25, which is what the UI runs (D-056).
