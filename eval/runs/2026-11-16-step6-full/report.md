# Generation run: step6-full

- Model: `qwen3.5:4b` (digest `d8b0f5e9760c`), prompt `s6-2`, temperature 0, num_ctx 4096, think False
- Corpus: **97 documents, 851 pages** (86 OCR pages)
- Questions: 55 (55 in the set), cache off

## End-to-end latency (seconds per question, retries and condense included)

| n | p50 | p95 | min | max | mean | over 20 s | over 30 s |
|---|---|---|---|---|---|---|---|
| 55 | 16.6 | 58.1 | 4.4 | 4587.2 | 103.4 | 19 | 10 |

Target: about 20 s for a short follow-up, 30 s+ acceptable for a deep or long question. Measured p50 **16.6 s**, p95 **58.1 s**.

Slowest questions: `q038` 4587.2 s, `q044` 67.7 s, `q040` 59.8 s. A single stalled question moves the mean, not the p50/p95.

## How the questions were handled

| | count |
|---|---|
| status `not_found` | 7 |
| status `unverified` | 6 |
| status `verified` | 42 |
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
| q001 | dev | fact | 11.2 | normal | 1 | 1 | verified |
| q002 | dev | fact | 23.9 | normal | 1 | 1 | verified |
| q003 | dev | fact | 16.5 | normal | 2 | 1 | verified |
| q004 | dev | fact | 30.6 | normal | 1 | 2 | verified |
| q005 | heldout | fact | 12.3 | normal | 1 | 1 | verified |
| q006 | dev | fact | 21.8 | normal | 1 | 1 | verified |
| q007 | heldout | fact | 13.3 | normal | 1 | 1 | verified |
| q008 | dev | exact | 28.1 | normal | 1 | 2 | verified |
| q009 | dev | exact | 12.4 | normal | 1 | 1 | verified |
| q010 | heldout | exact | 11.6 | normal | 1 | 1 | verified |
| q011 | dev | exact | 18.7 | normal | 1 | 1 | verified |
| q012 | heldout | exact | 30.0 | normal | 1 | 3 | verified |
| q013 | dev | summary | 20.8 | normal | 1 | 1 | verified |
| q014 | dev | summary | 22.3 | normal | 1 | 1 | verified |
| q015 | heldout | summary | 6.5 | normal | 1 | 0 | not_found |
| q016 | dev | comparison | 18.5 | normal | 1 | 1 | verified |
| q017 | dev | comparison | 19.4 | normal | 1 | 1 | verified |
| q018 | heldout | comparison | 18.1 | normal | 1 | 1 | verified |
| q019 | dev | notfound | 5.3 | normal | 1 | 0 | not_found |
| q020 | dev | notfound | 27.3 | normal | 2 | 1 | verified |
| q021 | dev | notfound | 9.9 | normal | 2 | 0 | unverified |
| q022 | heldout | notfound | 4.7 | normal | 1 | 0 | not_found |
| q023 | dev | followup | 17.5 | followup | 1 | 1 | verified |
| q024 | heldout | followup | 27.2 | followup | 1 | 2 | verified |
| q025 | dev | table | 14.9 | table | 1 | 1 | verified |
| q026 | dev | table | 7.0 | table | 1 | 0 | not_found |
| q027 | dev | table | 30.6 | table | 2 | 0 | unverified |
| q028 | dev | table | 19.9 | table | 2 | 0 | unverified |
| q029 | heldout | table | 17.4 | table | 1 | 1 | verified |
| q030 | heldout | table | 14.1 | table | 1 | 1 | verified |
| q031 | dev | number | 12.9 | table | 1 | 1 | verified |
| q032 | dev | number | 12.9 | normal | 1 | 1 | verified |
| q033 | dev | number | 16.1 | normal | 1 | 1 | verified |
| q034 | dev | exact | 15.4 | normal | 1 | 1 | verified |
| q035 | dev | number | 13.9 | normal | 1 | 1 | verified |
| q036 | dev | list | 4.4 | normal | 1 | 0 | not_found |
| q037 | dev | number | 10.0 | normal | 1 | 1 | verified |
| q038 | dev | comparison | 4587.2 | normal | 2 | 0 | unverified |
| q039 | dev | exact | 23.9 | normal | 1 | 2 | verified |
| q040 | dev | number | 59.8 | normal | 1 | 1 | verified |
| q041 | dev | exact | 15.3 | table | 1 | 1 | verified |
| q042 | dev | fact | 13.5 | table | 1 | 1 | verified |
| q043 | dev | fact | 15.7 | normal | 1 | 1 | verified |
| q044 | dev | fact | 67.7 | normal | 2 | 4 | unverified |
| q045 | dev | number | 36.4 | normal | 1 | 3 | verified |
| q046 | dev | table | 45.1 | table | 2 | 1 | verified |
| q047 | dev | table | 13.2 | table | 1 | 1 | verified |
| q048 | dev | fact | 57.3 | normal | 2 | 0 | unverified |
| q049 | dev | fact | 35.7 | normal | 1 | 4 | verified |
| q050 | dev | list | 17.2 | table | 1 | 1 | verified |
| q051 | dev | fact | 16.5 | normal | 1 | 1 | verified |
| q052 | dev | summary | 16.6 | normal | 1 | 1 | verified |
| q053 | dev | notfound | 5.8 | table | 1 | 0 | not_found |
| q054 | dev | notfound | 5.3 | normal | 1 | 0 | not_found |
| q055 | dev | notfound | 40.0 | normal | 2 | 2 | verified |
