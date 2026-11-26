# Stage 1 screen: Step 16 list retrieval

Written by `scripts/screen-list-retrieval.py`; no model was called.
Baseline: `reports/list-retrieval-baseline-hashes.json` (captured before the change).

## Trigger

Fires on **2 of 55** questions: `q036`, `q050`

- designed for: `q036`, `q050`
- canaries that must not fire: `q002`, `q004`, `q006`, `q013`

## What the model would be given

- questions compared: **55**
- changed prompt or passages: **2** — `q036`, `q050`
- changed but **not** a list question (must be empty): none
- canaries changed (must be empty): none
- questions in the baseline but not now (must be empty): none

## The two list questions

| question | top page | top passage chars | needed words present |
|---|---|---|---|
| q036 | 1 | 1623 (was 1367) | `Sunkosi` yes, `1964` yes, `1984` yes |
| q050 | 3 | 1200 | `ginger` yes, `11-15` yes |

## Result

**PASS** — exactly the two list questions change, the four canaries are byte-identical, and q036's passage carries its sentence.
