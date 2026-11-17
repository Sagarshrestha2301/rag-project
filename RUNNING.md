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

`corpus.build()` parses every PDF under `data/corpus/`, OCRs any page with no text layer,
and caches the result in `index/pages.json`. It is the only step between a PDF and being
searchable:

```powershell
.venv\Scripts\python.exe -c "import corpus; i=corpus.build(); print(len(i['docs']), 'documents', len(i['pages']), 'pages,', i['ocr_pages'], 'OCR pages')"
```

Measured on the current corpus: **97 documents / 851 pages, 86 OCR pages, 996 s (~17 min)**
— about 51 pages/min, with OCR at roughly 4 s/page. Every rebuild re-parses every
document, so after adding files run this once from the terminal instead of letting a
user's first question pay for it.

- **The index is a cache, not the authority.** It stores a *signature* (file name, size and
  mtime per document) and `build()` re-parses when the signature changes, so a new or
  edited PDF is picked up on the next build by itself. Deleting `index/pages.json` is never
  required; `corpus.build(force=True)` is the explicit way to force a full re-parse.
- **Adding a document, in one command:**

  ```powershell
  .\scripts\add-document.ps1 -Path C:\inbox\2019_report.pdf            # corpus root
  .\scripts\add-document.ps1 -Path C:\inbox\scan.pdf -Folder reports   # keeps a folder
  ```

  It hardlinks the PDF into `data\corpus\<folder>\` (copying when the volumes differ),
  refuses a file name the corpus already has — the loader identifies a document by name,
  so two `report.pdf` are an error, not two documents — then rebuilds the index and
  prints the document and page counts before and after, with the rebuild time. A file
  under `data\raw\` keeps its folder relative to `data\raw`; `data\raw` itself is never
  modified. It exits 1 on any refusal. PDFs only: convert Word files with the pinned
  LibreOffice to `<name>.docx.pdf` first. The new file is ranked against the old ones in
  the same pass; there is one index, not one per document.

- **Scans are fine:** a page with under 40 characters of text is OCR'd at build time and
  marked `source: "ocr"` in the index (86 pages here). Pages that stay empty are listed in
  `i["unreadable"]` — 8 documents have at least one — and `/api/health` reports the count.
- **No working-directory dependency:** `corpus.CORPUS` and `corpus.INDEX_CACHE` are
  absolute and derived from the project folder, so this works from any directory.

## 6. Ask a question

Two front ends sit on the same page index. They do **not** yet share the same answer path:
the pipeline below is Step 6, and the chat UI is still the older prototype. Step 7 replaces
the prototype's answer path with the pipeline.

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
| 8 | `generation/verify.py` | every `[n]` must be a passage that was shown; every quotation must exist, character for character, on the page it cites; one retry, then `unverified` |
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

### 6b. The chat UI (prototype: streaming, letter citations, no verification)

```powershell
.\scripts\open-chat.ps1 -Start        # Ctrl+C stops it
```

Then open **http://127.0.0.1:8000**. Streaming answers, conversations kept in the browser,
stop mid-answer, copy, regenerate, light/dark theme, and live tokens/second under each
reply. **Save chat** downloads the conversation as Markdown with its sources.

What it does today: BM25 over pages with `CHAT_TOP_K` passages (4 by default), **letter
citations `[A]`-`[D]`**, no router, no not-found floor, no quotation verification and no
answer cache. It is the prototype from before Step 6, and Step 7 replaces its answer path
with 6a — until then, use 6a when an answer has to be checked.

Operational details that still apply to it: source chips open the corpus PDF at the cited
page (OCR pages are marked `· OCR`), `/api/health` reports documents, pages, OCR pages and
unreadable pages, and `qwen3.5`'s literal ` thinking` tags are stripped from the stream.
One honest limit survives from the prototype: OCR occasionally loses a hyphen inside a
numeric range — the paper's `calcite (5-10 %)` comes back as `(510 %)` — so numbers from a
scanned page deserve a glance at the PDF, which the citation link makes easy.

Options, if you want a different port or model:

```powershell
$env:CHAT_MODEL = "qwen3.5:4b"   # or "qwen2.5" for the 7B fallback
$env:CHAT_THINK = "0"           # keep 0 for qwen3.5, or the replies come back empty
$env:CHAT_TOP_K = "4"           # passages the prototype puts in front of the model
.venv\Scripts\python.exe -m uvicorn ui.server:app --host 127.0.0.1 --port 8001
```

Stop it with `Ctrl+C` in that terminal (or stop the python process on that port). The
prototype builds its index once at import, so **after a corpus change, restart it**.

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
| `status: unverified` (exit 1) | The answer's quotations were not found on the pages they cite, after one retry. Re-ask, or open the cited page: the verifier is meant to fail here rather than pass a claim nobody can check. |
| A question answers in well under a second every time | It is a cache hit: same question, index, model and prompt. Use `--no-cache` to force a fresh answer. |

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
- **Stop the model** with `ollama stop qwen3.5:4b` (frees VRAM immediately).
- Tags and approvals are the owner's: `step-NN-approved` in git, and lines in
  `APPROVALS.md`.
