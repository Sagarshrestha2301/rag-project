# Generation run: step9-d060

- Model: `qwen3.5:4b` (digest `d8b0f5e9760c`), prompt `s6-2`, temperature 0, num_ctx 4096, think False
- Corpus: **97 documents, 851 pages** (86 OCR pages)
- Questions: 55 (55 in the set), cache off

## End-to-end latency (seconds per question, retries and condense included)

| n | p50 | p95 | min | max | mean | over 20 s | over 30 s |
|---|---|---|---|---|---|---|---|
| 55 | 16.4 | 50.8 | 4.2 | 133.8 | 22.4 | 19 | 11 |

Target: about 20 s for a short follow-up, 30 s+ acceptable for a deep or long question. Measured p50 **16.4 s**, p95 **50.8 s**.

Slowest questions: `q001` 133.8 s, `q044` 72.3 s, `q048` 58.5 s. A single stalled question moves the mean, not the p50/p95.

## How the questions were handled

| | count |
|---|---|
| status `not_found` | 12 |
| status `unverified` | 4 |
| status `verified` | 39 |
| route `followup` | 2 |
| route `normal` | 40 |
| route `table` | 13 |
| attempts 1 | 49 |
| attempts 2 | 6 |

## Scores (from eval/score.py on the same run.jsonl)

- citation: 31/48
- numeric: 34/43
- not-found (a): 6/6
- not-found (b): 43/48
- passed: 36/55

| id | split | type | seconds | route | attempts | citations | status |
|---|---|---|---|---|---|---|---|
| q001 | dev | fact | 133.8 | normal | 1 | 1 | verified |
| q002 | dev | fact | 42.6 | normal | 1 | 1 | verified |
| q003 | dev | fact | 16.1 | normal | 2 | 1 | verified |
| q004 | dev | fact | 31.6 | normal | 1 | 2 | verified |
| q005 | heldout | fact | 11.6 | normal | 1 | 1 | verified |
| q006 | dev | fact | 20.7 | normal | 1 | 1 | verified |
| q007 | heldout | fact | 12.1 | normal | 1 | 1 | verified |
| q008 | dev | exact | 26.4 | normal | 1 | 2 | verified |
| q009 | dev | exact | 11.6 | normal | 1 | 1 | verified |
| q010 | heldout | exact | 11.7 | normal | 1 | 1 | verified |
| q011 | dev | exact | 18.8 | normal | 1 | 1 | verified |
| q012 | heldout | exact | 30.1 | normal | 1 | 3 | verified |
| q013 | dev | summary | 23.3 | normal | 1 | 1 | verified |
| q014 | dev | summary | 23.1 | normal | 1 | 1 | verified |
| q015 | heldout | summary | 5.5 | normal | 1 | 0 | not_found |
| q016 | dev | comparison | 18.6 | normal | 1 | 1 | verified |
| q017 | dev | comparison | 20.2 | normal | 1 | 1 | verified |
| q018 | heldout | comparison | 18.6 | normal | 1 | 1 | verified |
| q019 | dev | notfound | 5.5 | normal | 1 | 0 | not_found |
| q020 | dev | notfound | 14.3 | normal | 1 | 0 | not_found |
| q021 | dev | notfound | 6.9 | normal | 1 | 0 | not_found |
| q022 | heldout | notfound | 4.8 | normal | 1 | 0 | not_found |
| q023 | dev | followup | 17.6 | followup | 1 | 1 | verified |
| q024 | heldout | followup | 28.0 | followup | 1 | 2 | verified |
| q025 | dev | table | 13.9 | table | 1 | 1 | verified |
| q026 | dev | table | 6.1 | table | 1 | 0 | not_found |
| q027 | dev | table | 12.3 | table | 1 | 0 | not_found |
| q028 | dev | table | 15.4 | table | 1 | 0 | not_found |
| q029 | heldout | table | 19.2 | table | 1 | 1 | verified |
| q030 | heldout | table | 14.9 | table | 1 | 1 | verified |
| q031 | dev | number | 13.0 | table | 1 | 1 | verified |
| q032 | dev | number | 12.8 | normal | 1 | 1 | verified |
| q033 | dev | number | 16.4 | normal | 1 | 1 | verified |
| q034 | dev | exact | 27.8 | normal | 1 | 1 | verified |
| q035 | dev | number | 13.6 | normal | 1 | 1 | verified |
| q036 | dev | list | 4.2 | normal | 1 | 0 | not_found |
| q037 | dev | number | 9.5 | normal | 1 | 1 | verified |
| q038 | dev | comparison | 41.4 | normal | 2 | 0 | unverified |
| q039 | dev | exact | 45.6 | normal | 2 | 2 | unverified |
| q040 | dev | number | 14.7 | normal | 1 | 1 | verified |
| q041 | dev | exact | 17.5 | table | 1 | 1 | verified |
| q042 | dev | fact | 13.6 | table | 1 | 1 | verified |
| q043 | dev | fact | 16.1 | normal | 1 | 1 | verified |
| q044 | dev | fact | 72.3 | normal | 2 | 4 | unverified |
| q045 | dev | number | 38.5 | normal | 1 | 3 | verified |
| q046 | dev | table | 47.5 | table | 2 | 1 | verified |
| q047 | dev | table | 13.8 | table | 1 | 1 | verified |
| q048 | dev | fact | 58.5 | normal | 2 | 0 | unverified |
| q049 | dev | fact | 35.8 | normal | 1 | 4 | verified |
| q050 | dev | list | 17.1 | table | 1 | 1 | verified |
| q051 | dev | fact | 16.2 | normal | 1 | 1 | verified |
| q052 | dev | summary | 16.5 | normal | 1 | 1 | verified |
| q053 | dev | notfound | 5.7 | table | 1 | 0 | not_found |
| q054 | dev | notfound | 5.0 | normal | 1 | 0 | not_found |
| q055 | dev | notfound | 21.7 | normal | 1 | 0 | not_found |
