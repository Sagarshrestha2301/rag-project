# Handoff: what is done, what is next

Written 2026-11-19, at commit `38480ac` (pushed to `origin/main`). Everything below was
measured in this repository; nothing is projected or estimated unless it says so. The
authoritative record is `STATUS.md` (measured facts and session log), `DECISIONS.md`
(decisions and their state) and `APPROVALS.md` (the only place an approval exists).

## Where the project stands

| Step | State | What is missing |
|---|---|---|
Tags exist for steps 00–05 (`git tag -l`). Steps 06–09 have their start approval and, in
06's case, a completion line, but no tag yet.

| Step | State | What is missing |
|---|---|---|
| 0–2 | done, tagged | nothing |
| 3 parsing sample | done, tagged; review material ready | the two owner review sheets (`artifacts/step3/review.html`, `artifacts/step3/tables-review.html`), and a yes/no on the Word-file box, which a PDF-only corpus cannot meet |
| 4 chunking / retrieval | done, tagged | nothing |
| 5 offline proof + model choice | done, tagged, offline run pass | nothing |
| 6 generation | built, gated, completion approved | only the `step-06-approved` tag |
| 7 web UI | built, measured in a real browser | **Wi-Fi-off session** (needs an elevated prompt), the completion line and the tag |
| 8 full ingestion | 9 of 10 boxes | **offline proof** (elevated prompt), D-063 (100k-page scope), not-found verdicts, the completion line and the tag |
| 9 evaluation | in progress | remaining experiment decisions; the failure analysis exists (`eval/failures.py`) |

## What has been done (measured)

### Ingestion and index
- `python -m ingest.pipeline build` takes `data/corpus/` to a searchable index in six
  resumable, per-document stages: `scan`, `parse`, `assemble`, `bibliography`, `chunk`,
  `embed`.
- **97 documents / 851 pages → 3,226 chunks** (2,958 text + 268 table), **3,226 vectors**
  (384-dim, unit length, no zeros). `index/` is **41,969,013 bytes (40 MB)**. 86 pages were
  read by OCR; 8 documents still have **19 pages** with no readable text.
- A second run with nothing changed takes **1.6 s** and parses nothing; a killed run
  resumes at the document in flight.
- Backup (40 MB, including LanceDB) and restore were exercised on the real index: restored
  `pages.json` and `chunks.jsonl` are byte-identical (`395c5a2b…`, `1208cb59…`).
- `2006_Komori_Scars_..._W2328682512.pdf` has **0 pages** and appears in no index artifact,
  which is why the corpus has 97 files but the index holds 96 documents.

### Answers and the regression gate
- 55-question generation eval, cache off, `qwen3.5:4b`, temperature 0:
  **33/55 passed** (dev 28/45, held-out 5/10), recall@5 **45/48**, MRR **0.826**, citation
  **31/48**, numeric **34/43**, not-found (a) **3/6**, not-found (b) **45/48**.
  Latency p50 **16.5 s**, p95 **46.4 s**.
- `eval/gate.py` enforces no unexplained pass-to-fail question, no metric down by two
  questions, not-found (a) never down. Both the dev and the held-out milestone gates pass
  on the 2026-11-19 run.
- The eval scores what the browser shows: the UI streams `generation.answer` itself (D-061).

### Bibliographic references (D-066)
- `ingest/bibliography.py` reads each document's header pages, asks the local model for
  title / authors / year / venue / DOI, and keeps a value **only when the page prints it**.
  Kept fields store the evidencing text; dropped fields store the reason.
- Coverage over **96 of 96 indexed documents**: title **62**, authors **64**, year **68**,
  venue **43**, DOI **5**, a printable reference **78**, **1 error** (a legacy-font PDF whose
  reply was not JSON; its DOI/year fallback still ran). **1,371.5 s** of model calls; a
  second pass over nothing **0.4 s**.
- The sources rail now shows "Marahatta & Bhusal (2009). Relating Hydrological Extremes
  with Area – A Case on Extreme Floods in South Central Nepal" instead of
  `1970_Marahatta_...pdf`; the file name stays as the hidden key.
- A build lock (`index/bibliography.lock`, `--force` to recover) stops two builds from
  rewriting the artifact from their own snapshots — that failure lost 57 records once.

### UI answers and citation trust
- Citation chips keep their brackets (`[1]`, not `1`), and the printed citation line under
  an answer is plain text, never chips.
- The unreadable-pages warning used to render as "Some pages cannot be read8 of 97
  documents…"; its title is now its own block, and the two counts are stated as two facts:
  **"19 of 851 pages, in 8 of 97 documents, still have no readable text after OCR. 86 pages
  were read by OCR."**
- **Clicking a citation opens the cited page inside the UI**, with the quotation marked:
  `ui/static/citation-viewer.js`, pdf.js 4.10.38 vendored at `ui/static/vendor/pdfjs/`,
  imported on the first click. Measured: q001's chip opened page 2 of 5 with 12 highlight
  rectangles over the quoted sentence, page 3 opened with none, and Escape closed it.
  Frontend only - no server, pipeline, prompt or index change.
- Every one of these is asserted by `scripts/ui-browser-check.mjs`, which drives the
  installed Chrome headless and fails on a missing chip, a chip inside a reference line, a
  merged warning, a source that is only a file name, or a citation that does not open its
  page with a highlight.
- Sentence-level entailment prototype (D-067, measure only): **92 sentences judged, 55
  SUPPORTED, 3 PARTIAL, 34 UNSUPPORTED**. Of the 37 failures, **15** state a number the
  quote lacks but the cited page prints, **0** state a number absent from the page, and 4
  sentences cite a marker the answer never explains (q002 `[1]`, q020 `[2]`, q046 `[5]`,
  `[6]`). Rows: `reports/entailment.jsonl`; readable list: `reports/entailment.md`.

## What is next

### For the owner (blocked on approval or elevation)
1. **Step 7 Wi-Fi-off session** — `powershell -NoProfile -ExecutionPolicy Bypass -File
   scripts\offline-ui-proof.ps1` from an elevated prompt with the UI on
   `http://127.0.0.1:8000/`. Answers 5 questions, 2 follow-ups; it self-tests the block.
2. **Step 8 offline proof** — `scripts\offline-generation-proof.ps1`, same elevation. This
   is Step 8's last box; the script and the self-test already pass from Step 6.
3. **D-063, the 100k-page scope** — the corpus is 851 pages, so 100k pages and the
   1,000-page dry run cannot be measured here (51.3 pages/min → ~32 h of parsing).
4. **Not-found verdicts** — `reports/not-found-recheck.md` lists all 7 unanswerable
   questions with their best pages and leaves the verdict to you (D-027).
5. **D-060 (refusal format)** — unbuilt. Not-found (a) is 3/6 because the model refuses in
   prose instead of the exact line; the proposal is containment plus a first-sentence
   negation, with a test and a re-run.
6. **D-066 and D-067** — both built and measured, both still PROPOSED in `DECISIONS.md`.
   D-067 needs a direction: wire it in as a per-answer warning, keep it as a periodic
   report, or drop it.

### For the agent (no approval needed, all measurable)
0. **The viewer only opens a page it can highlight on the page it renders.** A hash-link
   `#page=N` would scroll a native PDF viewer to a page even when the text layer is empty;
   this one shows "cited text not found on this page" instead. If a reader wants the
   native viewer as the default, that is a one-line change in `openSource`.
1. **The 4 unexplained markers.** Sentences in q002, q020 and q046 carry a `[n]` with no
   citation line at all, so nothing about them was verified. Fix the citation listing (or
   drop the marker) and re-run those four questions; changing the prompt needs the eval and
   the gate.
2. **The 15 weak quotations.** The quotation printed for a number does not contain the
   sentence's fact, even though the page does. The fix is to quote the sentence's own
   evidence rather than one fixed passage per source — a prompt/verifier change, so it goes
   through the eval and `eval/gate.py`.
3. **OCR honesty.** An answer drawn from an OCR-read page (86 pages) can carry a misread
   number; D-045 recorded a hyphen loss that the model silently "corrected". Marking such
   citations in the UI is a small, honest change.
4. **The wrong-author cases.** Validation proves a string is on the header page, not that it
   is the right author: `2001_Li_Water_Induced_Disasters…` yields "Tianchi & Gurung (2001)".
   A review sheet of the 78 references would settle which to correct.
5. **`eval/test_scorer.py` fixtures are stale** (they assume 30 questions, the set has 55),
   so 10 of its checks fail for that reason alone; regenerating the fixtures is a follow-up.
6. **Step 9 experiments** — `eval/failures.py` already groups the 22 failures by the
   scorer's own rules; the remaining work is the experiments you approve, each behind a
   flag and each with an eval before and after.

### Known limits worth repeating
- Two Drive PDFs are corrupt and contribute no text: `2005_Choudhary_Trans_boundary_Floods…`
  (truncated) and `2006_Komori_…` (0 pages). `data/raw/` is owner-only.
- The entailment judge is a 4B model. Its verdict is a reading aid; the page-checked
  quotation remains the arbiter (D-010, D-058).
- Everything above is measured at 97 documents / 851 pages. Nothing on this page is
  projected to 100k pages.

## Commands used for these numbers

```powershell
.venv\Scripts\python.exe -m ingest.pipeline build            # index, resumable
.venv\Scripts\python.exe -m ingest.bibliography build        # references only
.venv\Scripts\python.exe -m ingest.bibliography show         # coverage counts
.venv\Scripts\python.exe scripts/measure-entailment.py       # D-067 report
node scripts/ui-browser-check.mjs http://127.0.0.1:8000 "Who chaired the annual conservation action plan 2080 workshop?"
.venv\Scripts\python.exe eval/gate.py --current eval/runs/2026-11-19-step8-full `
  --baseline eval/runs/2026-11-18-step6-after-ui --start eval/runs/2026-11-18-step6-after-ui
```

Tests: `ingest/test_bibliography.py` 7/7, `ingest/test_pipeline.py` 12/12,
`ui/test_pipeline.py` 7/7, `ui/test_server.py` 8/8, `scripts/measure-entailment.py
--selftest` pass.
