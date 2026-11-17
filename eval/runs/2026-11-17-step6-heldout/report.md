# Generation run: step6-heldout

- Model: `qwen3.5:4b` (digest `d8b0f5e9760c`), prompt `s6-2`, temperature 0, num_ctx 4096, think False
- Corpus: **97 documents, 851 pages** (86 OCR pages)
- Questions: 10 (10 in the set), cache off

## End-to-end latency (seconds per question, retries and condense included)

| n | p50 | p95 | min | max | mean | over 20 s | over 30 s |
|---|---|---|---|---|---|---|---|
| 10 | 12.1 | 26.3 | 4.2 | 27.5 | 14.0 | 2 | 0 |

Target: about 20 s for a short follow-up, 30 s+ acceptable for a deep or long question. Measured p50 **12.1 s**, p95 **26.3 s**.

Slowest questions: `q012` 27.5 s, `q024` 24.8 s, `q018` 16.7 s. A single stalled question moves the mean, not the p50/p95.

## How the questions were handled

| | count |
|---|---|
| status `not_found` | 2 |
| status `verified` | 8 |
| route `followup` | 1 |
| route `normal` | 7 |
| route `table` | 2 |
| attempts 1 | 10 |

## Scores (from eval/score.py on the same run.jsonl)

- citation: 5/9
- numeric: 7/8
- not-found (a): 0/0
- not-found (b): 8/9
- passed: 5/10

| id | split | type | seconds | route | attempts | citations | status |
|---|---|---|---|---|---|---|---|
| q005 | heldout | fact | 10.8 | normal | 1 | 1 | verified |
| q007 | heldout | fact | 11.1 | normal | 1 | 1 | verified |
| q010 | heldout | exact | 10.4 | normal | 1 | 1 | verified |
| q012 | heldout | exact | 27.5 | normal | 1 | 3 | verified |
| q015 | heldout | summary | 5.1 | normal | 1 | 0 | not_found |
| q018 | heldout | comparison | 16.7 | normal | 1 | 1 | verified |
| q022 | heldout | notfound | 4.2 | normal | 1 | 0 | not_found |
| q024 | heldout | followup | 24.8 | followup | 1 | 2 | verified |
| q029 | heldout | table | 15.9 | table | 1 | 1 | verified |
| q030 | heldout | table | 13.0 | table | 1 | 1 | verified |
