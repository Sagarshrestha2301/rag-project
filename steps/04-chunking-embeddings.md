# Step 4: Chunking, metadata, embeddings

**Goal:** turn parsed pages into well-formed chunks with metadata, and pick the embedder using our own eval.
**Needs approval to start:** yes. Embedder candidates re-checked first (OD-3).

## Tasks
1. Chunker: split by heading, paragraph and table; never across a heading. Prefix every chunk with its section path.
2. Tables: keep each table as one chunk with caption, units and footnotes. Very long tables split by row groups, repeating the header row.
3. Programmatic metadata: year, publisher, document type, file, page range.
4. One LLM-generated 2-line context per document (not per chunk); record the prompt and model.
5. Benchmark 3 embedding models on the Step 3 sample with the eval set: recall@k and MRR, speed in pages per minute on CPU (and GPU for the bulk build, if it is faster).
6. Record the embedder choice, vector size and storage per page.

## Definition of done
- [ ] Chunker tested: no chunk crosses a heading; every table chunk keeps caption, units, footnotes
- [ ] Every chunk has file, page range, section path and metadata
- [ ] Embedder comparison table (recall@k, MRR, speed, size) in `DECISIONS.md`
- [ ] Embedder chosen; dense-only retrieval baseline recorded in `EVAL.md`
- [ ] Index size per 1k pages measured and extrapolated to 100k pages

## Context to read
This file, `ARCHITECTURE.md` (ingestion flow), `DECISIONS.md` (D-009, OD-3), `EVAL.md`, the parsed output from Step 3, `reports/parsing-sample.md`.

## Expected output
Chunker module with tests, chunk records stored with their metadata, and `reports/embedder-comparison.md` (recall@k, MRR, speed, size for 3 embedders). Chunk record fields: `chunk_id, file, page_start, page_end, section_path, type (text|table), text, caption, units, footnotes, year, publisher, doc_type, doc_context, chunker_version`.

## Verification
Owner inspects 10 random chunks (3 of them tables) for correctness.

## Risks
Chunks too small to answer, too big to fit 4-6 in the context; heading detection errors from the parser.
