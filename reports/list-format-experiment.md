# A list-format experiment that can move q036 and q050 — design, and why the built one could not

Status: **design only.** No code, prompt, retrieval, corpus or index change was made for this
report. The `s6-4` list rule that was measured on 2026-11-25 is rejected (PROPOSED D-092);
its diff is kept at `eval/runs/2026-11-25-step16-list-format/prompt-s6-4.diff`, and the
working tree was reverted to `s6-3`.

## 1. What the rejected experiment measured

`eval/runs/2026-11-25-step16-list-format/` — 55 questions, `qwen3.5:4b` digest `d8b0f5e9760c`,
prompt `s6-4`, temperature 0, seed 0, cache off, Ollama 0.40.18, 186 documents / 2,669 pages.

| | accepted `2026-11-24-repro-a` (`s6-3`) | step 15 (`s6-3` + refusal line) | **step 16 (`s6-4`)** |
|---|---|---|---|
| passed | 35/55 | 37/55 | **35/55** |
| dev passed | 28/45 | 30/45 | 29/45 |
| held-out passed | 7/10 | 7/10 | **6/10** |
| citation | 32/48 | 32/48 | **30/48** (dev 25/39, held-out 5/9) |
| numeric | 37/43 | 37/43 | 39/43 |
| not-found (a) / (b) | 3/6 / 46/48 | 5/6 / 45/48 | 5/6 / 46/48 |
| MRR | 0.839 | 0.839 | 0.839 |
| p50 / p95 | 12.9 / — | 12.2 / 46.7 | 11.9 / 48.9 |

`eval/gate.py --current eval/runs/2026-11-25-step16-list-format
--baseline eval/runs/2026-11-24-repro-a --start eval/runs/2026-11-24-repro-a`
→ **GATE FAILS, 8 problems**, all rule 1: **q002, q004, q006 and q013 pass → fail** on
`citation, verdict`, with no explanation, against both baselines. Rules 2, 3 and 4 pass.

### The mechanism, per question

All four losses are citation-shape losses; the facts in the answers stay correct.

- **q004** keeps its verified `[1]` and adds a sentence citing `[4]` (a real quotation from
  page 4 of the same paper) — page 4 is not gold, and D-041 requires every cited page to be gold.
- **q006** adds two sentences, one citing `[3]` for "The correlation is satisfactory." — real
  text, wrong page.
- **q013** replaces its garbled formula quotation with a wider `[1]` quotation and adds `[3]`
  to page 1 of the same file — again a real, non-gold page.
- **q002** keeps only `[3]` and copies the quotation as `East-Rapti`; the page prints
  `East- Rapti`, so the quotation no longer exists on the page and verification fails.

So the rule's wording invited exactly this: it waived the four-sentence cap ("The
four-sentence limit does not apply to a list"), allowed "at most eight items", and required a
`[n]` on every line. More sentences and more markers is more chances to cite a real but
non-gold page, and a longer rule block shifts the model's copying enough to alter a quotation.

### Why it did not touch the two list questions

- **q050** answers in prose, **byte-identical to the `s6-3` baseline answer**. The rule never
  fired: it sat above the `table` route's own rules, and the model followed the table rules.
  The passage does contain the answer (`ginger` and `11-15` both present in the rank-1
  context), so this one *is* reachable by a prompt — but changing its shape changes nothing
  that is scored: `eval/score.py` has no list rule and the question already passes.
- **q036** is not a formatting failure at all. Measured on the live index:

  | | value |
  |---|---|
  | page text (`Marahatta`, p. 1) | 3,077 chars |
  | position of "Floods of 1964, 1981 and 1984 in the Sunkosi River…" | char **2,330** |
  | passage the model received (`corpus.search` rank 1) | **1,367 chars** |
  | "1964" in that passage | **False** |
  | "Sunkosi" in that passage | **False** |

  `corpus.context_for` keeps `HEAD_CHARS` 700 plus `best_window`'s 1,200-char window, and
  `best_window` picks the window containing the most **distinct query terms** with no
  weighting — so common words ("years", "floods", "paper", "list") beat the rare word
  "Sunkosi", and the page's only Sunkosi sentence is cut off. The model refused in both
  `s6-3` and `s6-4` because the answer was never in front of it.

## 2. How big that is, measured over the whole set

Offline screen over all 55 questions using the shipped router and `corpus.search`, asking
"does the question's `gold_quote` appear in the passages the model is given?" (whitespace
normalised, case-folded; no model calls):

- 48 answerable questions with a `gold_quote`;
- **37 have the quote in the passages the model sees**;
- **11 do not**: q012, q013, q015, q026, q027, q028, q030, **q036**, q039, q045, **q050**;
- **10 of those 11 have the gold page in the top-k anyway** (`page-in-topk`); only q015 and
  q045 are genuine retrieval misses.

That is the honest frame for this work: a list-format prompt change cannot move q036, and a
passage-window change is not a list experiment. They are two different changes and must be
measured separately.

## 3. The design

### Part A — make the passage contain the question's rare term (retrieval; required for q036)

Not a prompt change. Change how the window is placed, not how long it is:

1. `corpus.best_window` should pick the window by **IDF-weighted** term overlap (weights from
   the same `corpus.BM25`), so "Sunkosi" outranks "years".
2. Add a **coverage rule** instead of a bigger window: if a query term occurs on the page but
   not in the chosen window, **move the window to centre on that term** — do not append a
   second window and do not raise `WINDOW_CHARS`.

Rule 2 matters because the context budget is already measured as a constraint: D-073 showed
the table route's prompt reaching 16,012 characters against a 4,096-token `num_ctx`, after
which Ollama truncates and the model refuses. Growing passages would repeat that failure.

Candidate A2 (coverage only) is the one to try first because it is provable rather than
statistical: after the change, "every query term that appears on the page is present in the
delivered passage" is a check that can be asserted over all 55 questions, not tuned.

**Predicted, not measured:** q036's passage contains its sentence, so the model can answer.
It may still refuse, and that must be run. The other nine `page-in-topk` questions may move
in either direction — these are table and exact questions whose gold sentence is currently
cut off (q026/q027/q028 are the D-060/D-069 table failures), so this could help more than
q036. It is also the kind of change that can silently hurt, because every passage body is
the model's input.

### Part B — a list shape that cannot lengthen the answer (prompt, `s6-4`)

Two changes to the rejected wording, both aimed at the measured failure mode:

```
- When the answer is a set of parallel items -- years, names, crops, places -- answer with \
one list instead of sentences: at most six lines, each starting with "- " and ending with the \
[n] of the passage that item came from. The list is the answer; if the items need a unit or a \
range, at most one sentence may follow the list. Do not add a sentence or a citation to \
explain or contextualise the list, and cite only the passage the items came from.
```

Differences from the rejected rule, each tied to a measurement:

| rejected (`s6-4`) | proposed | why |
|---|---|---|
| "The four-sentence limit does not apply" | "The list is the answer; … at most one sentence may follow" | the four losses all added sentences and citations; an open-ended waiver invites that |
| "at most eight items" | "at most six lines" | eight items is eight more chances at a non-gold citation, and no gold answer in the set has more than five items |
| "every line starting with `- `" | unchanged | the shape itself was never the problem |
| rule placed before the route's `EXTRA_RULES` | **triggered deterministically**, see below | q050's answer was byte-identical: the model ignored the rule |

**Trigger deterministically.** `s6-4` relied on the model noticing the question "asks for a
list". It did not, on q050. The router is already a rule-based classifier with one
`prompt_mode` per route; a list **fragment** appended when a small regex matches the question
(`\blist\b`, `\bname the\b`, `\bwhich\b .* \b(crops|years|places|organisations?|documents?)\b`,
`\benumerate\b`) makes the rule reach the question whether or not the model notices. The
fragment must compose with `table` and `summary` rather than replace them, or q050 (route
`table`) loses the rule that keeps its numbers verbatim.

Explicitly rejected alternatives:
- routing lists to their own `k` — changes retrieval, which is a separate change and would
  confound the gate;
- a "list" prompt mode that replaces `table` — q050 is a table question and needs both rules.

## 4. Acceptance criteria (measure each part alone; never as one run)

Part A is a retrieval change, Part B a prompt change. Running them together makes the gate
unreadable, which is exactly what `s6-4` did by mixing in an unrelated prompt rewrite.

For each part, in this order:

1. **Offline screen, no model calls** (`scripts/`-style, as `scripts/measure-rerank.py` does).
   - Part A: the "gold quote present in the passages" count must go **37/48 → at least 39/48**
     and must not fall for any question; every query term on a page must be in its passage.
   - Part B: no screen applies; the regex trigger is checked by unit cases on q036 and q050
     ("both match the list pattern") and on q002/q004/q006/q013 ("none match").
2. **Full 55-question run**, then `eval/gate.py` against **both** the last accepted baseline
   and the start-of-step baseline: no unexplained pass → fail, no metric down by more than one
   question, **not-found (a) no drop at all**, MRR within 1/N.
3. **The four canaries are checked per question, not via the total**: q002, q004, q006 and
   q013 must keep the same status *and* the same citation set. A total that stays at 35/55
   while these four trade with four others is not acceptable, because that is what `s6-4`
   did against the 35/55 baseline (4 pass → fail, 5 fail → pass).

## 5. Expected effect, stated as prediction

- Part B alone: **q050 becomes a dash list; no score changes**, because the scorer has no list
  rule and q050 already passes. It cannot move q036. If the aim is the canary total, Part B
  alone is worth **zero questions** and should only be adopted if list-shaped answers are
  wanted for readers.
- Part A alone: unknown, and the screen says it can affect up to 10 questions. It is the only
  part that can move q036, and the only part with real upside.
- **Neither part meets D-086.** None of q003, q040, q052, q055 is a passage-window or list
  case, so the 2-of-3 recovery trigger is untouched and the wave-01 rollback question stays
  open regardless of what these measure.

## 6. What is not measured here

- Whether the model answers q036 once its sentence is in the passage. Both existing runs
  refused, and both lacked the sentence, so this is untested either way.
- Whether Part A helps or hurts the 10 affected questions. Only the offline screen above was
  run, and it measures presence of the gold quote, not answerability.
- Token cost of Part A. Because the window *moves* instead of growing, the intended cost is
  zero characters, but that is a property of the implementation, not something measured yet.
- Any effect on the UI's `debug` payload or the answer cache; Part A changes passage text,
  so cached answers would be stale and Part B would need the usual `PROMPT_VERSION` bump.
