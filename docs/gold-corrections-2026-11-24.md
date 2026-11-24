# Gold-data corrections drafted: q042, q044, q050 (2026-11-24)

**Status: DRAFT, not applied.** `eval/questions.jsonl` is owner-only (AGENTS.md rule 13),
so this file is the patch, not the change. Everything below was measured on scratch copies
in `.tmp-gold/` (deleted); the live file was not touched.

These are the three questions `eval/test_scorer.py` names as impossible for a perfect
fixture, because a gold field disagrees with the PDF or with the scorer's own rules:

```
gold data that no perfect fixture can pass:
  q042: gold number 50 is not written in gold_answer
  q044: gold_quote is not on the gold page
  q050: gold number 11 is not written in gold_answer
```

All three are dev questions, `added_in_step: 5`, approved 2026-11-16, and all three read
the same source: `data/corpus/1970_Das_Beliefs_superstitions_and_taboos_associated_with_bamboos_in_W1999918290.pdf`
(SHA-256 `a483da158585…`, unchanged by these edits — so no integrity re-check is needed).

Each correction is **one field**. No question text, split, answerable flag, source or
SHA-256 changes, and the record count stays 55.

## 1. q042 (line 42) — the answer spells the number as a word

| field | current | corrected |
|---|---|---|
| `gold_numbers` | `[{"value": "50", "unit": "species"}]` | `[{"value": "Fifty", "unit": "species"}]` |

Page 1 prints, verbatim:

> Fifty species of bamboos are already recorded in Nepal (Das, 2004).

and the current `gold_quote` matches it exactly, so the quote is fine. The answer,
`Fifty species, recorded by Das (2004)`, is also faithful — but the numeric rule looks for
the literal `50`, which no honest answer contains. Evidence: **all 15 saved runs that contain q042** answers with the page's wording (`Fifty species of bamboos are already recorded in
Nepal [1]…`); not one writes `50`. The fix must therefore accept the word, not force the
model to rewrite the document's text (which would also sit badly with the verbatim answer
rule).

`score.norm_number("Fifty")` returns `fifty`, the numeric search is case-insensitive, and
`species` is not one of the required units (`mm`, `m3/s`, `m3/s/km2`, `km2`, `mm/h`), so the
word satisfies the check. Dropping the gold number instead would delete the count check;
changing the value keeps it.

**Measured impact** on the accepted baseline run
(`eval/runs/2026-11-20-step9-retry-guard/run.jsonl`): **37/55 → 38/55**, numeric
**37/43 → 38/43**, fail→pass `q042`, no pass→fail. q042's retrieval and citation already
passed; only `numeric_ok` flips.

## 2. q044 (line 44) — the quote lost a line-break hyphen

| field | current | corrected |
|---|---|---|
| `gold_quote` | `Gurung (1989) reported an unwillingness to plant bamboo amongst some villagers in the KakaniKathmandu area, where it was associated with childlessness.` | `Gurung (1989) reported an unwillingness to plant bamboo amongst some villagers in the Kakani- Kathmandu area, where it was associated with childlessness.` |

The page is typeset as:

```
Gurung (1989) reported an unwillingness to plant
bamboo amongst some villagers in the Kakani-
Kathmandu area, where it was associated with
childlessness.
```

so the extracted text is `Kakani-\nKathmandu`, and after the scorer's whitespace
normalisation `Kakani- Kathmandu`. Strict matching (D-041) never joins a hyphen the PDF split
across a line, which is why the original quote could not match. Inserting `- ` restores the
page's own characters; it does not weaken the rule or touch D-041.

**Measured:** the corrected quote is found on page 1 (`norm(quote) in norm(page_text)` →
True). No run's score changes: all 14 saved runs that contain q044 cite it with the hyphen, so
citation stays **36/48** on the baseline.

## 3. q050 (line 50) — the gold answer never states the distances it is checked for

| field | current | corrected |
|---|---|---|
| `gold_answer` | `Ginger, turmeric, large cardamom, orchard grass and dinanath grass` | `Ginger, turmeric, large cardamom, orchard grass and dinanath grass up to 11-15 m from the bamboo row` |

`gold_numbers` is `[{"value": "11", "unit": "m"}, {"value": "15", "unit": "m"}]` and the
`gold_quote` on page 3 matches the page. The numeric rule requires every gold number to
appear in the answer, and a bare crop list cannot satisfy `11` and `15`. The runs are right
and the gold answer is incomplete: every saved answer says *"…can be effectively grown up to
11-15 m from a bamboo row"*. Appending the clause the page prints makes the gold answer
consistent with its own numbers.

**Measured:** q050 already passes numeric in all 15 saved runs that contain it, so no score changes; only the
perfect fixture gains the ability to pass it.

## After the owner applies it: expected state (measured on a scratch copy)

1. **Regenerate the fixtures by hand.** `test_scorer.ensure_fixtures()` only compares row
   counts, and the count is 55 before and after, so it will *not* rebuild. Run
   `python eval/make_fixtures.py` (writes 55 rows to each of the four fixtures). Skipping
   this makes the perfect case fail on q044's old quote — a stale-fixture failure, not a
   scorer regression.
2. `python eval/test_scorer.py` should report **no gold limits** and: perfect **55/55**
   (citation 48/48, numeric 43/43), empty **7/55**, partial **30/55** with **25 pass→fail**,
   both integrity refusals still exiting 3. Measured by building the corrected fixtures and
   scoring them against the corrected set.
3. Re-scoring the accepted baseline gives **38/55** (was 37/55).

## Apply script (owner only — edits a protected file)

```bash
.venv/Scripts/python.exe - <<'PY'
import json, pathlib
path = pathlib.Path("eval/questions.jsonl")
qs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
assert len(qs) == 55, len(qs)
by = {q["id"]: q for q in qs}
fix = {
    "q042": {"gold_numbers": [{"value": "Fifty", "unit": "species"}]},
    "q044": {"gold_quote": "Gurung (1989) reported an unwillingness to plant bamboo amongst "
                           "some villagers in the Kakani- Kathmandu area, where it was "
                           "associated with childlessness."},
    "q050": {"gold_answer": "Ginger, turmeric, large cardamom, orchard grass and dinanath "
                            "grass up to 11-15 m from the bamboo row"},
}
old = {"q042": by["q042"]["gold_numbers"][0]["value"],
       "q044": "KakaniKathmandu",
       "q050": by["q050"]["gold_answer"]}
assert old["q042"] == "50", "q042 already changed"
assert old["q044"] in by["q044"]["gold_quote"], "q044 already changed"
assert old["q050"].endswith("dinanath grass"), "q050 already changed"
for qid, fields in fix.items():
    by[qid].update(fields)
path.write_text("\n".join(json.dumps(q, ensure_ascii=False) for q in qs) + "\n",
                encoding="utf-8")
print("applied", ", ".join(fix))
PY
```

Rehearsed on a scratch copy: exactly **3 lines change** (42, 44, 50), the line count stays 55,
and the only textual differences are `50 → Fifty`, an inserted `- `, and an appended
` up to 11-15 m from the bamboo row`. Commit it as an `OWNER:` commit.

## Why this is not "editing gold to make a score pass" (rule 3)

Each edit repairs a field that contradicts the page or the scorer's own documented rules; the
score movement is a consequence, not the goal. q042 flips only because the *word* the page
prints was always the right answer. Two things must be recorded with it, so nobody can read
the change as a free point:

- the baseline is restated: **37/55 superseded, 38/55 after the correction**, numeric 38/43;
- the gate is **not** re-run to "earn" the point, and no already-recorded run's scores are
  rewritten. `eval/runs/` keeps its original `scores.json`; only future runs score against
  the corrected set.

## EVAL.md edits that follow (owner's, not applied here)

EVAL.md is protected except for appending rows to the Results table (AGENTS.md rule 13), so
the point-value table below is an **owner edit**. Both texts are ready to paste.

### 1. One-question point values — replace the four-row table

It still describes the 30-question set (20 dev at 5 points). Current set: **45 dev, 10
held-out** (55 records), so `100/45 = 2.22` and `100/10 = 10`.

```markdown
| Set | N | One question |
|---|---|---|
| Dev | 45 | 2.22 points |
| Held-out | 10 | 10 points |
| Not-found (a) on dev | 6 | 16.67 points |
```

The not-found (a) figure is context, not tolerance: rule 4 gives it zero tolerance, so one
flip costs 16.67 points of the dev total.

Also stale in the same file, one line, optional: the composition section still says
`Split: 20 dev, 10 held-out`; the frozen split is 45 dev / 10 held-out.

### 2. Results-table row — append only after the corrections are applied

A row appended now would record a projection as a result, so it is held back. The exact row,
using the accepted baseline's saved answers re-scored against the corrected set:

```markdown
| 2026-11-24 | **gold-data correction applied; accepted baseline re-scored, no new generation** — q042/q044/q050 gold fields corrected per `docs/gold-corrections-2026-11-24.md`; answers are the unchanged `eval/runs/2026-11-20-step9-retry-guard/run.jsonl` | 9 | dev+heldout | 55 | 45/48 | 46/48 | 46/48 | 0.826 | 36/48 | 38/43 | 3/6 / 46/48 | 11.4 | **38/55 passed (dev 31/45, held-out 7/10)**, one above the 37/55 baseline: **only q042 moved, fail -> pass**, numeric 37/43 -> 38/43, and no pass -> fail in any of the 17 saved runs (`reports/gold-corrections-rescore.md`). Not a new run and not an improvement: the gold data was wrong, and the gate was not re-run. |
```

Appending a Results row is the one EVAL.md edit an agent may make, so this row can be
appended by the agent once the owner has applied the corrections — no owner edit needed for
this half.
