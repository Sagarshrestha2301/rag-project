# Step 19: the scorer reads a page's text the way the verifier does

**Goal:** make `eval/score.py` check a quotation against `corpus.page_text` — the one reader the
pipeline already uses — instead of opening the raw PDF itself. Then re-score every stored run and
measure the single question it changes.

**Needs approval to start:** yes. The owner asked for option B in chat on 2026-11-26 ("Implement
option B so the scorer and the verifier read a page's text from the same source, then re-score and
measure q003"). The `APPROVALS.md` line says it was typed on that instruction.

## Why

`corpus.page_text(doc, page)` is the project's one rule for what a page says: the PDF's own text,
and for a page with no text layer (fewer than 40 non-space characters) the OCR text the index built.
`generation/verify.py` uses it; `eval/score.py` opened the raw PDF instead, so a quotation taken
from an OCR page could be **verified by the pipeline and failed by the eval**.

Measured on the current runs: of 59 citations in `2026-11-25-step17-list-shape`, exactly **one**
differs between the two sources — **q003**, whose second citation quotes p. 15 of the 1975 Thakali
paper, a page with no text layer whose OCR text is what the model was shown. Eight runs carry it
(all since the wave added that document); none of the earlier runs do. Its removal is also the
second half of D-086: q040 was recovered by step 18, so q003 would make 2 of 3.

`eval/SCORER.md` already says a quote must exist "in the parsed text of that page", so this makes
the implementation match the spec rather than changing the spec.

## Tasks

1. `eval/score.py`: import `page_text` from `corpus` (with the repo root on `sys.path`, as
   `eval/gate.py` does) and use it for the quotation check, with the basename of the cited path.
   The existence check stays, and so does the strict, case-sensitive, whitespace-collapsed
   comparison — nothing about matching loosens.
2. `eval/test_scorer.py`: a new case proving the reader is shared, and that a quotation from a page
   with **no text layer** verifies against the OCR text while the raw PDF contains none of it
   (`0_NARAYAN_…` p. 1: raw 0 characters, OCR 1,476).
3. Re-score every restatable stored run and compare question by question against the step-18
   numbers: only q003 may move, and only in the eight runs that contain it.
4. Re-run the gate comparisons, including `--milestone`, and record the exit codes.
5. Docs: `eval/SCORER.md` (the reader), `STATUS.md` (step row, measured facts, log line),
   `DECISIONS.md` (PROPOSED D-098, with the D-086 accounting) and one `EVAL.md` Results row.

## Definition of done

- [ ] `eval/score.py` verifies quotations through `corpus.page_text`, with no second page reader
- [ ] The strict comparison is unchanged: a paraphrase, a case change or a missing page still fails
- [ ] The new cases pass and the earlier six cases still pass
- [ ] Every restatable run is re-scored and only q003 moves, in the eight runs that carry it
- [ ] The gate comparisons still exit 0 on dev and `--milestone`
- [ ] `eval/SCORER.md` names the reader; the step row, log line, D-098 and the `EVAL.md` row exist

## Context to read

`AGENTS.md`, `STATUS.md` (the 2026-11-26 entries), `DECISIONS.md` D-041, D-097, `corpus.py`
(`page_text`, `_raw_page_text`, `_indexed_text`), `generation/verify.py` (what it compares and why),
`eval/score.py`, `eval/test_scorer.py`, `eval/SCORER.md`.

## Expected output

```
>>> score.score_question(scan_question, row_quoting_ocr_text)
{'citation_ok': True, 'extra_citations': 0, 'passed': True, ...}
# raw PyMuPDF text for that page: 0 characters
```

## Risks

- **One reader is now load-bearing for both halves.** A bug in `corpus.page_text` would make the
  pipeline and the eval agree on the wrong text; the test pins the OCR fallback's direction.
- **The OCR text is not what a reader sees.** For a scanned page the reader sees an image; the
  project already accepted that trade when the verifier was built (D-058), and this step only makes
  the eval consistent with it.
- **History moves again.** q003 flips in eight runs, so the step-18 restatement is superseded by a
  step-19 restatement; the run folders carry the new numbers and `STATUS.md` says which contract
  each era was measured under.
