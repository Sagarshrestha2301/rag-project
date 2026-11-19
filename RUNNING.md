# How to run this project

Everything runs offline on this machine. The model server is **Ollama**; the
pinned llama.cpp build was removed on 2026-11-13 because Ollama measured faster
on the same weights (499 tok/s prompt, 9.43 tok/s generation, against 293 and
7.46).

Model: **`qwen3.5:4b`** (4.2B, Q4_K_M, 3.3 GB), 4096-token context, temperature 0,
**thinking off**. It won the Step 2 comparison (23/30 against 18/30 for the 7B
and 16/30 for phi4-mini, and faster on every latency measure). Thinking must stay
off: with it on, qwen3.5 spends its whole answer budget on hidden reasoning and
returns an empty reply. `qwen2.5` 7B remains installed as the fallback.

---

## 1. Start the model

```powershell
.\scripts\launch-llm.ps1
```

That sets offline mode, binds Ollama to `127.0.0.1:11434`, and loads `qwen3.5:4b`
with a 30-minute keep-alive so the first question is not slowed by a cold start.

If the model is missing:

```powershell
ollama pull qwen3.5:4b
```

Plain Ollama also works if you do not want the script:

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11434"
ollama run qwen3.5:4b
```

## 2. Ask the model

> **Write `curl.exe`, not `curl`.** In Windows PowerShell 5.1, `curl` is an alias
> for `Invoke-WebRequest`, which sends a **GET** — Ollama answers `405 method not
> allowed` for a GET on `/api/chat`, `/api/generate` and `/v1/chat/completions`.
> `curl.exe` is the real program and works.

Native endpoint (`curl.exe`):

```powershell
curl.exe -s -X POST http://127.0.0.1:11434/api/chat -H "Content-Type: application/json" -d '{
  "model": "qwen3.5:4b",
  "stream": false,
  "options": { "temperature": 0 },
  "messages": [ { "role": "user", "content": "What was the 24-hour rainfall at Tistung in 1993?" } ]
}'
```

The same thing without any quoting pain, using PowerShell natively:

```powershell
$body = @{
  model   = "qwen3.5:4b"
  stream  = $false
  options = @{ temperature = 0 }
  messages = @(@{ role = "user"; content = "What was the 24-hour rainfall at Tistung in 1993?" })
} | ConvertTo-Json -Depth 5

(Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/chat" -Method Post `
  -Body $body -ContentType "application/json").message.content
```

OpenAI-compatible endpoint, which is what the project's own scripts use:

```powershell
curl.exe -s -X POST http://127.0.0.1:11434/v1/chat/completions -H "Content-Type: application/json" -d '{
  "model": "qwen3.5:4b",
  "temperature": 0,
  "messages": [ { "role": "user", "content": "Say OK" } ]
}'
```

Check what is loaded and how much VRAM it takes:

```powershell
ollama ps
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader
```

## 3. Score an answer run

The scorer takes a run file (one JSON line per question) and writes
`scores.json` plus `scores.md`:

```powershell
.venv\Scripts\python.exe eval\score.py --run <run.jsonl> --out <output-dir>
.venv\Scripts\python.exe eval\score.py --run <run.jsonl> --out <dir> --baseline <earlier-run.jsonl>
```

It refuses to score, and exits 3, if a cited file is outside `data/corpus/`, is
missing, or its SHA-256 does not match the gold record.

Prove the scorer itself still works (five fixtures, 30 checks):

```powershell
.venv\Scripts\python.exe eval\test_scorer.py
```

**Known stale:** the fixtures still count 30 questions, so 10 of these checks fail
against the 55-question set (the expected values, not the scorer, are old). Tracked as a
follow-up; until it is fixed, a failure here is not evidence of a scorer regression.

## 3b. Run the full generation eval

Answers every eval question through `generation/answer.py` — router, condense,
retrieval, gate, prompt, the local model and quote verification — with the cache off,
then writes `run.jsonl`, `meta.json` and `report.md` (latency, routes, refusals):

```powershell
.venv\Scripts\python.exe eval\run_generation.py --label step6-full
.venv\Scripts\python.exe eval\score.py --run eval\runs\<date>-step6-full\run.jsonl --out eval\runs\<date>-step6-full
```

`--only q001,q023` runs a smoke subset; `--resume` keeps finished lines and answers the
rest. It stops before the first question if Ollama is down or the model is not pulled.

## 3c. Enforce the regression gate

`eval/gate.py` is EVAL.md's gate as a script: the last accepted baseline and the
start-of-step baseline are compared with the current run on the dev set, and the exit
code is the verdict.

```powershell
.venv\Scripts\python.exe eval\gate.py `
  --current  eval\runs\2026-11-16-step6-full `
  --baseline eval\runs\2026-11-16-rebased-2026-11-16 `
  --start    eval\runs\2026-11-16-rebased-2026-11-16
```

- **Exit 0** every rule holds, **1** a rule is broken, **2** the runs cannot be compared
  (different question sets, missing run file, unreadable explanations file).
- Rules, in EVAL.md's numbering: 1 no pass-to-fail question without a written
  explanation, 2 and 3 no count metric down by two or more questions and MRR down by
  more than 1/N against either baseline, 4 not-found (a) down at all.
- A pass-to-fail question is accepted only with a reason: `--explain "q029=table row
  absent from the six passages"`, or `--explanations notes.txt` with one `qID: reason`
  per line.
- The gate **re-scores the raw runs** with `eval/score.py` and never trusts a stored
  `scores.json`, so all three runs are measured by today's scorer.
- It compares only what both runs measured. A retrieval-only run has no answers, so its
  citation, numeric, not-found and passed figures print as `unmeasured` rather than 0,
  and the gate says `SKIP` instead of inventing a regression.
- `--milestone` gates the held-out split instead (end of Steps 5, 6 and 8).

Measured on 2026-11-17: the pair above passes (recall@5 37/39 both sides, MRR 0.831 vs
0.834, one question = 0.026), and the same check fails on a deliberately regressed copy
of that run in every rule it breaks. Proof logs: `artifacts/gate-demo/` and
`artifacts/gate-demo-one/`.

## 4. Run the oracle benchmark

Gives the model the gold page for every question and scores its answers — the
current quality baseline for the generator:

```powershell
.venv\Scripts\python.exe benchmarks\llm\oracle_run.py --model qwen3.5:4b --no-think --out benchmarks\llm/oracle-qwen3.5-4b-nothink-ollama.jsonl
.venv\Scripts\python.exe eval/score.py --run benchmarks/llm/oracle-qwen3.5-4b-nothink-ollama.jsonl --out benchmarks/llm/scores-qwen3.5-4b-nothink
```

Last measured for the current model: **23/30 pass** (dev 17/20, held-out 6/10),
citations 20/30, numeric 23/24, not-found 3/3 and 26/26, median 4.9 s.
`--no-think` is required for qwen3.5; drop `--model`/`--no-think` to re-run the
7B fallback as `qwen2.5:latest`.

## 5. Build the page index

`python -m ingest.pipeline build` is the one command that takes `data/corpus/` to a
searchable index. It walks the corpus, records what it did in `index/manifest.sqlite`, and
works only on documents that are new, changed or unfinished:

```powershell
.venv\Scripts\python.exe -m ingest.pipeline build                  # everything still pending
.venv\Scripts\python.exe -m ingest.pipeline build --limit 5        # five documents, then stop
.venv\Scripts\python.exe -m ingest.pipeline status --report        # counts + reports\full-ingestion.md
.venv\Scripts\python.exe -m ingest.pipeline backup --out backups\2026-11-19
.venv\Scripts\python.exe -m ingest.pipeline restore --from backups\2026-11-19
```

Six stages, in order; `--stages scan,parse` runs a subset:

| Stage | What it does | Where the result goes |
|---|---|---|
| `scan` | SHA-256, size and page count of every corpus PDF; flags duplicates | manifest rows |
| `parse` | `corpus.parse_document` + `ingest.manifest.parse_document`, one document at a time | `index/parsed/shards/<sha>.{search.json,structure.jsonl,summary.json}` |
| `assemble` | concatenates the shards in corpus order | `index/pages.json` (search) and `index/parsed/pages.jsonl` (chunking) |
| `bibliography` | one local-model call per new document: title, authors, year, venue, DOI from its header pages (D-066) | `index/bibliography.json` |
| `chunk` | one record per chunk | `index/chunks.jsonl` |
| `embed` | bge-small-en-v1.5 on CPU, per document | LanceDB table `chunks` in `index/lancedb/` |

`bibliography` is the only stage that calls a model, and it never fails the run: if Ollama
is down the DOI and year are still read off the page and the rest stays blank, and the UI
falls back to the short label. Run it alone when you only want references:

```powershell
.venv\Scripts\python.exe -m ingest.bibliography build      # resume-safe, one call per new document
.venv\Scripts\python.exe -m ingest.bibliography show       # counts, then a few references
```

Every field is checked against the page it was read from — a title or author that the
model returns but the page does not print is dropped and the reason is recorded — so a
blank field means "not printed", not "not tried".

**Measured on 2026-11-19** on the current corpus (97 documents / 851 pages):

- parse: **1,414 s summed over the 97 documents** (86 pages OCR'd at about 4 s each). The
  run's total wall time is not recorded - the background shell was killed after the work
  finished and before the summary line flushed - so the parse figure is measured and the
  embed figure is **not measured separately**.
- chunk: **3,226 chunks**; embed: **3,226 vectors, 384-dim, all unit length, no zeros**,
  counted straight out of LanceDB after the run.
- `index/` totals **41,969,013 bytes (40 MB)**; the per-artifact table is in
  `reports/full-ingestion.md`.
- **Nothing else changed:** `index/pages.json`, `index/chunks.jsonl` and
  `index/parsed/pages.jsonl` have the same SHA-256 before and after the Step 8 refactor -
  `395c5a2b…`, `1208cb59…`, `f7e82daf…` (see `artifacts/step8/baseline/artifact-hashes.txt`).
  The pipeline reproduces the index the eval was measured on, byte for byte.
- A second `build` with nothing changed takes **1.6 s** and parses nothing.

- **Resume is per document.** A manifest row's status is written only after that
  document's work is on disk, so a kill costs at most the document in flight; the next run
  starts from the unfinished ones. Killing and resuming is a case in
  `ingest/test_pipeline.py` ("a killed run resumes where it stopped"), along with eleven
  others.
- **Adding a document, in one command:**

  ```powershell
  .\scripts\add-document.ps1 -Path C:\inbox\2019_report.pdf            # corpus root
  .\scripts\add-document.ps1 -Path C:\inbox\scan.pdf -Folder reports   # keeps a folder
  ```

  It hardlinks the PDF into `data\corpus\<folder>\` (copying when the volumes differ),
  refuses a file name the corpus already has — the loader identifies a document by name,
  so two `report.pdf` are an error, not two documents — then runs the pipeline, which
  parses, chunks and embeds **only the new document**, and prints the before/after counts
  and measured time. A file under `data\raw\` keeps its folder relative to `data\raw`;
  `data\raw` itself is never modified. It exits 1 on any refusal. PDFs only: convert Word
  files with the pinned LibreOffice to `<name>.docx.pdf` first.
- **Duplicates are flagged, never deleted.** Same SHA-256 under another name, or pages at
  least 80% the same text as an indexed document, become `duplicate` with `duplicate_of`
  set and are left out of the index; `status` lists them. This is why a stray copy cannot
  skew retrieval, and why nothing on disk moves.
- **After adding documents, three checks:**
  1. re-run `.venv\Scripts\python.exe scripts\recheck-not-found.py` and read
     `reports/not-found-recheck.md`. An unanswerable question becomes a **false** answer the
     moment the corpus starts stating its fact, and D-027 says a not-found question may only
     be replaced with owner approval - so the report lists the pages and leaves the verdict
     to the owner.
  2. Word files: convert once with the pinned LibreOffice **26.8.2.2** (headless) into
     `data\corpus\<name>.docx.pdf`, rename after conversion (`--convert-to pdf` writes
     `<stem>.pdf`), and never convert again silently - every gold page and citation refers to
     the stored PDF (D-023, D-030).
  3. run the offline proof if the change touched anything that could reach the network:
     `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\offline-generation-proof.ps1`
     from an elevated prompt (`scripts\offline-check.py` is the self-test it uses).
- **Backups are complete.** `backup` copies the manifest (through SQLite's backup API), the
  artifacts, the shards and `index/lancedb/` — **40 MB** for this corpus. `restore --from`
  into a folder was verified on the real index: restored `pages.json` and `chunks.jsonl`
  are byte-identical to the live ones (`395c5a2b…`, `1208cb59…`), all 3,226 dense rows came
  back, and the restored index answered a BM25 query with the same top page.
- **Scans are fine:** a page with under 40 characters of text is OCR'd during `parse` and
  marked `source: "ocr"` in the index (86 pages here). Pages that stay empty are listed by
  `status` and `/api/health`: **8 documents have at least one** (19 pages).
- **Scale:** this is measured on 97 documents / 851 pages. The 100k-page target is an
  owner scope decision (D-063); nothing above is projected to it.
- **No working-directory dependency:** `corpus.CORPUS` and `corpus.INDEX_CACHE` are
  absolute and derived from the project folder, so this works from any directory.

## 6. Ask a question

Two front ends sit on the same page index and the same answer path: the CLI and the eval
call `generation.answer` directly, and the chat UI streams that same call (D-061). What
the eval scores is what the browser shows.

### 6a. The generation pipeline (router, gate, verified citations, cache)

```powershell
# one question
.venv\Scripts\python.exe -m generation.answer "What was the 24-hour rainfall depth at Tistung?"

# a follow-up: the previous question lets "and at Ghantemadi?" be rewritten before search
.venv\Scripts\python.exe -m generation.answer "and at Ghantemadi?" --history "What was the 24-hour rainfall depth at Tistung?"

# the whole record as JSON (route, gate, passages, citations, timings), or a fresh answer
.venv\Scripts\python.exe -m generation.answer "Summarise this paper" --json
.venv\Scripts\python.exe -m generation.answer "…" --no-cache
```

What happens, in order:

| Step | Module | What it decides |
|---|---|---|
| 1 | `generation/router.py` | route: `greeting` (no retrieval, no model), `followup` (condense first, 5 passages), `summary` (6 passages, summary rules), `table` (6 passages, table rules) or `normal` (5 passages) |
| 2 | `generation/condense.py` | only for a follow-up, and only when there is a previous turn: rewrite the question so a pronoun has a subject |
| 3 | `generation/cache.py` | answer already known for this question, index, model and prompt? (see below) |
| 4 | `corpus.search` | BM25 over pages: the top `k` passages for the route |
| 5 | `generation/gate.py` | `pre_ask`: best score below 15 → refuse without calling the model |
| 6 | `generation/prompt.py` | number the passages `[1]…[n]`, add the citation rules and the route's extra rules |
| 7 | Ollama `qwen3.5:4b` | temperature 0, thinking off, 4096-token context |
| 8 | `generation/verify.py` | every `[n]` must be a passage that was shown; every quotation must exist, character for character, on the page it cites; every number a sentence states must be on a page that same sentence cites; one retry, then `unverified` |
| 9 | `generation/gate.py` | `resolve`: `verified`, `not_found` or `unverified` |

Answers use **`[1]…[n]` passage numbers** and end with one citation line per number, which
is what makes them checkable:

```
540 mm fell in 24 hours at Tistung [1].

[1] 1970_Marahatta_Relating_Hydrological_Extremes_with_Area_A_Case_on_Extreme_F_W2121362616.pdf, p. 2: "the 24-hour rainfall depth of 540 mm at Tistung"
```

When the passages do not answer the question the reply is exactly
`Not found in the indexed documents.` — from the floor with no model call, or from the
model itself. The command exits 1 when the status is `unverified`, so a script can tell.

**The answer cache** (`index/answer-cache.json`) is a hit only when *all* of these still
match: the normalised question, the index signature, the model digest, the prompt version,
a hash of the text of every cited page, and the index the process holds against the corpus
on disk (`corpus.is_current`). Measured: **0.4-0.6 s for a hit against 19.1 s to generate**.
An `unverified` answer is never cached, and `--no-cache` bypasses the cache entirely.

### 6b. The chat UI (the shipped pipeline, streamed)

```powershell
.\scripts\open-chat.ps1 -Start        # Ctrl+C stops it
```

Then open **http://127.0.0.1:8000**. Streaming answers, conversations kept in the browser,
stop mid-answer, copy, regenerate, light/dark theme, and live tokens/second under each
reply. **Save chat** downloads the conversation as Markdown with its sources.

**Clicking a citation (`[1]`) or an evidence card opens the cited page in the UI**, with the
quotation highlighted - no browser tab, no plugin. `ui/static/citation-viewer.js` renders
the page with pdf.js (`ui/static/vendor/pdfjs/`, pinned 4.10.38, imported on the first
click) and marks the words by measuring the page's own text layer; `←`/`→` and `Esc`
navigate and close, and *Open PDF* is still there for the browser's own viewer. If pdf.js
cannot read a file the click falls back to that tab, so nothing new can block reading.

It has **no answer path of its own**: `ui/pipeline.py` calls `generation.answer` — router,
condense step, not-found gate, prompt, quote verifier and its one retry, and the cache are
the code `eval/` measures (D-061). So the screen shows `verified`, `not_found`,
`unverified` (a streamed answer is retracted in place when the verifier rejects it),
`streaming` and `error`, with **numeric citation chips** `[1]`-`[5]` rather than the old
prototype's `[A]`-`[D]`. Each chip opens the corpus PDF at the cited page (verified on 10
answers / 13 links, 2026-11-19) and OCR pages are marked `· OCR`. `/api/health` reports
documents, pages, OCR pages and unreadable pages from `index/pages.json`, and `qwen3.5`'s
literal ` thinking` tags are stripped from the stream.

One honest limit: OCR occasionally loses a hyphen inside a numeric range — the paper's
`calcite (5-10 %)` comes back as `(510 %)` — so numbers from a scanned page deserve a
glance at the PDF, which the citation chip makes easy.

Options, if you want a different port or model:

```powershell
$env:CHAT_MODEL = "qwen3.5:4b"   # or "qwen2.5" for the 7B fallback
$env:CHAT_THINK = "0"           # keep 0 for qwen3.5, or the replies come back empty
$env:CHAT_KEEP_ALIVE = "30m"    # how long Ollama keeps the model resident
.venv\Scripts\python.exe -m uvicorn ui.server:app --host 127.0.0.1 --port 8001
```

Stop it with `Ctrl+C` in that terminal (or stop the python process on that port). The server
loads the page index once, so **after a corpus change, restart it**.

## 7. Check the environment

```powershell
.venv\Scripts\python.exe -m pip check
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader
git status
```

## If something fails

| Symptom | Cause and fix |
|---|---|
| `405 method not allowed` | You used `curl` in Windows PowerShell 5.1, which is `Invoke-WebRequest` and sends GET. Use `curl.exe`, or `Invoke-RestMethod -Method Post`. `GET http://127.0.0.1:11434/` returning 200 only proves the server is up, not that the request was right. |
| Connection refused on 11434 | Ollama is not running, or `OLLAMA_HOST` points elsewhere. Start it with `ollama serve`, or just `ollama list` to check the model file is present. |
| `model 'qwen3.5:4b' not found` | `ollama pull qwen3.5:4b`. The store is content-addressed; the local IDs are `d8b0f5e9760c` (qwen3.5 4B) and `78fad5d182a7` (phi4-mini). |
| Answers are empty strings | Thinking was left on for qwen3.5. Start the UI with `CHAT_THINK=0` and the launcher without `-Think`; with it on, the model spends the budget reasoning and emits nothing. |
| First answer takes ~10 s longer | The model was unloaded. `ollama ps` shows `UNTIL`; the launcher sets 30 minutes. |
| Answers crawl | `ollama ps` shows the CPU/GPU split. Our 7.6B model runs at 55%/45% on 4 GB VRAM; close other GPU apps (`ollama stop`, browsers with hardware acceleration). |
| Prompt rejected as too long | Context is 4096 tokens. Retrieved passages plus history must stay under roughly 3.5k. |
| `status: unverified` (exit 1) | The answer's quotations, or a number a sentence states, were not found on the pages they cite, after one retry. Re-ask, or open the cited page: the verifier is meant to fail here rather than pass a claim nobody can check. |
| A question answers in well under a second every time | It is a cache hit: same question, index, model and prompt. Use `--no-cache` to force a fresh answer. |
| `build` finishes in seconds and parses nothing | Nothing changed: every manifest row is `embedded`. A changed file is detected by SHA-256, so an edit is picked up on the next run without deleting anything. |
| `status` lists a document as `duplicate` | The same bytes under another name, or at least 80% of its pages repeat an indexed document. It is left out on purpose; `duplicate_of` names the file that is indexed. Nothing was deleted. Rename or remove the copy yourself if you want it gone. |
| A document is `failed` | `status` prints the error. Fix the PDF (or the parser), then run `build` again: failed documents are retried, finished ones are not re-parsed. |
| `restore` and the answers differ from before the backup | Restore with `python -m ingest.pipeline restore --from <backup>` and stop the UI server while it runs - copying folders by hand can mix a new `pages.json` with an old `lancedb/`. |

## Notes and limits

- **Context is 4096 tokens.** A prompt of 4226 tokens is rejected outright. Keep
  retrieved passages plus history under about 3.5k tokens, and leave room for the
  answer. Routes ask for 5 passages (normal, follow-up), 6 (table, summary) or none
  (greeting), which is why `--k` stays inside that budget rather than free.
- **Generation is about 10.5 tok/s** at 4B, and first token at 3.64 s for a
  2,323-token prompt, so a 120-token answer lands inside the 20 s target. Long
  answers are the slow case: 343 tokens took 44.8 s.
- **VRAM is 4 GB.** The 4B model peaks at 3.7 GB including context, leaving
  roughly 400 MiB — enough for the model, not for a GPU reranker (D-004 keeps it
  on CPU). Closing other GPU applications buys headroom.
- **Ingestion is measured on 97 documents / 851 pages**, not on the 100k-page target: a
  full parse summed to 1,414 s (OCR ~4 s/page) and produced 3,226 chunks / 3,226 vectors on
  CPU, with `index/` at 40 MB. Nothing here is projected to 100k pages (D-063); the
  manifest and per-document resume were built so that scale is possible, not proven.
- **Embedding is CPU-only** (D-054 / rule 10). A GPU embed would be faster, but it competes
  with the LLM for 4 GB and no benchmark has been run; the pipeline keeps the embedder on
  CPU deliberately.
- **Stop the model** with `ollama stop qwen3.5:4b` (frees VRAM immediately).
- Tags and approvals are the owner's: `step-NN-approved` in git, and lines in
  `APPROVALS.md`.
