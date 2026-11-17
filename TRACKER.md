# Tracker — where this project stands and what is yours to decide

One page, checked against the repository on **2026-11-17**: `git log`, `git tag`,
`APPROVALS.md`, `STATUS.md`, `DECISIONS.md` and the DoD boxes in `steps/`. If this page
and those files disagree, the files win — this is a summary.

Approvals live **only** in `APPROVALS.md` plus your `step-NN-approved` tags.
Nothing in this file is an approval.

---

## 1. Where you are

```
step 00  environment      DONE   10/10 boxes, tagged
step 01  eval set         DONE    6/6  boxes, tagged (55 questions: 45 dev + 10 held-out)
step 02  LLM benchmark    DONE    5/5  boxes, tagged (qwen3.5 4B won: 23/30)
step 03  parsing          TAGGED  4/7  boxes (97 docs, 851 pages, 242 tables); 3 open: your page
                                 review, your table review, and the Word-file box that a
                                 PDF-only corpus cannot meet
step 04  chunk + embed    DONE    5/5  boxes, tagged (3,226 chunks with contexts)
step 05  hybrid retrieval DONE    7/7  boxes, tagged (hybrid rejected on measurement; BM25 kept)
step 06  generation       DONE    7/7  boxes - awaiting your completion line and tag
step 07  web UI           SPEC    0/8  boxes - ui/SPEC.md written 2026-11-17, awaiting your approval
step 08  full ingestion   NOT STARTED  0/10 boxes
step 09  tuning + docs    NOT STARTED  0/5  boxes
```

`git tag` lists **step-00-approved … step-05-approved**. Steps 07, 08 and 09 have start
approvals in `APPROVALS.md`; step 06 has one too and is now finished by its own boxes.

## 2. What actually works today

Two surfaces, one measured pipeline and one prototype:

```powershell
# the measured pipeline (router, retrieval, gate, prompt, verifier, cache)
.venv\Scripts\python.exe -m generation.answer "Compare the Bagmati and East-Rapti peak floods." --json

# the older chat prototype: streaming, [A]-[D] citations, its own prompt, no verifier
.venv\Scripts\python.exe -m uvicorn ui.server:app --host 127.0.0.1 --port 8000
```

- The pipeline answers with verified quotations, refuses when the passages do not cover the
  question, caches repeated questions (0.4-0.6 s vs 9-19 s), and is what `eval/` measures.
- `eval/gate.py` enforces `EVAL.md`'s regression gate: two baselines, per-question diff,
  non-zero exit when a rule breaks (`RUNNING.md` §3c).
- `scripts/add-document.ps1 -Path <pdf>` adds a document in one command and rebuilds the index.
- `scripts/offline-generation-proof.ps1` proves the pipeline runs with the network blocked; it
  refuses to run the eval unless `scripts/offline-check.py` proves the block first.
- The prototype UI is **not** the Step 7 product: it has no router, gate, verifier or cache,
  and its `[A]` letters come from its own prompt.

Measured, not claimed:

| Thing | Number |
|---|---|
| Corpus | **97 PDFs, 851 pages**, 8 documents with unreadable pages (19 pages), 86 pages OCR'd |
| Chunks | **3,226** (2,958 text + 268 table) from 95 documents, every chunk carrying a document context |
| Retrieval baseline (55 questions) | recall@5 **45/48**, MRR **0.829** (dev 37/39 at 0.834, held-out 8/9 at 0.806) |
| Full generation run | **33/55 passed**; citation 31/48, numeric 35/43, not-found (a) 3/6, (b) 45/48; p50 16.6 s, p95 58.1 s |
| Held-out, own run | **5/10 passed**, recall 8/9, MRR 0.806 — identical to the subset view |
| Offline proof | **PASS** with 6 firewall rules and a probe that refused 1.1.1.1 and 8.8.8.8; metrics identical to the online run |
| Regression gate | 55-question run vs the rebased baseline: passes, zero drift; a regressed copy fails all four rules |
| Unit suites | 86 generation cases + 7 corpus cases pass; no pytest, each suite prints `all N cases pass` |

## 3. Open decisions only you can sign

| # | Asks | My recommendation | Blocks |
|---|---|---|---|
| **D-060** | A prose refusal counts as a refusal when its first sentence says the passages do not contain the answer | Approve and build it — it is the cheapest fix for not-found (a) 3/6 | not-found (a) |
| **D-061** | The Step 7 UI calls the shipped pipeline through one streaming wrapper, and stays in `ui/` rather than `src/ui/` | Approve both halves | Step 7 code |
| **D-062** | Five answer states, `debug_version` 1 payload, and per-stage timings added to the `generation.answer` record | Approve | Step 7 code |
| — | `EVAL.md`'s one-question table still says dev is 20 questions at 5 points (it is 45, so 2.2 points) | your edit — protected file | nothing |

The six UI choices in `ui/SPEC.md` §12 are D-061/D-062 in more detail; "approve all
recommended" answers everything and unblocks Step 7.

## 4. Blocked or deviating, stated plainly

1. **Step 3's Word-file box cannot be met as written**: its DoD asks for five `.docx`
   conversions, and the corpus holds PDFs only. The step is tagged, so this stands as an
   accepted deviation; the page and table reviews are still open boxes in the step file.
2. **Step 8's 100k-page target is not reachable from this corpus** (97 documents, 851 pages).
   Its resumability, manifest, duplicate detection and incremental-add tasks are, so the
   step will need the same kind of owner decision Step 3 got.
3. **Not-found (a) is 3/6.** Three refusals were written in prose instead of the exact
   `NOT FOUND` line; D-060 is the fix and it is not built.
4. **Citation 31/48** is under the strict rule you chose (D-041) and stays that way: the
   benchmark failures are paraphrase and extra pages, not invented sources.
5. **The prototype UI is not held to any of the above numbers**; it still has its own prompt.
   Nothing it shows should be treated as a pipeline measurement.

## 5. What to do, in this order

1. **Step 6:** add `2026-11-17 | completion | step 06 | owner` to `APPROVALS.md` in an
   `OWNER:` commit, then `git tag step-06-approved`.
2. **Step 7:** read `ui/SPEC.md` and answer §12 (or approve all recommended). No UI code has
   been written and none will be until you do.
3. **D-060:** decide the refusal rule; it is the smallest change with a measured payoff.
4. **Step 3:** tick or reword the two review boxes (only you may edit step text).
5. **Step 8:** decide what "full ingestion" means for an 851-page corpus before it starts.

## 6. Honest risks, in the order they will bite

1. **Latency is ~17 s median, 58 s at p95.** The 4B model is what keeps it that low; a
   larger one would spill to RAM on this card.
2. **A paginated UI will show the ~20 s wait.** The spec streams, so text appears early, but
   the verifier only has an answer at the end.
3. **The gate only protects you if it is run.** It is a command, not a hook.
4. **`data/corpus` is read-only and the index is derived**; a corpus change rebuilds it
   (minutes, because the scans are OCR'd).
5. **The cache is keyed on the index signature**, so an edited corpus misses the cache
   instead of replaying a stale answer — but a long-lived process holds its own index in
   memory, so restart it after adding documents.

---

## Handy commands

```powershell
git status                                        # must be clean before any agent session
git tag                                           # what you have attested
.venv\Scripts\python.exe generation\test_think.py # 8 cases, same shape as the other suites
.venv\Scripts\python.exe eval\gate.py --current eval\runs\2026-11-17-offline-step6 `
  --baseline eval\runs\2026-11-16-step6-full --start eval\runs\2026-11-16-step6-full
.venv\Scripts\python.exe scripts\offline-check.py  # exit 0 = external network refused
curl.exe -s http://127.0.0.1:11434/api/tags        # is Ollama serving qwen3.5:4b
```

Restarting the prototype UI: kill the process **listening** on 8000, not the `.venv`
wrapper — the wrapper is a shim and the real listener is its child
(`netstat -ano | findstr :8000`).
