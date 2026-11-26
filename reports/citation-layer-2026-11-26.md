# Where the failures actually are: the citation layer (2026-11-26)

Read-only analysis of the current run, `eval/runs/2026-11-25-step17-list-shape/`
(**38/55**: dev 31/45, held-out 7/10, citation 33/48, numeric 38/43, not-found (a) 5/6,
(b) 46/48). No code, prompt, index, corpus or gold file was changed; every number below comes
from the run's own `run.jsonl` and `scores.json`, `eval/questions.jsonl`, and the page text of
the cited PDFs.

**Why this file exists.** D-086 says the next accepted change must recover at least 2 of the
wave-01 losses (q003, q040, q052; q055 was recovered by step 15) or wave 01 is rolled back.
The last three steps each attacked that question through retrieval or prompts and each moved a
different question (q036, q055). Before writing a fourth, this file asks what the losses are
actually made of. The answer is not retrieval: **all three remaining losses are citation-layer
outcomes**, and two of them are not the model's fault.

## The 17 failures, by cause

| cause | n | questions |
|---|---|---|
| every quotation verbatim, but an extra cited page is not gold (D-041) | **5** | q017, q030, q039, q040, q049 |
| no citation produced at all (the model said the passages lack the answer) | 5 | q015, q026, q027, q028, q046 |
| quotation is a paraphrase, not the page's words | 3 | q044, q045, q048 |
| quotation differs from the page only in the first letter's case | **1** | q052 |
| pipeline and scorer read the page from different text sources | **1** | q003 |
| numeric mismatch (68.33% vs the gold figure) | 1 | q029 |
| an unanswerable question answered, and `verified` with a citation | 1 | q020 |
| **total** | **17** | |

Bold rows are the three D-086 losses, plus q040's neighbours.

## 1. Five answers quote real pages and are failed for it (5 questions)

For q017, q030, q039, q040 and q049 **every citation's quotation appears verbatim on the page
it names**. They fail only because `eval/score.py` requires every cited page to be a gold page
(D-041). Four of the five cite the gold page *as well*; q030 cites a different page of the right
document.

- **q040** (a D-086 loss): gold p. 2 plus p. 1 of the same paper — `"The maximum rainfall
  intensity of 88 mm h-1 was recorded in 1989 at Pokhara…”` is really on p. 1. Answer and
  numbers are correct; the extra citation is honest and verified.
- **q017**: gold p. 1 plus p. 4 of the same paper, both verbatim.
- **q039**: three citations, all verbatim; the extra one is the Tistung/Ghantemadi passage.
- **q049**: gold plus one extra page, both verbatim.
- **q030**: gold is the table on p. 6; the answer cites p. 2, where the sentence
  `"Altogether, 199 households in the Terai, 208 in the Midhills"` really is printed, and the
  figures (41 / 208) are right. The gold page is the table, so the answer is marked a miss for
  sourcing the same fact from prose.

So this group is five questions where the system gave a correct answer with real evidence and the
eval's gold-page rule turned it into a failure. That is a contract question, not a bug — but it
is 29% of the remaining failures and it contains one of the three D-086 losses.

## 2. q052 fails on one capital letter (1 question, a D-086 loss)

Gold page p. 5, two citations, both quotes genuinely on the page. The page prints
`"Bamboo clumps invites wild elephants"`; the answer's second sentence lowercases it to
`"bamboo clumps invites wild elephants"` because it sits mid-sentence. Both `generation.verify`
and `eval/score.py` compare case-sensitively, so the pipeline correctly refused it
(`unverified`, `attempts=2`) — the retry produced the same lowercased quote, so the model cannot
fix this defect by being asked again.

## 3. q003 is `verified` by the pipeline and failed by the scorer (1 question, a D-086 loss)

The answer cites gold p. 1 (verbatim) and p. 15 of the 1975 Thakali paper for
`"…annual rainfall is 3587 mm per year…"`. The quotation **is** in the text the system holds and
shows (`generation.verify.page_text` → `index/pages.json`, which carries OCR text), so the
verifier passed the answer on attempt 1. It is **not** in the PDF's own text layer that
`eval/score.py` reads with PyMuPDF, so the scorer fails it.

Measured scope: of **59** citations in the run, exactly **1** differs between the two text
sources — this one. So it is not a systemic defect, but it is a real inconsistency: **the system
can be failed for quoting the text it showed the reader.**

## 4. The genuine content failures are a different, more expensive group (9 questions)

- **5 questions produced no citation** (q015, q026, q027, q028, q046) because the model said the
  passages did not contain the table or the sentence. This is the table/passage-window group that
  `reports/next-experiments.md` item 2 describes (rows must **replace** the prose window, not be
  added to it — D-073 measured the table route already at the 4,096-token limit).
- **3 questions quote a paraphrase** (q044, q045, q048). The verifier caught all three and both
  attempts were rejected, so this is a model limitation the current retry cannot repair.
- **q029** states 68.33% where the gold figure differs; **q020** is an unanswerable question the
  model answered and the pipeline marked `verified` with a citation — the worst single state in
  the set, because a reader is shown it as trustworthy.

## What this means for D-086

q040 is group 1, q052 is group 2, q003 is group 3. **None of the three remaining losses is a
retrieval failure** — recall@5 is 45/48 and q040/q052/q003 all retrieve their gold page at rank 1.
Three more retrieval or prompt steps would be aimed at the wrong layer.

## Options, ranked

### A. Step 18 — "cite fewer pages, quote them exactly" (pipeline only, no contract change)

One prompt rule plus a sharper retry message: cite only the passage that carries the answer
(no supporting citation for background), and copy the page's sentence including its capital
letter. Targets group 1 (the extras) and group 2 (the case), i.e. **q040 and q052**.

- Cost: one prompt-version bump (`s6-6` → `s6-7`, cache invalidated), one full 55-question run,
  gate against `2026-11-25-step17-list-shape`.
- Risk: a rule against extra citations can hurt the comparison questions that legitimately cite
  two pages (q013, q017, q018) — those must be checked individually, as step 17 checked
  q002/q004/q006/q013.
- Honest projection: **q040 likely, q052 uncertain** (the model already ignored a formatting rule
  twice; D-094 says a checked property beats a requested one, and this one is a prompt request).
  So A alone probably does not meet D-086's 2-of-3 trigger.

### B. Fix the one text-source disagreement (small, correctness)

Score a quotation against the same page text the pipeline reads, or make the verifier read the
PDF layer. Either way one side changes, and all stored runs must be re-scored to stay comparable.
Recovers **q003**. It is a correctness fix, not a relaxation: today the two halves of the system
disagree about what a page says.

### C. Owner decision: what "cites a true page" should mean (D-041 contract)

Accept a verified extra page when the gold page is also cited, and/or match a quotation
case-insensitively. That recovers **q017, q039, q040, q049** and **q052** at once (five
questions), and with B it meets D-086 without touching the pipeline.

**Say plainly what this is:** it raises the score by changing what a pass means, not by making the
system better. It is defensible (a correct answer with real evidence is arguably a pass) but it
must be an explicit owner decision with every past run re-scored, not a step an agent slips in to
clear a trigger. If the number is meant to track system quality, C should be rejected.

### D. The content group (highest quality payoff, highest cost)

The 5 no-citation table questions, then the 3 paraphrase-quote questions. This is the only group
that would make the reader experience better in a way the score currently under-reports. It needs
the paired table-window experiment from `reports/next-experiments.md` item 2, which touches
passage construction and therefore the gold pages — the largest change on this list.

### E. Not proposed: a fourth retrieval step

Recall@5 is 45/48 and every remaining D-086 loss retrieves its gold page at rank 1. Step 16's
window rule was right for q036 and has nothing left to win here.

## Recommendation

1. **Step 18 = A** (citation discipline: fewer citations, exact quotation), measured on its own.
   It is the only option that can move q040 and q052 without changing the eval contract.
2. **Put C to the owner as a decision in parallel**, because no amount of code can settle whether
   an extra true citation is a pass. If C is accepted, re-score every stored run in the same
   session and record that the historical numbers are on a new contract.
3. **Fold B into whichever of those runs**, since it is one citation and a genuine inconsistency.
4. **D after that**, because it is the only group where a reader is actually losing an answer.

With B + C the D-086 trigger is met (q003 + q040, plus q052) without a wave-01 rollback. With A
alone it is probably not, and that must be said before the step is approved, not after the run.

## Not measured

- Whether the prompt rule in A changes the comparison questions (q013, q017, q018) — that is what
  its run would measure.
- Whether any of this generalises past the 55-question canary.
- The cost in model calls: A adds no call unless a retry fires.
