# Status

**Last updated:** 2026-11-13
**Phase:** Steps 0 and 1 complete and verified (owner approved both in chat 2026-11-13): environment, Python 3.12 stack, 30-question eval set and scorer. No application code written.
**Current step:** Step 1 done, pending the owner's `step-01-approved` tag (and `step-00-approved`), which only the owner writes. Step 2 needs its own start approval.

## Step tracker
Approvals are NOT recorded here. They exist only in `APPROVALS.md` and in the owner's `step-NN-approved` git tags.

| # | Step | State |
|---|---|---|
| 0 | Environment check | done (approval recorded 2026-11-13; owner tag pending) |
| 1 | Eval set | done (30 questions and scorer approved 2026-11-13; owner tag pending) |
| 2 | LLM benchmark | in progress (`qwen2.5` 7B chosen and oracle-tested; 2 of 3 comparison rows will never exist, by the owner's decision) |
| 3 | Parsing sample | not started |
| 4 | Chunking + embeddings | not started |
| 5 | Hybrid retrieval | not started |
| 6 | Generation | not started |
| 7 | Web UI | not started |
| 8 | Full ingestion | not started |
| 9 | Tuning + docs | not started |

States: not started / in progress / awaiting verification / awaiting approval / done / blocked.

## Next action
Owner tags `step-00-approved` and `step-01-approved`, then approves the start of Step 2 **and the 8.38 GB download list in proposal 10** (three Q4_K_M models: Qwen3.5-4B, Phi-4-mini-instruct, Gemma 4 E2B). Nothing is downloaded until that approval exists.

## Earlier next action
Owner approved the 30 questions and the scorer spec in chat; the scorer was then implemented and tested on fake outputs, which completed Step 1.

## Blockers / open questions
- Two owner tags are outstanding (`step-00-approved`, `step-01-approved`); agents never tag.
- Step 2 needs a download approval for the candidate models before measurement starts.
- Proposal 4 (staged corpus plan, drafted as D-038) is still undecided by the owner.

## Measured facts
- GPU / driver / CUDA: NVIDIA RTX 3050 Laptop, 4096 MiB, compute 8.6; driver 566.07; CUDA 12.7 (driver-reported). No CUDA toolkit installed.
- GPU idle: 377 MiB used by the display, 3719 MiB free.
- CPU / RAM: AMD Ryzen 7 6800HS, 8C/16T; 15.3 GB RAM.
- OS: Windows 11 Pro, build 26300.
- LibreOffice: 26.8.2.2, headless .docx -> PDF works (1-page test PDF, 23240 bytes).
- Hardlinks `data/raw` -> `data/corpus`: **work** (same inode, links=2, write-through confirmed).
- Free disk on the project drive (C:): 814.2 GB of 952.8 GB.
- llama.cpp build: **b12340** (CUDA 12.4 prebuilt + cudart), offloaded **29/29 layers** to the GPU. Reports `0.9.0-dev (build 12340, commit 8954f1948)`, built with Clang 20.1.8.
- Supported architectures in that build (checked by scanning `llama.dll`): `gemma2`, `gemma3`, `gemma3n`, `gemma4`, `qwen2`, `qwen3`, `qwen35`, `phi3`, `phi4` — so Qwen3.5, Gemma 4 and Phi-4 GGUFs all load without changing the pinned tool.
- Test model: Qwen2.5-1.5B-Instruct Q4_K_M. Prompt **219.0 tok/s** (22 tokens), generation **65.4 tok/s** (96 tokens), temperature 0.
- VRAM with that model at 4k context: **1622 MiB** of 4096 (2343 MiB free).
- Offline proof: firewall-blocked run answered at 74.2 tok/s, VRAM 1594 MiB, `offline run: PASS`.
- Python stack: Python 3.12.10 venv; torch **2.15.0+cpu** (`torch.cuda.is_available() = False` by design, D-010), lancedb 0.41.0, pymupdf 2.1, sentence-transformers 6.3.0, transformers 5.22.2, fastapi 0.162.5. All imports succeed with offline env vars set.
- Generator measured so far: **`qwen2.5` Q4_K_M, 7.62B, 4.36 GiB** (the owner's existing Ollama model, `ollama 0.40.16`), served by the pinned `llama-server.exe` from a hardlink (`links=2`, no extra disk). SHA-256 `2bada8a7450677000f678be90653b85d364de7db25eb5ea54136ada5f3933730`, which is exactly the digest Ollama stores the blob under.
  - `llama-bench` (auto layer split): pp512 **347.8 tok/s**, pp2048 **293.3**, pp4096 **261.0**; tg128 **8.38 tok/s**.
  - 4096 ctx, f16 KV cache: VRAM **3800 MiB of 4096** loaded; 3389-token prompt evaluated in **11.56 s (293 tok/s)**, generation **7.46 tok/s**; answer correct ("540 mm") for a 17-token reply, 13.9 s total.
  - 6144 ctx, `q8_0` KV cache: VRAM **3835 MiB of 4096**; 5397-token prompt in **24.0 s (225 tok/s)**, generation **5.77 tok/s**; answer correct ("about 100 years").
  - Latency projection from those numbers: short follow-up (1k prompt, 100 tokens) ≈ **16 s**, inside the 20 s target; standard RAG (3.4k prompt, 120 tokens) ≈ **28 s**, outside it; deep (5.4k) ≈ **41 s**, inside the 30 s+ target only.
- Parsing profile of the five corpus documents (42 pages): NARAYAN 0 chars / 4 pages / 1 image per page (scan); Ahasan 17 pages, 3 table pages; Das 9 pages, 6 tables; Marahatta 5 pages, 92 figure images; Watanabe 7 pages. `pymupdf4llm` throughput **0.64 s/page (27.07 s / 42 pages)**. `find_tables` finds tables pdfplumber misses (Das p2, p6) but corrupts cells (`69.85` → `6985\n.`); pdfplumber returns clean cells only where it finds a table (Das p9). Unreadable share **9.5% (4/42)**, above the D-020 1-2% threshold.
- A 4226-token prompt was rejected at 4096 context (`exceed_context_size_error`), so the prompt budget must stay under the context window minus the answer; recorded because it is easy to hit with five chunks plus history.
- **Oracle test of `qwen2.5` 7B** (gold page text as context, temperature 0, 30 questions, 3.5-8.8 s per question): **17/30 pass** (dev 12/20, held-out 5/10). recall 26/26 by construction; **citation 14/26 strict**, **19/26** once surrounding quotation marks and the PDF's `East- Rapti` line-break hyphen are ignored — 7 quotes are genuinely paraphrased or truncated (q011, q015, q018, q025, q027, q028, q030); **numeric 22/24** (q016 answered without numbers, q029 said 41 where the gold is 71 growers); not-found (a) 3/3 on dev and (b) 26/26, so refusals and non-refusals are both correct. Raw output and scores in `benchmarks/llm/`.
- Chosen generator: **`qwen2.5` 7B Q4_K_M**, 4096 ctx, f16 KV cache (owner's choice, 2026-11-13); fallback `qwen2.5-1.5b-instruct` Q4_K_M, which fits entirely on the GPU (1622 MiB, 65.4 tok/s generation in Step 0).
- Parse speed (pages/min): not measured.
- Embedding speed (pages/min): not measured.

## Proposals for owner (agents add here; owner decides)
1. **Optional commit hook (Step 0 task 6) — proposed, not installed.** The task calls it a pre-commit hook, but `pre-commit` hooks do not receive the commit message, so a hook that must check the `OWNER:` prefix belongs in `commit-msg`. Proposed `.git/hooks/commit-msg` (owner installs; hooks live in `.git/hooks` and are not committed):

   ```sh
   #!/bin/sh
   # Block edits to owner-only files unless the message starts with "OWNER:" (D-025, D-028).
   msg=$(head -1 "$1")
   case "$msg" in OWNER:*) exit 0 ;; esac
   staged=$(git diff --cached --name-only --diff-filter=ACMR)
   for f in AGENTS.md PLAN.md REQUIREMENTS.md APPROVALS.md; do
     if echo "$staged" | grep -qx "$f"; then
       echo "blocked: $f is owner-only; commit it with a message starting 'OWNER:'" >&2
       exit 1
     fi
   done
   exit 0
   ```
   Limit: it still runs as the same Windows user, so it blocks accidents, not a determined agent.

2. **`APPROVALS.md` check A will flag the bootstrap commit.** The root commit `initial docs` adds `AGENTS.md`, `PLAN.md`, `REQUIREMENTS.md` and `APPROVALS.md` without an `OWNER:` message, because the owner asked for plain commit messages and authorized the agent to bootstrap the repository (D-032 normally makes this owner-only). Check A will list that commit. Suggested: note it in `APPROVALS.md`, or accept it as a known, documented deviation.

3. **LibreOffice output naming (for Step 3).** `--convert-to pdf` writes `<stem>.pdf`, not `<original name>.pdf`. D-030's naming rule needs an explicit rename after conversion; recorded in `env-report.md` so Step 3 does not rediscover it.

4. **Staged corpus growth (owner's plan, 2026-11-13) — needs a `DECISIONS.md` entry.** Stage A: only `1970_Marahatta_Relating_Hydrological_Extremes…pdf` for Steps 1-3 as a plumbing test. Stage B: 30-50 documents before the Step 4 embedder benchmark and Step 5, from the real corpus including table-heavy files, plus near-topic flood/rainfall papers as hard distractors. Stage C: full corpus in Step 8. Re-baseline the eval whenever the corpus grows. This changes the approved plan (Step 1 eval built from one document; Step 3 sample of 1 instead of 50), so the step files need an owner edit. Drafted as PROPOSED in `DECISIONS.md`.

5. **Python interpreter — DECIDED by the owner (2026-11-13): Python 3.12.** Installed as 3.12.10 project-local in `tools\python312` (3.12.11 and later are security-only releases with no Windows installer). Venv at `.venv`, `requirements.txt` installed, imports verified. Open sub-point: wheel-level SHA-256 is recorded only for the Python installer; the 76 installed packages are pinned by version in `requirements.lock.txt`. Adding `--require-hashes` (and therefore wheel hashes) is proposed for the next dependency change.

6. **Keep other tools out of the project venv.** While Step 0 was running, a VS Code terminal installed `aider-chat` into `.venv`. Aider pins `click==8.3.1`, `hf-xet==1.2.0` and `idna==3.11` exactly, and drags `numpy` back to 1.26.4, which breaks `pyarrow` (it requires NumPy >= 2) and therefore `lancedb`. **Resolved 2026-11-13 (owner's choice): the two environments are split.** The aider environment is kept at `tools\aider-venv` (inside the gitignored `tools\`), and `.venv` was rebuilt from scratch: `pip check` reports "No broken requirements found." and every import works. The project venv now has 77 packages, exactly what `requirements.txt` resolves to. Consequences worth keeping: (a) never run `pip install` into `.venv` for a tool that is not in `requirements.txt`; (b) `numpy`, `pyarrow`, `scipy` and `Pillow` are now pinned explicitly in `requirements.txt`, because aider silently pushed numpy back to 1.x, which breaks pyarrow and therefore lancedb; (c) the aider venv is not a working aider install right now — it holds the leftover packages of a failed install. `tools\aider-venv\Scripts\pip install aider-chat` there re-creates it on request. A rule in `AGENTS.md` rule 2 is still proposed for this.

8. **RESOLVED 2026-11-13: the table gap is closed.** The owner added four more PDFs (Ahasan rainfall trends, Das bamboo beliefs, Watanabe glaciers, NARAYAN liquefaction). The corpus is now five documents, and the Das tables made six real table questions possible. `eval/questions.jsonl` now has the full composition: 30 questions (fact 7, exact 5, table 6, summary 3, comparison 3, not-found 4, follow-up 2), split 20 dev / 10 held-out, 3 not-found on dev, so one dev question is 5 points and not-found (a) still rests on 3 questions (33 points each). New finding: `0_NARAYAN_...pdf` has **0 extractable characters** (4 scanned pages) and is the first real D-020/D-021 case — it must be flagged as unreadable and the UI warning must surface it.

9. **Superseded proposal 8 (kept for the record).** `EVAL.md` asks for 30 questions including 6 table lookups. The Marahatta paper contains no tables (only figures and equations), so a table question would have to be invented. The draft set therefore has **24 questions** (fact 7, exact 5, summary 3, comparison 3, not-found 4, follow-up 2), split 16 dev / 8 held-out, with 3 not-found questions on dev. Options: (a) accept 24 for Stage A, with table questions deferred to Stage B where real tables exist — recommended, since a fabricated table question is worse than a missing type; (b) hold Step 1 until Stage B documents arrive; (c) the owner supplies table documents now. Either way the point values in `EVAL.md` should be re-read for N=16 (6.25 points per question).

7. **Eval expectations with a single PDF (owner's note, for Step 1).** With about 4 pages, recall@k is near 100% regardless of method, so the Step 1-3 results must be labelled "smoke baseline", never accuracy. The Marahatta paper has no real tables (a core requirement), its equations extract as garbled text, its text layer drops spaces ("duringthe", "byfloods") which will hurt BM25, and Figures 4-6 are images that must stay out of the eval.

12. **RESOLVED 2026-11-13: citation matching stays strict.** The owner declined the normalisation, so a quote wrapped in quotation marks, or one whose hyphen the PDF split across a line, still counts as a failed citation. Oracle result stays **14/26 citations, 17/30 overall**. Consequence for Step 6: the prompt must produce clean, unquoted, verbatim sentences, and 5 of the 12 current failures are things a better prompt can fix. `SCORER.md` now records the decision so a later agent does not quietly "fix" it. Original analysis, kept for the record: the scorer requires the cited sentence to appear in the page text after whitespace normalisation (`SCORER.md`). The oracle run shows two failure modes that are formatting, not fabrication: the model wraps a correct quote in `"…"`, and the extracted page text splits `East- Rapti` across a line break while the model writes `East-Rapti`. Counting those as correct moves citations from **14/26 to 19/26** and the overall pass rate from 17/30 to **22/30**; the remaining 7 really are paraphrased or truncated. I have **not** changed the scorer, because loosening a gate metric after seeing a bad number is exactly the move the rules forbid. Proposal: add a rule that strips only leading/trailing quotation marks and joins `- ` line-break hyphens — applied to every model equally and re-verified on the fixtures — recorded as a decision you approve. Until then 14/26 is the honest number.

11. **Step 2 needs a decision: 7B that misses 20 s, or one 3-4B download (2026-11-13).** The owner approved Step 2 and said to use the existing `qwen2.5`. Measured (see "Measured facts"): it runs, answers our gold questions correctly, and fits in VRAM at 4096 ctx (3800 MiB) and even at 6144 ctx with `q8_0` KV (3835 MiB) — but it generates at **7.46 tok/s**, so a standard 3.4k-token RAG prompt plus a 120-token answer takes about **28 s**, missing the 20 s target for short follow-ups by roughly 8 s. It is also outside **D-002**, which pinned the generator to a 3-4B model at Q4 *because* 7B spills on this 4 GB card; D-002 is owner-only, so the agent cannot change it. Options:
   - **(a) Accept `qwen2.5` 7B.** Best answer quality already on disk, zero download, but the 20 s target is missed and VRAM headroom is only ~260 MiB. D-002 would need an owner edit explaining the exception.
   - **(b) Add one 3-4B model for comparison** (Qwen3.5-4B `Q4_K_M`, 2.78 GB, Apache-2.0, or Qwen2.5-3B, ~1.9 GB). Expected to hit 20 s and leave VRAM headroom; costs one download and roughly 20 minutes of measurement.
   - **(c) Complete the table with the models already on disk** (`deepseek-r1`, `starcoder2:7b`). Zero download, but neither is a sensible RAG generator (a reasoning model and a code model), so the comparison would choose `qwen2.5` on quality, not on measurement.

   Recommendation: **(b) with Qwen3.5-4B**, because the step exists to choose a generator on numbers and currently only one candidate has any. If the owner prefers no download, (a) is workable: every metric is already honest, the 20 s target just becomes "~28 s for a standard question".

10. **Step 2 candidate list and download approval (needs owner decision).** OD-3 says the list is re-checked at the start of Step 2; that re-check is done, and the step file's hints ("Phi-4-mini, Qwen3-4B, Gemma 4 E2B/E4B") were mostly still current but partly superseded:

   - **Qwen3.5-4B** exists (released February 2026; Qwen3 is the previous generation, April 2025). 4.21B dense, **Apache-2.0**, Q4_K_M **2.71-2.78 GB**.
   - **Gemma 4** exists, but **E4B is 8B total parameters and 4.98 GB at Q4_K_M, needing about 6 GB of VRAM — it cannot fit this 4 GB card** and is excluded. **E2B** is 5B total (2B effective), **Apache-2.0**, Q4_K_M **3.11 GB**.
   - **Phi-4-mini-instruct** is still current as the small Microsoft model: 3.8B, **MIT**, GGUF architecture `phi3`, Q4_K_M **2.49 GB**.
   - **No llama.cpp change is needed (measured).** The pinned build reports `0.9.0-dev (build 12340, commit 8954f1948)`, and `llama.dll` carries the architecture strings `gemma2`, `gemma3`, `gemma3n`, `gemma4`, `qwen2`, `qwen3`, `qwen35`, `phi3`, `phi4`. All three candidates load on the pinned tool, so no re-pin and no re-verification of Step 0.

   **Proposed three**, all Q4_K_M, all text-only:

   | # | Model | File | Source | Size | Licence | Why it is in the list |
   |---|---|---|---|---|---|---|
   | 1 | Qwen3.5-4B | `Qwen3.5-4B-Q4_K_M.gguf` | `ggml-org/Qwen3.5-4B-GGUF` (HF) | 2.78 GB | Apache-2.0 | Closest to D-002's 3-4B target; newest weights; thinking and non-thinking modes |
   | 2 | Phi-4-mini-instruct | `Phi-4-mini-instruct-Q4_K_M.gguf` | `bartowski/microsoft_Phi-4-mini-instruct-GGUF` (HF) | 2.49 GB | MIT | Control: same class, older, no thinking mode, smallest file; its publisher SHA-256 is already published (`01999f17c39cc3074afae5e9c539bc82d45f2dd7faa3917c66cbef76fce8c0c2`) |
   | 3 | Gemma 4 E2B | `gemma-4-E2B-it-Q4_K_M.gguf` | `unsloth/gemma-4-E2B-it-GGUF` (HF) | 3.11 GB | Apache-2.0 | Different family, so a same-class model that still answers our questions is a real finding. Note it is 5B total (2B effective), so it is outside the 3-4B band in weights while sitting in the same memory band |

   **Total download: 8.38 GB** into `models/`. Each file's SHA-256 is read from the Hugging Face LFS metadata at download time and compared after, as in Step 0. No new Python packages: the models are served by the pinned `llama-server.exe` over HTTP.

   **Two things the owner should know before approving:**
   - **VRAM is the real constraint, not the file size.** The card has 4096 MiB total and the display already uses 377 MiB, so about 3719 MiB is free. Weights of 2.5-3.1 GB plus KV cache and compute buffers will not fit fully at a 3.5k-token prompt and 4096 context. Step 2 task 2 measures exactly this (several context sizes, with and without KV-cache quantisation), and the answer may be KV cache `q8_0` at 2048-3072 context, or partial offload with a slower generation rate. If all three miss the 20 s target, the owner chooses between answer quality and latency; that decision is not mine to make.
   - **Step 0's 219 tok/s prompt number cannot be extrapolated.** It was measured with a 22-token prompt, where fixed overhead dominates. Prompt-processing speed at 512, 2048 and 4096 tokens is measured first in Step 2, because at 3.5k tokens of context prompt processing may be the largest part of the 20 s budget.

13. **Step 3 parsing plan, checked against the five real documents (needs owner decisions).** Nothing was installed and no parser code was written; these are measurements with the tools already pinned.

   **What the corpus actually is** (42 pages total): NARAYAN 4 pages / **0 characters** / 1 image per page (pure scan); Ahasan 17 pages / 43,937 chars / **3 table pages** / 21 images; Das 9 pages / 34,399 chars / **6 tables** / 0 images; Marahatta 5 pages / 11,267 chars / **92 images** (figures); Watanabe 7 pages / 6,462 chars / 7 images.

   **Speed**: `pymupdf4llm.to_markdown` on all five documents took **27.07 s for 42 pages = 0.64 s/page ≈ 93 pages/min**, so 100k pages is about **18 hours** single-threaded. Extrapolating from five papers is optimistic; multi-column layouts and dense tables will be slower.

   **The table question is the open one, and neither library wins alone.** Same pages, both tools:

   | Page | `find_tables` (PyMuPDF) | `pdfplumber` (lines) | `pdfplumber` (text) | Cell text quality |
   |---|---|---|---|---|
   | Das 2 | **1 table** | 0 | 1 (journal running head, wrong) | `6985\n.` for **69.85**; `Believeintaboosandsuperstitions` — spaces and the decimal point destroyed |
   | Das 6 | **1 table** | 0 | 1 (running head, wrong) | `1407\n.` for **14.07**; same damage |
   | Das 9 | 3 tables | 3 tables | — | pdfplumber clean: `21.84`, `31.67`, `78.16`; PyMuPDF also corrupt |

   So PyMuPDF **finds** the tables pdfplumber misses but **corrupts every cell**, and pdfplumber is correct only where it finds them. Costs: `find_tables` 0.65-1.9 s/page, pdfplumber 0.15-0.74 s/page. The text layer itself is clean (`"Believe in taboos and superstitions 139 69.85 79 37.96 16 39.02"`), and the damage happens inside the table assembler, not in extraction.

   **Proposed tier 2, no new dependency:** use pdfplumber (lines strategy) for table pages it detects, and for pages where `find_tables` detects a table pdfplumber misses, assemble rows/columns from `page.get_text("words")` by x-coordinate against the header row. That keeps `69.85` intact because it never leaves the text layer. **Docling is not installed and I do not propose installing it yet**: it is a heavy dependency with its own models to download, and the evidence above says the failure is cell assembly, which a position-based assembler addresses without it. If the 20-table cell check in Step 3 does not reach 100% on numbers, Docling becomes the fallback and would need an install plus download approval.

   **What to test on NARAYAN** (the owner's question): (1) confirm 0 extractable characters on all 4 pages and one image per page — done, so it is a scan, not a broken PDF; (2) confirm `pymupdf4llm` returns an **empty string** rather than garbage or a crash — done, it returns 0 characters; (3) require the manifest to record `unreadable_pages: [1,2,3,4]` for that file and the D-021 UI warning to say "4 of 4 pages unreadable" when an answer is "not found" for a NARAYAN question; (4) if OCR is approved later, hand-transcribe page 1 as ground truth and measure word accuracy, since **no eval question covers NARAYAN** and there is currently nothing to measure OCR against.

   **Two decisions this needs from the owner, in order of importance:**
   - **The unreadable share is 9.5% (4 of 42 pages), far above the 1-2% rule in D-020**, which says report it and *propose a separate OCR step*. At five documents the number is skewed by one scanned paper, but the rule is triggered now, not later. Options: **(a) OCR NARAYAN only** — `pymupdf4llm` already looks for RapidOCR and warns it is missing, so this means approving a RapidOCR install plus its model download; **(b) exclude NARAYAN from the corpus** and record why, losing one of five documents; **(c) keep flagging it as unreadable** and accept that 4 pages of the corpus are unsearchable, with the UI warning carrying the burden. Recommendation: (a) if the text matters (it is a liquefaction paper, on-topic for a hazards corpus), otherwise (b) — silently keeping (c) makes "not found" answers misleading.
   - **Step 3 asks for a 50-document sample, and the corpus has 5.** D-038's staged plan puts 30-50 documents at Stage B, before Steps 4-5. Running Step 3's 50-doc checks on 5 documents would tick boxes without testing anything. Recommendation: run Step 3 as a **5-document smoke test** (all eval documents, the real table pages, the real scan) and do the full 50-doc pass when Stage B arrives, with the DoD checkboxes marked as smoke-tested rather than satisfied.

   Also worth knowing: `pymupdf4llm` prints "RapidOCR is missing" **once per document**, so a 100k-page run produces one warning per file. Harmless, but it means the flag list — not the log — has to be the source of truth for unreadable pages.

## Pinned tools and downloaded files
Pinned tool versions (D-018):

| Tool | Version |
|---|---|
| Windows | 11 Pro, build 26300 |
| Python (project) | **3.12.10**, project-local at `tools\python312`, venv `.venv` |
| pip | 25.0.1 (in `.venv`) |
| Git | 2.56.0.windows.2 |
| LibreOffice | 26.8.2.2 |
| llama.cpp | b12340 (prebuilt win-cuda-12.4-x64 + cudart 12.4) |
| NVIDIA driver | 566.07 (CUDA 12.7) |

Downloaded files (name, source, version, SHA-256, path):

| Name | Source | Version | SHA-256 | Path |
|---|---|---|---|---|
| `llama-b12340-bin-win-cuda-12.4-x64.zip` | github.com/ggml-org/llama.cpp releases | b12340 | `72c3654c1495c7b08444ac8edf5e1c658943e9721a70787074612e3480286f9e` | `tools/llama.cpp/` |
| `cudart-llama-bin-win-cuda-12.4-x64.zip` | github.com/ggml-org/llama.cpp releases | b12340 | `8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6` | `tools/llama.cpp/` |
| `qwen2.5-1.5b-instruct-q4_k_m.gguf` | huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF | main | `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` | `models/` |
| `python-3.12.10-amd64.exe` | python.org/ftp/python/3.12.10 | 3.12.10 | `67b5635e80ea51072b87941312d00ec8927c4db9ba18938f7ad2d27b328b95fb` | `tools/installers/` |
| Python wheel set (76 packages) | PyPI | see `requirements.lock.txt` | not recorded per wheel (version-pinned only) | `.venv/Lib/site-packages` |
| `qwen2.5-7b-instruct-q4_k_m.gguf` | owner's existing Ollama store (`ollama pull qwen2.5`) | Q4_K_M, 7.62B | `2bada8a7450677000f678be90653b85d364de7db25eb5ea54136ada5f3933730` | `models/` (hardlink to `~/.ollama/models/blobs/sha256-2bada8a7…3730`) |

All three hashes were compared with the digest published on the release page (GitHub) and in the Hugging Face API, and match.

## Session log (newest first)
- 2026-11-13: Step 3 planning only (no start approval, nothing installed). Profiled all five corpus documents with the pinned parsers: 42 pages, `pymupdf4llm` at 0.64 s/page (18 h extrapolated to 100k pages). Found that PyMuPDF detects the Das tables pdfplumber misses but corrupts their cells while pdfplumber is clean only where it detects them, and that pdfplumber's text strategy returns the journal running head instead of the table — so the plan proposes pdfplumber plus a word-position assembler instead of installing Docling. NARAYAN confirms 4 pages with 0 characters and one image each, which puts the unreadable share at 9.5%, above D-020's 1-2% rule, so the owner must choose OCR or exclusion. The 50-doc sample versus a 5-doc corpus is the second open decision. Written up as proposal 13.
- 2026-11-13: Owner chose `qwen2.5` 7B as the generator (no download). Ran the oracle test (task 4): the gold page text as context, temperature 0, all 30 questions, 3.5-8.8 s each. Scored **17/30** (dev 12/20, held-out 5/10), not-found (a) 3/3 and (b) 26/26, numeric 22/24, citation 14/26 strict / 19/26 ignoring quote marks and a PDF hyphen break, with 7 quotes genuinely paraphrased. Recorded the generator and fallback, ctx 4096 with f16 KV, and the D-002 exception as PROPOSED D-040; the citation-normalisation question is proposal 12 and PROPOSED D-041, deliberately not applied.
- 2026-11-13: Step 2 started with the owner's existing `qwen2.5` (7.62B Q4_K_M) instead of downloads. Hardlinked the Ollama blob into `models/` (no extra disk); its SHA-256 equals Ollama's blob digest. Measured with the pinned build: pp512/2048/4096 = 347.8/293.3/261.0 tok/s, tg128 8.38 tok/s; 4096 ctx uses 3800 MiB VRAM and answers a 3389-token prompt in 11.56 s at 7.46 tok/s; 6144 ctx with q8_0 KV uses 3835 MiB and takes 24.0 s for 5397 tokens at 5.77 tok/s. Both answers were correct. A 4226-token prompt is rejected at 4096 ctx. The 7B misses the 20 s target for standard RAG prompts (~28 s projected) and is outside D-002, so proposal 11 asks the owner to choose: accept 7B, or approve one 3-4B download for comparison.
- 2026-11-13: Step 2 planning only (Step 2 has no start approval, so nothing was downloaded). Re-checked OD-3 against current releases: Qwen3.5-4B supersedes Qwen3-4B, Gemma 4 exists but E4B is 8B/4.98 GB and cannot fit 4 GB VRAM, Phi-4-mini is still current (MIT). Verified by scanning `llama.dll` that the pinned build b12340 supports `gemma4`, `qwen35` and `phi3`, so no tool re-pin is needed. Proposed three candidates and an 8.38 GB download list as proposal 10, with the VRAM and prompt-processing risks stated.
- 2026-11-13: Step 1 finished. Owner approved the 30 questions and the scorer spec in chat; added `eval/score.py` (recall@5/10/30 over answerable questions, MRR, citation correctness with quote verification, numeric exact match, not-found a and b, per-question diff, SHA-256 integrity gate), `eval/make_fixtures.py` and `eval/test_scorer.py`. All 30 checks pass: perfect 30/30, empty 4/30, partial 15/30 with exactly q016-q030 flagged as regressions, a run citing `data/raw/` rejected (exit 3), and a tampered gold hash rejected (exit 3) with no scores written. Also added `eval/build_review.py`, a static side-by-side review page used to approve the questions, and recorded the approval in `APPROVALS.md`.
- 2026-11-13: Owner added 4 PDFs; corpus is now 5 documents (all hardlinked, hashes pinned). Extended the eval set to the full 30-question composition with 6 verified table questions from Das Tables 1-3 (the owner's table requirement is now covered), split 20 dev / 10 held-out. `eval/build_questions.py` checks every quote and every file hash before writing.
- 2026-11-13: Step 1 started. Corpus set up (Marahatta PDF hardlinked into `data/corpus/`, SHA-256 `1b42e67f…`, 5 physical pages = printed 44-48). Built the Stage A eval draft: 24 questions with gold answers, page numbers and quotes, every quote verified against the PDF text by `eval/build_questions.py`; split 16 dev / 8 held-out; `eval/SCORER.md` written. Blocked on owner approval of the questions and the table-type gap (proposal 8).
- 2026-11-13: venv collision with `aider-chat` (installed from a VS Code terminal) resolved the way the owner chose: aider's environment moved to `tools\aider-venv`, project `.venv` rebuilt clean (install exit 0, `pip check` clean, 77 packages, all imports OK, numpy pinned to 2.5.4). Intermediate install logs removed; `artifacts/step0/pip-clean.log` keeps the evidence.
- 2026-11-13: Python 3.12 environment built after the owner approved it: 3.12.10 installed project-local (`tools\python312`, hash recorded), venv `.venv`, all pinned requirements installed (exit 0), imports verified offline, exact transitive pins frozen in `requirements.lock.txt` (77 lines). torch is the CPU build, so VRAM stays free for the LLM.
- 2026-11-13: Step 0 finished. llama.cpp b12340 downloaded, hash-verified against the publisher and run with **29/29 layers on the GPU**: 219.0 tok/s prompt, 65.4 tok/s generation, 1622 MiB VRAM. Offline proof passed with `llama-server.exe` firewall-blocked (74.2 tok/s, `offline run: PASS`). Python wheels item held by the owner; per-package wheel check recorded. Staged corpus plan drafted as a PROPOSED decision.
- 2026-11-13: Step 0 started. Recorded environment (`env-report.md` + `scripts/env-report.ps1`); LibreOffice 26.8.2.2 headless conversion verified; NTFS hardlink test passed; `requirements.txt` pinned and `scripts/launch-llm.ps1` sets offline mode; repo bootstrapped with root commit `initial docs`.
- 2026-11-13: Third review applied: D-032 (owner runs git init and first commit; `.gitignore` added), D-033 (tamper check split, tested in scratch repo), D-034 (held-out not-found zero tolerance), attribution wording fixed in D-025 and D-028, D-035 to D-037 (Task/Context/Output, code rules, plan before code). Context and output sections added to steps 00-09; Step 7 got a UI spec task.
- 2026-11-13: Applied second owner review: D-028 (approvals in `APPROVALS.md`, owner-only tags), D-029 (gate drift, not-found (a) zero drop), D-030 (corpus layout, hardlinks), D-031 (clean tree, owner commits first). Updated AGENTS, EVAL, PLAN, README, ARCHITECTURE, DECISIONS, STATUS, steps 00, 01, 03.
- 2026-11-13: Applied owner review: D-022 (gate arithmetic, growing dev set), D-023 (converted PDFs are the corpus), D-024 (git), D-025 (protected files), D-026 (offline enforcement), D-027 (Step 8 not-found re-check). Updated AGENTS, EVAL, PLAN, REQUIREMENTS, ARCHITECTURE, DECISIONS, STATUS, steps 00, 01, 03, 05, 06, 08, 09.
- 2026-11-13: Owner decided OD-1 (LibreOffice headless, D-019) and OD-2 (flag only, 1-2% rule, D-020), and added the unreadable-pages UI warning (D-021). Updated DECISIONS, ARCHITECTURE, steps 03, 07, 08. Owner has read only the open-decisions list and file listing so far; full docs approval still pending.
- 2026-11-13: Requirements interview done. Docs created. Awaiting approval.

## How to update this file
After every session: update the tracker, "Next action", "Measured facts", and add one log line (date, agent, what was done, what was verified, what is next).
