# Step 20: one tolerated case difference at the start of a quotation (q052)

**Goal:** let a quotation verify when its **only** difference from the page is the case of its first
letter, through a helper the verifier and the scorer both use, and measure that it recovers q052
and moves nothing else.

**Needs approval to start:** yes. Owner instruction 2026-11-27 in chat ("lets do what is incomplete
and mark it done in the tracker", then choosing **q052 quote exactness** from the three scopes).
The `APPROVALS.md` line says it was typed on that instruction.

## Why

q052 is the one remaining question of the four D-086 losses. It fails for a copying defect, not a
retrieval or reasoning one: the page prints **"Bamboo clumps invites wild elephants, poisonous
snakes and insects."** and the model wrote

```
[1] 1970_Das_…_bamboos_in_W1999918290.pdf, p. 5: "bamboo clumps invites wild elephants"
```

The words are the page's, in the page's order, with one character changed: the sentence-initial
capital `B` became `b` because the quotation follows "because …" in the sentence. Both
`generation/verify.py` and `eval/score.py` compare case-sensitively (D-041), so the pipeline
rejected the answer, the retry produced the same quotation, and the question ended `unverified`.
Measured on the step-17 run: q052's gold page is **rank 1** and its other quotation
("every 2-3 years wild elephants roam around Kerabari and damage crops of the households") matches
the page after whitespace collapse, so this one character is the whole defect.

The narrowest honest fix is therefore one character: accept the quotation as typed or with its
first character's case flipped, and nothing else. A fully case-insensitive comparison is rejected:
it would stop the eval testing whether the model copies names and acronyms at all, which is the
property D-041 exists to protect.

## Tasks

1. `corpus.py`: add `quote_case_variant(text)` — returns the text with its first character's case
   flipped, or `None` when the first character is not an ASCII letter. No normalisation of its own;
   each caller keeps its existing comparison (`verify.norm`, `score.norm_space`).
2. `generation/verify.py`: a quotation verifies when it occurs in the page text **or** when its
   first-letter variant does. Everything else stays: case-sensitive, whitespace-collapsed,
   typographic quotes folded, no ellipsis, no stemming.
3. `eval/score.py`: the same two-way check, importing the same helper, so the pipeline and the eval
   cannot disagree the way they did on q003 (step 19).
4. Tests: `generation/test_verify.py` gains the q052 shape (accept), a case change **inside** the
   quotation (reject), one changed word (reject), and a quote whose first character is a digit or
   punctuation (reject); `eval/test_scorer.py` gains the accept and the mid-quote-reject cases.
5. Re-score every restatable stored run and diff question by question against the step-19 numbers:
   only q052 may move, and only where an answer has this shape.
6. Run the full 55-question eval on the installed pipeline (`CHAT_CACHE=0`) and compare against the
   step-17 run: q052 must reach `verified`, no other question may change status.
7. Re-run the gate comparisons against the step-17 predecessor and the accepted baseline, dev and
   `--milestone`, and record the exit codes.
8. Docs: `eval/SCORER.md` (the tolerance), `STATUS.md` (step row, measured facts, log line),
   `TRACKER.md` (step 20 line, D-086 accounting, next action), `DECISIONS.md` (PROPOSED D-100) and
   one `EVAL.md` Results row.

## Definition of done

- [ ] One helper in `corpus.py`; the verifier and the scorer both use it and neither keeps a copy
- [ ] The tolerance is exactly one character: the case of the quotation's first ASCII letter, and nothing else
- [ ] The new verifier and scorer cases pass, and every earlier case still passes
- [ ] Every restatable stored run is re-scored and only q052 moves
- [ ] The full run has q052 `verified` (attempts may be 1 or 2) with no other status change
- [ ] The gate exits 0 on dev against the predecessor and the accepted baseline, and on `--milestone`
- [ ] `eval/SCORER.md`, the step row, the log line, D-100 and the `EVAL.md` row exist; `TRACKER.md` is updated

## Context to read

`AGENTS.md`, `STATUS.md` (the 2026-11-26 entries and `reports/citation-layer-2026-11-26.md`),
`DECISIONS.md` D-041, D-096, `corpus.py` (`page_text`), `generation/verify.py` (`norm`,
`verify_answer`), `eval/score.py` (`norm_space`, the citation block), `eval/test_scorer.py`,
`generation/test_verify.py`, `eval/SCORER.md`.

## Expected output

```
>>> verify.verify_answer(answer, passages, check_page=lambda f, p: 'Bamboo clumps invites wild elephants, poisonous snakes and insects.')
{'ok': True, 'verified_quotes': 2, 'problems': [], ...}
# the same call with 'bamboo Clumps …' (a second character changed) still fails
```

## Risks

- **A case difference is still a difference.** A reader comparing the quotation to the page sees a
  lowercase `b` where the paper prints `B`; this step accepts that, which is why it is one character
  and not case folding in general.
- **The scorer becomes slightly kinder.** Every stored number has to be restated on the new contract
  (the step-18/19 practice), and the gate cannot detect the change because it re-scores both sides.
- **A cache could hide the fix.** `PROMPT_VERSION` does not move: only `unverified` answers can
  become verified, and unverified answers are never cached (D-017), so no stored answer can be
  replayed as verified without the new rule having been applied. This follows step 15's reasoning.
