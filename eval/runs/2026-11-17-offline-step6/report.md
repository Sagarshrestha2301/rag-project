# Generation run: offline-step6

- Model: `qwen3.5:4b` (digest `d8b0f5e9760c`), prompt `s6-2`, temperature 0, num_ctx 4096, think False
- Corpus: **97 documents, 851 pages** (86 OCR pages)
- Questions: 55 (55 in the set), cache off

## End-to-end latency (seconds per question, retries and condense included)

| n | p50 | p95 | min | max | mean | over 20 s | over 30 s |
|---|---|---|---|---|---|---|---|
| 55 | 15.4 | 43.3 | 4.1 | 67.9 | 19.1 | 17 | 8 |

Target: about 20 s for a short follow-up, 30 s+ acceptable for a deep or long question. Measured p50 **15.4 s**, p95 **43.3 s**.

Slowest questions: `q044` 67.9 s, `q046` 59.1 s, `q048` 56.0 s. A single stalled question moves the mean, not the p50/p95.

## How the questions were handled

| | count |
|---|---|
| status `not_found` | 7 |
| status `unverified` | 7 |
| status `verified` | 41 |
| route `followup` | 2 |
| route `normal` | 40 |
| route `table` | 13 |
| attempts 1 | 45 |
| attempts 2 | 10 |

## Scores (from eval/score.py on the same run.jsonl)

- citation: 31/48
- numeric: 35/43
- not-found (a): 3/6
- not-found (b): 45/48
- passed: 33/55

| id | split | type | seconds | route | attempts | citations | status |
|---|---|---|---|---|---|---|---|
| q001 | dev | fact | 13.9 | normal | 1 | 1 | verified |
| q002 | dev | fact | 20.9 | normal | 1 | 1 | verified |
| q003 | dev | fact | 14.8 | normal | 2 | 1 | verified |
| q004 | dev | fact | 29.9 | normal | 1 | 2 | verified |
| q005 | heldout | fact | 9.3 | normal | 1 | 1 | verified |
| q006 | dev | fact | 19.8 | normal | 1 | 1 | verified |
| q007 | heldout | fact | 12.0 | normal | 1 | 1 | verified |
| q008 | dev | exact | 24.7 | normal | 1 | 2 | verified |
| q009 | dev | exact | 11.0 | normal | 1 | 1 | verified |
| q010 | heldout | exact | 10.6 | normal | 1 | 1 | verified |
| q011 | dev | exact | 18.2 | normal | 1 | 1 | verified |
| q012 | heldout | exact | 30.9 | normal | 1 | 3 | verified |
| q013 | dev | summary | 21.7 | normal | 1 | 1 | verified |
| q014 | dev | summary | 22.1 | normal | 1 | 1 | verified |
| q015 | heldout | summary | 5.3 | normal | 1 | 0 | not_found |
| q016 | dev | comparison | 17.6 | normal | 1 | 1 | verified |
| q017 | dev | comparison | 17.8 | normal | 1 | 1 | verified |
| q018 | heldout | comparison | 17.1 | normal | 1 | 1 | verified |
| q019 | dev | notfound | 4.8 | normal | 1 | 0 | not_found |
| q020 | dev | notfound | 25.0 | normal | 2 | 1 | verified |
| q021 | dev | notfound | 9.0 | normal | 2 | 0 | unverified |
| q022 | heldout | notfound | 4.1 | normal | 1 | 0 | not_found |
| q023 | dev | followup | 15.4 | followup | 1 | 1 | verified |
| q024 | heldout | followup | 25.0 | followup | 1 | 2 | verified |
| q025 | dev | table | 12.8 | table | 1 | 1 | verified |
| q026 | dev | table | 5.7 | table | 1 | 0 | not_found |
| q027 | dev | table | 27.4 | table | 2 | 0 | unverified |
| q028 | dev | table | 17.9 | table | 2 | 0 | unverified |
| q029 | heldout | table | 16.0 | table | 1 | 1 | verified |
| q030 | heldout | table | 13.1 | table | 1 | 1 | verified |
| q031 | dev | number | 11.8 | table | 1 | 1 | verified |
| q032 | dev | number | 11.7 | normal | 1 | 1 | verified |
| q033 | dev | number | 15.0 | normal | 1 | 1 | verified |
| q034 | dev | exact | 14.4 | normal | 1 | 1 | verified |
| q035 | dev | number | 12.8 | normal | 1 | 1 | verified |
| q036 | dev | list | 4.1 | normal | 1 | 0 | not_found |
| q037 | dev | number | 9.5 | normal | 1 | 1 | verified |
| q038 | dev | comparison | 37.9 | normal | 2 | 0 | unverified |
| q039 | dev | exact | 23.4 | normal | 1 | 2 | verified |
| q040 | dev | number | 14.0 | normal | 1 | 1 | verified |
| q041 | dev | exact | 15.0 | table | 1 | 1 | verified |
| q042 | dev | fact | 12.1 | table | 1 | 1 | verified |
| q043 | dev | fact | 14.8 | normal | 1 | 1 | verified |
| q044 | dev | fact | 67.9 | normal | 2 | 4 | unverified |
| q045 | dev | number | 35.4 | normal | 1 | 3 | verified |
| q046 | dev | table | 59.1 | table | 2 | 0 | unverified |
| q047 | dev | table | 12.9 | table | 1 | 1 | verified |
| q048 | dev | fact | 56.0 | normal | 2 | 0 | unverified |
| q049 | dev | fact | 34.0 | normal | 1 | 4 | verified |
| q050 | dev | list | 16.2 | table | 1 | 1 | verified |
| q051 | dev | fact | 15.5 | normal | 1 | 1 | verified |
| q052 | dev | summary | 15.8 | normal | 1 | 1 | verified |
| q053 | dev | notfound | 5.5 | table | 1 | 0 | not_found |
| q054 | dev | notfound | 4.8 | normal | 1 | 0 | not_found |
| q055 | dev | notfound | 37.9 | normal | 2 | 2 | verified |
