# Embedder comparison (Step 4 task 5)

Measured on the same 3,226 chunks from `index/chunks.jsonl` and the same
30 questions (26 answerable). Chunk hits are mapped back to pages and
deduplicated, so these numbers are comparable with the page-level BM25
row in `EVAL.md`. Embeddings run on **CPU**; throughput is chunks per
minute for the encode pass only (model load included). Model size is the
folder on disk after pruning (ONNX/OpenVINO copies removed).

| Model | Recall@5 | Recall@10 | Recall@30 | MRR | Chunks/min (CPU) | Model size | Dim |
|---|---|---|---|---|---|---|---|
| `bge-small-en-v1.5` | 23/26 | 24/26 | 24/26 | 0.702 | 822 | 134 MB | 384 |
| `multilingual-e5-small` | 23/26 | 24/26 | 25/26 | 0.723 | 585 | 493 MB | 384 |
| `all-MiniLM-L6-v2` | 18/26 | 20/26 | 22/26 | 0.430 | 2148 | 92 MB | 384 |

| Model | dev recall@5 | dev MRR | heldout recall@5 | heldout MRR | Missed entirely |
|---|---|---|---|---|---|
| `bge-small-en-v1.5` | 17/17 | 0.740 | 6/9 | 0.630 | q010, q015 |
| `multilingual-e5-small` | 16/17 | 0.821 | 7/9 | 0.536 | q015 |
| `all-MiniLM-L6-v2` | 14/17 | 0.577 | 4/9 | 0.153 | q015, q017, q029, q030 |

All three models are 384-dimensional, so the comparison is about
quality and speed only, not index size.
