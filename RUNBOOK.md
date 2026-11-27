# Runbook — operate the system, in order

`RUNNING.md` is the reference (what each module does and why). This page is the
procedure: every command here was run in this order on 2026-11-20 and the output is kept
in `artifacts/step9/runbook-test.log`. If a step does not print what the "you should see"
column says, stop and use §8 before going on.

Everything is local. Nothing here downloads, and nothing here edits `data/raw/` or the
PDFs in `data/corpus/`.

---

## 0. Before you start

```powershell
git status --short        # must print nothing (AGENTS.md rule 14)
ollama list               # must list qwen3.5:4b
.venv\Scripts\python.exe -m ingest.pipeline status
```

You should see a clean tree, the pinned model, and **187 files / 2,669 pages** with
`embedded 186`, `failed 1`, `pending 0`. The one failure is the known PyMuPDF crash
(§9), not a fault of this machine. If `status` shows a second failure, or anything
pending, run §4 first.

Approvals and step state live in `APPROVALS.md` and `TRACKER.md`; the measured numbers
behind this page are in `STATUS.md`.

---

## 1. Start

### 1a. The model server

```powershell
.\scripts\launch-llm.ps1                 # binds Ollama to 127.0.0.1 and keeps the model warm
curl.exe -s http://127.0.0.1:11434/api/tags    # JSON listing qwen3.5:4b
```

`launch-llm.ps1` sets the offline variables (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`,
`HF_DATASETS_OFFLINE=1`); the ingestion and UI scripts set them too, so a shell without
them is still offline.

### 1b. The chat UI

```powershell
.\scripts\open-chat.ps1 -Start           # foreground; it prints the URL it chose, Ctrl+C stops it
```

Open the URL, or check it without a browser:

```powershell
curl.exe -s http://127.0.0.1:8300/api/health   # use the port the launcher printed
```

Expect `documents` 186, `pages` 2,669, `ocr_pages` 222 and `unreadable` listing 22
documents / 62 pages.
The server binds **127.0.0.1 only**; another machine cannot reach it.

The port is 8000 unless `$env:UI_PORT` says otherwise; `-Port` wins over both.
`open-chat.ps1` measures the port first, because Windows reserves long ranges for
Hyper-V/WinNAT and a bind inside one fails with WinError 10013 while nothing is
listening. If 8000 is reserved it starts on a free port in 8300-8599 and prints
which one. `health.ps1` follows `UI_PORT` but not that swap, so pass `-UiPort`.

### 1c. The same pipeline from a terminal

```powershell
.venv\Scripts\python.exe -m generation.answer "What was the 24-hour rainfall depth at Tistung?"
```

You should see a `verified` answer with `[1]` markers and a citation line, and
`status: verified`. The UI streams this same call (D-061); there is no second prompt.

From your own client, `POST /api/chat` takes `{"messages": [{"role": "user", "content":
…}], "use_cache": true}` (not a `message` field) and answers with **one raw JSON object
per line** — `{"event": "start"}`, then `{"event": "token", "text": …}` per piece, then
`{"event": "done", "payload": {…}}`. A cached answer sends `start` and `done` with no
tokens, which is correct, not an error.

---

## 2. Stop

```powershell
ollama stop qwen3.5:4b     # frees the VRAM immediately
```

Stop the UI with `Ctrl+C` in its window. If it is running detached, stop the process that
is **listening** on the port the launcher printed (8000, or the substitute in 8300-8599) —
the `.venv` interpreter is a trampoline and its child is the real listener:

```powershell
netstat -ano | findstr :8000        # or :8300 if the launcher reported a substitute
```

Read the **LISTENING** line; ignore `TIME_WAIT`.

```powershell
taskkill /PID <pid> /F
```

---

## 3. Add documents

Do these four steps in this order; step 3.2 is not optional (D-027).

### 3.1 Put the PDF in the corpus and ingest only it

```powershell
.\scripts\add-document.ps1 -Path C:\inbox\2019_report.pdf              # corpus root
.\scripts\add-document.ps1 -Path C:\inbox\scan.pdf -Folder reports     # keeps a folder
```

It hardlinks the file into `data\corpus\` (copies when the volumes differ), refuses a
name the corpus already has, then runs `ingest.pipeline build`, which parses only the new
or changed document, and prints the document and page counts before and after with the
measured time. **PDFs only.**

### 3.1a A staged folder of PDFs (a wave)

Stage the files under `data\raw\incoming-wave-NN\` (owner-only), then:

```powershell
.venv\Scripts\python.exe -m ingest.pipeline add-batch --from data\raw\incoming-wave-00 --wave 00
```

It checks every file before placing anything, and exits 1 with a list when a file is not a
PDF, is outside `data\raw`, repeats a name inside the batch, or repeats a name the corpus
has with different bytes. A file whose bytes are already indexed, or repeat an earlier
file in the same batch, is **skipped** and listed with the document it repeats; the rest
of the batch still lands. A refused batch places nothing. Accepted files are hardlinked with their folder relative to `data\raw`, one row
per file goes to `logs\wave-additions.jsonl`, the wave is recorded in the manifest's `meta`
table, and `build` runs on the new documents. Re-running the same folder reports
`unchanged` and adds nothing; `--no-build` places the files without parsing.

### 3.2 Re-check the not-found questions

```powershell
.venv\Scripts\python.exe scripts\recheck-not-found.py
```

Read `reports/not-found-recheck.md`. Each of the 7 unanswerable questions is listed with
its best BM25 pages and the pages that contain every distinctive term. If a document now
states the fact, the question is no longer a valid not-found question: propose a
replacement of the same type to the owner. **Never change `eval/questions.jsonl`
silently** (D-027; that file is protected).

### 3.3 Word files: convert once, with the pinned version

```powershell
& "C:\Program Files\LibreOffice\program\soffice.exe" --headless --convert-to pdf --outdir <tmp> <file>.docx
```

Then rename the result to the full original name plus `.pdf` (`report.docx` becomes
`report.docx.pdf`) and add it with §3.1. LibreOffice is pinned at **26.8.2.2** (D-023).
Never convert a file a second time silently: every gold page, citation and UI link points
at the stored PDF.

### 3.4 Restart the UI, then re-check the offline proof

The UI holds its page index in memory, so **restart it** after a corpus change (§1b).

If the change could reach the network (a new parser, a new model), prove it cannot:

```powershell
# from an ELEVATED prompt - creating firewall rules needs it
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\offline-generation-proof.ps1
```

The script blocks the interpreter and Ollama at Windows Firewall, runs
`scripts\offline-check.py` first and refuses to start the eval unless the block is
proven. From a normal prompt it fails with `Access is denied` (Windows System Error 5) -
that is the shell, not the pipeline.

---

## 4. Rebuild the index

```powershell
.venv\Scripts\python.exe -m ingest.pipeline build                  # only what is pending
.venv\Scripts\python.exe -m ingest.pipeline build --limit 5        # five documents, then stop
.venv\Scripts\python.exe -m ingest.pipeline build --stages scan,parse
.venv\Scripts\python.exe -m ingest.pipeline status --report        # also writes reports/full-ingestion.md
```

Five stages run by default: `scan`, `parse`, `assemble`, `chunk`, `embed` — add `--jobs 8`
to parse eight documents at once (1.41x measured 2026-11-22). A row's status
is written only after that document's work is on disk, so killing the run costs at most
the document in flight and the next run continues. **A build with nothing changed takes
a few seconds** — 6.9 s measured 2026-11-20 on the then 97-document corpus and not
re-measured since it grew to 187 files, mostly the corpus signature walk; if it is
parsing, something did change (the SHA-256 comparison is the detector).

`bibliography` is the sixth stage and is **opt-in**: one model call per document (8.2 s
measured, ~45 h for 20,000), for the reference line in the evidence rail only. Fill it on
demand with `python -m ingest.bibliography build` (resumes per document by SHA-256), or add
it to a build with `--stages scan,parse,assemble,bibliography,chunk,embed`. A document with
no record keeps its file-name label in the UI. It is the only stage that calls the model:
if Ollama is down it degrades instead of failing.

Expect `embedded 186`, `failed 1` (the known crash), `duplicate 0`, 11,334 chunks and
11,334 dense rows.

---

## 5. Backup

```powershell
.venv\Scripts\python.exe -m ingest.pipeline backup --out backups\2026-11-20
```

Writes about **120 MB** (the index alone is 121,165,771 bytes): the manifest (through
SQLite's backup API), `pages.json`,
`chunks.jsonl`, `parsed/` shards and `lancedb/`. A backup that omits LanceDB would need a
re-embed on restore, which is why it is included.

---

## 6. Restore

```powershell
.venv\Scripts\python.exe -m ingest.pipeline restore --from backups\2026-11-20 --index backups\restore-check\index
```

Restore into a **different** folder first and compare, rather than over the live index.
`pages.json` and `chunks.jsonl` must come back byte-identical:

```powershell
.venv\Scripts\python.exe -c "import hashlib,pathlib; [print(p, hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()[:16]) for p in ('index/pages.json','index/chunks.jsonl','backups/restore-check/index/pages.json','backups/restore-check/index/chunks.jsonl')]"
```

Expected for this corpus: `pages.json` **395c5a2b…** and `chunks.jsonl` **1208cb59…**, the
same on both sides. To go back to a backup in place, stop the UI first and restore with
the default `--index index`.

---

## 7. Verify the install

```powershell
.venv\Scripts\python.exe ingest\test_pipeline.py       # resume, duplicates, backup/restore
.venv\Scripts\python.exe generation\test_verify.py     # the quote and number verifier
.venv\Scripts\python.exe generation\test_answer.py     # the retry budget guard (D-072)
.venv\Scripts\python.exe generation\test_cache.py      # the cache key and page guard
.venv\Scripts\python.exe retrieval\test_tables.py      # both table passes (off by default)
.venv\Scripts\python.exe eval\test_scorer.py           # the scorer against the gold data
.venv\Scripts\python.exe ui\test_pipeline.py
.venv\Scripts\python.exe ui\test_server.py
node scripts\ui-browser-check.mjs                       # one question, warning + viewer
node scripts\ui-starters-check.mjs                      # all four starter cards and their chips
.venv\Scripts\python.exe eval\gate.py --current eval\runs\2026-11-20-step9-retry-guard --baseline eval\runs\2026-11-20-step9-retry-guard --start eval\runs\2026-11-19-step8-full
```

The two browser checks need the server running (§1) and a page the corpus can answer; they
drive the installed Chrome, install nothing, and touch nothing outside 127.0.0.1. The gate
exits 0 when no rule breaks; see `RUNNING.md` §3c for the rules and `EVAL.md` for the
thresholds. A fresh full eval is §7b in `EVAL.md`'s protocol (about 25-40 min).

---

## 8. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `405 method not allowed` | `curl` in PowerShell 5.1 is `Invoke-WebRequest` and sends GET. Use `curl.exe` or `Invoke-RestMethod -Method Post`. |
| Connection refused on 11434 | Ollama is not running. Start it with `.\scripts\launch-llm.ps1` or `ollama serve`. |
| Empty answers | Thinking was left on for qwen3.5. Set `CHAT_THINK=0`; with it on the model spends its budget reasoning and emits nothing. |
| `status: unverified` (exit 1) | A quotation, or a number a sentence states, was not on the page it cites, after one retry. Open the cited page rather than trusting the sentence. |
| Answers come back in under a second | A cache hit: same question, index, model and prompt. `--no-cache` forces a fresh answer. |
| `build` parses nothing in 2 s | Nothing changed. An edited file is detected by SHA-256, so `build` alone is enough. |
| A document is `duplicate` | The same bytes under another name, or ≥80% of its pages repeat an indexed document. It is left out on purpose; `duplicate_of` names the original. Nothing was deleted. |
| A document is `failed` | `status` prints the error. Fix the PDF, then run `build` again; finished documents are not re-parsed. |
| Restored answers differ from before the backup | Restore with `restore --from`, with the UI stopped. Copying folders by hand can mix a new `pages.json` with an old `lancedb/`. |
| The not-found line is shown for a question you know is answered | Read the warning: 62 of 2,669 pages have no readable text after OCR, and the answer may be on one of them. Check `reports/not-found-recheck.md` before blaming the gate. |
| `Access is denied` from an offline-proof script | The shell is not elevated. Firewall rules need an administrator prompt. |
| `WinError 10013` binding `127.0.0.1:8000`, nothing in `netstat` | Windows reserved the port for Hyper-V/WinNAT. `netsh interface ipv4 show excludedportrange protocol=tcp` lists the ranges. `open-chat.ps1` works around it by starting on a free port in 8300-8599 and printing it; `$env:UI_PORT` pins one. To give 8000 back for good, in an **elevated** shell: `net stop winnat`, `netsh int ipv4 set dynamicport tcp start=49152 num=16384`, `net start winnat` (this stops Hyper-V from reserving ports below 49152; it affects every program on the machine). |

`RUNNING.md`'s "If something fails" table has the rest.

---

## 9. Known limits

- **62 of 2,669 pages (2.3%) have no readable text after OCR**, in 22 documents; 222
  pages were read by OCR. Above the 1-2% band D-020 uses to decide, and reported to the
  owner rather than hidden. An OCR'd page can lose a hyphen inside a number
  (`5-10 %` → `510 %`), so a number from a scan deserves a look at the PDF.
- **Two corpus PDFs contribute no text**: `2005_Choudhary_Trans_boundary_Floods…` (truncated)
  and `2006_Komori_Scars…` (0 pages). `data/raw/` is owner-only; replacing them is the
  owner's call.
- **Latency is p50 14.4 s, p95 48.7 s** end to end on the latest graded run (4B model,
  4 GB VRAM). A larger model does not fit profitably.
- **Citation is a capped rule since step 18** (D-097, revising D-041): at least one cited
  page must be a gold page, every quotation must be verbatim on the page it names, and at
  most **two** cited pages may be outside the gold set (`extra_citations` reports how
  many). Quotations are read through `corpus.page_text`, the same reader the pipeline uses
  (step 19, D-098). One character is tolerated: a quotation may differ in the case of its
  first letter and nowhere else (step 20, D-100). That is a measurement choice, not an
  invented source.
- **The parse and chunk figures above (1,414 s, 3,226 chunks) were measured at 97
  documents / 851 pages.** The live corpus is 187 files / 2,669 pages / 11,334 chunks.
  Nothing here is projected to 100k pages; that is a separate corpus-and-hardware
  decision (D-063).
- **The not-found decision is the model's**, with a floor at top-1 BM25 < 15 (D-058). The
  prompt's exact refusal line counts when the answer cites nothing (D-090); D-060's prose
  rule was measured and rejected (D-068).

---

## 10. Results, as of 2026-11-27

The number to quote is the **last accepted baseline**, `2026-11-24-repro-a`, re-scored under
the current contract (prompt `s6-6`, steps 18-19). The latest graded run is quoted beside it
because it is measured but **not yet accepted** (D-093/D-094/D-100 are open):

| Metric | Value |
|---|---|
| Passed | **41/55 accepted** (`2026-11-24-repro-a`, dev 34/45, held-out 7/10); latest graded run **44/55** (`2026-11-27-step20-first-letter`, dev 37/45, held-out 7/10) |
| Retrieval | recall@5 **45/48**, recall@10 46/48, MRR **0.839** |
| Citation / numeric | 38/48 / 37/43 accepted; 39/48 / 38/43 latest |
| Not-found (a) / (b) | 3/6 / 46/48 accepted; 5/6 / 46/48 latest |
| Latency (latest graded run) | p50 **12.7 s**, p95 **44.3 s** |
| Corpus and index | 187 files, 2,669 pages, 11,334 chunks, 121 MB index |
| Offline proof | Step 6 **PASS** 2026-11-17 with output; Steps 7 and 8 **PASS on the owner's own runs** (reported 2026-11-20/21, no artifact supplied) |

Three experiments measured on 2026-11-20 were **rejected**: accepting a refusal in the
model's own words (it turned two answerable questions into a false "not found", D-068), the
page-level table pass (no gold page gained, D-070), and adding a page's table rows to its
passage (the table prompt is already ~4,100 tokens, so it truncated and the model refused,
D-073). Both table passes are still in the code, off, behind `CHAT_TABLE_RETRIEVAL` and
`CHAT_TABLE_CONTENT`. A cross-encoder rerank of the top 10 (2026-11-22, D-081) is also in
the code and **off**: `CHAT_RERANK=1` turns it on, `CHAT_RERANK_DEPTH` sets how many pages
it reads (default 10) and `CHAT_RERANK_ANCHOR` keeps BM25's own first pages in front. It
needs `models/ms-marco-MiniLM-L-6-v2` and adds about 0.4 s per question on CPU. The rules **in** the table are the per-sentence quotation rule (D-071) and the list rules (D-093) carried by prompt `s6-6`, the `s6-6` list-shape check (D-094), the retry guard (D-072), and the step-18/19 scoring contract (the two-extra-page cap, D-097; one page-text reader, D-098). The full row-by-row history is `EVAL.md`; the latest graded run is `eval/runs/2026-11-25-step17-list-shape/`, and the ranked next steps are in `reports/next-experiments.md`.
