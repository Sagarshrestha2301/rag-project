# Status

**Last updated:** 2026-11-13
**Phase:** Step 0 in progress. Environment recorded, LibreOffice/hardlink/git checks pass, stopped at the download gate.
**Current step:** Step 0 (environment check) — start approval given by the owner in chat on 2026-11-13; the durable `APPROVALS.md` line is still to be written by the owner.

## Step tracker
Approvals are NOT recorded here. They exist only in `APPROVALS.md` and in the owner's `step-NN-approved` git tags.

| # | Step | State |
|---|---|---|
| 0 | Environment check | in progress (blocked at download gate) |
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
Owner approves (or changes) the download list below, then the llama.cpp test, the offline proof and the pinned-versions table are completed.

**Download list awaiting approval (nothing has been downloaded yet):**

| # | Item | Source | Size |
|---|---|---|---|
| 1 | `llama-b12340-bin-win-cuda-12.4-x64.zip` | github.com/ggml-org/llama.cpp releases, build b12340 | 317,483,709 B (317.5 MB) |
| 2 | `cudart-llama-bin-win-cuda-12.4-x64.zip` | same release (CUDA runtime, needed by #1) | 391,443,627 B (391.4 MB) |
| 3 | `qwen2.5-1.5b-instruct-q4_k_m.gguf` | huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF | 1,117,320,736 B (1.12 GB) |
| 4 | Python wheels for `requirements.txt` | PyPI | ~0.8 GB estimated, measured at install |

Total about 2.6 GB; 814.2 GB free.

## Blockers / open questions
- `APPROVALS.md` has no approval line yet. Work is proceeding on the owner's explicit chat instruction; see "Proposals for owner".
- The latest llama.cpp release tags (`b12352`, `b12300`) publish **source archives only**; the newest tag with Windows CUDA binaries is `b12340`. Pinning `b12340` rather than tracking latest.

## Measured facts
- GPU / driver / CUDA: NVIDIA RTX 3050 Laptop, 4096 MiB, compute 8.6; driver 566.07; CUDA 12.7 (driver-reported). No CUDA toolkit installed.
- GPU idle: 377 MiB used by the display, 3719 MiB free.
- CPU / RAM: AMD Ryzen 7 6800HS, 8C/16T; 15.3 GB RAM.
- OS: Windows 11 Pro, build 26300.
- LibreOffice: 26.8.2.2, headless .docx -> PDF works (1-page test PDF, 23240 bytes).
- Hardlinks `data/raw` -> `data/corpus`: **work** (same inode, links=2, write-through confirmed).
- Free disk on the project drive (C:): 814.2 GB of 952.8 GB.
- llama.cpp build: not measured yet (b12340 chosen, not downloaded).
- Chosen LLM + tokens/s + VRAM: not measured (Step 2 decides the model; Step 0 measures only a test model).
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
   Limit: still runs as the same Windows user, so it blocks accidents, not a determined agent.

2. **`APPROVALS.md` check A will flag the bootstrap commit.** The root commit `initial docs` adds `AGENTS.md`, `PLAN.md`, `REQUIREMENTS.md` and `APPROVALS.md` without an `OWNER:` message, because the owner asked for a plain message and authorized the agent to bootstrap the repo. Check A (`git log --invert-grep --grep="^OWNER:" ... -- AGENTS.md PLAN.md REQUIREMENTS.md APPROVALS.md`) will list that commit. Suggested: add a note to `APPROVALS.md` recording that the bootstrap commit was owner-authorized, or accept the flag as known.

3. **LibreOffice output naming (for Step 3).** `--convert-to pdf` writes `<stem>.pdf`, not `<original name>.pdf`. D-030's naming rule needs an explicit rename after conversion; recorded in `env-report.md` so Step 3 does not rediscover it.

4. **Python 3.14 vs 3.12.** The installed interpreter is 3.14.10. Wheel availability was checked from PyPI metadata (pymupdf `cp311-abi3`, lancedb `cp310-abi3`, torch `cp314`), which suggests 3.14 is fine, but that is not the same as a successful install. If the install fails, the fallback is Python 3.12 (one extra download, needs approval).

## Pinned tools and downloaded files
Pinned tool versions (D-018):

| Tool | Version |
|---|---|
| Windows | 11 Pro, build 26300 |
| Python | 3.14.10 (pip 26.2.2) |
| Git | 2.56.0.windows.2 |
| LibreOffice | 26.8.2.2 |
| llama.cpp | b12340 (selected, not yet downloaded) |
| NVIDIA driver | 566.07 (CUDA 12.7) |

Downloaded files (name, source, version, SHA-256, path) — **none yet**, the gate is not approved:

| Name | Source | Version | SHA-256 | Path |
|---|---|---|---|---|
| (nothing downloaded) | | | | |

## Session log (newest first)
- 2026-11-13: Step 0 started. Recorded environment (`env-report.md` + `scripts/env-report.ps1`); LibreOffice 26.8.2.2 headless conversion verified; NTFS hardlink test passed; `requirements.txt` pinned and `scripts/launch-llm.ps1` sets offline mode; repo bootstrapped with root commit `initial docs`. Stopped at the download gate. Not measured: llama.cpp offload/speeds/VRAM, offline proof.
- 2026-11-13: Third review applied: D-032 (owner runs git init and first commit; `.gitignore` added), D-033 (tamper check split, tested in scratch repo), D-034 (held-out not-found zero tolerance), attribution wording fixed in D-025 and D-028, D-035 to D-037 (Task/Context/Output, code rules, plan before code). Context and output sections added to steps 00-09; Step 7 got a UI spec task.
- 2026-11-13: Applied second owner review: D-028 (approvals in `APPROVALS.md`, owner-only tags), D-029 (gate drift, not-found (a) zero drop), D-030 (corpus layout, hardlinks), D-031 (clean tree, owner commits first). Updated AGENTS, EVAL, PLAN, README, ARCHITECTURE, DECISIONS, STATUS, steps 00, 01, 03.
- 2026-11-13: Applied owner review: D-022 (gate arithmetic, growing dev set), D-023 (converted PDFs are the corpus), D-024 (git), D-025 (protected files), D-026 (offline enforcement), D-027 (Step 8 not-found re-check). Updated AGENTS, EVAL, PLAN, REQUIREMENTS, ARCHITECTURE, DECISIONS, STATUS, steps 00, 01, 03, 05, 06, 08, 09.
- 2026-11-13: Owner decided OD-1 (LibreOffice headless, D-019) and OD-2 (flag only, 1-2% rule, D-020), and added the unreadable-pages UI warning (D-021). Updated DECISIONS, ARCHITECTURE, steps 03, 07, 08. Owner has read only the open-decisions list and file listing so far; full docs approval still pending.
- 2026-11-13: Requirements interview done. Docs created. Awaiting approval.

## How to update this file
After every session: update the tracker, "Next action", "Measured facts", and add one log line (date, agent, what was done, what was verified, what is next).
