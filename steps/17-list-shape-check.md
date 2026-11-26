# Step 17: A list question's answer must be a list, enforced by the verifier

**Goal:** make the list shape a *checked* property of the answer instead of a prompt request
the model can ignore. For a question the router flags as a list, `verify_answer` rejects an
answer that is prose, and the existing retry (D-010) tells the model what shape is required.
Measured cause for the step: `s6-4` and `s6-5` both asked for dash lines and the model wrote
prose anyway, byte-identically to `s6-3` (D-092, D-093) — a prompt is not a lever for output
shape on this model, but the retry loop is a different one.

**Needs approval to start:** yes. Owner approval line for `APPROVALS.md` (proposed, the exact
date filled in when you approve):

```
2026-11-?? | start | step 17 | owner
```

The line must be committed with a message starting `OWNER:`, as steps 10-16 were.

## Why this step exists (measured 2026-11-25, out of tree, no repository code changed)

Step 16 left q050's answer byte-identical to `s6-3` while carrying `LIST_RULES`. Before writing
any code I asked the model the two list questions on the **current** `s6-5` prompt, then sent
the answer back with a shape complaint through the same `prompt.retry_message` the answer loop
uses, on Ollama 0.40.18, `qwen3.5:4b`, temperature 0, seed 0. Two calls per question.

| question | first answer | with a shape complaint |
|---|---|---|
| q036 | prose: "The paper lists floods in the Sunkosi River occurring in 1964, 1981, and 1984 [1]." | **`- 1964 [1]` / `- 1981 [1]` / `- 1984 [1]`** + the same verified quotation |
| q050 | prose: "…ginger, turmeric, large cardamom, orchard grass, and dinanath grass … up to 11-15 m …" | **`- ginger [1]` / `- turmeric [1]` / `- large cardamom [1]` / `- orchard grass [1]` / `- dinanath grass [1]`** + the quotation |

Both retries satisfy a strict rule ("at least two `- ` lines, no prose line before them") with
zero remaining problems. So the shape is reachable in one retry, and the cost is one extra model
call on the two list questions only.

**The catch, measured and not fixed by this step:** q050's list **drops `11-15` from the body**.
The number survives only inside the quotation in the citation block, and `eval/score.py` reads
`gold_numbers` from the whole answer text (`answer_has_number(answer, …)`), so the numeric rule
still passes. A reader, though, gets a list of crops with no distance. If the run shows q050
`verified` but the distance gone from the body, that is a real quality loss the score cannot
see; the step file records it rather than hiding it, and the remedy is a separate content rule.

## Tasks

1. `generation/verify.py`:
   - add `list_shape_problems(answer: str) -> list[str]`. Split the answer into the **body**
     (everything before the first line that starts with a citation marker `[n]`) and the
     citation block (ignored — it is evidence, not answer prose). The body must have at least
     two lines, every line must start with `- `, and at most one non-`- ` line may appear
     **after** the last item (the single unit/range sentence the prompt already allows). No
     non-`- ` line may appear **before** the first item. Each problem is one clear sentence that
     names what to change, because it is shown to the model on the retry.
   - extend `verify_answer(answer, passages, *, check_page=None, list_style=False)` to append
     those problems when `list_style` is true. **A refusal is not a shape failure:** skip the
     check when the answer is `said_not_found()` or `refused_with_line()` accepts it, and skip
     it when the answer has no content at all.
2. `generation/answer.py`: pass `list_style=bool(routed.get("list"))` at **both**
   `verify.verify_answer` calls (first attempt and retry). Nothing else changes: the retry
   already fires on any non-empty `problems` and already re-verifies.
3. `generation/prompt.py`: bump `PROMPT_VERSION` `s6-5` → **`s6-6`**. The cache key carries the
   prompt version and not the verifier (D-017), so without the bump a cached verified prose
   answer from `s6-5` would be replayed as if it were shaped. The text of the prompt is
   unchanged; the version records that answers are no longer interchangeable.
4. Tests, `generation/test_verify.py`:
   (a) a prose answer to a list question fails with a problem that names the `- ` lines;
   (b) a dash list (two or more items) with a citation block passes;
   (c) one closing sentence after the list passes; a sentence **before** the list fails;
   (d) a refusal passes even with `list_style=True`;
   (e) `list_style=False` never adds a shape problem (every existing case stays green).
   `generation/test_answer.py`: one case proving a list-route question whose first answer is
   prose is retried and a non-list question is not (the existing fake-`ask` fixture).
5. Verification, in this order: `generation/` suites, then one full 55-question run
   (`.venv\\Scripts\\python.exe -m eval.run_generation --out eval/runs/2026-11-??-step17-list-shape`),
   then `eval/gate.py` against `2026-11-25-step16-list-retrieval` (the immediate predecessor, so
   this change is isolated) and against `2026-11-24-repro-a`, plus `--milestone`.
6. Report per question: q036 and q050 (status, attempts, the answer body, whether `11-15` is in
   the body), and q002/q004/q006/q013 (unchanged). Check the run's `attempts` count: only the
   two list questions may gain an attempt.
7. Revert rule, stated before the run: if **either** q036 or q050 ends `unverified`, or any
   non-list question moves, revert in the same session and record the run as measured and
   rejected, the way D-092 closed `s6-4`. Do not weaken the shape rule to make the run pass.
8. Append one `EVAL.md` Results row, one `STATUS.md` log line and a PROPOSED `DECISIONS.md`
   entry. State the D-086 accounting explicitly (this step cannot meet it: neither list question
   is one of q003/q040/q052/q055).

## Definition of done

- [x] `list_shape_problems` rejects a prose answer and accepts a dash list, a closing sentence and a refusal, with the citation block ignored
- [x] Only list questions are checked: every non-list answer is verified exactly as before
- [x] `PROMPT_VERSION` is `s6-6` so no `s6-5` answer can be replayed
- [x] q036 and q050 are `verified` **and** dash lists in the full run, on the appeal that is retry 2
- [x] No non-list question changes status, and no question gains an attempt except the two list questions
- [x] `eval/gate.py` passes against `2026-11-25-step16-list-retrieval` (the predecessor) and against `2026-11-24-repro-a`, or the change is reverted
- [x] The new cases and every existing `generation/` case pass
- [x] `EVAL.md` row, `STATUS.md` log line and the D-086 statement are present, `git status` clean
## Context to read

`AGENTS.md`, `STATUS.md` (step 16 row, D-093), `steps/16-list-retrieval.md`, `DECISIONS.md`
D-010 (the retry), D-017 (cache key), D-073 (prompt size), D-090 (what counts as a refusal),
D-092/D-093 (both prompt attempts at this shape), `generation/verify.py`, `generation/answer.py`
(the retry block, `_retry_messages`), `generation/prompt.py` (`LIST_RULES`, `retry_message`),
`generation/test_verify.py`, `generation/test_answer.py`, `eval/score.py` (`score_question`,
`answer_has_number`), `eval/runs/2026-11-25-step16-list-retrieval/run.jsonl`.

## Expected output

```
>>> from generation import verify
>>> verify.list_shape_problems("The paper lists floods in 1964, 1981 and 1984 [1].\n\n[1] x.pdf, p. 1: \"Floods ...\"")
['the answer is a list question, so it must be written as "- " lines (at least two), not as prose']
>>> verify.list_shape_problems("- 1964 [1]\n- 1981 [1]\n- 1984 [1]\n\n[1] x.pdf, p. 1: \"Floods ...\"")
[]
```

## Verification

Show in the handoff: the new and existing test totals; the run's `scores.md`; gate exit codes
against the predecessor and the accepted baseline, and `--milestone`; the q036/q050 answer bodies
with `attempts`; the per-question comparison for q002/q004/q006/q013; and
`git diff --stat -- index/ data/ eval/questions.jsonl` printing nothing.

## Risks

- **The retry is the appeal, and there is only one.** A model that writes prose twice ends
  `unverified` on a question that was passing — that is the revert condition, and it is why the
  predecessor run is the gate baseline here.
- **The check cannot tell a good list from a tidy wrong one.** It enforces shape only; content
  is still the citation and numeric rules' job.
- **q050's list drops the distance from the body** (measured above) while the score's numeric
  rule still passes on the quotation. Shape bought at the price of a reader-facing number is a
  partial win, and the handoff must say so.
- **A list question phrased with a genuine refusal** must not be turned unverified; the skip on
  `said_not_found`/`refused_with_line` is what protects that, and it has a test.
- **Cache:** an `s6-5` answer is not valid under `s6-6` semantics, hence the bump; do not compare
  this run against a cached one.
