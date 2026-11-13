# Offline RAG Project

Fully offline question answering over 100k+ pages of official reports and papers (PDF, Word), with page-level citations.

**Target machine:** Windows 11, RTX 3050 4GB VRAM, 16GB RAM. No internet at runtime.

## Status
First-time setup for the owner (git init, first commit, approvals): see `APPROVALS.md`.
See `STATUS.md`. **No code is written or installed until the docs are approved and each step is approved separately.**

## Document map
| File | Purpose |
|---|---|
| `REQUIREMENTS.md` | What the system must do and its limits |
| `ARCHITECTURE.md` | Components, data flow, choices and rejected alternatives |
| `PLAN.md` | Step order (0-9) and approval gates |
| `STATUS.md` | Current state, log, next action. Updated after every work session |
| `DECISIONS.md` | Decision log and open decisions |
| `AGENTS.md` | Rules every coding agent must follow |
| `APPROVALS.md` | Owner-only record of step approvals (agents read, never edit) |
| `EVAL.md` | Evaluation set, metrics, regression gate, results |
| `steps/NN-name.md` | One file per step: tasks, definition of done, verification |

## Workflow
1. Run `git status` (stop if not clean). Read `AGENTS.md`, then `STATUS.md`, then the current `steps/NN-*.md`.
2. Work on exactly one step that has a start approval in `APPROVALS.md`.
3. Verify against the step's definition of done and `EVAL.md`.
4. Update `STATUS.md` (and `DECISIONS.md` if anything was decided).
5. Stop and wait for the owner's approval before the next step. Only the owner records approvals and tags steps.
