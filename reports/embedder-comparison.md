# Embedder comparison (Step 4 task 5)

Measured on the same 3,226 chunks from `index/chunks.jsonl` and the same
30 questions (26 answerable). Chunk hits are mapped back to pages and
deduplicated, so these numbers are comparable with the page-level BM25
row in `EVAL.md`. Embeddings run on **CPU**; throughput is chunks per
minute for the encode pass only (model load included).

| Model | Recall@5 | Recall@10 | Recall@30 | MRR | Chunks/min (CPU) | Model size | Dim |
|---|---|---|---|---|---|---|---|
| `bge-small-en-v1.5` | 23/26 | 24/26 | 24/26 | 0.702 | 606 | 401 MB | 384 |
| `multilingual-e5-small` | 23/26 | 24/26 | 25/26 | 0.723 | 585 | 2279 MB | 384 |
| `all-MiniLM-L6-v2` | 18/26 | 20/26 | 22/26 | 0.430 | 2148 | 794 MB | 384 |

| Model | dev recall@5 | dev MRR | heldout recall@5 | heldout MRR | Missed entirely |
|---|---|---|---|---|---|
| `bge-small-en-v1.5` | 17/17 | 0.740 | 6/9 | 0.630 | q010, q015 |
| `multilingual-e5-small` | 16/17 | 0.821 | 7/9 | 0.536 | q015 |
| `all-MiniLM-L6-v2` | 14/17 | 0.577 | 4/9 | 0.153 | q015, q017, q029, q030 |

All three models are 384-dimensional, so the comparison is about
quality and speed only, not index size.

## Reading these numbers

`bge-small-en-v1.5` and `multilingual-e5-small` are **within one question of each
other** on recall@5 and recall@10 and differ by 0.021 MRR, which is less than a
single rank shift on 26 questions — not a measurable winner. Their splits
disagree (e5 better on dev MRR, bge better on held-out), so neither ordering is
reliable at this sample size. The recommendation in `DECISIONS.md` (D-054) picks
`bge-small-en-v1.5` on cost — 471 MB of weights and 2,279 MB of files versus
133 MB and 401 MB — not on a quality difference it cannot prove.

`all-MiniLM-L6-v2` is not close: 18/26 at recall@5 and 0.430 MRR, with four
questions missed entirely. It is 3.5x faster and that speed does not buy
anything here.

**Every dense configuration scores below the page-level BM25 baseline**
(25/26, MRR 0.885). Part of the gap is granularity: BM25 ranks pages directly,
while a dense index ranks chunks, so a gold page's four chunks compete with each
other and crowd out the top 5. That is a reason to build hybrid retrieval in
Step 5, not a reason to call dense retrieval broken.
