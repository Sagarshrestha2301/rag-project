# Tracker — where this project stands and what is yours to decide

One page, checked against the repository on **2026-11-19**: `git log`, `git tag`,
`APPROVALS.md`, `STATUS.md`, `DECISIONS.md`, `EVAL.md` and the DoD boxes in `steps/`. If
this page and those files disagree, the files win — this is a summary.

Approvals live **only** in `APPROVALS.md` plus your `step-NN-approved` tags. Nothing in
this file is an approval.

---

## 1. Where you are

```
step 00  environment      DONE     10/10 boxes, tagged
step 01  eval set         DONE      6/6  boxes, tagged (55 questions: 45 dev + 10 held-out)
step 02  LLM benchmark    DONE      5/5  boxes, tagged (qwen3.5 4B won: 23/30)
step 03  parsing          TAGGED    4/7  boxes (97 docs, 851 pages, 242 tables); 3 open:
                                    your page review, your table review, and the Word-file
                                    box a PDF-only corpus cannot meet
step 04  chunk + embed    DONE      5/5  boxes, tagged (3,226 chunks with contexts)
step 05  hybrid retrieval DONE      7/7  boxes, tagged (hybrid rejected on measurement; BM25 kept)
step 06  generation       DONE      7/7  boxes - completion line recorded, tag still yours
step 07  web UI           BUILT     7/8  boxes - only the Wi-Fi-off session left, and it
                                    needs an elevated prompt
step 08  full ingestion   BUILT     9/10 boxes - the full ingest is measured; only the
                                    offline proof is left (elevated) and the 100k-page
                                    item is D-063
step 09  tuning + docs    RUNNING   1/5  boxes - failure list and runbook done; every
                                    experiment needs its own approval before it can start
```

`git tag` lists **step-00-approved … step-05-approved**. Steps 06-09 have start approvals
in `APPROVALS.md`; step 06 also has its completion line. Only you create tags.

## 2. What actually works today

One answer path, and it is the one the eval measures:

```powershell
# the shipped UI: streams generation.answer (router, condense, gate, verifier, cache)
.\scripts\open-chat.ps1 -Start                    # then http://127.0.0.1:8000

# the same pipeline from a terminal, with the JSON record
.venv\Scripts\python.exe -m generation.answer "Compare the Bagmati and East-Rapti peak floods." --json

# index from the corpus: resumable, parses only new or changed documents
.venv\Scripts\python.exe -m ingest.pipeline build
.venv\Scripts\python.exe -m ingest.pipeline status --report
```

- **The UI keeps no prompt of its own.** `ui/pipeline.py` calls `generation.answer`, so the
  five answer states (`streaming`, `verified`, `not_found`, `unverified`, `error`), the
  numeric citation chips and the unreadable-page warning show the measured pipeline's
  output (D-061). Verified 2026-11-19: **13 citation links across 10 answers** open the cited
  page and carry the quoted sentence, and a real headless Chrome shows the not-found warning
  with per-document counts matching `index/pages.json`.
- **`ingest/pipeline.py`** runs scan → parse → assemble → chunk → embed from one manifest
  (`index/manifest.sqlite`), resumes per document after a kill, flags exact and 80%-shared
  duplicates instead of indexing them twice, keeps `backup`/`restore`, and rebuilds
  `index/pages.json` and `index/chunks.jsonl` **byte for byte**.
- **`scripts/add-document.ps1 -Path <pdf>`** adds a document in one command and ingests only
  that document; `scripts/recheck-not-found.py` re-checks every unanswerable question after a
  corpus change.
- **`eval/gate.py`** enforces `EVAL.md`'s regression gate (two baselines, per-question diff,
  non-zero exit when a rule breaks — `RUNNING.md` §3c).
- **`scripts/offline-generation-proof.ps1`** proves the pipeline runs with the network
  blocked and refuses to run the eval until `scripts/offline-check.py` proves the block.

Measured, not claimed (2026-11-19 unless a row says otherwise):

| Thing | Number |
|---|---|
| Corpus | **97 PDFs, 851 pages**, 8 documents with unreadable pages (19 pages), 86 pages OCR'd |
| Chunks | **3,226** (2,958 text + 268 table) from 95 documents, every chunk carrying a document context |
| Index | **40 MB** (41,969,013 bytes incl. LanceDB); load 0.04 s; BM25 top-5 2–140 ms; **67 MiB** peak RSS for a process that loads and searches |
| Rebuild | `pages.json` `395c5a2b…`, `parsed/pages.jsonl` `f7e82daf…`, `chunks.jsonl` `1208cb59…` — identical before and after the Step 8 pipeline; a second run with nothing changed 1.6 s |
| Retrieval (55 questions) | recall@5 **45/48**, recall@10 46/48, MRR **0.826** (dev 37/39, held-out 8/9) |
| Full generation run | **33/55 passed**; citation 31/48, numeric 34/43, not-found (a) 3/6, (b) 45/48; p50 **16.5 s**, p95 **46.4 s** |
| Held-out milestone | **5/10 passed**, recall@5 8/9, MRR 0.806 — both gates pass |
| Eval drift since 2026-11-18 | **zero** — 0 status changes, 0 answer changes over all 55 questions |
| Backup / restore | 40 MB snapshot restores byte-identically, 3,226 dense rows, same top BM25 page |
| Offline proof | step 06 **PASS** 2026-11-17 (6 firewall rules + refused probes, run identical to online); steps 07 and 08 **not run** — they need an elevated prompt |
| Unit suites | 94 generation cases, 11 pipeline, 8 UI server, 6 UI pipeline, 7 corpus, 6 chunk suites pass; `eval/test_scorer.py` is stale (its fixtures still assume 30 questions) |

## 3. Open decisions only you can sign

| # | Asks | My recommendation | Blocks |
|---|---|---|---|
| **D-063** | Step 8 is judged on the pipeline at 97 documents / 851 pages; reaching 100k pages is a separate corpus-and-hardware decision | Approve — the 1,000-page dry run cannot be run on an 851-page corpus, and 100k is ~32 h of parsing at the measured 51.3 pages/min | the Step 08 tag |
| **D-064** | Parsed output is per-document shards keyed by SHA-256, assembled in corpus order | Approve — already built, and the rebuild is byte-identical | nothing |
| **D-065** | Duplicates are flagged (exact SHA-256 or ≥80% shared pages) and never deleted or indexed | Approve — already built and tested | nothing |
| **D-060** | Approved 2026-11-17 but **not built**: a prose refusal counts when its first sentence negates the question | Build it — `verify.said_not_found` still compares only the first line, so not-found (a) stays 3/6 | not-found (a) |
| — | `EVAL.md`'s one-question table still says dev is 20 questions at 5 points (it is 45, so 2.2) | your edit — protected file | nothing |

The six UI choices in `ui/SPEC.md` §12 became D-061/D-062 and are approved and built.

## 4. Blocked or deviating, stated plainly

1. **Step 3's Word-file box cannot be met as written**: its DoD asks for five `.docx`
   conversions and the corpus holds PDFs only. The step is tagged, so this stands as an
   accepted deviation; the page and table reviews are still open boxes in the step file.
2. **Step 8's 100k-page items cannot be run here** (97 documents, 851 pages). The pipeline
   half is built and measured; D-063 asks you to accept that split.
3. **Not-found (a) is 3/6.** q020, q021 and q055 were refused in prose instead of the exact
   `Not found in the indexed documents.` line, so the scorer counts them as answers. D-060
   is the approved fix and it is **not built**.
4. **Citation 31/48** is under the strict rule you chose (D-041) and stays that way: the
   failures are paraphrase and extra pages, not invented sources.
5. **The offline proofs for Steps 07 and 08 need an elevated prompt.** This shell cannot
   create firewall rules (`Access is denied`, Windows System Error 5); the scripts are
   written and parse-checked, and Step 06's identical script passed.
6. **19 of 851 pages (2.2%) stay unreadable after OCR**, above the 1–2% band D-020 uses to
   decide. OCR is already applied (86 pages), so the remaining action is a decision.

## 5. What to do, in this order

1. **Step 6:** `git tag step-06-approved` (the completion line is already in `APPROVALS.md`).
2. **Offline proofs, elevated prompt:** `scripts\offline-ui-proof.ps1` for Step 07 and
   `scripts\offline-generation-proof.ps1` for Step 08.
3. **Decide D-063 / D-064 / D-065** (one line each), then tag `step-07-approved` and
   `step-08-approved`.
4. **Confirm the not-found questions:** `reports/not-found-recheck.md` lists all 7 with the
   best pages and the pages containing every term, and leaves the verdict to you (D-027).
5. **Build D-060** (approved): the test suite it asks for plus one 55-question re-run; it is
   the cheapest measured gain on the board (not-found (a) 3/6 → expected 6/6).
6. **Step 09:** read `reports/failures.md` and approve or reject one experiment (HyDE,
   multi-query, RAPTOR, fine-tuning) — or stop at the docs. Nothing was tried without you.
7. **Step 3:** tick or reword the two review boxes (only you may edit step text).

## 6. Honest risks, in the order they will bite

1. **Latency is 16.5 s median, 46.4 s at p95** — inside N2's 20 s typical target at the
   median, over it at p95 (the table route with one retry). The 4B model is what keeps it
   that low; a larger one would spill to RAM on this card.
2. **Twelve of the 22 failures are citations**, not retrieval: the answer quotes a page it
   does not cite, or paraphrases past the verifier. That is where the remaining accuracy is.
3. **The gate only protects you if it is run.** It is a command, not a hook.
4. **`data/corpus` is read-only and the index is derived**; a corpus change re-runs ingestion
   (one document is cheap, a full rebuild is ~24 min of parsing), and a long-lived process
   holds its own index in memory, so restart the UI after adding documents.
5. **2.2% of pages have no readable text**, so some questions can only be answered "not
   found" with a warning — by design, not by accident.
6. **100k pages is not proven.** The manifest and per-document resume are built for it; the
   acquisition, the ~32 h run and the disk budget are not.

---

## Handy commands

```powershell
git status                                        # must be clean before any agent session
git tag                                           # what you have attested
.venv\Scripts\python.exe -m ingest.pipeline status --report
.venv\Scripts\python.exe -m ingest.pipeline backup --out backups\2026-11-19
.venv\Scripts\python.exe ingest\test_pipeline.py   # 11 cases: resume, duplicates, backup
.venv\Scripts\python.exe eval\gate.py --current eval\runs\2026-11-19-step8-full `
  --baseline eval\runs\2026-11-18-step6-after-ui --start eval\runs\2026-11-18-step6-after-ui
.venv\Scripts\python.exe eval\gate.py --milestone --current eval\runs\2026-11-19-step8-full `
  --baseline eval\runs\2026-11-18-step6-after-ui --start eval\runs\2026-11-18-step6-after-ui
.venv\Scripts\python.exe scripts\offline-check.py  # exit 0 = external network refused
curl.exe -s http://127.0.0.1:11434/api/tags        # is Ollama serving qwen3.5:4b
```

Restarting the chat UI: kill the process **listening** on 8000, not the `.venv`
wrapper — the wrapper is a shim and the real listener is its child
(`netstat -ano | findstr :8000`).
