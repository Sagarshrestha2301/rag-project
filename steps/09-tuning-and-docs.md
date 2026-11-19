# Step 9: Tuning and docs

**Goal:** fix the specific failures the eval shows, then finish the documentation.
**Needs approval to start:** yes. Each experiment needs its own approval.

## Tasks
1. List remaining failures from the full-scale eval, grouped by cause (retrieval miss, table error, wrong number, false "not found", slow).
2. Only for a listed failure, try one backlog experiment behind a flag: HyDE, multi-query, RAPTOR-style summaries, embedder/reranker fine-tuning. One at a time.
3. Keep an experiment only if it passes the regression gate on dev and does not hurt held-out. Otherwise remove it.
4. Final docs: runbook (start, stop, add documents, rebuild, backup, restore), troubleshooting, known limits, final results table. The "add documents" section must include re-checking the not-found questions (D-027), storing converted PDFs in `data/corpus/` with the pinned converter (D-023), and the offline check.

## Definition of done
- [ ] Every kept change has a before/after eval row in `EVAL.md`
- [ ] Rejected experiments recorded in `DECISIONS.md` with results
- [ ] Runbook tested by following it from scratch
- [x] `STATUS.md`, `ARCHITECTURE.md`, `README.md` match the real system
- [ ] Owner signs off

## Context to read
This file, `EVAL.md` (results and per-question diffs), `ARCHITECTURE.md` (experiments backlog), `DECISIONS.md`, `STATUS.md`, the list of failing questions from Step 8.

## Expected output
A failure list grouped by cause, one flagged experiment at a time with before/after eval rows, `RUNBOOK.md` (start, stop, add documents, rebuild, backup, restore, troubleshooting, known limits), and docs updated to match the real system.

## Verification
A fresh agent or the owner can operate the system using only the docs.

## Risks
Tuning to the small eval set; adding complexity for a one-question gain.
