# Adding 20,000 PDFs offline, in waves

Status: **plan for owner approval. Nothing has been ingested, downloaded or changed.**
Date: 2026-11-21.

The pipeline already supports incremental, resumable ingestion (`ingest/pipeline.py`:
`build`, `status`, `backup`, `restore`; SQLite manifest; per-document resume; exact and
near-duplicate flagging). What it does not yet have is a way to add a *batch* of local PDFs
safely, a retrieval-quality gate that can judge a corpus this much larger, or a measured
answer to "does page-level BM25 still work at 20k documents". This plan supplies the
sequence and the gates; each wave has to be measured, not assumed.

Every number below is either **measured** at the current 97-document corpus or **projected**
from a measured per-page/per-chunk rate. Projections are not results.

---

## 1. What is measured today

| Fact | Value | Source |
|---|---|---|
| Documents / pages / chunks | 97 / 851 / 3,226 | `ingest.pipeline status` |
| Originals on disk | 49 MB (`data/raw`, hardlinked into `data/corpus`) | `du -sh data/raw` |
| Parse throughput | 51.3 pages/min (1.66 s/page), 1,414.5 s for 851 pages | `ingest.pipeline status`, `reports/parsing-sample.md` |
| OCR cost | 4.2 s/page; 86 of 851 pages were OCR'd | `reports/parsing-sample.md` |
| Chunk ratio | 3.79 chunks/page | 3,226 / 851 |
| Embedding (bge-small, CPU) | 322.4 s for 3,226 chunks = 0.0999 s/chunk | `reports/index-size.md` |
| Document context | ~7 s/document (96 docs, ~11 min) | STATUS.md, Step 4 |
| Bibliography | 14.3 s/document (96 docs, 1,371.5 s) | STATUS.md, D-066 |
| Index size on disk | 43 MB total: `pages.json` 2.41 MB, `chunks.jsonl` 6.64 MB, `parsed/` 13 MB, `lancedb/` 18 MB (Step 4 recorded 8 MB for the table; LanceDB keeps older versions, which a 20k table accumulates faster) | `ls -l`, `du -sh index/*` |
| BM25 top-5 query | 2–140 ms; process loading the index peaks at 67 MiB RSS | STATUS.md, Step 8 |
| Retrieval baseline | recall@5 45/48, MRR 0.826 on 48 answerable dev questions | `eval/runs/2026-11-20-step9-retry-guard` |
| Disk free | 717 GB on `C:` | `df -h` |
| Hardware ceiling | RTX 3050 Laptop, 4 GB, model already 50/50 CPU/GPU | `nvidia-smi`, `ollama ps` |

### 1a. Measured pilot (2026-11-21, Step 11) — 118 documents

What was actually run: 7 PDFs per leaf folder planned (212), fetched 210 with 2 same-batch name
duplicates skipped; 91 staged files were byte-identical to already-indexed documents and were
removed, leaving **119**; one of those (a 21-page NSO report) reproducibly crashes PyMuPDF's
ONNX table detector with a native access violation on page 6, so the throwaway build covered
**118 documents / 2,275 pages / 8,910 chunks**. Nothing here touched `data/corpus` or
`index/`; the live index still reported 97 documents afterwards.

| Stage | Measured | Per document | Projection used in §2 | Verdict |
|---|---|---|---|---|
| Drive download | 210 files, 257.1 MB in 426 s (29.6 files/min, 1.17 MB/s) | 2.0 s | not projected | — |
| Parse | 2,660 s for 2,275 pages (1.17 s/page, 51.4 pages/min) | 22.5 s | 1.66 s/page, 57 h at 20k | **matches** the 51.3 pages/min baseline |
| Embed | 584.6 s for 8,910 chunks (15.2 chunks/s) | 5.0 s | 0.0999 s/chunk, 18.5 h at 20k | **faster**: 0.0656 s/chunk |
| Bibliography | 82.5 s for 12 re-extracted documents (6.9 s/doc, Ollama warm) | 6.9 s | 14.3 s/doc, 79 h at 20k | **faster**; the 118-document run itself is invalid (Ollama was down, see below) |
| Whole build | 3,528 s wall for 118 documents (add-batch 2,187 s + resumed build 1,341 s) | **29.9 s** | pilot 2.3 h for 200 | 200 docs at this rate = **1.7 h** |

Consequences for §2:

- Parse and embed confirm the model within a few percent. At 29.9 s/document, 20k documents is
  **~166 h ≈ 7 days** of continuous compute, against the 194 h / 8 days projected — the plan's
  number was conservative, which is the safe direction.
- The pilot's pages and bytes per document are **larger** than the corpus average (19.3 pages and
  1.76 MB on the 119 staged files versus 8.77 pages and 0.505 MB), so 20k at this mix means more pages, not fewer.
  Per-page rates, not per-document rates, are what §2 should be re-derived from once the real
  mix is known (175,400 projected pages at 51.4 pages/min = 57 h, unchanged).
- **The bibliography measurement above is a 12-document sample, not the wave:** the 118-document
  build ran while Ollama was down, so all 118 records carry `ConnectError`, and its 265 s is a
  failed-call timing, not an LLM timing. The 6.9 s/doc sample was taken afterwards with Ollama
  up. A full-wave bibliography timing is therefore **not measured**.
- Document contexts are not a separate stage in `ingest.pipeline` any more; `chunk` produced
  8,910 chunks in the same build with no LLM calls of its own, so the 7 s/document context line in
  §2 is legacy and should be dropped when the plan is next revised.

---

## 2. Size at 20,000 documents (projected)

Assumes the same mix as today: 8.77 pages/document and 0.505 MB/document.

| Quantity | Projection | How |
|---|---|---|
| Pages | ~175,400 | 20,000 × 8.77 |
| Originals | ~10 GB | 20,000 × 0.505 MB (the real set may be much larger; ask) |
| Chunks | ~665,000 | 175,400 × 3.79 |
| `pages.json` | ~500 MB | 2,833 B/page measured |
| `chunks.jsonl` | ~1.4 GB | 7,800 B/page measured |
| `index/parsed/` | ~2.7 GB | 15,300 B/page measured |
| `index/lancedb/` | ~3.7 GB | 5,579 B/chunk measured |
| Index total | **~8.3 GB** | sum above |
| Backup | ~8.3 GB per backup | `backup` copies the index |
| Parse time | **~57 h** one-time | 175,400 / 51.3 pages/min |
| Embed time | **~18.5 h** one-time, one CPU process | 665,000 × 0.0999 s |
| Document contexts | **~39 h** one-time | 20,000 × 7 s |
| Bibliography | **~79 h** one-time | 20,000 × 14.3 s |

**The surprise in that table: the 4B model calls cost more than parsing.** Bibliography and
document context together are ~118 h, about twice the parse. That must be a decision (see
§7), not an accident of running `build` and walking away.

Disk is not the constraint (717 GB free). Continuous compute is: at today's design 20k
documents is **~194 h ≈ 8 days** of uninterrupted work.

---

## 3. Waves

Ten waves of 2,000 documents, after a 200-document pilot. A wave is the unit that gets
measured, backed up and accepted; nothing starts the next wave until the gates in §5 pass.

| Wave | Documents | Cumulative | Compute per wave (projected) |
|---|---|---|---|
| 0 (pilot) | 200 | 200 | ~2.3 h (parse 1 h, embed 0.2 h, contexts 0.4 h, bibliography 0.8 h) |
| 1–9 | 2,000 each | 2,200–18,200 | ~19 h each |
| 10 | 1,800 | 20,000 | ~17 h |

Why a 200-document pilot first: it is the cheapest point at which the per-page rates,
`pages.json` load time, RSS and BM25 latency can be re-measured at 2× the current corpus,
before 19,800 files are committed to the same design. If a projection is wrong by 2× we
learn it in an afternoon, not after a week.

Wave order should be **topic-coherent** (e.g. flood reports, then glacier reports), not
alphabetical, so each wave's new gold questions can be written from documents a person can
read in one sitting.

---

## 4. What happens to the files (rule 5, rule 11)

`data/raw/` is owner-only and the corpus is a hardlink mirror of it, so adding files is two
steps:

1. **Owner stages the batch** at `data/raw/incoming-wave-NN/<same relative folder>/...`.
   The 20k set must arrive in batches; agents do not download or move owner originals.
2. **A new `add-batch` command** (to be built and approved in the step) walks the staged
   folder, hashes each file, refuses a name that already exists anywhere in `data/corpus`,
   refuses a content hash already in the manifest, hardlinks into `data/corpus/` with the
   same relative path (copy only if `os.link` fails), and records the SHA-256 and Drive/
   source row in `logs/`. `ingest/drive.py::mirror()` already implements the hardlink
   (with a copy fallback), but it silently returns "already there" when the target exists,
   so `add-batch` must refuse a name collision before calling it rather than inherit that
   quiet overwrite. The command reuses `mirror()` instead of adding a second hardlinker.

Word documents are converted once with the pinned LibreOffice into
`<original name>.pdf`, at staging time, and the converted file is what enters the corpus
(rule 11). Re-running the converter silently is forbidden; the converter version goes in
`STATUS.md` before wave 0.

No new dependency is needed for any of this.

---

## 5. Per-wave gates (the important part)

A wave is accepted only if **all** of these hold. They are run in this order; a failure
stops the next wave.

### 5.1 Ingestion integrity (mechanical, no thresholds to argue about)

```
.venv\Scripts\python.exe -m ingest.pipeline build          # resumable
.venv\Scripts\python.exe -m ingest.pipeline status --report
```

- 100% of the corpus in `embedded`, 0 `failed`, 0 `pending`.
- Every file has a SHA-256; no file without one.
- Duplicates are **listed**, never deleted. Review the list: an exact content duplicate is
  recorded as `duplicate` and skipped (not embedded, not removed), a near-duplicate is kept
  and flagged.
- Unreadable pages reported against D-020's 1–2% band. The current corpus is already 2.2%,
  so this is a **monitoring** number, not a new gate.

### 5.2 Frozen canary retrieval (the regression gate that already exists)

The 55-question set does not change when documents are added. Re-run retrieval over it:

```
.venv\Scripts\python.exe eval\run_retrieval.py --label wave-NN-canary
:: writes eval/runs/<today>-wave-NN-canary/retrieval.jsonl
.venv\Scripts\python.exe eval\gate.py ^
    --current eval\runs\<today>-wave-NN-canary ^
    --baseline eval\runs\2026-11-20-step9-retry-guard ^
    --start eval\runs\2026-11-20-step9-retry-guard
```

`gate.py` reads `retrieval.jsonl` as well as `run.jsonl`, so a retrieval-only run is a
valid input; it refuses to compare runs whose question sets differ.

Pass conditions, taken from `eval/gate.py` rather than invented here:

- recall@5 **≥ 44/48**: no more than one question below the accepted 45/48.
- MRR no lower than one question's worth (0.021) against 0.826.
- No unexplained pass-to-fail question.

A retrieval-only run carries no answers, so `gate.py` prints `[SKIP] rule 4` for
not-found (a) instead of passing it. That metric is therefore checked on the generation
sample in §5.4, not here; the SKIP is expected and must not be read as a pass.

This is the check that catches "20k documents made the old answers harder to find". It is
expected to move: today's 45/48 is measured on 97 documents, and 200× the pages means more
near-miss competitors. A two-question drop is a **stop-and-fix**, not a new baseline.

### 5.3 New-wave retrieval (needs new gold data first)

There is no honest quality check for new documents without questions whose gold page is in
them. Before wave NN is ingested:

- Write **25 new dev questions** whose answers are in that wave's documents, with gold
  file, page, quote and numbers, in the `eval/questions.jsonl` format. New dev questions
  follow the process in `EVAL.md` and need owner approval; they are not added by the agent
  unilaterally.
- Score them with the same `run_retrieval.py` on a wave-local question file.

Proposed acceptance for a new wave (owner to confirm, since this is a target and not a
measured baseline): **recall@5 ≥ 20/25**. Below that, the wave is not usable through the
current page-BM25 retriever and §6 is triggered before the next wave.

25 questions per wave is 275 across the whole corpus, and that is the hidden human cost of
this plan. Ten questions per wave halves it but makes the 20/25 threshold a 8/10 read:
cheaper, weaker, and easier to pass by luck. The plan keeps 25 and says so.

### 5.4 Answer quality sample (small, cheap, catching the failure a corpus can cause)

Run 10 questions from the wave's new set plus 5 canary questions through the real pipeline:

```
.venv\Scripts\python.exe eval\run_generation.py --label wave-NN-sample ^
    --questions <wave question file> --only <15 ids> --resume
```

The cache is off by default in that runner. There is no pass threshold at 15 questions — the
canvas is too small — so this is a **read, record and compare**: statuses, citation,
numeric, and any prompt that Ollama truncated. Three events stop a wave:

- any generated prompt is truncated (`prompt_tokens` at the context limit);
- not-found (a) is lower than the accepted run (it may not drop at all); or
- a canary answer changes status for a question whose gold page was in the top 5.

### 5.5 Not-found re-check (D-027)

```
.venv\Scripts\python.exe scripts\recheck-not-found.py
```

A document set 200× larger can make a question that was correctly unanswerable become
answerable. Every question whose re-check now finds the answer is reported to the owner;
replacing a not-found question is an owner decision (D-027), never an agent edit.

### 5.6 Record and back up

`ingest.pipeline backup --out backups/wave-NN`, then record in `STATUS.md`: documents,
pages, chunks, index bytes, parse/embed wall time, canary recall@5/MRR, new-wave recall@5,
unreadable share, BM25 p50/p95, RSS, and the gate output. A wave with no recorded numbers
did not pass.

---

## 6. When the retriever has to change (scale triggers)

Page-level BM25 is the shipped retriever because Step 5 measured it beat hybrid at 97
documents (D-056/D-057). That result does **not** transfer to 20k. Change nothing on a
hunch; change on one of these measured triggers:

| Trigger | Action | Approval |
|---|---|---|
| Canary recall@5 falls ≥ 2 questions, or wave recall@5 < 20/25 | Add a CPU cross-encoder reranker over a top-50 candidate pool (D-054 keeps VRAM for the LLM) | New experiment, own gate run |
| `pages.json` load > 3 s, RSS > 2 GB, or BM25 top-5 p95 > 300 ms | Move lexical search to SQLite FTS5 or LanceDB full-text with a top-100 candidate stage | New step task |
| > 3% of a wave is duplicate/near-duplicate | Review before embedding; improve dedupe, never delete evidence | Report to owner |
| Any generation prompt truncated | Passage budget change (fewer/shorter passages), not a bigger `num_ctx` (the GPU has no room) | Gate run |
| Citation rate falls | Inspect whether the new pages are OCR'd; do not loosen the verifier | Report |

The reranker is the change I expect to need first, and the pilot is designed to say so at
200 documents rather than after 20,000.

**Measured 2026-11-21: the sharding trigger arrives around 9,000 documents, not 20,000.**
Loading `index/pages.json` and building its page BM25 on the real 851-page index, then on a
synthetic 1,702-page copy of it (every page duplicated, token counts unchanged), gives
linear growth in both memory and query time:

| | 851 pages | 1,702 pages |
|---|---|---|
| BM25 top-5 latency | p50 2.54 ms, p95 3.18 ms | p50 5.15 ms, p95 7.16 ms |
| RSS after BM25 | 73 MB | 95 MB |

Doubling pages doubles the latency, so the section's own **p95 > 300 ms** trigger is reached
at about **80,000 pages (~9,100 documents)** and **2 GB RSS** at about **81,000 pages
(~9,200 documents)** - during wave 4 or 5, not near the end. That is a linear extrapolation
from two measured points, not a 20k measurement, but it is enough to plan the SQLite
FTS5-or-shard step *before* wave 4 rather than after the corpus is built.

---

## 7. Decisions the owner has to make before wave 0

1. **Bibliography and document context at 20k.** ~118 h of 4B model calls for metadata
   that only the UI and the rail need. Options:
   - (a) run both for every document (~118 h added to ~75 h of parse+embed);
   - (b) run **document context only** (~39 h) because chunk quality depends on it;
   - (c) run bibliography **lazily** for the documents an answer actually cites, and
     document context only for documents that enter the index (recommended: keeps the
     reference rail useful without paying 79 h up front).
   This plan assumes (c) until the owner decides.
2. **Where the 20,000 PDFs come from and their real size.** The 0.5 MB/document average is
   this corpus's; a different set can be 4× larger.
3. **The 25 gold questions per wave.** Writing them is the real bottleneck and the only
   part that cannot be automated honestly. The agent can propose them from the documents;
   the owner approves them through the `EVAL.md` process.
4. **Compute window.** 8 days of continuous work needs the machine awake; the earlier
   eval run was corrupted by the system sleeping. Wave jobs are resumable, so stopping is
   safe, but timing numbers only count uninterrupted runs.
5. **One offline proof with the network off** after the pilot and after the last wave
   (needs an elevated shell — the open Step 8 box is the same requirement).

---

## 8. What gets built in the step (small, testable)

1. `ingest/pipeline.py add-batch --from <staged folder> --wave NN` — hash, collide, hardlink,
   record; refuses a file that is inside `data/corpus` (reuses `ingest/drive.py::mirror`).
   Unit cases
   mirror the existing add-document cases: duplicate name, duplicate content, hardlink
   fallback, resumable rerun.
2. `--shard`/grouping for the lexical index if the pilot's numbers demand it (not built
   pre-emptively; the trigger table decides).
3. `scripts/wave-report.py` — writes the §5.6 row from the manifest, the index files and a
   retrieval run, so a wave report cannot be hand-typed from memory.
4. A wave section added to `RUNBOOK.md`, after the owner has read the text (the runbook is
   not in the protected list, but it is the document the owner follows by hand).

No changes to `data/raw`, the corpus, the eval set, the gold answers, or `DECISIONS.md`.

---

## 9. Schedule and what I would measure first

```
wave 0 (200 docs)  ->  re-measure every rate in §1 at 2x corpus
                   ->  write 25 pilot gold questions
                   ->  canary gate + pilot gate + generation sample + not-found recheck
                   ->  backup, record, offline proof
wave 1 (2,000)     ->  same checklist; compare rates with wave 0
...
wave 10 (1,800)    ->  final gate, final backup, final offline proof
```

The pilot is also the answer to "will 20k work at all": if `pages.json` load time or BM25
latency grows super-linearly at 2×, the sharding decision is made there, cheaply.

## 10. Risks, stated plainly

- **Retrieval quality is the risk, not disk or the LLM.** Today's 45/48 is likely to fall;
  the plan stops a wave when it falls by two, rather than resetting the baseline.
- **~8 days of compute** is the honest cost at the current design, dominated by model
  calls for metadata. Option (c) in §7 cuts it to ~114 h.
- **The 4 GB GPU cannot grow.** Adding documents must not add prompt tokens; more context
  per answer is not available.
- **`eval/questions.jsonl` is frozen.** New gold questions go through `EVAL.md` and owner
  approval; no agent may append them unilaterally (rule 13).
- **Not-found questions will age.** A larger corpus makes some of them answerable; D-027
  says the owner replaces them, and this plan re-checks them every wave instead of
  discovering it at the end.

## Approval needed

A new step (say `step 10`) with a start line in `APPROVALS.md`, the owner's staging path
for wave 0, and the §7 decisions. Until then this document is the only artifact; nothing
under `data/`, `index/` or `eval/` was touched.
