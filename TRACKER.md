# Tracker — where this project stands and what is yours to decide

One page, checked against the repository on **2026-11-27**: `git log`, `git tag`,
`APPROVALS.md`, `STATUS.md`, `DECISIONS.md`, `EVAL.md`, the DoD boxes in `steps/` and the
stored `scores.json` of the two runs quoted below. If this page and those files disagree,
the files win — this is a summary. Nothing here is new measurement; it is the recorded state.

Approvals live **only** in `APPROVALS.md` plus your `step-NN-approved` tags. Nothing in
this file is an approval.

---

## 1. Where you are

```
step 00  environment      DONE      10/10 boxes, tagged step-00-approved
step 01  eval set         DONE       6/6  boxes, tagged (55 questions: 45 dev + 10 held-out)
step 02  LLM benchmark    DONE       5/5  boxes, tagged (qwen3.5 4B won: 23/30)
step 03  parsing          TAGGED     4/7  boxes (97 docs, 851 pages, 242 tables); 3 open:
                                     your 20-page review, your 5-table review, and the
                                     Word-file box a PDF-only corpus cannot meet
step 04  chunk + embed    DONE       5/5  boxes, tagged (3,226 chunks with contexts)
step 05  hybrid retrieval DONE       7/7  boxes, tagged (hybrid rejected on measurement)
step 06  generation       DONE       7/7  boxes, completion line 2026-11-17; tag is yours
step 07  web UI           DONE       8/8  boxes, completion line 2026-11-20; tag is yours
step 08  full ingestion   BUILT     10/10 boxes; completion open only on the 100k-page
                                     scope decision (D-063)
step 09  tuning + docs    SIGNED OFF 5/5 boxes, completion line 2026-11-20; tags are yours
step 10  batch ingestion  BUILT      6/7  boxes - `add-batch` with an all-or-nothing
                                     pre-flight; open: owner review of one refusal and
                                     one landed batch
step 11  pilot wave       RAN        6/6  boxes - 210 real PDFs fetched, 118 built in
                                     3,528 s (29.9 s/document); wave 01 later added to
                                     the live corpus
step 12  parse isolation  BUILT      7/7  boxes - each document parses in its own
                                     `parse-one` child, crash rows not retried. No start
                                     line in `APPROVALS.md` (only you may add it)
step 13  parallel parse   BUILT      7/7  boxes - `--jobs N`, default 1; measured 1.41x on
                                     20 documents, 1.22x across a full 119-document wave
step 14  bibliography off BUILT      7/7  boxes - five default stages; removes 8.2 s/doc
                                     (45.1 h at 20k). D-083 still needs your verdict
step 15  refusal line     BUILT      7/7  boxes - exact line counted when nothing is cited;
                                     37/55, nf(a) 5/6; dev gate needs the q027
                                     explanation, held-out clean (D-090)
step 16  list retrieval   BUILT      7/8  boxes - window rule recovers q036; q050 is still
                                     prose because the prompt rule was ignored, so the
                                     shape box is not met
step 17  list shape check BUILT      8/8  boxes - the verifier enforces the dash list and
                                     the retry produces it; 38/55 at the time, every
                                     metric unchanged (D-094)
step 18  citation cap     BUILT      7/7  boxes - at most two extra verified pages, per
                                     question `extra_citations`, every stored run
                                     re-stated (D-097 approved)
step 19  one page reader  BUILT      6/6  boxes - scorer and verifier read page text the
                                     same way; q003 recovered, **D-086 met**
step 20  quote case        BUILT      7/7  boxes - a quotation may differ only in its first
                                     letter's case; **q052 verified, all 55 answers
                                     byte-identical**, D-086 fully recovered (D-100)
```

`git tag` lists **step-00-approved … step-05-approved** and nothing later. Completion lines
in `APPROVALS.md` exist for steps 00–07 and 09; steps 08 and 10–20 have none yet. Only you
create tags.

## 2. What actually works today

One answer path, and it is the one the eval measures:

```powershell
# operation, start to restore: RUNBOOK.md (followed step by step)
# the reference with the detail: RUNNING.md

# the shipped UI (D-091: it measures the port; 8000 is reserved by Windows on this
# machine, so it prints the swap and serves on 8300)
.\scripts\open-chat.ps1 -Start                    # then http://127.0.0.1:8300

# the same pipeline from a terminal, with the JSON record
.venv\Scripts\python.exe -m generation.answer "Compare the Bagmati and East-Rapti peak floods." --json

# index from the corpus: resumable, parses only new or changed documents
.venv\Scripts\python.exe -m ingest.pipeline build
.venv\Scripts\python.exe -m ingest.pipeline status --report
```

- **The UI keeps no prompt of its own.** `ui/pipeline.py` calls `generation.answer` with an
  `on_token` hook, so the five answer states, numeric citation chips, the Sources/Debug
  tabs and the unreadable-page warning show the measured pipeline's output (D-061).
- **`ingest/pipeline.py`** runs scan → parse → assemble → chunk → embed from one manifest
  (`index/manifest.sqlite`); bibliography is on demand (`python -m ingest.bibliography
  build`). It resumes per document after a kill, isolates a crashing document, flags exact
  and 80%-shared duplicates instead of indexing them twice, keeps `backup`/`restore`, and
  rebuilds `index/pages.json` and `index/chunks.jsonl` byte for byte.
- **`add-batch --from <staged folder> --wave NN [--jobs N]`** brings a folder in all or
  nothing: every file is checked before any is placed, non-PDFs and bad names refuse the
  whole batch, already-indexed bytes are skipped with the reason, then the build runs.
- **`eval/gate.py`** enforces `EVAL.md`'s regression gate (two baselines, per-question diff,
  `--explain qID=REASON` or `--explanations FILE` for pass-to-fail questions, `--milestone`
  for held-out). It is what rejected D-060 and what keeps every accepted change honest.
- **`eval/score.py`** is the current contract: citation passes when at least one cited page
  is gold, every quotation is verbatim on the page it names (read through
  `corpus.page_text`, the pipeline's own reader), and at most **two** cited pages are
  outside the gold set; `extra_citations` is recorded per question (D-097, step 19).

Measured, not claimed:

| Thing | Number |
|---|---|
| Corpus | **187 PDFs** in `data/corpus` (216 before the 29 mostly-non-Latin files were quarantined, D-080) |
| Index | **186 documents, 2,669 pages, 11,334 chunks, 120 MB**; manifest **187 rows: 186 embedded, 1 failed** (the known PyMuPDF crash); **222 OCR pages** |
| Retrieval (55 questions) | recall@5 **45/48**, recall@10 46/48, MRR **0.839** |
| **Accepted baseline** (`2026-11-24-repro-a`, current scorer) | **41/55** (dev 34/45, held-out 7/10); citation 38/48, numeric 37/43, not-found (a) 3/6, (b) 46/48 |
| **Latest graded run** (`2026-11-27-step20-first-letter`, current scorer) | **44/55** (dev 37/45, held-out 7/10); citation 39/48, numeric 38/43, nf(a) 5/6, (b) 46/48; p50 **12.7 s**, p95 **44.3 s**. Not yet accepted: D-093/D-094/D-100 are open |
| Held-out milestone | last measured **7/10** on the step-20 run, gate `--milestone` exit 0 both ways |
| Model and runtime | `qwen3.5:4b`, digest `d8b0f5e9760c`, prompt **`s6-6`**, temperature 0, seed 0, cache off; **Ollama 0.40.18** (pin proposed as D-088) |
| Wave-01 cost | **0 questions**: pre-wave corpus 41 vs `repro-a` 41 on today's contract (was 3 when D-089 measured it, 1 after step 19) |
| D-086 trigger | **Fully recovered** — q003, q040, q052 and q055 all pass; the rollback is no longer needed |
| Unit suites | `eval/test_scorer.py` **39 checks**, `generation/test_verify.py` **38/38** (3 new for the case flip), `ingest/test_pipeline.py` **28/28**, `ui/test_server.py` **8/8**, `ui/test_pipeline.py` **7/7**, corpus **11/11** |
| Offline proof | step 06 **PASS** 2026-11-17 with recorded output (6 firewall rules + refused probes, run identical to online). Steps 07 and 08 **PASS on your own runs** (reported 2026-11-20/21); no artifact was supplied, so the repository cannot show those two |

## 3. Open decisions only you can sign

`D-097` is decided (you approved it 2026-11-26 and step 18 shipped it). The rest have no
verdict line in `APPROVALS.md` or `DECISIONS.md`:

| # | Asks | Recorded recommendation |
|---|---|---|
| **D-063** | Step 8 is judged on the pipeline that exists; 100k pages is a separate corpus-and-hardware decision | Approve — neither scale item can be run on this corpus |
| **D-083** | The bibliography is an on-demand stage, not part of a wave (shipping since step 14) | Approve — measured 8.2 s/doc, 45.1 h at 20k, no eval reads it |
| **D-086** | Keep the 186-document English-only corpus rather than roll wave 01 back | **Triggers now met**: keep. Needs your confirmation line |
| **D-087 / D-088** | Record Ollama **0.40.18** as the pinned runtime; 0.40.16 runs are not comparable with it | Approve both — two back-to-back runs are identical on 55/55 |
| **D-090** | A refusal counts when the prompt's exact line is present and nothing is cited; q027 is re-labelled at no score cost | Approve — 37/55, nf(a) 5/6; the dev gate needs the written q027 explanation |
| **D-092** | The `s6-4` list-format prompt rule is measured and **not kept** (four dev questions lost) | Close it as rejected — the tree is already back on `s6-3`-derived prompts |
| **D-093** | Accept the scoped window rule (recovers q036); keep `LIST_RULES` as formatting with no measured benefit, or drop it | Accept the window rule; your call on `LIST_RULES` |
| **D-094** | Output shape is verified, not requested: the dash-list check plus the existing retry is what finally produces lists | Accept — and carry "verification beats instructions" to future format rules |
| **D-095** | A list question whose answer is missing ends `unverified` (list item + refusal line); option (b) counts it as a refusal | Approve (b) as its own small step, with the L5 question re-asked before and after |
| **D-098** | Scorer and verifier share one page-text reader (shipped as step 19) | Accept — record that an OCR error can now certify a quote, as it already could in the pipeline |
| **D-099** | The extra-page cap counts **pages**; the ten excluded q049 answers are correct and fully cited, so it should count **documents** | Accept: allow two extra **documents**, record `extra_documents`; it keeps every current result |
| **D-100** | A quotation may differ from the page only in the case of its first ASCII letter (shipped as step 20; recovers q052) | Accept — one character, both halves share the helper, and a case change anywhere else still fails |
| **D-091** | The chat UI measures its port because Windows reserves 8000 here (Hyper-V/WinNAT) | Accept as built, or run the elevated command that gives 8000 back |
| **D-064 / D-065 / D-066 / D-067** | Parsed shards; duplicates flagged never deleted; bibliography extraction; sentence entailment as a secondary signal | All carried forward with no verdict line yet — D-064/D-065 are already built and tested |
| — | `EVAL.md`'s Metrics sentence still says "every cited page is gold" | Your edit (protected file). Replacement text is in `STATUS.md` → Proposals |

## 4. Blocked or deviating, stated plainly

1. **Step 3's Word-file box cannot be met as written** — the corpus holds PDFs only. The
   step is tagged, so this stands as an accepted deviation; your page and table reviews are
   still open boxes in the step file.
2. **Step 8's 100k-page items cannot be run here.** The pipeline half is built and measured;
   D-063 asks you to accept that split before the completion line.
3. **Step 12 has no start line in `APPROVALS.md`.** The code exists, its boxes are ticked and
   it is measured; the approval record is missing and only you can add it.
4. **Step 10's review is yours:** watch one refused batch and one landed batch.
5. **The step 07 and 08 offline proofs rest on your reports, not an artifact.** Step 06 is
   the only offline run with recorded output. The six `step7-offline-proof` firewall rules
   were removed on 2026-11-21; the sandbox's own rules must not be touched.
6. **q052 is the last of D-086's four losses** and still fails on one lowercased capital
   letter in a quotation — a model-copying defect the verifier rejects honestly. D-086 is
   already met without it, but it is the open technical item.
7. **Step 16's shape box stays unmet** (q050 ignored the prompt, byte-identical to `s6-3`).
   Step 17's verifier is the fix that worked; the box remains unticked in the step file.
8. **One pilot PDF crashes PyMuPDF natively** in `page.find_tables`
   (`2023_Small_Area_Estimation_of_Nepal…pdf`, access violation 0xC0000005). It is isolated
   to one failed manifest row and a non-zero exit; it is not retried.
9. **Unreadable pages are above the D-020 1–2% band.** On the original 97-document corpus it
   was **19 of 851 pages (2.2%)**; the current 187-file corpus's ratio is not recorded, and
   222 pages need OCR text to be readable at all.

## 5. What to do, in this order

1. **Tags and completion lines.** Tags: `step-06-approved` … `step-19-approved` (only 00–05
   exist). Completion lines: step 08 after D-063, and steps 10–19 after your reviews.
2. **Edit `EVAL.md`'s citation sentence** so the metric and `eval/SCORER.md` agree; the
   replacement is written out in `STATUS.md` → Proposals.
3. **Verdicts, cheapest first:** D-087/D-088 (pin the daemon), D-083, D-090, D-093, D-094,
   D-098, D-099, D-086 confirmation, then D-063, D-091, D-095.
4. **Step 10's two reviews** (one refusal, one landed batch) and **step 3's** 20-page and
   5-table reviews.
5. **q052 is fixed** (step 20: one first-letter case flip, 44/55, only q052 moved). The next
   small, measured candidates are **D-095(b)** (a list answer ending in the exact refusal
   line counts as a refusal — the L5 case) and the **`11-15` loss** in q050's list body;
   each needs its own step file and your start line.
6. **Scaling:** `reports/20k-download-and-rag-guide.md` is the procedure for the remaining
   ~19,800 PDFs; it needs a download start line in `APPROVALS.md` before any network run.
   Ten cursor waves fill one `data/raw/bulk` tree without downloading a file twice.

## 6. Honest risks, in the order they will bite

1. **The citation layer is still the largest failure group.** On the step-20 run the
   remaining failures are paraphrases the verifier rejects twice (q044, q045, q048), answers
   that cite nothing (q015, q026–q028, q046), q029's number and q020's false answer. q052 is
   now recovered. Improvements now come from quote discipline and passage content, not from
   retrieval.
2. **Latency is 14.4 s median, 48.7 s at p95** on the latest graded run. p95 is the number
   a reader feels; only two questions can take the extra shape retry, so the rest is the
   4B model and long table prompts.
3. **Not-found accuracy is a trade, measured, not a free win.** The exact-line rule took
   (a) from 3/6 to 5/6 and cost one (b) question and q027's label (D-090). Any change to
   the refusal rule must run both halves plus the gate.
4. **Cross-daemon comparisons are invalid.** Temperature 0 with a fixed seed reproduces
   exactly within one daemon (55/55 identical fields) but not across a version change
   (0.40.16 → 0.40.18 moved q019/q051/q039/q044). D-087/D-088 pin 0.40.18 for that reason.
5. **The gate only protects you if it is run.** It is a command, not a hook, and the extra
   -page rule moves both sides of a comparison equally, so a looser contract cannot be
   detected by the gate (D-097).
6. **One page-text reader is now load-bearing for both halves (D-098).** An OCR error can
   certify a quotation the PDF image does not show; that was already true of every answer
   the pipeline accepted, and 222 pages depend on OCR.
7. **The 20k build is not proven end to end.** Rates are measured per stage (~41 h projected
   with `--jobs 8` and no bibliography), the acquisition and disk budget are not, and the
   first real trigger is FTS5/sharding at roughly 9,000 documents, from the measured
   linear page-BM25 growth, not 20,000.
8. **The context on the table route is nearly spent.** q047 measured 4,063 of 4,096 tokens
   before D-072's retry guard, and D-073 measured a 16,012-character table prompt that
   Ollama truncated. Any change that *adds* text to a table passage overflows.
9. **The canary is frozen on 97 documents.** Wave 01 costs 1 question today; a future
   corpus change should be judged on the same two baselines and the same gates.

---

## Handy commands

```powershell
git status                                          # must be clean before any agent session
git tag                                             # what you have attested
.venv\Scripts\python.exe -m ingest.pipeline status --report
.venv\Scripts\python.exe -m ingest.pipeline backup --out backups\2026-11-27
.venv\Scripts\python.exe ingest\test_pipeline.py     # 28 cases: resume, duplicates, jobs, watchdog
.venv\Scripts\python.exe generation\test_verify.py   # 29 cases: quotes, numbers, refusals, list shape
.venv\Scripts\python.exe eval\test_scorer.py         # 36 checks: the citation contract
node scripts\ui-starters-check.mjs                   # every starter card and citation chip (Chrome)
.venv\Scripts\python.exe eval\gate.py --milestone --current eval\runs\2026-11-25-step17-list-shape `
  --baseline eval\runs\2026-11-24-repro-a --start eval\runs\2026-11-24-repro-a
# dev gate against the accepted baseline needs the recorded D-090 reason for q027, e.g.
#   --explain q027="<the D-090 q027 reason recorded in STATUS.md>"
.venv\Scripts\python.exe eval\gate.py --current eval\runs\2026-11-25-step17-list-shape `
  --baseline eval\runs\2026-11-24-repro-a --start eval\runs\2026-11-24-repro-a
.venv\Scripts\python.exe scripts\offline-check.py    # exit 0 = external network refused
curl.exe -s http://127.0.0.1:11434/api/tags          # is Ollama serving qwen3.5:4b
```

Restarting the chat UI: kill the process **listening** on the port, not the `.venv` wrapper —
the wrapper is a shim and the real listener is its child (`netstat -ano | findstr :8300`).
`open-chat.ps1` prints the port it chose; `-Port` or `UI_PORT` pins it (D-091).
