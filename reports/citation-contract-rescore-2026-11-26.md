# Option C, re-scored on every stored run (2026-11-26)

**What this is.** The owner asked for option C from `reports/citation-layer-2026-11-26.md`
(accept a **verified** extra page when a gold page is also cited) to be turned into a decision
entry and scored against every saved run, so it can be accepted or rejected on numbers rather
than on one run's anecdote.

**What this is not.** No repository code changed, no stored `scores.json` was rewritten, and
`eval/score.py` is untouched. The alternative rule was applied **in process**, by importing the
real `eval/score.py`, calling its real `score_question`, and replacing only `citation_ok` (and
the `passed` flag that reads it), so recall, numeric and not-found come from the shipped scorer
on both sides of every comparison. `git status` is clean apart from this report and the notes.

## The rule, exactly

| | today | C1 |
|---|---|---|
| every cited page must be gold | **yes** | no |
| at least one cited page is gold | implied | **yes** |
| every cited quotation appears verbatim on the page it names | yes | yes |

So C1 changes one clause: an answer may cite extra pages **as long as one of them is the gold
page and every quotation on every cited page is real**. A paraphrase still fails. A citation to a
page that does not contain the quote still fails. An answer that misses the gold page still
fails (q030, which sources the same true sentence from p. 2 where the gold is the p. 6 table).

## Control: the re-score reproduces the recorded numbers

Before applying C1, the same script re-scored each run with the shipped rule. Every run agrees
with its recorded count except the runs made **before the D-085 gold correction**, which gain
exactly one question (q042, whose `gold_numbers` changed `50` → `Fifty`):

- pre-2026-11-24 runs: recorded + 1 (for example `2026-11-20-step9-retry-guard` 37 → 38);
- `2026-11-24-corrected-gold` onward: recorded = re-scored (35, 35, 38, 38, 37, 38, 38).

That is the same effect `reports/gold-corrections-rescore.md` recorded, so the comparison below is
clean: **before** and **after** are both measured on today's gold, and only the citation clause
differs.

## Every stored run

| run | n | recorded | before | **C1** | questions that flip to PASS |
|---|---|---|---|---|---|
| 2026-11-16-step6-full | 55 | 33 | 34 | **40** | q004, q008, q012, q024, q039, q049 |
| 2026-11-17-offline-step6 | 55 | 33 | 34 | **40** | q004, q008, q012, q024, q039, q049 |
| 2026-11-17-step6-heldout | 10 | 5 | 5 | **7** | q012, q024 |
| 2026-11-18-step6-after-ui | 55 | 33 | 34 | **39** | q004, q008, q012, q024, q049 |
| 2026-11-18-step6-prose-number-check | 55 | 33 | 34 | **39** | q004, q008, q012, q024, q049 |
| 2026-11-19-step8-after-condense-guard | 55 | 33 | 34 | **39** | q004, q008, q012, q024, q049 |
| 2026-11-19-step8-full | 55 | 33 | 34 | **39** | q004, q008, q012, q024, q049 |
| 2026-11-20-smoke-retry-guard | 4 | — | 1 | **1** | — |
| 2026-11-20-smoke-table-content | 13 | — | 4 | **4** | — |
| 2026-11-20-step9-cite-evidence | 55 | 36 | 37 | **42** | q017, q039, q048, q049, q051 |
| 2026-11-20-step9-d060 | 55 | 36 | 37 | **42** | q004, q008, q012, q024, q049 |
| 2026-11-20-step9-retry-guard | 55 | 37 | 38 | **42** | q017, q048, q049, q051 |
| 2026-11-20-step9-table-retrieval | 55 | 33 | 34 | **39** | q004, q008, q012, q024, q049 |
| 2026-11-22-english-only | 55 | 33 | 34 | **37** | q017, q049, q051 |
| 2026-11-22-rerank-anchor1 | 55 | 37 | 38 | **42** | q002, q039, q048, q049 |
| 2026-11-22-rerank-top10 | 55 | 37 | 38 | **42** | q002, q039, q048, q049 |
| 2026-11-22-wave01-full | 55 | 33 | 34 | **37** | q040, q049, q051 |
| 2026-11-24-corrected-gold | 55 | 35 | 35 | **39** | q017, q039, q040, q049 |
| 2026-11-24-prewave-corrected-gold | 55 | 38 | 38 | **41** | q004, q017, q039 |
| 2026-11-24-repro-a | 55 | 35 | 35 | **39** | q017, q039, q040, q049 |
| 2026-11-24-repro-b | 55 | 35 | 35 | **39** | q017, q039, q040, q049 |
| 2026-11-25-step15-refusal-line | 55 | 37 | 37 | **41** | q017, q039, q040, q049 |
| 2026-11-25-step16-list-format (rejected) | 55 | — | 35 | **43** | q004, q006, q012, q013, q024, q039, q044, q049 |
| 2026-11-25-step16-list-retrieval | 55 | 38 | 38 | **42** | q017, q039, q040, q049 |
| 2026-11-25-step17-list-shape | 55 | 38 | 38 | **42** | q017, q039, q040, q049 |

No run loses a question. The gain is **+3 to +6 on full runs** and **+8 on the rejected
`s6-4` run**, whose four "casualties" (q002, q004, q006, q013) were mostly extra-page failures.

## What it does to the numbers that matter

- **Accepted baseline `2026-11-24-repro-a`: 35 → 39.** Citation 32/48 → 36/48 (dev 25/39 →
  29/39, held-out unchanged), passed dev 28/45 → 32/45. Every other metric unchanged: recall@5
  45/48, MRR 0.839, numeric 37/43, not-found (a) 3/6, (b) 46/48.
- **Current run (step 17): 38 → 42.** Citation 33/48 → 37/48.
- **Wave-01 cost: 3 → 2.** Pre-wave 41 vs English-only 39 (was 38 vs 35). The wave still costs
  two questions, so "keep the corpus" still rests on something, but the gap narrows.
- **All three re-verified gate comparisons come out the same** — exit 0 before and after, because
  the four flips are identical on both sides of each comparison: step 17 vs its predecessor
  (dev passed 31/45 → 35/45 and citation 26/39 → 30/39 on *both* sides), step 17 vs `repro-a`,
  and `--milestone`. Nothing passes *because* of the rule; the gate simply cannot tell.

## D-086 accounting

C1 recovers **q040 only** — q017, q039 and q049 are not D-086 questions. **q052** (one lowercased
capital) and **q003** (the OCR text-source disagreement) are unchanged, so C1 alone recovers
**1 of 3** and does **not** meet the trigger. With option B (same page text on both sides) q003
would be the second, and the wave-01 rollback would be answered — but that is a second change and
must be measured as such.

## What the rule gives up (the honest cost)

- **Answers may cite up to two extra real pages** (q039 is the widest, with two extras; the other
  flips add one each). C1 never looks at how many, so a future answer could cite six true pages
  and pass. A cap (`at most 2 extras`) would keep every current gain — q039 uses exactly 2 — and
  is worth writing into the rule if C is accepted.
- **The canary stops checking that the answer is anchored to the page the question was written
  from.** That is the property that catches a plausible answer built from a distractor page. It is
  the reason D-041 was strict in the first place, and the reason this is an owner decision.
- **Every stored number changes.** If accepted, the whole history has to be re-stated on the new
  contract (the table above is the restatement), and two eras stop being comparable: runs before
  and after the change.
- **The signal does not have to be lost:** C1 plus a recorded per-answer `extra_pages` counter
  keeps the old information visible in the run table while it stops being a pass/fail rule.

## Recommendation

**Accept C1 with two conditions, or reject it — do not adopt it silently.** If accepted:

1. add the cap (at most 2 extra verified pages) so "any number of true citations" is not a pass;
2. record `extra_citations` per question in the score output, so a drift toward citation padding
   is still visible after it stops failing;
3. re-score and re-state every run in the same commit (this table), and say in `STATUS.md` that
   the canary measures a new contract from 2026-11-26.

If the canary is meant to keep testing "the answer is anchored to the designated page", **reject
it** and pursue option A instead: C1 would make the remaining 8 content failures look like 4, and
hide the anchoring property that D-041 was written to protect.

Either way, this does not clear D-086 on its own (q040 only), so it is not a substitute for the
next pipeline step.

## Not measured

- Any effect on a corpus other than this one, or on questions outside the 55.
- Whether a cap of 2 would hold on future answers (only q039 reaches 2 today).
- The four older-run flip sets (q004, q008, q012, q024) were not read one by one; only the recent
  four (q017, q039, q040, q049) were verified quote by quote in
  `reports/citation-layer-2026-11-26.md`.
