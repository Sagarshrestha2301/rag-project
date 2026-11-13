# Status

**Last updated:** 2026-11-13
**Phase:** Docs written, waiting for owner approval. No code, no installs.
**Current step:** none (Step 0 not yet approved)

## Step tracker
Approvals are NOT recorded here. They exist only in `APPROVALS.md` and in the owner's `step-NN-approved` git tags.

| # | Step | State |
|---|---|---|
| 0 | Environment check | not started |
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
Owner reviews and approves the docs, then approves Step 0.

## Blockers / open questions
See "Open decisions" in `DECISIONS.md` (OD-3, OD-4, OD-5 remain; they are settled at later steps).

## Measured facts (fill in as measured)
- GPU / driver / CUDA: 
- llama.cpp build: 
- Free disk on target drive: 
- Chosen LLM + tokens/s + VRAM: 
- Parse speed (pages/min): 
- Embedding speed (pages/min): 

## Proposals for owner (agents add here; owner decides)
- none yet

## Pinned tools and downloaded files (fill in; one line per file: name, source, version, SHA-256, path)
- none yet. Pin the LibreOffice version here in Step 0.

## Session log (newest first)
- 2026-11-13: Third review applied: D-032 (owner runs git init and first commit; `.gitignore` added), D-033 (tamper check split, tested in scratch repo), D-034 (held-out not-found zero tolerance), attribution wording fixed in D-025 and D-028, D-035 to D-037 (Task/Context/Output, code rules, plan before code). Context and output sections added to steps 00-09; Step 7 got a UI spec task.
- 2026-11-13: Applied second owner review: D-028 (approvals in `APPROVALS.md`, owner-only tags), D-029 (gate drift, not-found (a) zero drop), D-030 (corpus layout, hardlinks), D-031 (clean tree, owner commits first). Updated AGENTS, EVAL, PLAN, README, ARCHITECTURE, DECISIONS, STATUS, steps 00, 01, 03.
- 2026-11-13: Applied owner review: D-022 (gate arithmetic, growing dev set), D-023 (converted PDFs are the corpus), D-024 (git), D-025 (protected files), D-026 (offline enforcement), D-027 (Step 8 not-found re-check). Updated AGENTS, EVAL, PLAN, REQUIREMENTS, ARCHITECTURE, DECISIONS, steps 00, 01, 03, 05, 06, 08, 09.
- 2026-11-13: Owner decided OD-1 (LibreOffice headless, D-019) and OD-2 (flag only, 1-2% rule, D-020), and added the unreadable-pages UI warning (D-021). Updated DECISIONS, ARCHITECTURE, steps 03, 07, 08. Owner has read only the open-decisions list and file listing so far; full docs approval still pending.
- 2026-11-13: Requirements interview done. Docs created. Awaiting approval.

## How to update this file
After every session: update the tracker, "Next action", "Measured facts", and add one log line (date, agent, what was done, what was verified, what is next).
