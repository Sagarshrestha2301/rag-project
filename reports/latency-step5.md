# Retrieval latency per stage (Step 5)

- Corpus: 3226 chunks, page index over 851 pages
- Questions timed: 30 (same set as the eval)
- One-off index build: **18.9 s** (page BM25 + chunk BM25 + opening the LanceDB table and loading bge)
- Timed on this machine, CPU only, with the dense model warm after the build; the first encode is inside the build figure, not in the per-question rows

| stage | p50 ms | p95 ms | max ms |
|---|---|---|---|
| page_bm25 | 5.5 | 7.0 | 7.5 |
| chunk_bm25 | 19.5 | 26.8 | 27.8 |
| dense | 44.7 | 47.7 | 80.2 |
| fuse | 6.8 | 10.7 | 11.6 |
| **retrieval total** | 77.1 | 92.6 | 108.3 |

**Budget:** retrieval p95 is 92.6 ms against a 20 s end-to-end target for a standard question, so retrieval is not the bottleneck: generation is, at 13.5 tokens/s (about 3.7 s for a short cited answer). The dense stage dominates retrieval at roughly 44.7 ms p50, because it encodes the question with bge on the CPU - moving it to the GPU would contend with the model for the 4 GB card (D-004 keeps embeddings on the CPU).

Not measured here: BM25 index build time split by stage, memory, and latency under concurrent requests. The UI answers one question at a time.
