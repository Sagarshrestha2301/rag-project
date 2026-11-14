# How to run this project

Everything runs offline on this machine. The model server is **Ollama**; the
pinned llama.cpp build was removed on 2026-11-13 because Ollama measured faster
on the same weights (499 tok/s prompt, 9.43 tok/s generation, against 293 and
7.46).

Model: **`qwen2.5`** (7.6B, Q4_K_M, 4.7 GB), 4096-token context, temperature 0.

---

## 1. Start the model

```powershell
.\scripts\launch-llm.ps1
```

That sets offline mode, binds Ollama to `127.0.0.1:11434`, and loads `qwen2.5`
with a 30-minute keep-alive so the first question is not slowed by a cold start.

If the model is missing:

```powershell
ollama pull qwen2.5
```

Plain Ollama also works if you do not want the script:

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11434"
ollama run qwen2.5
```

## 2. Ask the model

> **Write `curl.exe`, not `curl`.** In Windows PowerShell 5.1, `curl` is an alias
> for `Invoke-WebRequest`, which sends a **GET** — Ollama answers `405 method not
> allowed` for a GET on `/api/chat`, `/api/generate` and `/v1/chat/completions`.
> `curl.exe` is the real program and works.

Native endpoint (`curl.exe`):

```powershell
curl.exe -s -X POST http://127.0.0.1:11434/api/chat -H "Content-Type: application/json" -d '{
  "model": "qwen2.5",
  "stream": false,
  "options": { "temperature": 0 },
  "messages": [ { "role": "user", "content": "What was the 24-hour rainfall at Tistung in 1993?" } ]
}'
```

The same thing without any quoting pain, using PowerShell natively:

```powershell
$body = @{
  model   = "qwen2.5"
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
  "model": "qwen2.5",
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
.venv\Scripts\python.exe benchmarks\llm\oracle_run.py --port 11434 --out benchmarks\llm\oracle-qwen2.5-7b.jsonl
.venv\Scripts\python.exe eval\score.py --run benchmarks\llm\oracle-qwen2.5-7b.jsonl --out benchmarks\llm\scores-qwen2.5-7b
```

Last measured: **17/30 pass**, citations 14/26 (strict), numeric 22/24,
not-found 4/4.

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

It talks to Ollama through the same local server, so the browser never contacts
anything else. **There is no retrieval yet** — no index exists until Steps 4-6 —
so answers come from the model alone and are not grounded in `data/corpus/`.
The UI says so on its empty screen.

Options, if you want a different port or model:

```powershell
$env:CHAT_MODEL = "qwen2.5"
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
| `model 'qwen2.5' not found` | `ollama pull qwen2.5`. The store is content-addressed; the digest for our copy is `2bada8a7…3730`. |
| First answer takes ~10 s longer | The model was unloaded. `ollama ps` shows `UNTIL`; the launcher sets 30 minutes. |
| Answers crawl | `ollama ps` shows the CPU/GPU split. Our 7.6B model runs at 55%/45% on 4 GB VRAM; close other GPU apps (`ollama stop`, browsers with hardware acceleration). |
| Prompt rejected as too long | Context is 4096 tokens. Retrieved chunks plus history must stay under roughly 3.5k. |

## Notes and limits

- **Context is 4096 tokens.** A prompt of 4226 tokens is rejected outright. Keep
  retrieved chunks plus history under about 3.5k tokens, and leave room for the
  answer.
- **Generation is about 9.4 tok/s**, so a 120-token answer takes roughly 13 s and
  a standard RAG question lands near the 20 s target. Deeper contexts are slower.
- **VRAM is 4 GB.** The 7.6B model does not fit fully; Ollama keeps the rest on
  the CPU. Closing other GPU applications buys headroom.
- **Stop the model** with `ollama stop qwen2.5` (frees VRAM immediately).
- Tags and approvals are the owner's: `step-NN-approved` in git, and lines in
  `APPROVALS.md`.
