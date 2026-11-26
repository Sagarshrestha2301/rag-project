# One page-text reader for the pipeline and the eval (2026-11-26, step 19)

**The defect.** The pipeline and the scorer disagreed about what a page says.
`corpus.page_text()` is the project's one rule: the PDF's own text, and for a page with no text
layer (under 40 non-space characters) the OCR text the index built. `generation/verify.py` has
always used it, because a scanned page has no text to quote otherwise. `eval/score.py` opened the
raw PDF itself. So a quotation taken from an OCR page could be **accepted by the answer pipeline
and failed by the eval** — the system penalised for quoting the text it had shown.

**How big it is.** Of the **59 citations** in `2026-11-25-step17-list-shape`, exactly **one**
differs between the two readers: **q003**, whose second citation quotes p. 15 of
`1975_Cost_cutting_caste_and_community_…pdf`, a page with **0 characters** of its own text and
1,476+ characters of OCR text. Eight stored runs carry it — every run made after the wave added
that document; no run before the wave does.

**The change.** `eval/score.py` now verifies a quotation through `corpus.page_text`, with the
basename of the cited path, and keeps the existence check and the strict comparison (case-
sensitive, whitespace-collapsed, no quote stripping, no hyphen joining — D-041 stands). The only
thing that changed is *which text* the comparison reads.

## Re-score, question by question

Every restatable run was re-scored and compared with its step-18 `scores.json`. Eight runs move;
**no other question in any run changes**, and no run loses anything:

| run | step 18 | **step 19** | move |
|---|---|---|---|
| 2026-11-22-english-only | 37 | **38** | q003 fail → PASS (citation) |
| 2026-11-22-wave01-full | 37 | **38** | q003 |
| 2026-11-24-corrected-gold | 39 | **40** | q003 |
| 2026-11-24-repro-a | 39 | **40** | q003 |
| 2026-11-24-repro-b | 39 | **40** | q003 |
| 2026-11-25-step15-refusal-line | 41 | **42** | q003 |
| 2026-11-25-step16-list-retrieval | 42 | **43** | q003 |
| 2026-11-25-step17-list-shape | 42 | **43** | q003 |
| the other 15 runs | unchanged | unchanged | none |

## What it means

- **D-086 is met.** The trigger was "recover at least 2 of q003, q040, q052 (q055 was step 15)".
  Step 18 recovered **q040**; this recovers **q003**. Wave 01 no longer needs to be rolled back.
  q052 (one lowercased capital letter) is the only one of the four still failing, and it is a
  model-copying defect, not a scorer or retrieval one.
- **The wave-01 cost is now 1 question**: pre-wave 41 vs the accepted English-only baseline
  `repro-a` 40, against 3 when D-089 measured it.
- **No gate verdict changes.** q003 moves on both sides of every recent comparison, so
  `eval/gate.py` still exits 0 on dev against the predecessor and `repro-a`, and on `--milestone`
  (q003 is a dev question, so held-out is untouched at 7/10).

## Risks

- **One reader is now load-bearing for both halves.** If `corpus.page_text` is wrong, the pipeline
  and the eval now agree on the wrong text instead of disagreeing. The test pins the OCR fallback's
  direction: a page with no text layer verifies from the OCR text, and the test asserts the raw
  page is empty.
- **For a scanned page the reader sees an image.** The project accepted that when the verifier was
  built (D-058); this step only makes the eval consistent with it.
- **The OCR text is not visible to a reader who opens the PDF**, so a verified quote on such a page
  cannot be found by the reader's own search. That was already true of every answer the pipeline
  accepted; it is now true of the score as well.

## Not measured

- How many corpus pages have no text layer and rely on OCR: the index reports **222 OCR pages**, but
  no run cites more than the one page above, so the practical effect on the canary is one question.
- Whether an OCR error could make a wrong quotation look verbatim. The strict comparison is against
  the OCR text, so an OCR mistake is now able to certify a quote the PDF image does not show.
