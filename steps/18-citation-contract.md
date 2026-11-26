# Step 18: the citation contract accepts a verified extra page, capped at two

**Goal:** change the scorer's citation rule from *every cited page must be a gold page* to
*at least one cited page is a gold page, every quotation is verbatim, and at most two cited pages
are outside the gold set*, and record how many extra pages each answer cited. Then re-score every
stored run so the history is on one contract.

**Needs approval to start:** yes — the owner asked for this in chat on 2026-11-26 ("Implement the
capped C1 rule in the scorer with an extra_citations counter and restate every stored run"), after
accepting option C of `reports/citation-layer-2026-11-26.md` with its three conditions. The
`APPROVALS.md` line added for it says it was typed on that instruction.

## Why

Measured in `reports/citation-contract-rescore-2026-11-26.md`: the old rule fails five questions
whose every quotation is verbatim on a real page, only because a second cited page is not in the
gold set (q017, q030, q039, q040, q049). The gold page rule is still worth keeping in part — it is
what stops an answer being sourced from a distractor page — so the accepted rule keeps it (at
least one gold page), keeps the quote check on every cited page, and caps the extras at two, which
is the widest any current answer uses (q039).

## Tasks

1. `eval/score.py`:
   - add `MAX_EXTRA_CITATIONS = 2`, with the reason in a comment (D-097, this step);
   - in `score_question`, compute `extra_citations` = the number of citation entries whose
     `(file, page)` is not in `gold_sources`, and require `gold_cited` and `quotes_ok` as well;
   - the quotation check now runs on **every** citation, including extras (a paraphrase on an
     extra page still fails the answer);
   - a missing cited file still fails, as before;
   - record `extra_citations` per question (`None` for unanswerable questions, which are not
     scored on citation);
   - add a per-set `extra_citations` summary (total, maximum in one answer, number of answers with
     at least one) to `_metrics`, and one line in `scores.md`.
2. `eval/test_scorer.py`: a new case with six rows built from a real gold question —
   (a) gold page only → citation ok, extras 0; (b) gold + one verified extra → ok, extras 1;
   (c) gold + three verified extras → fails on the cap; (d) gold + an extra whose quote is not on
   its page → fails, and the same row with only the extra page (no gold) → fails.
3. `eval/SCORER.md`: replace the `citation_correct` definition and record the change, the cap and
   the counter, with the date and D-097.
4. Re-score every stored run that can be scored in the live tree:
   `.venv\Scripts\python.exe eval/score.py --run eval/runs/<run>/run.jsonl --out eval/runs/<run>`
   Run it for every run that already has a `scores.json` and for `2026-11-25-step16-list-format`
   (55 rows, never scored). Runs whose citations point at a quarantined file cannot pass the
   integrity check; list them rather than forcing them.
5. Re-run the three gate comparisons (step 17 vs its predecessor on dev and `--milestone`,
   step 17 vs `2026-11-24-repro-a`) and record the exit codes and the metric table.
6. Docs: one `EVAL.md` Results row for the contract change, the step row and log line in
   `STATUS.md`, and the approval note on D-097 in `DECISIONS.md`. **`EVAL.md`'s metric definition
   still says "every cited page is gold"** — that sentence is owner-only, so its exact
   replacement goes under "Proposals for owner" in `STATUS.md`, not into the file.

## Definition of done

- [x] `citation_ok` follows the new rule: gold page required, every quote verified, extras ≤ 2
- [x] `extra_citations` is recorded per question and summarised per set
- [x] The six new cases pass and the earlier five cases still pass
- [x] Every restatable stored run is re-scored, and each new count equals the number measured in
      the C1 probe, less the questions the cap excludes (q049 in ten old runs, q026/q044 in `s6-4`)
- [x] The three gate comparisons still exit 0, with their metric tables recorded
- [x] `eval/SCORER.md` describes the rule it implements; the `EVAL.md` contradiction is proposed
- [x] `git status` clean, and the runs not restated (two smoke subsets with no stored scores) are named with the reason

## Context to read

`AGENTS.md`, `STATUS.md` (the 2026-11-26 entries), `DECISIONS.md` D-041 and D-097,
`reports/citation-contract-rescore-2026-11-26.md`, `eval/score.py`, `eval/test_scorer.py`,
`eval/SCORER.md`, `eval/gate.py`, `EVAL.md` (metrics section).

## Expected output

```
>>> score.score_question(q001, row_with_gold_plus_one_verified_extra)
{'citation_ok': True, 'extra_citations': 1, 'passed': True, ...}
>>> score.score_question(q001, row_with_gold_plus_three_verified_extras)
{'citation_ok': False, 'extra_citations': 3, 'passed': False, ...}
```

## Risks

- **The canary stops testing anchoring.** An answer built from a distractor page that carries a
  true quotation can now pass. The cap limits it; the counter keeps it visible; nothing else does.
- **Comparability.** Every stored number changes. The restatement is the point, but any sentence
  in `STATUS.md` or a report that quotes an old count has to be read as "under the old contract".
- **The gate cannot see this change.** It moves both sides of a comparison equally, so a future
  scorer change with a similar shape would also be invisible — the counter is the mitigation.
