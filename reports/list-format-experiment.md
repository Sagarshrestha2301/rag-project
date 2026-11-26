# A list-format experiment that moves q036 and q050 and cannot cost q002/q004/q006/q013

Status: **design only, not built.** No prompt, retrieval, corpus or index change was made for
this report. The `s6-4` list rule measured on 2026-11-25 is rejected (PROPOSED D-092); its diff
is kept at `eval/runs/2026-11-25-step16-list-format/prompt-s6-4.diff` and the tree is on `s6-3`.

## 1. What the rejected experiment measured

`eval/runs/2026-11-25-step16-list-format/` — 55 questions, `qwen3.5:4b` digest `d8b0f5e9760c`,
prompt `s6-4`, temperature 0, seed 0, cache off, Ollama 0.40.18, 186 documents / 2,669 pages.

| | accepted `2026-11-24-repro-a` (`s6-3`) | step 15 (`s6-3` + refusal line) | **step 16 (`s6-4`)** |
|---|---|---|---|
| passed | 35/55 | 37/55 | **35/55** |
| dev passed | 28/45 | 30/45 | 29/45 |
| held-out passed | 7/10 | 7/10 | **6/10** |
| citation | 32/48 | 32/48 | **30/48** |
| numeric | 37/43 | 37/43 | 39/43 |
| not-found (a) / (b) | 3/6 / 46/48 | 5/6 / 45/48 | 5/6 / 46/48 |
| MRR | 0.839 | 0.839 | 0.839 |

`eval/gate.py --current eval/runs/2026-11-25-step16-list-format
--baseline eval/runs/2026-11-24-repro-a --start eval/runs/2026-11-24-repro-a`
→ **GATE FAILS, 8 problems, all rule 1**: q002, q004, q006 and q013 pass → fail on
`citation, verdict`, no explanation, against both baselines.

Cause, per question — citation shape, not facts: q004 adds a verified quotation from p. 4 of
the same paper (not gold), q006 adds two sentences including `[3]` for "The correlation is
satisfactory." (real, wrong page), q013 widens its `[1]` quotation and adds `[3]` to p. 1, and
q002's quotation loses the page's space in `East- Rapti`, so it no longer exists on the page.
The rule invited that by waiving the four-sentence cap and demanding a `[n]` on every line.

Why it never touched the list questions:

- q050's answer is **byte-identical** to `s6-3`: the rule sat above the `table` route's rules
  and was ignored.
- **q036 cannot be moved by any prompt.** Measured on the live index: page text 3,077 chars,
  "Floods of 1964, 1981 and 1984 in the Sunkosi River…" at char **2,330**, delivered passage
  **1,367 chars**, containing neither "Sunkosi" nor "1964". The model refused in both runs
  because the answer was never in front of it.

Wider, measured: **11 of the 48 answerable questions never see their `gold_quote` in the
retrieved passages**, and 10 of those already have the gold page in the top-k.

## 2. The guarantee: scope the change to questions it fires on

The only way a prompt change "cannot cost" four specific questions is for those four to receive
**byte-identical input**. That is available here, because the change can be scoped by a rule
that provably does not match them, and because identical inputs reproduce identical answers on
one daemon (measured 2026-11-24: two runs identical on 55/55, D-088).

### The trigger, measured over all 55 questions

```python
LIST = re.compile(
    r"\b(list|enumerate)\b|\bname the\b"
    r"|\bwhich\s+[a-z]+s\s+(can|could|are|were|do|did|have|include)\b",
    re.IGNORECASE,
)
```

Fires on **exactly q036 and q050** in the 55-question set (measured).

Two near misses that the wording is chosen to avoid:

- `\blisted\b` would add **q038** ("those listed by DHM/DPTC"), a passing comparison question;
  the trigger keeps `\blist\b`, not `listed`.
- A `which … has` alternative would also add q038; the trigger requires a **plural** subject
  (`[a-z]+s`), which is the shape of a list question.

The four canaries — q002, q004, q006, q013 — match neither branch (measured).

### Consequence

`list_style` is a **modifier**, not a route: it does not change `k`, does not change
`prompt_mode`, and does not change retrieval ranking. For a question where the trigger does not
fire, `build_system` and `context_for` take exactly their current code path. So:

- prompt for q002/q004/q006/q013: byte-identical;
- passages for q002/q004/q006/q013: byte-identical;
- answer: cannot change without the model drifting, and drift is measured as zero on one daemon.

This is asserted by a test, not hoped for: hash `prompt.build_system(hits, mode=...)` and the
`context_for` output for those four with the new code and compare against the current build.

## 3. The change, in two parts that ship together for the list questions only

### Part A — cover the rarest query term (this is what moves q036)

`corpus.best_window` maximises the count of **distinct** query terms in a 1,200-char window,
unweighted, so "years/floods/paper" beat "Sunkosi". Proposed signature change:

```python
def best_window(text, terms, width=WINDOW_CHARS, cover=()): ...
```

with `cover` = the query tokens present on the page, ordered by the corpus BM25 IDF, top two
kept. If a cover term is absent from the chosen window, the window is placed at that term
(`start = position - 200`) instead of at the highest-count position. **Sizes do not change**:
`WINDOW_CHARS` stays 1,200 and `HEAD_CHARS` 700, because D-073 measured the table route's
prompt already reaching 4,096 tokens; the window *moves*, it does not grow.

`corpus.search(..., cover=False)` passes `cover` only when the caller asks, and
`generation/answer.py` asks only for list questions.

**Prototype, measured out of tree** (no code changed), q036 rank 1:

| | before | after |
|---|---|---|
| cover terms | — | `sunkosi` (idf 7.48), `floods` (4.03) |
| window start | 167 | **2,157** |
| passage chars | 1,367 | **1,623** (+256 chars ≈ 64 tokens) |
| contains "Sunkosi" | False | **True** |
| contains "1964" / "1984" | False / False | **True / True** |

For q050 the coverage move leaves the useful page (p. 3) substantively intact — the passage
already contains "results indicate" in both the old and the new window — so its change is the
answer's **shape**, not its evidence.

### Part B — a list rule that cannot lengthen the answer

```
- When the answer is a set of parallel items -- years, names, crops, places -- answer with one \
list instead of sentences: at most six lines, each starting with "- " and ending with the [n] of \
the passage that item came from. The list is the answer; if the items need a unit or a range, at \
most one sentence may follow the list. Do not add a sentence or a citation to explain or \
contextualise the list, and cite only the passage the items came from.
```

Against the rejected rule, each difference answers a measurement:

| `s6-4` | proposed | why |
|---|---|---|
| "four-sentence limit does not apply" | "the list is the answer; at most one sentence may follow" | all four losses were added sentences carrying extra citations |
| "at most eight items" | "at most six lines" | no gold answer in the set has more than five items; eight is eight more chances at a non-gold citation |
| rule placed above the route rules | appended after `EXTRA_RULES` | q050 ignored the rule sitting above `table` |
| model decides it is a list | router regex decides | q050's answer was byte-identical, so discretion failed |

`PROMPT_VERSION` `s6-3` → `s6-5` (the cache is keyed on it, D-017); the fragment applies only
when `list_style` is true, so non-list answers keep their prompt byte for byte even though the
version string moves.

## 4. Measurement plan, in this order

**Stage 1 — offline, no model calls** (the existing pattern of `scripts/measure-rerank.py`):

1. Trigger table: `LIST` fires on q036 and q050 only, and on **none** of q002/q004/q006/q013.
2. q036: the delivered passage contains `gold_quote`'s sentence ("Sunkosi"); record chars before
   and after.
3. q050: the delivered passage still contains its evidence; record chars.
4. **The guarantee check:** for the other 52 questions, sha256 of every `build_system` output and
   every `context_for` output is identical to `HEAD`. Any difference fails the step.

**Stage 2 — full 55-question run**, cache off, same daemon, then `eval/gate.py` against both the
last accepted baseline and the start-of-step baseline.

Acceptance:

- q036 **no longer refuses** (status `verified` or `unverified`, not `not_found`). If it still
  refuses with its sentence in the passage, this design is falsified and the next lever is the
  list answer's evidence budget, not another prompt rewrite.
- q050 remains `verified` with the numeric rule still passing (`11-15` must stay in the answer);
  its shape is a dash list.
- q002/q004/q006/q013: **identical answer text and identical citation set**, checked per
  question. A 35/55 total that hides four trades is a failure, which is exactly what `s6-4` did.
- gate: no unexplained pass → fail, no metric down by more than one question, not-found (a) no
  drop, MRR within 1/N.

## 5. Honest expectations

- **The list shape alone changes nothing that is scored**: `eval/score.py` has no list rule and
  q050 already passes. Part B is reader-facing only.
- **Part A is the only part with upside**, and its upside is not just q036: the same sentence is
  missing from 11 answerable questions' passages. It is scoped to list questions here precisely
  to keep the guarantee, which means the other nine are untouched. Widening it later is a
  separate change with its own gate.
- **Neither part meets D-086.** q003, q040, q052 and q055 are not list or window cases, so the
  2-of-3 recovery trigger is untouched and the wave-01 rollback question stays open.
- **Cost:** +256 chars on one question's prompt (q036) for Part A; ~90 tokens of rules on two
  questions for Part B; one cache invalidation from the version bump.

## 6. Not measured

- Whether the model answers q036 once the sentence is in its passage. Both existing runs lacked
  the sentence, so this is untested either way — that is what Stage 2 is for.
- Whether the coverage move changes a passage badly on some other list question (the set has
  only two, so this cannot be generalised from 55 questions).
- Token cost of Part A across a real wave; the snapshot here is one question.
- Behaviour on a corpus change: coverage terms come from BM25 IDF over the live index, so the
  same question can place its window differently after a rebuild. That is acceptable for a
  retrieval-time decision but must be stated, and it is another reason to keep the change scoped.
