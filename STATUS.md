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
Owner tags `step-00-approved` and `step-01-approved`, then approves the start of Step 2 (LLM benchmark: three models, same settings, temperature 0). Step 2 downloads models, so the download list needs approval before it starts.

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
- llama.cpp build: **b12340** (CUDA 12.4 prebuilt + cudart), offloaded **29/29 layers** to the GPU.
- Test model: Qwen2.5-1.5B-Instruct Q4_K_M. Prompt **219.0 tok/s** (22 tokens), generation **65.4 tok/s** (96 tokens), temperature 0.
- VRAM with that model at 4k context: **1622 MiB** of 4096 (2343 MiB free).
- Offline proof: firewall-blocked run answered at 74.2 tok/s, VRAM 1594 MiB, `offline run: PASS`.
- Python stack: Python 3.12.10 venv; torch **2.15.0+cpu** (`torch.cuda.is_available() = False` by design, D-010), lancedb 0.41.0, pymupdf 2.1, sentence-transformers 6.3.0, transformers 5.22.2, fastapi 0.162.5. All imports succeed with offline env vars set.
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

5. **Python interpreter — DECIDED by the owner (2026-11-13): Python 3.12.** Installed as 3.12.10 project-local in `tools\python312` (3.12.11 and later are security-only releases with no Windows installer). Venv at `.venv`, `requirements.txt` installed, imports verified. Open sub-point: wheel-level SHA-256 is recorded only for the Python installer; the 76 installed packages are pinned by version in `requirements.lock.txt`. Adding `--require-hashes` (and therefore wheel hashes) is proposed for the next dependency change.

6. **Keep other tools out of the project venv.** While Step 0 was running, a VS Code terminal installed `aider-chat` into `.venv`. Aider pins `click==8.3.1`, `hf-xet==1.2.0` and `idna==3.11` exactly, and drags `numpy` back to 1.26.4, which breaks `pyarrow` (it requires NumPy >= 2) and therefore `lancedb`. **Resolved 2026-11-13 (owner's choice): the two environments are split.** The aider environment is kept at `tools\aider-venv` (inside the gitignored `tools\`), and `.venv` was rebuilt from scratch: `pip check` reports "No broken requirements found." and every import works. The project venv now has 77 packages, exactly what `requirements.txt` resolves to. Consequences worth keeping: (a) never run `pip install` into `.venv` for a tool that is not in `requirements.txt`; (b) `numpy`, `pyarrow`, `scipy` and `Pillow` are now pinned explicitly in `requirements.txt`, because aider silently pushed numpy back to 1.x, which breaks pyarrow and therefore lancedb; (c) the aider venv is not a working aider install right now — it holds the leftover packages of a failed install. `tools\aider-venv\Scripts\pip install aider-chat` there re-creates it on request. A rule in `AGENTS.md` rule 2 is still proposed for this.

8. **RESOLVED 2026-11-13: the table gap is closed.** The owner added four more PDFs (Ahasan rainfall trends, Das bamboo beliefs, Watanabe glaciers, NARAYAN liquefaction). The corpus is now five documents, and the Das tables made six real table questions possible. `eval/questions.jsonl` now has the full composition: 30 questions (fact 7, exact 5, table 6, summary 3, comparison 3, not-found 4, follow-up 2), split 20 dev / 10 held-out, 3 not-found on dev, so one dev question is 5 points and not-found (a) still rests on 3 questions (33 points each). New finding: `0_NARAYAN_...pdf` has **0 extractable characters** (4 scanned pages) and is the first real D-020/D-021 case — it must be flagged as unreadable and the UI warning must surface it.

9. **Superseded proposal 8 (kept for the record).** `EVAL.md` asks for 30 questions including 6 table lookups. The Marahatta paper contains no tables (only figures and equations), so a table question would have to be invented. The draft set therefore has **24 questions** (fact 7, exact 5, summary 3, comparison 3, not-found 4, follow-up 2), split 16 dev / 8 held-out, with 3 not-found questions on dev. Options: (a) accept 24 for Stage A, with table questions deferred to Stage B where real tables exist — recommended, since a fabricated table question is worse than a missing type; (b) hold Step 1 until Stage B documents arrive; (c) the owner supplies table documents now. Either way the point values in `EVAL.md` should be re-read for N=16 (6.25 points per question).

7. **Eval expectations with a single PDF (owner's note, for Step 1).** With about 4 pages, recall@k is near 100% regardless of method, so the Step 1-3 results must be labelled "smoke baseline", never accuracy. The Marahatta paper has no real tables (a core requirement), its equations extract as garbled text, its text layer drops spaces ("duringthe", "byfloods") which will hurt BM25, and Figures 4-6 are images that must stay out of the eval.

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

All three hashes were compared with the digest published on the release page (GitHub) and in the Hugging Face API, and match.

## Session log (newest first)
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
