# Tracker — where this project stands and what is yours to decide

One page, checked against the repository on **2026-11-21**: `git log`, `git tag`,
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
step 07  web UI           DONE      8/8  boxes - the Wi-Fi-off session passed on the
                                    owner's own run (reported 2026-11-20)
step 08  full ingestion   BUILT     10/10 boxes - the offline proof passed on the owner's
                                    run (reported 2026-11-21); only the 100k-page scope
                                    decision (D-063) is open before the tag
step 09  tuning + docs    SIGNED OFF 5/5 boxes - six experiments measured; two kept
                                    (D-071, D-072), three rejected (D-068, D-070, D-073),
                                    RUNBOOK.md written and followed; owner approval
                                    2026-11-20, tags are yours
step 10  batch ingestion  BUILT     5/7  boxes - `add-batch` with an all-or-nothing
                                    pre-flight, 19/19 pipeline cases; the pilot batch
                                    wall time is now measured (step 11); open: your review
step 11  pilot wave       RAN       6/6  boxes - 210 real PDFs fetched, 118 built into a
                                    throwaway index in 3,528 s (29.9 s/document,
                                    51.4 pages/min parse); live index still 97 docs.
                                    One PDF crashes PyMuPDF's table detector natively
                                    (D-075 parse isolation proposed and approved by
                                    the owner); bibliography re-timed with Ollama
                                    up: 866 s / 106 docs = 8.2 s/doc, 1 doc left
                                    in error
step 12  parse isolation  BUILT     4/6  boxes - each document parses in its own
                                    `parse-one` subprocess; pilot rerun 118
                                    parsed / 1 failed / 2,275 pages in 48 m 03 s,
                                    22/22 pipeline cases. Open: `add-batch` exits
                                    1 on the crashed file (box says 0), and
                                    `summary.json` timing fields; no
                                    `APPROVALS.md` line yet
```

`git tag` lists **step-00-approved … step-05-approved**. Steps 06-11 have start approvals
in `APPROVALS.md`; step 06 and step 09 also have completion lines. Only you create tags.

## 2. What actually works today

One answer path, and it is the one the eval measures:

```powershell
# the procedure to operate it, start to restore: RUNBOOK.md (followed step by step 2026-11-20)
# the reference with the detail: RUNNING.md

# the shipped UI: streams generation.answer (router, condense, gate, verifier, cache)
.\scripts\open-chat.ps1 -Start                    # then http://127.0.0.1:8000

# the same pipeline from a terminal, with the JSON record
.venv\Scripts\python.exe -m generation.answer "Compare the Bagmati and East-Rapti peak floods." --json

# index from the corpus: resumable, parses only new or changed documents
.venv\Scripts\python.exe -m ingest.pipeline build
.venv\Scripts\python.exe -m ingest.pipeline status --report
```

- **The UI keeps no prompt of its own.** `ui/pipeline.py` calls `generation.answer`, so the
  five answer states, the numeric citation chips and the unreadable-page warning show the
  measured pipeline's output (D-061). Verified 2026-11-19: **13 citation links across 10
  answers** open the cited page and carry the quoted sentence, and a real headless Chrome
  shows the not-found warning with counts matching `index/pages.json`.
- **`ingest/pipeline.py`** runs scan → parse → assemble → bibliography → chunk → embed from
  one manifest (`index/manifest.sqlite`), resumes per document after a kill, flags exact and
  80%-shared duplicates instead of indexing them twice, keeps `backup`/`restore`, and
  rebuilds `index/pages.json` and `index/chunks.jsonl` **byte for byte**.
- **`scripts/add-document.ps1 -Path <pdf>`** adds a document in one command and ingests only
  that document; `scripts/recheck-not-found.py` re-checks every unanswerable question after a
  corpus change. Both are refusals-tested and in `RUNBOOK.md` §3.
- **`python -m ingest.pipeline add-batch --from <staged folder> --wave NN`** brings a whole
  folder of PDFs in at once: it checks every file before placing any, refuses the batch on a
  bad name or a non-PDF, skips files whose bytes are already indexed (with the reason), then
  runs the build. `RUNBOOK.md` §3.1a; 19/19 pipeline cases.
- **`eval/gate.py`** enforces `EVAL.md`'s regression gate (two baselines, per-question diff,
  non-zero exit when a rule breaks — `RUNNING.md` §3c). It is what rejected D-060.
- **`scripts/offline-generation-proof.ps1`** proves the pipeline runs with the network
  blocked and refuses to run the eval until `scripts/offline-check.py` proves the block.

Measured, not claimed (2026-11-19 unless a row says otherwise):

| Thing | Number |
|---|---|
| Corpus | **97 PDFs, 851 pages**, 8 documents with unreadable pages (19 pages), 86 pages OCR'd |
| Chunks | **3,226** (2,958 text + 268 table) from 95 documents, every chunk carrying a document context |
| Index | **40 MB** (41,969,013 bytes incl. LanceDB); load 0.04 s; BM25 top-5 2–140 ms; **67 MiB** peak RSS for a process that loads and searches |
| Rebuild | `pages.json` `395c5a2b…`, `parsed/pages.jsonl` `f7e82daf…`, `chunks.jsonl` `1208cb59…` — identical before and after the Step 8 pipeline; a build with nothing changed **6.9 s** (measured 2026-11-20) |
| Retrieval (55 questions) | recall@5 **45/48**, recall@10 46/48, MRR **0.826** (dev 37/39, held-out 8/9) |
| **Last accepted answer run** (2026-11-20, prompt `s6-3` + retry guard) | **37/55 passed**; citation 36/48, numeric 37/43, not-found (a) 3/6, (b) 46/48; p50 **11.4 s**, p95 **28.9 s** |
| Held-out milestone | **5/10 passed**, recall@5 8/9, MRR 0.806 — both gates pass |
| Experiments tried 2026-11-20 | prose refusals **rejected** (D-068); page-level table pass **rejected** (D-070); per-sentence citation prompt **kept** (D-071); retry guard **kept** (**37/55**, q047 fixed, D-072); table rows in the passage **rejected** (overflows the context, D-073) |
| Backup / restore | 40 MB snapshot restores byte-identically, 3,226 dense rows, same top BM25 page (re-run 2026-11-20) |
| Offline proof | step 06 **PASS** 2026-11-17 (6 firewall rules + refused probes, run identical to online); steps 07 and 08 **PASS on the owner's own run** (reported 2026-11-20 and 2026-11-21). No output file from those two runs was supplied to the repository |
| Unit suites | 26 verifier, 21 cache, 11 condense, 9 gate, 7 prompt, 16 router, 10 think, **19 ingest pipeline**, 8 UI server, 7 UI pipeline, 7 corpus, 6 chunk suites pass; `eval/test_scorer.py` was rebuilt 2026-11-20 and passes |

## 3. Open decisions only you can sign

| # | Asks | My recommendation | Blocks |
|---|---|---|---|
| **D-063** | Step 8 is judged on the pipeline at 97 documents / 851 pages; reaching 100k pages is a separate corpus-and-hardware decision | Approve — the 1,000-page dry run cannot be run on an 851-page corpus, and 100k is ~32 h of parsing at the measured 51.3 pages/min | the Step 08 tag |
| **D-064** | Parsed output is per-document shards keyed by SHA-256, assembled in corpus order | Approve — already built, and the rebuild is byte-identical | nothing |
| **D-065** | Duplicates are flagged (exact SHA-256 or ≥80% shared pages) and never deleted or indexed | Approve — already built and tested | nothing |
| **D-068** | D-060 (prose refusals) is measured and **not kept**: +3 passed and nf(a) 6/6, but nf(b) 37/39 → 35/39 and two answerable questions lost | Approve the rejection; re-propose it after table retrieval, when it costs nothing | closing D-060 |
| **D-069** | Table retrieval was the recommended next experiment | **Answered by measurement**: rejected, see D-070 | nothing |
| **D-070** | The table pass adds no gold page on this set and costs one dev question | Approve the rejection — the real gap is table *content* in a passage, which changes what a quotable passage is | nothing |
| **D-071** | The prompt now makes each sentence quote its own evidence (`s6-3`) and it is **kept** | Approve — citation 31/48 → 35/48, numeric 34/43 → 36/43, held-out 5/10 → 7/10, no metric down | the new baseline |
| **D-072** | A retry drops the failed answer when the first call used >85% of `num_ctx`, and it is **kept** | Approve — 37/55, q047 answered correctly, citation 35 → 36, numeric 36 → 37 | the current baseline |
| **D-073** | Appending a page's table rows to its passage is **rejected**: the table prompt is already ~4,100 tokens, so it truncates and the model refuses | Approve — and design the next table change as rows *instead of* the prose window | nothing |
| **D-066** | Per-document reference extracted from the header pages (built, 78 of 96 documents name the work) | Approve — measured, and the rail no longer shows a storing key | nothing |
| **D-067** | Sentence-level entailment check (measure only; 34 UNSUPPORTED / 3 PARTIAL of 92 sentences) | Pick one: wire it in as a warning, keep it as a periodic report, or drop it | nothing |
| — | `EVAL.md`'s one-question table still says dev is 20 questions at 5 points (it is 45, so 2.2) | your edit — protected file | nothing |

The six UI choices in `ui/SPEC.md` §12 became D-061/D-062 and are approved and built.

## 4. Blocked or deviating, stated plainly

1. **Step 3's Word-file box cannot be met as written**: its DoD asks for five `.docx`
   conversions and the corpus holds PDFs only. The step is tagged, so this stands as an
   accepted deviation; the page and table reviews are still open boxes in the step file.
2. **Step 8's 100k-page items cannot be run here** (97 documents, 851 pages). The pipeline
   half is built and measured; D-063 asks you to accept that split.
3. **Not-found (a) is 3/6 and stays there for now.** q020, q021 and q055 refuse in prose
   instead of the exact `Not found in the indexed documents.` line. D-060 was the fix and it
   was measured on 2026-11-20: it reaches 6/6, but only by also refusing two answerable
   questions, so the gate rejected it (D-068). The real cause is that the Das Table 2 rows
   are not retrieved at all (D-069).
4. **Citation 31/48** is under the strict rule you chose (D-041) and stays that way: the
   failures are paraphrase and extra pages, not invented sources.
5. **The offline proofs for Steps 07 and 08 were run by the owner, not by an agent.** Both
   boxes are ticked on the owner's report (2026-11-20 and 2026-11-21); no console output or
   artifact from those runs is in `artifacts/`, so the repository cannot show them. Step 06's
   identical script is the only offline run with recorded output. Note also that the six
   `step7-offline-proof` firewall rules are still enabled; removing them needs an elevated
   shell (`Access is denied`).
6. **19 of 851 pages (2.2%) stay unreadable after OCR**, above the 1–2% band D-020 uses to
   decide. OCR is already applied (86 pages), so the remaining action is a decision.

## 5. What to do, in this order

1. **Tags:** `step-06-approved` (completion line already recorded), then
   `step-07-approved` and `step-08-approved` now that their offline boxes are ticked.
2. **Decide D-063 / D-064 / D-065** (one line each); D-063 is the only thing between
   Step 08 and its completion line.
3. **Step 10:** stage the pilot and run `add-batch`, then review one refusal and one landed
   batch; Step 11 waits on a network the sandbox does not have.
4. **Confirm the not-found questions:** `reports/not-found-recheck.md` lists all 7 with the
   best pages and the pages containing every term, and leaves the verdict to you (D-027).
5. **D-068:** accept that D-060 is rejected, or tell me to take the not-found (b) drop for
   the (a) 6/6 gain. The numbers are in `DECISIONS.md` and the 2026-11-20 row of `EVAL.md`.
6. **D-070 / D-071 / D-072 / D-073:** accept the four experiment outcomes (Step 09 is
   already signed off). The ranked next experiments are in `reports/next-experiments.md`; the first one
   is a one-rule change that should gain q020, q021 and q055 (refuse in exact words, count
   it as a refusal).
7. **Step 3:** tick or reword the two review boxes (only you may edit step text).

## 6. Honest risks, in the order they will bite

1. **Latency is 13.4 s median, 27.7 s at p95** on the current accepted run (`s6-3`) —
   inside N2's 20 s typical target at both, and faster than the 16.5 / 46.4 of the run it
   replaced. The 4B model is what keeps it that low; a larger one would spill to RAM.
2. **Twelve of the 22 failures are citations**, not retrieval: the answer quotes a page it
   does not cite, or paraphrases past the verifier. That is where the remaining accuracy is.
3. **Not-found accuracy is a trade, measured, not a free win.** Accepting prose refusals
   fixed three unanswerable questions and broke two answerable ones. Anything that changes
   the refusal rule must run both halves of not-found (a) and (b) plus the gate.
4. **The gate only protects you if it is run.** It is a command, not a hook.
5. **`data/corpus` is read-only and the index is derived**; a corpus change re-runs ingestion
   (one document is cheap, a full rebuild is ~24 min of parsing), and a long-lived process
   holds its own index in memory, so restart the UI after adding documents (`RUNBOOK.md` §3.4).
6. **2.2% of pages have no readable text**, so some questions can only be answered "not
   found" with a warning — by design, not by accident.
7. **100k pages is not proven.** The manifest and per-document resume are built for it; the
   acquisition, the ~32 h run and the disk budget are not.
8. **The context is nearly spent on the table route, and that now bounds what can be
   added.** q047 measured 4,063 of 4,096 tokens of retry prompt before D-072 fixed it, and
   D-073 measured a 16,012-character table prompt that Ollama truncated. The retry guard
   buys room only on a retry; any change that *adds* text to a table passage overflows.

---

## Handy commands

```powershell
git status                                        # must be clean before any agent session
git tag                                           # what you have attested
.venv\Scripts\python.exe -m ingest.pipeline status --report
.venv\Scripts\python.exe -m ingest.pipeline backup --out backups\2026-11-20
.venv\Scripts\python.exe ingest\test_pipeline.py   # 12 cases: resume, duplicates, backup
.venv\Scripts\python.exe generation\test_verify.py # 26 cases: quotes, numbers, refusals
.venv\Scripts\python.exe retrieval\test_tables.py   # 11 cases: both table passes (off)
node scripts\ui-starters-check.mjs                  # every starter card and citation chip (Chrome)
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
