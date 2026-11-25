# Step 15: Accept a refusal the model actually wrote, without swallowing a table answer

**Goal:** count an answer as `not_found` when it contains the prompt's exact refusal line
and cites nothing at all, so q021 and q055 - unanswerable questions the model did refuse in
prose - stop scoring as false answers. The prompt, retrieval and index do not change, and
`said_not_found`'s strict reading stays.
**Needs approval to start:** yes. Owner approval line for `APPROVALS.md` (proposed):

```
2026-11-?? | start | step 15 | owner
```

## Why this step exists (measured on 2026-11-24)

The accepted baseline is **35/55** on the English-only 186-document corpus, Ollama
**0.40.18**, corrected gold (`eval/runs/2026-11-24-corrected-gold/`). Not-found (a) is
**3/6**: q020, q021 and q055 are unanswerable, and the model *did* refuse on q021 and q055,
but not in the required form, so the scorer counts both as answers.

Measured over that run's 55 answers, **11 contain `Not found in the indexed documents.`**
verbatim. Seven of the 11 are gold not-found questions, four are answerable:

| id | gold | status now | citation markers | text after the line |
|---|---|---|---|---|
| q015 | answerable | not_found | 0 | the line only |
| q019 | not found | not_found | 0 | the line only |
| q021 | not found | **unverified** | 0 | disclaimer sentence |
| q022 | not found | not_found | 0 | the line only |
| q026 | answerable | unverified | 1 | disclaimer + `[3] …Das…` |
| q027 | answerable | unverified | **0** | disclaimer naming a table |
| q028 | answerable | unverified | 1 | disclaimer + citation |
| q036 | answerable | not_found | 0 | the line only |
| q053 | not found | not_found | 0 | the line only |
| q054 | not found | not_found | 0 | the line only |
| q055 | not found | **unverified** | 0 | disclaimer sentence |

Two measurements decide the rule:

1. **Position does not separate them.** In all 11 the line is the last non-empty line, so
   "the answer ends with the line" changes nothing useful.
2. **"No citation marker anywhere" separates nine of the ten that matter.** It leaves q021
   and q055 (the two wins) plus q027 (an answerable table question whose disclaimer never
   cites anything, so it slips through and becomes a false refusal).

So the proposal is: accept the line when it appears and the answer carries **no `[n]`
marker at all**; keep the exact line as the prompt's contract; leave `said_not_found` and
`gate.resolve`'s other branches alone.

### Why this is not D-060 again

D-060 accepted a refusal written *in the model's own words*, was built on 2026-11-20 and
was rejected on measurement as **D-068**: not-found (a) 3/6 -> 6/6, but q027 and q028 —
both answerable and both **passing** — were flipped to a false "not found", so the gate
failed on rule 1 and not-found (b) fell 37/39 -> 35/39. That change was removed.

This rule never reads the prose: it waits for the exact line the prompt tells the model to
write, and only asks whether the answer cites anything. Its predicted cost is **one**
answerable question (q027, today already failing), not two passing ones, and the guard it
uses is structural (did the model cite a page), not a phrase list fitted to two questions.
The honest limit: q027 is still misfiled, and that is one question of not-found (b).

### What it does not fix

q003, q040 and q052 are answerable questions that wave 01 broke, and this step touches
none of them. It therefore **does not satisfy D-086's trigger** on its own (recover at
least 2 of the 3 lost questions, or roll wave 01 back): q055 is one. If this is the last
change before the next accepted run, that decision is the owner's, not this step's.

## Tasks

1. In `generation/verify.py`, keep `said_not_found()` strict (the first non-empty line is
   the exact line) and add one helper, `refused_with_line(answer) -> dict`, that reports
   `{"accepted": bool, "line_only": bool, "markers": int, "reason": str}` for the wider
   form: the exact line appears as a whole line (case-insensitive, trailing period
   optional) **and** the answer contains no `[n]` citation marker. Use the same
   `NOT_FOUND_TEXT` constant; do not add a second copy of the string.
2. In `verify_answer()`, when the wide form is accepted, set `said_not_found` true **and**
   record `"refusal_form": "exact_line_with_prose"` on the result, instead of appending
   the "more text follows the refusal line" problem. A strict refusal keeps
   `"refusal_form": "line_only"`. Do not rewrite the model's text.
3. `gate.resolve()` then needs no branch of its own: `said_not_found` already maps to
   `not_found`, and the reason string must name which form was accepted so the record and
   the UI debug payload can show it.
4. No prompt change, so `PROMPT_VERSION` stays `s6-3` and no cache key moves. Note in the
   handoff why that is safe: an accepted refusal was `unverified` before, and `answer.py`
   never caches an unverified answer.
5. Cases in `generation/test_verify.py` and `generation/test_gate.py`, using the fixtures
   those files already build:
   (a) disclaimer + exact line, no marker -> `said_not_found` true, form
       `exact_line_with_prose`, decision `not_found`;
   (b) the line alone -> unchanged (`line_only`);
   (c) disclaimer + exact line **and** a `[3]` citation -> not a refusal, unchanged
       behaviour (the q026 shape);
   (d) an answerable-looking answer that merely *quotes* the line inside a quotation with
       a citation -> not a refusal;
   (e) empty answer -> not a refusal, no crash;
   (f) every existing verify/gate case still passes.
6. Run the full 55-question set, cache off, on the shipped daemon (0.40.18):
   `.venv\Scripts\python.exe -m eval.run_generation --out eval/runs/2026-11-??-step15-refusal-line`
   then `.venv\Scripts\python.exe eval/gate.py` against both the last accepted baseline
   and the start-of-step baseline. Re-run any comparison that needs the pre-wave corpus
   with the sandbox recipe in `reports/wave01-unconfounded-2026-11-24.md`, never against
   the live corpus.
7. Compare question by question with `2026-11-24-corrected-gold` and report: passes, dev,
   held-out, not-found (a), not-found (b), citation, numeric, recall@5, MRR, and the
   status change for each of the 11 questions in the table above. **Expected from the
   projection: passed 35 -> 37, not-found (a) 3/6 -> 5/6, not-found (b) 46/48 -> 45/48,
   q021 and q055 pass, q027 becomes a false "not found", q026 and q028 unchanged.** That
   is a projection from the saved run, not a result: the run decides.
8. If the gate fails, revert the change in the same session and record the run as measured
   and rejected, the way D-068 was closed; do not tune the marker guard against the 55
   questions.
9. Append one `EVAL.md` Results row and one `STATUS.md` log line, and state in the handoff
   whether D-086's 2-of-3 trigger was met (with this change alone it is not).

## Definition of done

- [ ] A prose-then-exact-line refusal with no citation marker resolves as `not_found`, and the record names the form
- [ ] A disclaimer that cites a page still resolves as `unverified` and is never rewritten into a refusal
- [ ] `generation/verify.py`, `gate.py` and `eval/score.py` are the only code touched; prompt, retrieval, index and `eval/questions.jsonl` are byte-unchanged
- [ ] The new cases and every existing `generation/` case pass
- [ ] The full run is recorded with its gate output against both baselines, and the per-question diff matches the table above or the difference is explained
- [ ] The D-086 accounting is stated in `STATUS.md` (how many of q003/q040/q052/q055 this change recovered)
- [ ] `EVAL.md` has the Results row and `git status` is clean at session end

## Context to read

This file, `STATUS.md` ("Next action", round eight, D-086, the not-found (a) bullet),
`DECISIONS.md` D-060 (approved) and D-068 (measured and rejected), `reports/next-experiments.md`
section 1, `reports/failures.md`, `generation/verify.py`, `generation/gate.py`,
`generation/answer.py` (`gate.resolve` call site and the cache rule), `generation/test_verify.py`,
`generation/test_gate.py`, `eval/gate.py`, `eval/runs/2026-11-24-corrected-gold/run.jsonl`.

## Expected output

One extra helper and a wider branch in `generation/verify.py`, no new branch in
`generation/gate.py`, six cases, one full run and one `EVAL.md` row. Nothing under `data/`,
`index/` or `eval/questions.jsonl` changes.

```
>>> from generation import verify, gate
>>> v = verify.verify_answer("The provided passages do not state the elevation.  "
...                          "Not found in the indexed documents.", passages)
>>> v["said_not_found"], v["refusal_form"]
(True, 'exact_line_with_prose')
>>> gate.resolve(v)["decision"]
'not_found'
>>> v2 = verify.verify_answer("Passages do not contain Table 2. [3] Das 1970, p. 4: \"...\"",
...                           passages)
>>> v2["said_not_found"], gate.resolve(v2)["decision"]
(False, 'unverified')
```

## Verification

Show, in the handoff:
- `python -m generation.test_verify` and `generation.test_gate` output, all cases;
- the new run's `scores.md` and `eval/gate.py` exit status against both baselines;
- the per-question status table for q015, q019, q021, q022, q026, q027, q028, q036, q053,
  q054, q055 before and after;
- `git diff --stat -- generation/prompt.py index/ eval/questions.jsonl` printing nothing.

## Risks

- **The guard is structural, not semantic.** q027 (answerable, no marker, disclaimer names
  a table) is predicted to be misfiled as a refusal. That is one question of not-found (b)
  and it is the gate's tolerance, not a licence: if the run shows a second answerable
  question flipping, revert rather than widen the guard.
- **D-068 is the precedent for that failure mode.** Re-reading it is cheaper than repeating
  it; the difference here is which questions are already failing, and that difference is
  the whole argument, so it must be re-checked against the run rather than assumed.
- **A refusal is not a failed answer, and a failed answer is not a refusal.** The rule must
  never fire on an answer whose quotations merely failed to verify: that would hide
  unverified answers, which D-010 and D-058 deliberately surface.
- **Do not turn this into the not-found gate.** D-058 measured that no retrieval score
  separates the classes; nothing here adds a threshold.
- **Wave 01 stays where it is during the run.** Only the sandbox recipe may hold the
  pre-wave corpus, and the live `data/corpus` and index are not to be touched (rules 5, 11).
