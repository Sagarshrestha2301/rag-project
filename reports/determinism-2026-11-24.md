# Reproducibility on one Ollama daemon (2026-11-24)

**Question.** After the daemon auto-updated from 0.40.16 to 0.40.18, the fresh run on the
corrected gold (35/55) differed from the saved English-only run on four questions (q019,
q039, q044, q051). Is that sampling noise, or the runtime? This run answers it directly.

**Setup.** Two complete 55-question runs, back to back in one background job so nothing about
the runtime could change between them: `qwen3.5:4b` digest `d8b0f5e9760c`, prompt `s6-3`,
temperature 0, seed 0, `num_ctx` 4096, cache off, table and rerank passes off, 186-document
corpus (2,669 pages), corrected gold (`eval/questions.jsonl` SHA-256 `e679c341…`), Ollama
**0.40.18** throughout (`/api/version` checked before and after).

## Totals (identical)

| run | passed | dev | held-out | recall@5 | MRR | citation | numeric | nf(a) | nf(b) | p50 | p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A `2026-11-24-repro-a` | 35/55 | 28/45 | 7/10 | 45/48 | 0.839 | 32/48 | 37/43 | 3/6 | 46/48 | 12.9 s | 47.3 s |
| B `2026-11-24-repro-b` | 35/55 | 28/45 | 7/10 | 45/48 | 0.839 | 32/48 | 37/43 | 3/6 | 46/48 | 12.2 s | 47.0 s |

## Per question, not just totals

| field | identical between A and B |
|---|---|
| `status` | 55/55 |
| `answer` (exact text, including whitespace) | 55/55 |
| `citations` (file, page, quote, raw) | 55/55 |
| `retrieved` passages and scores | 55/55 |
| condensed `search_question` | 55/55 |
| `attempts` | 55/55 |

`eval/gate.py --current repro-b --baseline repro-a --start repro-a`: **exit 0, every rule
holds**, zero pass->fail and zero fail->pass. Verdict changes: **none**.

The earlier `2026-11-24-corrected-gold` run (same daemon, same gold, same corpus) is
**identical on all six compared fields** against run A, so the result is not a one-off pairing.

## Conclusion and consequence

Within one daemon, a 55-question run is **exactly reproducible** at temperature 0 with a fixed
seed - same statuses, same answer text, same quotations, same passages. Therefore the four
questions that differ against the 0.40.16-era runs are the **daemon version**, not sampling
noise, and comparisons across daemon versions are not valid measurements of a change.

Practical rules this fixes:

1. The English-only baseline **35/55 is stable** on 0.40.18; two independent repetitions
   reproduce it bit for bit, so it can be used for gating.
2. Any run made before 2026-11-24 was on 0.40.16 and must not be compared with a 0.40.18 run
   as if the only difference were the change under test (this is exactly the mistake the
   q039/q044 entries would have caused).
3. Pin **0.40.18** as the recorded runtime (PROPOSED D-088); the alternative, going back to
   0.40.16 and re-measuring, needs a download window and buys nothing unless a specific
   regression is traced to 0.40.18.

Runs: `eval/runs/2026-11-24-repro-a/`, `eval/runs/2026-11-24-repro-b/` (run files, scores,
reports). No eval set, corpus or code changed.
