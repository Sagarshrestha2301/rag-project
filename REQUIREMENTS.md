# Requirements

## Data
- 100,000+ pages; mostly text-based PDFs (official reports, published papers) plus Word files.
- English only. Tables and numbers are very important.
- New files are added now and then (incremental indexing, not rebuild).
- 50GB+ free disk for parsed text, index and caches.

## Functional
- F1. Chat web UI in the local browser, streaming answers, follow-up questions.
- F2. Every claim carries a citation (file name + page number). Quotes are verified in code.
- F3. If evidence is weak, answer "not found". Never guess.
- F4. Question types: specific fact, exact lookup (names, IDs, numbers), table lookup, cross-document summary, comparison.
- F5. Click a citation to open the PDF at the cited page.
- F6. Debug view: retrieved chunks, scores, per-stage timings.
- F7. Add new documents incrementally; resumable ingestion.

## Non-functional
- N1. 100% offline at runtime (and after the one-time approved downloads of models/tools). Enforced with offline mode in launch scripts and proven with network-disabled runs (see `AGENTS.md` rule 6).
- N2. Latency: short follow-up about 20s; deep or long question 30s+ is acceptable. Exact targets set after Step 2.
- N3. Accuracy is measured (see `EVAL.md`), not assumed. No change is accepted unless it passes the regression gate in `EVAL.md`.
- N4. Fit in 4GB VRAM and 16GB RAM. Embedding and reranking run on CPU unless a benchmark proves GPU is better.
- N5. Everything reproducible: pinned versions, deterministic eval runs.
- N6. Web UI binds to localhost only.

## Out of scope (unless the owner changes this)
- OCR of scanned pages (pages without a text layer are flagged only).
- Multi-user access, cloud services, GraphRAG, agentic loops, generator fine-tuning.
- Non-English documents.

## Accuracy targets
Set after Step 1 (eval set) and Step 5 (retrieval baseline). Until then: no numbers promised.
