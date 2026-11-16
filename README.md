# Offline RAG Project

Fully offline question answering over 100k+ pages of official reports and papers (PDF, Word), with page-level citations.

**Target machine:** Windows 11, RTX 3050 4GB VRAM, 16GB RAM. No internet at runtime.

## Status
First-time setup for the owner (git init, first commit, approvals): see `APPROVALS.md`.
See `STATUS.md`. **No code is written or installed until the docs are approved and each step is approved separately.**

## Quickstart

The short version; options, checks and failure fixes are in `RUNNING.md`.

```powershell
# 1. Install into the project venv (Python 3.12; this machine has the pinned
#    interpreter at tools\python312, otherwise use any 3.12 install)
tools\python312\python.exe -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Parse the corpus and build chunks (~17 min for the current 97 PDFs, then ~1 s)
.venv\Scripts\python.exe -m ingest.cli build
.venv\Scripts\python.exe -m chunk.cli build

# 3. Dense index (CPU; needs models\bge-small-en-v1.5; writes reports\index-size.md)
.venv\Scripts\python.exe -m chunk.dense

# 4. Start the model: Ollama on 127.0.0.1:11434, qwen3.5:4b, 30-minute keep-alive
.\scripts\launch-llm.ps1

# 5. Start the chat UI, then open http://127.0.0.1:8000
.\scripts\open-chat.ps1 -Start
```

Everything runs offline and binds to localhost only. The launcher exports the
offline flags for Ollama. `data/`, `index/` and `models/` are gitignored: the
corpus and the embedder weights must already be on disk, and step 2 creates
`index/` from them.

## Document map
| File | Purpose |
|---|---|
| `REQUIREMENTS.md` | What the system must do and its limits |
| `ARCHITECTURE.md` | Components, data flow, choices and rejected alternatives |
| `PLAN.md` | Step order (0-9) and approval gates |
| `STATUS.md` | Current state, log, next action. Updated after every work session |
| `DECISIONS.md` | Decision log and open decisions |
| `AGENTS.md` | Rules every coding agent must follow |
| `APPROVALS.md` | Owner-only record of step approvals (agents read, never edit) |
| `EVAL.md` | Evaluation set, metrics, regression gate, results |
| `docs/manual.html` | Stand-alone manual for readers who will not open the repo; `reports/build_manual.py` regenerates it, and `scripts/manual-to-pdf.ps1` prints `docs/manual.pdf` for emailing |
| `steps/NN-name.md` | One file per step: tasks, definition of done, verification |

## Repository layout

What is where, and whether git tracks it. A `#` note on a folder says what it holds; the
`(generated, gitignored)` marker means do not commit it and do not treat it as source.

```
rag-project/
├── README.md                     # this file: document map and folder map
├── AGENTS.md                     # rules every coding agent follows (protected)
├── APPROVALS.md                  # owner-only approval log (protected; agents read, never write)
├── REQUIREMENTS.md               # what the system must do, and its limits
├── ARCHITECTURE.md               # components, data flow, rejected alternatives
├── PLAN.md                       # step order 0-9 and the approval gate before each step
├── STATUS.md                     # current state, measured facts, session log, proposals
├── DECISIONS.md                  # decision log; agents append PROPOSED entries only
├── EVAL.md                       # eval set, metrics, regression gate, result rows
├── RUNNING.md                    # how to start the model, the UI and the checks
├── TRACKER.md, STEP3-PLAN.md, STEP4-PLAN.md, env-report.md
│                                 # working notes for the steps they are named after
├── requirements.txt              # direct dependencies, pinned
├── requirements.lock.txt         # full resolved lock
├── steps/                        # one file per step: tasks, definition of done, verification
│   └── 00-…md … 09-…md
├── chunk/                        # Step 4: parsed pages -> chunks, one module per concern
│   ├── base.py                   # Block, Section, Chunk, DocMeta, the chunker registry
│   ├── structure.py              # heading detection, document blocks, section splitting
│   ├── text.py                   # section-bounded text chunks (never across a heading)
│   ├── tables.py                 # one table = one chunk, with caption/units/footnotes
│   ├── build.py                  # merges text + table chunks; no block used by both
│   ├── meta.py                   # year/publisher/doc_type from the path, then from page 1
│   ├── doc_context.py            # one cached 2-line context per document
│   ├── cli.py                    # python -m chunk.cli build   -> index/chunks.jsonl
│   ├── dense.py                  # python -m chunk.dense       -> index/lancedb + reports/index-size.md
│   ├── review.py                 # python -m chunk.review      -> artifacts/step4/review.html (10 chunks, 3 tables)
│   └── test_*.py                 # one suite per module; run the file directly
├── ingest/                       # Step 3: PDF -> parsed pages, tables, OCR, verification
│   ├── base.py                   # corpus paths, page records
│   ├── text.py, tables.py, ocr.py, manifest.py
│   ├── drive.py                  # bounded Google Drive sample fetch + SHA-256 manifest
│   ├── cli.py                    # python -m ingest.cli build | verify
│   └── verify.py                 # cell check + the two review sheets the owner reads
├── eval/                         # the eval set and its scorer
│   ├── questions.jsonl           # 30 questions (gold answers, gold pages, dev/held-out)
│   ├── score.py, run_retrieval.py, build_questions.py, build_review.py, make_fixtures.py
│   ├── fixtures/                 # hand-made scorer fixtures
│   └── runs/                     # recorded eval runs (committed on purpose)
├── ui/                           # chat UI: FastAPI + static files, no build step
│   ├── server.py                 # streams answers, serves /pdf/{name}, health endpoint
│   ├── retrieval.py              # page-level BM25 prototype (superseded by Step 5)
│   └── static/                   # index.html, app.js, styles
├── scripts/                      # PowerShell helpers: health, health report, launch, offline proof
├── benchmarks/                   # what was measured, and with what
│   ├── embeddings/run_embedder_bench.py   # the three-model comparison
│   └── llm/                      # oracle runs, scores per model, speed measurements
├── reports/                      # measured findings: embedder comparison, metadata, index size,
│                                 # parsing sample, manual test sheet, knowledge graph
├── data/                         (generated, gitignored) corpus PDFs in data/corpus (read-only)
├── index/                        (generated, gitignored) parsed pages + chunks.jsonl + lancedb/
├── models/                       (generated, gitignored) embedder weights, ~690 MB
├── logs/                         (generated, gitignored) health log, build logs, download manifests
├── artifacts/                    (generated, gitignored) review sheets, step evidence,
│                                 #   plus owner-kit/ which is force-added because it is text
├── tools/                        (generated, gitignored) python312 interpreter, installer, prototypes
└── .venv/                        (generated, gitignored) the project virtual environment
```

The split matters more than the list: **source and record** are tracked, **anything
regenerated** is not. `data/`, `index/`, `models/`, `logs/`, `artifacts/`, `tools/` and
`.venv/` are gitignored, so `git status` stays readable and no 100 MB artefact enters
history. Two of them repay a note, because someone always asks:

- `tools/python312` (70 MB) is the interpreter `.venv` is built on (`pyvenv.cfg` points at
  it). Deleting it breaks every Python command in the project.
- `models/` holds `bge-small-en-v1.5` (129 MB, in use), `multilingual-e5-small` (470 MB,
  the alternative in D-054) and `all-MiniLM-L6-v2` (88 MB, rejected on measurement). Only
  the third is removable without touching a decision, and only after its entry is dropped
  from `benchmarks/embeddings/run_embedder_bench.py`.

## Workflow
1. Run `git status` (stop if not clean). Read `AGENTS.md`, then `STATUS.md`, then the current `steps/NN-*.md`.
2. Work on exactly one step that has a start approval in `APPROVALS.md`.
3. Verify against the step's definition of done and `EVAL.md`.
4. Update `STATUS.md` (and `DECISIONS.md` if anything was decided).
5. Stop and wait for the owner's approval before the next step. Only the owner records approvals and tags steps.
