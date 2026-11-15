# Dense index size (Step 4 task 6)

Measured, not estimated: the table below is the byte size of `index/lancedb` on
disk after embedding every chunk of the 97-document corpus, read back with
`python -m chunk.dense` (which prints the same numbers it writes here).

| Embedder | Chunks | Pages | Dim | Index size | Bytes/chunk | Bytes/page | 100k pages | Encode |
|---|---|---|---|---|---|---|---|---|
| `bge-small-en-v1.5` | 3226 | 836 | 384 | 8.03 MB | 2488 B | 9602 B | 0.96 GB | 322.4 s |

## How to read it

`Pages` counts the pages a chunk actually covers; the corpus has 851 pages and the
rest are unreadable or empty, so they cost nothing in the index. The ratio is
computed from the row above: the same text chunked differently moves bytes/chunk
but barely moves bytes/page, which is why bytes/page is the unit used here.

The extrapolation multiplies **bytes/page** by 100,000 and assumes the same
average page and the same chunking. It does not model LanceDB compaction or
version overhead growing with table count, which only makes a real 100k-page
table larger, never smaller.

What is *not* included: any BM25/lexical index (Step 5 builds that), the
`index/chunks.jsonl` file itself, and the embedding model weights (134 MB for
bge, 493 MB for e5), which are shipped once and not per page.

Usage: `.venv\Scripts\python.exe -m chunk.dense`
