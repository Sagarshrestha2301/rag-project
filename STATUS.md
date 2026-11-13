# Status

**Last updated:** 2026-11-13
**Phase:** Step 0 complete and verified, awaiting owner completion approval. No Step 1 work started.
**Current step:** Step 0 (environment check) — every definition-of-done box ticked with evidence. Start approval was given by the owner in chat on 2026-11-13; the durable `APPROVALS.md` line is still to be written by the owner.

## Step tracker
Approvals are NOT recorded here. They exist only in `APPROVALS.md` and in the owner's `step-NN-approved` git tags.

| # | Step | State |
|---|---|---|
| 0 | Environment check | awaiting approval |
| 1 | Eval set | not started |
| 2 | LLM benchmark | not started |
| 3 | Parsing sample | not started |
| 4 | Chunking + embeddings | not started |
| 5 | Hybrid retrieval | not started |
| 6 | Generation | not started |
| 7 | Web UI | not started |
| 8 | Full ingestion | not started |
| 9 | Tuning + docs | not started |

States: not started / in progress / awaiting verification / awaiting approval / done / blocked.

## Next action
Owner reviews `env-report.md` and the proposals below, decides on (a) the Python interpreter and (b) the staged corpus plan, then records the Step 0 completion approval and tag.

## Blockers / open questions
- `APPROVALS.md` still has no approval line (the file was not edited by the agent, by rule). Work ran on the owner's explicit chat instruction.
- Python interpreter undecided: the venv install is on hold until the owner picks 3.12 or 3.14 (see proposal 5).

## Measured facts
- GPU / driver / CUDA: NVIDIA RTX 3050 Laptop, 4096 MiB, compute 8.6; driver 566.07; CUDA 12.7 (driver-reported). No CUDA toolkit installed.
- GPU idle: 377 MiB used by the display, 3719 MiB free.
- CPU / RAM: AMD Ryzen 7 6800HS, 8C/16T; 15.3 GB RAM.
- OS: Windows 11 Pro, build 26300.
- LibreOffice: 26.8.2.2, headless .docx -> PDF works (1-page test PDF, 23240 bytes).
- Hardlinks `data/raw` -> `data/corpus`: **work** (same inode, links=2, write-through confirmed).
- Free disk on the project drive (C:): 814.2 GB of 952.8 GB.
- llama.cpp build: **b12340** (CUDA 12.4 prebuilt + cudart), offloaded **29/29 layers** to the GPU.
- Test model: Qwen2.5-1.5B-Instruct Q4_K_M. Prompt **219.0 tok/s** (22 tokens), generation **65.4 tok/s** (96 tokens), temperature 0.
- VRAM with that model at 4k context: **1622 MiB** of 4096 (2343 MiB free).
- Offline proof: firewall-blocked run answered at 74.2 tok/s, VRAM 1594 MiB, `offline run: PASS`.
- Chosen LLM + tokens/s + VRAM: not measured (Step 2 decides the model).
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

5. **Python interpreter — decision needed before the wheels download.** All nine direct dependencies can install on both 3.12 and 3.14 (per-package evidence in `env-report.md`). Recommendation: **Python 3.12** in a project venv. Reason: 3.14 coverage is proven only for the direct pins; transitive packages (pyarrow, tokenizers, safetensors, pillow and friends) were not checked, and 3.12 has the widest wheel coverage. Cost: one installer download (~25 MB) and it needs approval. Alternative: use the installed 3.14.10 and save the download, accepting unverified transitive risk.

6. **Eval expectations with a single PDF (owner's note, for Step 1).** With about 4 pages, recall@k is near 100% regardless of method, so the Step 1-3 results must be labelled "smoke baseline", never accuracy. The Marahatta paper has no real tables (a core requirement), its equations extract as garbled text, its text layer drops spaces ("duringthe", "byfloods") which will hurt BM25, and Figures 4-6 are images that must stay out of the eval.

## Pinned tools and downloaded files
Pinned tool versions (D-018):

| Tool | Version |
|---|---|
| Windows | 11 Pro, build 26300 |
| Python | 3.14.10 installed (interpreter for the project not yet decided, see proposal 5) |
| pip | 26.2.2 |
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

All three hashes were compared with the digest published on the release page (GitHub) and in the Hugging Face API, and match.

## Session log (newest first)
- 2026-11-13: Step 0 finished. llama.cpp b12340 downloaded, hash-verified against the publisher and run with **29/29 layers on the GPU**: 219.0 tok/s prompt, 65.4 tok/s generation, 1622 MiB VRAM. Offline proof passed with `llama-server.exe` firewall-blocked (74.2 tok/s, `offline run: PASS`). Python wheels item held by the owner; per-package wheel check recorded. Staged corpus plan drafted as a PROPOSED decision.
- 2026-11-13: Step 0 started. Recorded environment (`env-report.md` + `scripts/env-report.ps1`); LibreOffice 26.8.2.2 headless conversion verified; NTFS hardlink test passed; `requirements.txt` pinned and `scripts/launch-llm.ps1` sets offline mode; repo bootstrapped with root commit `initial docs`.
- 2026-11-13: Third review applied: D-032 (owner runs git init and first commit; `.gitignore` added), D-033 (tamper check split, tested in scratch repo), D-034 (held-out not-found zero tolerance), attribution wording fixed in D-025 and D-028, D-035 to D-037 (Task/Context/Output, code rules, plan before code). Context and output sections added to steps 00-09; Step 7 got a UI spec task.
- 2026-11-13: Applied second owner review: D-028 (approvals in `APPROVALS.md`, owner-only tags), D-029 (gate drift, not-found (a) zero drop), D-030 (corpus layout, hardlinks), D-031 (clean tree, owner commits first). Updated AGENTS, EVAL, PLAN, README, ARCHITECTURE, DECISIONS, STATUS, steps 00, 01, 03.
- 2026-11-13: Applied owner review: D-022 (gate arithmetic, growing dev set), D-023 (converted PDFs are the corpus), D-024 (git), D-025 (protected files), D-026 (offline enforcement), D-027 (Step 8 not-found re-check). Updated AGENTS, EVAL, PLAN, REQUIREMENTS, ARCHITECTURE, DECISIONS, STATUS, steps 00, 01, 03, 05, 06, 08, 09.
- 2026-11-13: Owner decided OD-1 (LibreOffice headless, D-019) and OD-2 (flag only, 1-2% rule, D-020), and added the unreadable-pages UI warning (D-021). Updated DECISIONS, ARCHITECTURE, steps 03, 07, 08. Owner has read only the open-decisions list and file listing so far; full docs approval still pending.
- 2026-11-13: Requirements interview done. Docs created. Awaiting approval.

## How to update this file
After every session: update the tracker, "Next action", "Measured facts", and add one log line (date, agent, what was done, what was verified, what is next).
