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

## 5. Parse the corpus

```powershell
.venv\Scripts\python.exe -c "import pymupdf4llm, glob; print(len(pymupdf4llm.to_markdown(glob.glob('data/corpus/*.pdf')[0])))"
```

Scanned documents are OCR'd with RapidOCR (`rapidocr==3.10.0`). The one scan in
the corpus, `0_NARAYAN_...pdf`, yields 0 characters by plain extraction and about
7,000 characters per run through OCR. Throughput is 0.64 s/page for text pages;
OCR is far slower.

## 6. Open the chat UI

```powershell
.venv\Scripts\python.exe -m uvicorn ui.server:app --host 127.0.0.1 --port 8000
```

Then open **http://127.0.0.1:8000**.

Streaming answers, conversations kept in the browser, stop mid-answer, copy,
regenerate, light/dark theme, and live tokens/second under each reply.

**Answers are grounded in the corpus.** Before the model sees a question,
`ui/retrieval.py` scores all 42 pages with BM25 and passes the four best to
qwen3.5 4B, which cites them by letter. Each reply ends with **Sources** chips
(document and page); click a chip or an inline citation like [A] to open that PDF
page in a new tab. The model is told to answer `NOT FOUND` when the passages do
not contain the answer, so a miss looks like a miss instead of a guess.

**Save chat** downloads the current conversation as Markdown, including the
sources used for each answer.

qwen3.5 wraps its (empty) reasoning in literal ` thinking` tags even with thinking
off; the server strips them from the stream, so you should never see one.

The page index is cached in `index/ui-pages.json` (regenerated, not committed).
After changing the corpus, delete that file and restart the server above.

**The scanned NARAYAN paper is searchable too.** Its four pages have no text layer,
so the index runs OCR on them once through the pinned parser (about 20 s, RapidOCR)
and stores the text with the page. Source chips from those pages are marked `· OCR`,
and `/api/health` reports `ocr_pages` and an empty `unreadable`.

Two honest limits. This is *page-level* retrieval — a prototype for the chunking
and hybrid search of Steps 4-5, not those steps finished — so it can rank a page
but not part of one. And OCR occasionally loses a hyphen inside a numeric range:
the paper's `calcite (5-10 %)` comes back as `(510 %)`. Treat numbers from
scanned pages as needing a glance at the PDF, which the citation link makes easy.

Options, if you want a different port or model:

```powershell
$env:CHAT_MODEL = "qwen3.5:4b"   # or "qwen2.5" for the 7B fallback
$env:CHAT_THINK = "0"           # keep 0 for qwen3.5, or the replies come back empty
.venv\Scripts\python.exe -m uvicorn ui.server:app --host 127.0.0.1 --port 8001
```

Stop it with `Ctrl+C` in that terminal (or stop the python process on that port).

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
| Prompt rejected as too long | Context is 4096 tokens. Retrieved chunks plus history must stay under roughly 3.5k. |

## Notes and limits

- **Context is 4096 tokens.** A prompt of 4226 tokens is rejected outright. Keep
  retrieved chunks plus history under about 3.5k tokens, and leave room for the
  answer.
- **Generation is about 10.5 tok/s** at 4B, and first token at 3.64 s for a
  2,323-token prompt, so a 120-token answer lands inside the 20 s target. Long
  answers are the slow case: 343 tokens took 44.8 s.
- **VRAM is 4 GB.** The 4B model peaks at 3.7 GB including context, leaving
  roughly 400 MiB — enough for the model, not for a GPU reranker (D-004 keeps it
  on CPU). Closing other GPU applications buys headroom.
- **Stop the model** with `ollama stop qwen3.5:4b` (frees VRAM immediately).
- Tags and approvals are the owner's: `step-NN-approved` in git, and lines in
  `APPROVALS.md`.
