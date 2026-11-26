# Live list questions through the pipeline (2026-11-25)

What happens when a reader asks for a list, on the shipped code (`s6-6`: the Step 16 window
rule plus the Step 17 shape check). Eight questions, `generation.answer` with the cache off,
Ollama 0.40.18, `qwen3.5:4b`, temperature 0, seed 0, the model already loaded. The verifier was
wrapped read-only so **every attempt's problems are recorded**, not inferred from the totals.
No repository code was changed and no index, corpus or prompt was touched.

Why these eight: five list phrasings the router's `LIST` trigger matches, one `table`-phrased
list, one control the trigger deliberately does **not** match, and one whose answer is not in
the corpus. The corpus is the live English-only 186-document index.

## Result

| # | question | route | `list` | status | attempts | first attempt failed on | dash items |
|---|---|---|---|---|---|---|---|
| L1 | List the organizations that were interviewed in the improved cook stove programme study. | normal | yes | **verified** | 2 | shape (prose) | 14 |
| L2 | Which crops can be grown up to 11-15 m from a bamboo row, according to the study cited? | table | yes | **verified** | 2 | shape (prose) | 5 |
| L3 | In which years does the paper list floods in the Sunkosi River? | normal | yes | **verified** | 2 | shape (prose) | 3 |
| L4 | List the Ramsar sites of Nepal and their biodiversity value given in Table 1. | table | yes | **verified** | 2 | no citation line | 2 |
| L5 | Name the districts where the beneficiary-based survey was carried out. | normal | yes | unverified | 2 | shape (prose + sentence before list) | 1 |
| L6 | What are the four research programmes of IFPRI described in the proceedings? | normal | **no** | unverified | 2 | quotation not on p. 8 | 0 |
| L7 | List the main findings of the national wetland workshop proceedings. | summary | yes | **verified** | 2 | shape (prose) | 2 |
| L8 | Which villages were surveyed in the cook stove programme? | normal | yes | **not_found** | 1 | — (refused) | 0 |

**5 verified, 2 unverified, 1 refused.** Six of the seven retries were caused by the shape check;
one (L4) by a missing citation line; L8 refused and was **not** retried, which is the guard that
keeps a refusal out of the shape rule.

The answers, as recorded:

- **L1** 14 items, one call each for the retry — AEPC, Department of Forest, Biogas Support
  Program, ICIMOD, Bio-Nepal, CES, IOE, Kathmandu Engineering College, NAST, Practical Action,
  REP, RECAST, REDP, WDD — all citing `[5]`, p. 4, 30.8 s.
- **L2** `- Ginger / - Turmeric / - Large cardamom / - Orchard grass / - Dinanath grass`, p. 3,
  25.1 s.
- **L3** `- 1964 / - 1981 / - 1984`, p. 1, 19.4 s.
- **L4** two items from the table page (p. 66), 16.0 s.
- **L7** two long findings, citing pages 3, 5, 4, 22 and 7, **65.9 s** — the most expensive
  question here and the only one on the `summary` route.
- **L5** ended as `- 14 districts [1]` followed by `Not found in the indexed documents.` with
  **no citation at all**, so it is unverified.
- **L6** answered in prose, correctly in content ("Food Trends Analysis, Food Production Policy
  and Development Strategy, Food Consumption and Nutrition Policy, International Food Trade and
  Food Security"), but its quotation from p. 8 of the 1983 IFPRI annual report is not on that
  page, so it failed verification on both attempts — and as the control it was **never shape
  checked**, which is the scoping working.
- **L8** refused on the first attempt: the cook-stove paper does not name its villages.

## What this shows

1. **The trigger behaves on real phrasings.** 7 of 8 flagged; the control ("What are the four
   research programmes…") was not, and stayed prose and unchecked.
2. **The shape check is what produces the list.** On L1/L2/L3/L5/L7 the first answer was prose
   and the retry produced the list, matching the eval (q036/q050 needed `attempts=2` for the
   same reason). A single retry was enough in 5 of 6 shape failures.
3. **A refusal is untouched**, as designed: L8 returned `not_found` on attempt 1 with no retry.
4. **L5 is a new, real failure mode worth a decision.** The question has no answer in the
   corpus; the model wrote prose that mentioned "14 districts" and then the refusal line. The
   shape rule rejected the prose, and the retry produced a **one-item list plus the refusal
   line**, which cites nothing and is therefore `unverified` rather than `not_found`. A reader
   sees a malformed half-answer instead of a clean refusal. The refusal shortcut only applies
   when the refusal is the first line or the exact line with no `[n]` anywhere; a list item
   carrying a marker defeats it.
5. **The `11-15` loss repeats in the wild** (L2, the eval's q050 phrasing): the list drops the
   distance, and it survives only inside the quotation. The numeric rule reads the whole answer
   text, so nothing flags it.
6. **L7 shows the shape rule's other edge:** a `summary` question that is also phrased as a list
   gets long sentence-items, which pass the shape check because only the line prefix is read.
   That is by design (shape, not content), but it is not a tidy list, and it costs 66 s.

## Not measured

- The scaling this implies: every list question now costs a second model call (16-66 s here,
  versus 3 s for L8's refusal). Over the 55-question eval only two questions are affected, but
  a reader-facing mix with many list questions would pay it every time.
- No score is attached to this table: the eval set is the 55 questions, and this is a live probe
  on questions that are not in it. The probe is evidence about behaviour, not a gate.
