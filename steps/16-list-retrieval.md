# Step 16: Give a list question the passage that contains its items, and a list shape that cannot lengthen the answer

**Goal:** make a list question answerable when its items are printed on a retrieved page but
fall outside the passage window, and format the answer as a list — **without touching any
question that is not a list question**. `s6-4` failed both halves: it changed nothing on
q036/q050 and cost q002, q004, q006 and q013 (PROPOSED D-092). This step fixes the cause
(the window) and scopes the format change to a trigger that provably misses those four.

**Needs approval to start:** yes. Owner approval line for `APPROVALS.md` (proposed, the exact
date filled in when you approve):

```
2026-11-?? | start | step 16 | owner
```

The line must be committed with a message starting `OWNER:`, as steps 10-15 were.

## Why this step exists (measured 2026-11-25)

The accepted baseline is **35/55** on the English-only 186-document corpus, Ollama **0.40.18**,
prompt `s6-3`, corrected gold (`eval/runs/2026-11-24-repro-a/`). The step-15 refusal run is
**37/55** and is not yet accepted.

Two measurements set this step's size.

**1. The prompt is not the reason q036 refuses.** On the live index, `Marahatta` p. 1 holds
3,077 chars and the answering sentence — "Floods of 1964, 1981 and 1984 in the Sunkosi
River…" — starts at char **2,330**. The passage `corpus.search` hands the model is **1,367
chars** and contains neither "Sunkosi" nor "1964". `best_window` maximises the **count** of
distinct query terms in a 1,200-char window with no weighting, so "years", "floods", "paper"
and "which" beat the one rare term that matters. Both `s6-3` and `s6-4` refused because the
answer was never in front of the model.

This is not one question: over the 48 answerable questions, **11 never see their `gold_quote`
in the retrieved passages**, and 10 of those already have the gold page in the top-k.

**2. Scoping can be proven, not asserted.** One trigger regex, measured against all 55
questions, fires on **exactly q036 and q050** and on **none** of q002/q004/q006/q013:

```python
LIST = re.compile(
    r"\b(list|enumerate)\b|\bname the\b"
    r"|\bwhich\s+[a-z]+s\s+(can|could|are|were|do|did|have|include)\b",
    re.IGNORECASE,
)
```

Two variants were rejected on measurement because each also catches **q038** ("those listed by
DHM/DPTC", a passing comparison question): `\blisted\b`, and a `which … has` branch. A plural
subject (`[a-z]+s`) is what makes the second branch mean "several items".

**Prototype (out of tree, no code changed), q036 rank 1** — cover terms taken from the query's
two rarest tokens present on the page, window moved to the rarest one, `WINDOW_CHARS` and
`HEAD_CHARS` unchanged:

| | before | after |
|---|---|---|
| cover terms | — | `sunkosi` (idf 7.48), `floods` (4.03) |
| window start | 167 | **2,157** |
| passage chars | 1,367 | **1,623** (+256 ≈ 64 tokens) |
| contains "Sunkosi" / "1964" / "1984" | False / False / False | **True / True / True** |

The window **moves**; it does not grow. That constraint is measured, not stylistic: D-073
recorded the table route's prompt reaching 16,012 characters against a 4,096-token `num_ctx`,
after which Ollama truncates and the model refuses.

### Why this cannot cost q002/q004/q006/q013 (the design's whole point)

`list_style` is a **modifier**, not a route. It changes neither `k` nor `prompt_mode` nor the
ranking. Questions the trigger does not match take the current code path, so their rendered
prompt and their passages are **byte-identical**, and identical input reproduces identical
answers on one daemon (D-088 measured 55/55 bit-identical). Task 5 turns that into a test: hash
the rendered prompt and the passage for those four and compare against `HEAD`.

### Why the prompt change is small

`s6-4` waived the four-sentence cap, allowed eight items and demanded a `[n]` on every line;
all four losses were added sentences carrying extra citations to real but non-gold pages. The
replacement keeps the length contract and forbids extra commentary:

```
- When the answer is a set of parallel items -- years, names, crops, places -- answer with one \
list instead of sentences: at most six lines, each starting with "- " and ending with the [n] of \
the passage that item came from. The list is the answer; if the items need a unit or a range, at \
most one sentence may follow the list. Do not add a sentence or a citation to explain or \
contextualise the list, and cite only the passage the items came from.
```

It is appended **after** `EXTRA_RULES`, because q050 (`table`) ignored `s6-4` sitting above them
— its answer was byte-identical to the baseline.

### What this does not do

- **It does not score anything by itself.** `eval/score.py` has no list rule; q050 already
  passes. The visible gain is q036 (if the model answers once it can see the sentence) and the
  reader-facing list shape.
- **It does not meet D-086.** q003, q040, q052 and q055 are not list or window cases, so the
  2-of-3 trigger is untouched and the wave-01 rollback question stays open.
- **It does not widen coverage to all questions.** That is the tempting change and it is
  deliberately out of scope: the same missing sentence affects 10 other answerable questions,
  but touching every passage in the same run makes the gate unreadable. If this step is
  accepted, widening is the next step with its own approval.

## Tasks

1. `generation/router.py`: add `LIST` (exact regex above) and a `"list": bool` field on the
   route dict. Do **not** add a route, do not change `SETTINGS`, `k` or `prompt_mode`. Document
   in the module docstring that list is a modifier and why it is scoped.
2. `generation/prompt.py`: add `LIST_RULES` as its own constant (the text above, one string),
   extend `build_system(hits, *, mode="normal", list_style=False)` to append it **after**
   `EXTRA_RULES`, and bump `PROMPT_VERSION` `s6-3` → **`s6-5`** (not `s6-4`: that label belongs
   to the rejected run and its stored `meta.json`). The bump invalidates the answer cache per
   D-017; note that in the handoff.
3. `corpus.py`: give `best_window` and `context_for` an optional `cover=()` parameter and give
   `search` an optional `cover=False`. When `cover` is true, build the cover list from the
   query's tokens **present on that page**, ordered by the corpus `BM25` IDF, keep the top two,
   and if any is missing from the chosen window, place the window at the rarest one
   (`start = max(0, position - 200)`). Keep `WINDOW_CHARS`, `HEAD_CHARS` and the two-branch
   `context_for` shape; do not add a second window and do not change the ranking.
4. `generation/answer.py`: pass `cover=route["list"]` to `corpus.search` and
   `list_style=route["list"]` to `prompt.build_system`. Nothing else changes: the cache key
   already carries the prompt version, and a list question always renders the list prompt.
5. Tests, using the fixtures those files already build:
   (a) router: the trigger fires on q036 and q050, and on **none** of q002/q004/q006/q013/q038;
   (b) prompt: `list_style=True` appends the rule after the route rules and `list_style=False`
       renders byte-identically to today's output (hash both);
   (c) **the guarantee**: for q002/q004/q006/q013, the rendered prompt with the new code has
       the same sha256 as the current one, and so does `context_for` for their retrieved pages;
   (d) corpus: `context_for` with `cover` returns a passage containing the rare term for a
       fixed page/text fixture, and returns the current string when `cover=()` — no behaviour
       change by default;
   (e) every existing `generation/` case and the corpus case still passes.
6. Stage 1 screen, offline, no model calls — `scripts/screen-list-retrieval.py` writing
   `reports/list-retrieval-screen-2026-11-??.md`: the trigger table over all 55 questions, the
   q036/q050 passage before/after with char counts, and the sha256 equality check of Task 5c
   over the other 52 questions. **Any differing hash fails the step before a model is called.**
7. Stage 2, one full run, cache off, same daemon:
   `.venv\Scripts\python.exe -m eval.run_generation --out eval/runs/2026-11-??-step16-list-retrieval`
   then `.venv\Scripts\python.exe eval/gate.py` against the last accepted baseline
   (`2026-11-24-repro-a`) and the start-of-step baseline, plus `--milestone` for the held-out
   set.
8. Report per question: q036 (must not stay `not_found`; if it refuses with its sentence in the
   passage, stop and report — the design is then falsified and the next lever is the answer's
   evidence budget, not another prompt rewrite), q050 (must stay `verified`, `11-15` still in
   the answer, shape now a dash list), and q002/q004/q006/q013 (**identical answer text and
   citation set**, compared against the baseline run, not just equal totals).
9. If the gate fails, or any canary changes, revert in the same session and record the run as
   measured and rejected the way D-092 closed `s6-4`; do not tune the trigger or the rule
   against the 55 questions.
10. Append one `EVAL.md` Results row, one `STATUS.md` log line, and a PROPOSED `DECISIONS.md`
    entry describing the window rule and the scoping; state the D-086 accounting explicitly.

## Definition of done

- [x] `LIST` fires on q036 and q050 only among the 55 questions, is a modifier, and does not change `k`, `prompt_mode` or ranking
- [x] The rendered prompt and passages for q002/q004/q006/q013 are byte-identical to `HEAD`, proven by hash in the screen report and in a test
- [x] q036's passage contains its answering sentence (`Sunkosi`, `1964`, `1984`), with `WINDOW_CHARS`/`HEAD_CHARS` unchanged, so no passage grows beyond the mobile window plus head
- [ ] q050 answers as a list, stays `verified`, and still states `11-15`
- [x] `eval/gate.py` passes against both baselines, or the failure is explained and the change reverted
- [x] The new cases and every existing `generation/` and corpus case pass
- [x] Prompt, retrieval and `generation/answer.py` are the only code touched; `index/`, `data/`, `eval/questions.jsonl` and the gold are byte-unchanged
- [x] `EVAL.md` has the Results row, `STATUS.md` states the D-086 accounting, and `git status` is clean at session end

## Context to read

This file, `STATUS.md` ("Next action", the 2026-11-25 sixth-round log line, D-086, D-088),
`DECISIONS.md` D-073 (the prompt-size constraint), D-088 (reproduction within a daemon),
D-092 (this design's rejected predecessor), `reports/list-format-experiment.md` (the full
design and its measurements), `reports/failures.md`, `corpus.py` (`best_window`,
`context_for`, `search`, `BM25.idf`), `generation/router.py`, `generation/prompt.py`,
`generation/answer.py`, `generation/test_prompt.py`, `generation/test_router.py`,
`eval/gate.py`, `eval/runs/2026-11-24-repro-a/run.jsonl`,
`eval/runs/2026-11-25-step16-list-format/run.jsonl` and `prompt-s6-4.diff`.

## Expected output

One regex and a `list` flag in `generation/router.py`, one rule constant and a keyword in
`generation/prompt.py`, an optional `cover` parameter through three functions in `corpus.py`,
two keyword arguments at one call site in `generation/answer.py`, new cases, one screen script
and report, one full run, one `EVAL.md` row.

```
>>> from generation import router, prompt
>>> router.route("In which years does the paper list floods in the Sunkosi River?")["list"]
True
>>> router.route("What was the peak flood in the Bagmati River during the July 1993 event?")["list"]
False
>>> "at most six lines" in prompt.build_system(hits, list_style=True)
True
>>> import hashlib
>>> hashlib.sha256(prompt.build_system(hits).encode()).hexdigest() == baseline_hash
True
```

## Verification

Show, in the handoff:

- the trigger table from the screen script over all 55 questions;
- the q036 passage before/after (`chars`, and `Sunkosi`/`1964` present), and the q050 passage;
- the sha256 equality output for the four canaries and the count of unchanged questions (must
  be 53 of 55: the two list questions change, nothing else);
- `python -m generation.test_router`, `generation.test_prompt` and the corpus test output;
- the run's `scores.md`, and `eval/gate.py` exit status against both baselines and `--milestone`;
- the per-question comparison for q036, q050, q002, q004, q006, q013 (status, citations, answer
  text) against `2026-11-24-repro-a`;
- `git diff --stat -- index/ data/ eval/questions.jsonl` printing nothing.

## Risks

- **The trigger is fitted to this set.** It was written against 55 questions and refined after
  q038 matched. That is defensible because it is a question-shape rule a reader can check, but
  its behaviour on a real user's phrasing is unmeasured; the handoff must say so, and the regex
  must stay in the router where a wrong answer is a visible flag rather than a silent prompt.
- **Coverage can move a window onto a worse place.** On q050 the first page's passage shrinks;
  the screen only proves the gold quote survives on the useful page, not that every retrieved
  page improves. Only list questions are affected, and only two exist in the set.
- **The window rule is corpus-dependent.** Cover terms come from BM25 IDF over the live index,
  so the same question can place its window differently after a rebuild. Acceptable at retrieval
  time, but it must be stated in `STATUS.md` rather than discovered later.
- **The prompt bump invalidates the cache**, so the run after it re-asks every question; do not
  compare it against a cached run and call the difference an effect.
- **A list answer must not satisfy the numeric rule by accident.** q050's `11-15` has to appear
  in the list or in the one permitted sentence; a tidy list with the distances dropped would
  pass the shape and fail the number, which is a real regression even though the score may not
  show it.
- **Cross-daemon drift is not covered by the guarantee.** Byte-identical input means identical
  output only within one daemon (D-088); the baseline and this run must be on the same 0.40.18
  session, and the handoff must name the daemon.
