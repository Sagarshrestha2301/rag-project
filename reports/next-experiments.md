# What to fix next, ranked (Step 9, 2026-11-20)

Source run: `eval/runs/2026-11-20-step9-retry-guard` (37/55 passed, dev 30/45, held-out
7/10, citation 36/48, numeric 37/43, not-found (a) 3/6, (b) 46/48). The failing questions
and the rule each one broke are in `reports/failures.md`, written by `eval/failures.py`
from that run. This file turns those 18 failures into experiments, biggest and cheapest
first. Nothing here is approved; each item is one measured change of its own.

## 1. Count the exact refusal line as "not found", even when prose surrounds it (3 questions)

**Evidence.** q020, q021 and q055 are unanswerable, and the model did refuse: every one of
their answers contains `Not found in the indexed documents.` verbatim. But each also
carries a sentence of its own prose ("The provided passages do not state the elevation of
the Tistung rainfall station."), so `generation.gate` does not record a refusal, the
scorer counts them as `answered an unanswerable question`, and they cost 3 of the 18
failures.

**Change.** One rule in `generation/gate.resolve`: if the exact `prompt.NOT_FOUND_TEXT`
line appears anywhere in the answer, the decision is `not_found`, regardless of the prose
around it. No change to the prompt, the retrieval or the verifier.

**Why this is not D-060 again.** D-060 (2026-11-19) accepted a refusal written *in the
model's own words*, which meant guessing whether a sentence was a refusal; it turned two
answerable questions into false "not found" and was rejected (D-068). This rule never
guesses: it waits for the exact line the prompt tells the model to write.

**Measure.** Full 55-question run; not-found (a) must not drop (that is what the last
attempt broke), not-found (b) must not fall, and q020/q021/q055 must pass.

## 2. Table questions that need a row: the table route already has the page (5 questions)

**Evidence.** q026, q027 and q028 are unverified because the model says the passages "do
not contain Table 2", while the gold quote is a table row. The two table experiments so
far say why: which page to read is already right (D-070), and adding the rows to the
passage overflows the 4,096-token context and the model truncates and refuses (D-073).

**Change.** Do both halves together, once, as one experiment: shorten what a table passage
carries (page opening plus the matching rows, no middle prose window) *and* add the rows.
That keeps the prompt the same size while changing what is in it. The row text must stay
byte-identical to the page's text layer, or the quote check will reject it.

**Measure.** Full run with the flag on; the risk is the nine table questions that pass
today from prose (q025, q029-q031, q041, q042, q046, q050).

## 3. A verified extra page is still scored a miss (4 questions)

**Evidence.** q017, q048, q049 and q051 each cite a real page whose quotation verifies, in
addition to the gold page, and D-041's rule (every cited page must be a gold page) turns
that into a citation failure. Three of the four answers state the correct figures.

**Change.** This one needs an owner decision, not code: either D-041 accepts a verified
extra page when the gold page is also cited, or the gold sets are widened. Both touch the
eval contract, so it is a `DECISIONS.md` proposal first.

## 4. Retrieval window: the answer is on the page but not in the passage (3 questions)

**Evidence.** q015 (the paper's recommendation about equations 1-4), q045 and q046 are
retrieved correctly - recall@5 is 45/48 and MRR 0.826 - but the passage window
(`corpus.context_for`: 700 characters of page opening plus a 1,200-character window) does
not hold the sentence the question needs.

**Change.** Widen the window for the `summary` route only, or choose the window by the
question's terms at sentence granularity instead of a fixed 1,200 characters. One route,
one measurement; the cost is prompt tokens on a context that is already tight.

## 5. Latency: 11.4 s median, 28.9 s at p95

Not a failure, a budget check. Both are inside N2's 20 s typical target at the median and
over it only at p95, and the 37/55 run is faster than the run it replaced (13.4 / 27.7).
Nothing to do unless the target is meant as a p95.

## Not on this list, and why

- HyDE, multi-query and RAPTOR: no evidence in this set that the page is wrong; the
  failures above are about what the model is shown or how its answer is counted.
- Fine-tuning the model: the four answer-quality groups above are cheaper and reversible.
- A bigger model: 4B fits the card with room for the embedder and reranker on CPU; a
  larger one would spill to RAM and fail N2.
