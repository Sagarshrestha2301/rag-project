# Tracker — where this project stands and what is yours to decide

One page, checked against the repository on **2026-11-15**: `git log`, `git tag` (none),
`APPROVALS.md`, `STATUS.md`, `DECISIONS.md` and the DoD boxes in `steps/`. If this page
and those files disagree, the files win - this is a summary.

Approvals live **only** in `APPROVALS.md` plus your `step-NN-approved` tags.
Nothing in this file is an approval.

---

## 1. Where you are

```
step 00  environment      DONE   (10/10 DoD ticked, no tag yet)
step 01  eval set         DONE   (6/6 ticked, 30 questions approved, no tag yet)
step 02  LLM benchmark    DONE 5/5 - awaiting your approval + tag (3 models measured; qwen3.5 4B wins at 23/30)
step 03  parsing          97 DOCS PARSED (851 pages, 242 tables) - awaiting your page + table check; Word-file box unreachable
step 04  chunk + embed    BUILT AND MEASURED - 3,226 chunks with contexts, 6 suites (16+12+26+15+9+5 cases), embedder benchmark run; owner chose bge-small (D-054) on 2026-11-15; awaiting your 10-chunk inspection + completion line
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

- Answers are searched from the 97-PDF corpus before the model sees the question.
- Every answer cites `[A]`-`[D]`; clicking a citation opens that PDF page.
- **Save chat** exports the conversation as Markdown, including sources.
- `NOT FOUND` when the pages don't cover the question — checked on a real not-found question.

Measured, not claimed:

| Thing | Number |
|---|---|
| Corpus | **97 PDFs** (was 5); 37 fetched from your Drive folder, 1 duplicate skipped, no duplicate names |
| Parsed (97-doc run) | **851 pages, 242 tables, 86 OCR pages, 20 unreadable, 51.3 pages/min; 32.5 h per 100k pages** |
| Table numbers | **5,511 of 5,520** match the page's own words (9 mismatches listed) |
| Chunks (95 docs with text) | **3,226** (2,958 text + 268 table); 2,665 carry a year, 1,670 a publisher, 3,027 a document type, 946 a real section path, all 3,226 a document context |
| Document contexts | **96 of 96** documents with text, **all 3,226 chunks carry one** (qwen3.5:4b, temp 0, ~7 s per document) |
| Embedder benchmark (CPU, 3,226 chunks) | `bge-small` **23/26 recall@5, MRR 0.702**, 606 chunks/min; `e5-small` 23/26, 0.723, 585/min; `MiniLM` 18/26, 0.430, 2,148/min. All **below** the BM25 page baseline (25/26, 0.885) |
| Retrieval baseline (BM25 pages, 97 docs) | **recall@5 25/26, MRR 0.885** (dev 17/17, heldout 8/9). Control on the old 5 documents: 25/26, MRR 0.817. q015 missed at any size |
| `qwen2.5` 7B through Ollama | 499.1 tok/s prompt, 9.43 tok/s generation |
| Oracle test (gold page as context, 30 questions) | **17/30**; citation 14/26 strict; numeric 22/24; not-found 4/4 |
| Eval scorer self-tests | 30/30 checks pass |
| Unreadable pages | 0 of 42 in the old 5-document set - the scan is OCR'd (was 4 of 42) |

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

1. **Step 3's Word-file box cannot be met.** Its DoD asks for LibreOffice conversion of five
   `.docx` files, and the corpus holds PDFs only. The 50-document and 20-table boxes are
   **reachable now** (97 PDFs, 169 tables); the page-number check is still yours.
2. ~~Step 2's 5th DoD box will never be filled.~~ **Resolved 2026-11-14**: both remaining
   models were downloaded and measured, so the three-model table exists (D-047). The ticked
   box in `steps/02-llm-benchmark.md` still carries the old "one model measured only" note —
   only you may edit that text.
3. ~~The NARAYAN scan is invisible to search.~~ **Resolved 2026-11-14**: the four
   scanned pages are OCR'd at index build and are now citable, marked `· OCR`. Caveat:
   OCR drops hyphens in numeric ranges (`5-10 %` → `510 %`), so numbers from that paper
   should be checked against the PDF.
4. **Two of the 97 PDFs are broken** (truncated Choudhary file, 0-page Komori file). They
   contribute no text and are reported, not replaced — `data/raw/` is yours.
5. **Steps 03-09 have no start approval.** `APPROVALS.md` records the completions of steps 01 and 02 but no start line for 03 or 04.

## 5. What to do, in this order

**Now (git, only you can do these):**

- Create the two missing tags: `git tag step-00-approved` and `git tag step-01-approved`
  (the step 02 completion line is recorded, its tag is not).
- Add the missing start lines for steps 03 and 04 to `APPROVALS.md`; the completion
  lines for steps 01 and 02 are already there.
- After the checks below: completion lines plus `step-03-approved` and
  `step-04-approved`.

**Step 4 embedder (done, one edit left):** the owner chose `bge-small-en-v1.5` in chat on
2026-11-15. The three models were downloaded and benchmarked (3.4 GB actual, pruned to
719 MB) and the index is built with bge. Nothing is pending; the `DECISIONS.md` entry still
says PROPOSED, and only you may change an existing entry.

**Step 3 Word-file box:** the corpus has no `.docx`, so "tested on 5 real Word files" cannot
be met as written. Accept it as a deviation or supply five Word files.

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
5. **`data/corpus` is read-only and the index is derived.** `index/ui-pages.json` carries a
   corpus signature, so a changed corpus rebuilds it automatically; the first rebuild OCRs
   the scans and takes minutes. Two of the 97 PDFs are broken (see §4) and will stay
   textless until you replace them.
6. **The embedder is chosen but dense-only retrieval still trails BM25.** D-054 chose `bge-small-en-v1.5` (owner, 2026-11-15); it ties `e5-small` within one question and wins on size. Dense-only retrieval currently **underperforms** the BM25 page baseline (23/26 vs 25/26 recall@5), so Step 5's hybrid is where the gain has to come from.

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
