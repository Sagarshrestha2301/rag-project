# Tracker — where this project stands and what is yours to decide

One page, checked against the repository on **2026-11-14**: `git log` (23 commits),
`git tag` (none), `APPROVALS.md`, `STATUS.md`, `DECISIONS.md` and the DoD boxes in
`steps/`. If this page and those files disagree, the files win — this is a summary.

Approvals live **only** in `APPROVALS.md` plus your `step-NN-approved` tags.
Nothing in this file is an approval.

---

## 1. Where you are

```
step 00  environment      DONE   (10/10 DoD ticked, no tag yet)
step 01  eval set         DONE   (6/6 ticked, 30 questions approved, no tag yet)
step 02  LLM benchmark    NEARLY DONE (4/5 ticked; the 5th can never be filled - see 4)
step 03  parsing          NOT STARTED (0/7) - needs your approval to begin
step 04  chunk + embed    NOT STARTED
step 05  hybrid retrieval NOT STARTED
step 06  generation       NOT STARTED
step 07  web UI           NOT STARTED as a step (a working UI exists outside the steps)
step 08  full ingestion   NOT STARTED
step 09  tuning + docs    NOT STARTED
```

`git tag` prints **nothing**. Both completed steps are therefore unattested,
which is why the tracker still calls them "done, tag pending".

## 2. What actually works today

You can run it and get grounded answers right now:

```powershell
.\scripts\launch-llm.ps1                                              # loads qwen2.5 into Ollama
.venv\Scripts\python.exe -m uvicorn ui.server:app --host 127.0.0.1 --port 8000
# then open http://127.0.0.1:8000
```

- Answers are searched from the 42 corpus pages before the model sees the question.
- Every answer cites `[A]`-`[D]`; clicking a citation opens that PDF page.
- **Save chat** exports the conversation as Markdown, including sources.
- `NOT FOUND` when the pages don't cover the question — checked on a real not-found question.

Measured, not claimed:

| Thing | Number |
|---|---|
| `qwen2.5` 7B through Ollama | 499.1 tok/s prompt, 9.43 tok/s generation |
| Oracle test (gold page as context, 30 questions) | **17/30**; citation 14/26 strict; numeric 22/24; not-found 4/4 |
| Eval scorer self-tests | 30/30 checks pass |
| Parsing speed | 0.64 s/page (`pymupdf4llm`) |
| Unreadable pages | 4 of 42 (9.5%) — the NARAYAN scan |
| NARAYAN OCR (approved, installed) | 0 → 7,020 characters in 26.6 s |

## 3. Open decisions only you can sign

All are `PROPOSED` in `DECISIONS.md` except where noted. None blocks the UI.

| # | Asks | My recommendation | Cost of deciding |
|---|---|---|---|
| **D-038** | Grow the corpus in 3 stages (Marahatta → 30-50 docs → full) instead of jumping to 100k pages | Approve — it is what makes Steps 4-5 measurable | Edits needed in the step files (yours) |
| **D-039** | Download 3 small models (8.38 GB) to compare against the 7B | **Reject** — you already chose the 7B; this is superseded by D-040 | none |
| **D-040** | Keep `qwen2.5` 7B despite it being outside D-002's 3-4B rule, and despite ~28 s projected for a standard RAG prompt | Approve, and state the latency cost in the decision | one line in D-002's history |
| **D-042** | Ollama is the runtime; llama.cpp is deleted | Approve — it measured 1.7× faster and 1.9 GB smaller | none |
| **D-043** | A chat UI exists ahead of Step 7 | Approve, or say "discard it" | if approved, Step 7 adopts it as its shell |
| **D-044** | That UI carries a **page-level** BM25 prototype so citations are real, with letter labels | Approve with the limits stated (page-level only; scan pages unreachable) | none |
| — | D-041 (loosen citation matching) | already **REJECTED** by you — nothing to do | — |

## 4. Things that are genuinely blocked

1. **Step 3 cannot meet its own definition of done with 5 documents.** Its DoD says
   "50 docs parsed" and "20 tables checked cell by cell". The corpus holds 5 PDFs with
   11 tables. You already chose to run it as a **5-document smoke test** — that choice
   needs one line in the step file, which only you may edit, or the boxes stay unticked.
2. **Step 2's 5th DoD box will never be filled.** It wants a comparison table for three
   models; you declined the other two downloads. It is recorded as a stated deviation
   (D-040), not silently ticked. That is the honest end state, not a gap to close.
3. **The NARAYAN scan is invisible to search.** OCR now works, but those 7,020 characters
   are not yet parsed into the corpus, so the 4 pages can never be cited. Either that
   text gets indexed in Step 3, or "not found" answers about liquefaction are misleading.
4. **Steps 3-9 have no start approval.** `APPROVALS.md` stops at step 01.

## 5. What to do, in this order

**Now (5 minutes, in git — only you can do these):**

```powershell
cd C:\Users\sagar\Downloads\project\rag-project
git tag step-00-approved
git tag step-01-approved
git push --tags          # only if you want them off this machine
```

Then add to `APPROVALS.md`, with an `OWNER:` commit:

```
2026-11-14 | completion | step 01 | owner
2026-11-14 | completion | step 02 | owner
2026-11-14 | start | step 03 | owner
```

and `git tag step-02-approved` if you accept the one-model deviation in D-040.

**Then decide (no code needed):** D-038, D-040, D-042, D-043, D-044 as "approved" or
"rejected" — append a line to each in `DECISIONS.md` and commit with `OWNER:`.
D-039 can be closed as superseded.

**Then choose Step 3's scope explicitly**, because the step text and the corpus disagree:

- **(a) 5-document smoke test** — parse all 5 PDFs, check the 11 real tables, verify page
  numbers, record pages/min and the 9.5% unreadable share. Fast, honest, and the DoD boxes
  are marked "smoke-tested". *Recommended.*
- **(b) Wait for Stage B (30-50 documents)** so Step 3's 50-doc DoD is met literally.
  Nothing else gets built until then.

**Then approve Step 3 to start**, and parsing code gets written.

## 6. Honest risks, in the order they will bite

1. **Latency.** A standard RAG prompt (~3.4k tokens) plus ~120 answer tokens projects to
   ~28 s end to end. The target was 20 s. The UI hides this well by streaming, but it is
   still 20+ s before a complete answer.
2. **Citation quality is 14/26 under the strict rule you chose.** Seven of those failures
   are genuine paraphrase, which Step 6's prompt must fix; five are formatting the rule
   intentionally counts as failure. Do not loosen the rule to make the number look better.
3. **The retrieval in the UI is not Steps 4-5.** It ranks whole pages by BM25. It is good
   enough to cite honestly today and will likely be replaced by the real pipeline.
4. **Nothing here is offline-proven end to end.** Step 0 proved a firewall-blocked answer;
   the full app (Ollama + server + UI) has not been run with the network off. That proof
   is due at Step 5/6/8 anyway, but do not assume it.
5. **`data/corpus` is read-only and the index is derived.** Delete `index/ui-pages.json`
   after changing the corpus, or you will search stale text.

---

## Handy commands

```powershell
git status                                  # must be clean before any agent session
git tag                                     # what you have attested
curl.exe -s http://127.0.0.1:8000/api/health # model + index + unreadable pages
.venv\Scripts\python.exe eval\test_scorer.py # 30/30 expected
```

Restarting the UI server: kill the process **listening** on 8000, not the `.venv`
wrapper — the wrapper is a shim and the real listener is a child
(`netstat -ano | findstr :8000`).
