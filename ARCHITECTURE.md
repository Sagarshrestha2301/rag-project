# Architecture (draft, final choices confirmed per step by benchmark)

## Query flow
```
User question
  -> intent router (rules): greeting/off-topic | follow-up | broad summary | table lookup | normal
  -> condense question (only if chat history exists)
  -> answer cache lookup
  -> hybrid retrieval: dense vectors + BM25, fused with RRF  (LanceDB)
  -> CPU cross-encoder reranker on top 30-50 candidates
  -> small-to-big: expand best chunks to parent section context
  -> score gate: weak evidence => "not found"
  -> local LLM (llama.cpp, GPU) with 4-6 chunks, must cite
  -> code verifies each quote exists in the cited chunk/page
  -> stream answer + citations to UI
```

## Ingestion flow
```
Word -> PDF with LibreOffice headless (pinned version). data/corpus/ IS the corpus: native PDFs are hardlinked from data/raw/ (copied only if hardlinks fail), Word files become data/corpus/<name>.docx.pdf; gold pages, citations and UI links refer to these files (D-023, D-030)
PDF  -> PyMuPDF4LLM on all pages
     -> detect table pages -> Docling or pdfplumber for those pages
     -> flag pages with no text layer (no OCR; stored per file for the UI warning)
  -> chunk by heading / paragraph / table (never across a heading)
  -> prefix every chunk with section path
  -> metadata: year, publisher, type (programmatic)
  -> one LLM-generated 2-line context per document (not per chunk)
  -> embed (CPU, or GPU during bulk build if benchmarked faster)
  -> LanceDB (vectors + BM25 index) ; SQLite manifest
```

## Components
| Part | Draft choice | Why | Not chosen |
|---|---|---|---|
| LLM runtime | llama.cpp server (CUDA) | Offline, OpenAI-style API, control over KV cache | Ollama (less control; fallback) |
| Generator | 3-4B model at Q4, 3 candidates benchmarked in Step 2 | Larger models spill to RAM and are too slow on 4GB | 7B+ models |
| Embeddings | Small model, chosen on our eval in Step 4 | Leaves VRAM for the LLM | 8B embedders |
| Retrieval | Hybrid dense + BM25 with RRF | Exact terms (names, IDs) plus meaning | Dense-only |
| Reranker | Small CPU cross-encoder, top 30-50 | Cheapest accuracy gain | None |
| Store | LanceDB embedded | Native BM25 + vector hybrid, no server | Qdrant/Weaviate (server), Chroma (weaker hybrid) |
| Parsing | PyMuPDF4LLM bulk + Docling/pdfplumber for table pages | Speed on 100k pages, accuracy where tables are | Docling/Marker/MinerU on all pages (too slow, GPU-hungry), cloud parsers |
| Manifest | SQLite | Resumable, incremental, versioned | Ad-hoc JSON |
| UI | Simple local web app with streaming | Requirement F1 | Desktop app |

## Manifest (SQLite) fields
file path, file hash, page count, parser version, chunker version, embedding model + version, status (pending/parsed/embedded/failed), error, timestamps, duplicate-of, unreadable page numbers, source file type (pdf/docx) and path of the converted PDF.

## Resource budget (to be measured in Steps 0 and 2)
VRAM: LLM weights + KV cache must fit 4GB with headroom. RAM: 16GB shared by OS, embeddings, reranker, LanceDB. Record real numbers in `STATUS.md`.

## Planned folder layout (created only when code starts)
```
rag-project/
  docs (this folder)
  eval/        questions.jsonl, runs/
  src/         ingest/, retrieve/, generate/, ui/
  data/        raw/ (owner's originals, read-only), corpus/ (the only PDFs the system reads: hardlinks to native PDFs plus converted Word files as <name>.docx.pdf; mirrors raw/ folders; read-only; SHA-256 of every file in the manifest), parsed/, index/, manifest.sqlite
  .gitignore   data/, models/, index, .venv
  models/      downloaded model files
  scripts/
```

## Experiments backlog (only if eval shows a specific failure; each behind a flag; each needs approval)
HyDE, multi-query, RAPTOR-style summaries, embedder/reranker fine-tuning.

## Rejected
GraphRAG/Neo4j, agentic loops, per-chunk LLM context, generator fine-tuning.

## Offline enforcement (D-026)
One-time approved downloads, then offline mode (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `HF_DATASETS_OFFLINE=1`) set in launch scripts, models loaded from local folders, a list of every downloaded file with SHA-256, and a network-disabled proof run at the end of Steps 0, 5, 6 and 8.

## Version control (D-024)
Git repository created by the owner before Step 0 (first commit `OWNER: initial docs`, D-032). Commit per verified sub-task, tag per approved step, no history rewriting, rollback by `git revert`.
