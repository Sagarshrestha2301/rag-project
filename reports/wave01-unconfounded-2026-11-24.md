# Wave 01, unconfounded: pre-wave corpus re-run on the same daemon (2026-11-24)

**Why this run.** The wave-01 decision compared 35/55 (English-only, Ollama 0.40.18) with
38/55 (pre-wave, measured on 0.40.16). The determinism check showed the daemon update alone
moves four questions, so that gap was confounded. This re-measures the **pre-wave corpus on
the same 0.40.18 daemon**, with the same corrected gold, prompt and settings.

**How, without touching the live corpus.** `data/corpus` is read-only (AGENTS.md rule 5), so
the run used a sandbox copy of the project: code copied to `.tmp-prewave/`, the **97 pre-wave
PDFs hardlinked** into its `data/corpus` (83 from `data/corpus`, 14 from
`data/quarantine/non-english/`, no bytes copied), and the **pre-wave index restored** from
`backups/2026-11-22-pre-wave01/pages.json`. The hardlinks preserved size and mtime, so the
backup's signature matched exactly and `corpus.build()` loaded it in **0.03 s** - no re-parse,
no OCR. The live corpus and live index were not modified; the sandbox was deleted afterwards.

## Result on one daemon, one gold set, two corpora

| corpus | passed | dev | held-out | recall@5 | MRR | citation | numeric | nf(a) | nf(b) | p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|
| pre-wave, 97 docs / 851 pages `2026-11-24-prewave-corrected-gold` | **38/55** | 31/45 | 7/10 | 45/48 | 0.826 | 34/48 | 37/43 | 4/6 | 46/48 | 12.3 / 56.3 s |
| English-only, 186 docs / 2,669 pages `2026-11-24-repro-a` | 35/55 | 28/45 | 7/10 | 45/48 | 0.839 | 32/48 | 37/43 | 3/6 | 46/48 | see `reports/determinism-2026-11-24.md` |

## What actually changed (question by question)

Lost when the wave and the quarantine are present: **q003, q040, q052, q055**.
Regained in the English-only corpus: **q004**.
Net: **-3** questions.

So the three-question gap is **real and corpus-driven**, not daemon drift, and it is not
"retrieval collapse": recall@5 is identical (45/48)
and MRR is *higher* on the larger corpus (0.839 vs 0.826). Two costs are visible
in the answer side: citation 34/48 -> 32/48 and
not-found (a) 4/6 -> 3/6 (one unanswerable
question is now answered because a wave document supplies plausible text).

## Consequence for the wave-01 decision

The decision to **keep** the English-only corpus and re-baseline at 35/55 (D-086) is now
measured without the version confound: the corpus costs **3 questions**, not 3-vs-a-different-
daemon, and the not-found (a) cost is **one question**. The conditions in D-086 stand, and the
rollback trigger is now precise: if the next step does not recover at least 2 of the 3 lost
questions (q003, q040, q052/q055 family), roll wave 01 back.

**Re-scoring caveat:** this run's citations can name documents that are now in
`data/quarantine/non-english/`, so re-running `eval/score.py` on it in the live tree would fail
the integrity check. The stored `scores.json` is the one produced inside the sandbox, where all
97 files existed. Re-scoring needs the pre-wave corpus restored (the 14 files are one move away,
listed in `logs/english-only-removed.jsonl`).

Settings: `qwen3.5:4b` digest `d8b0f5e9760c`, prompt `s6-3`, temperature 0, seed 0, num_ctx 4096,
cache off, table and rerank passes off, Ollama 0.40.18, corrected gold (`e679c341…`).
