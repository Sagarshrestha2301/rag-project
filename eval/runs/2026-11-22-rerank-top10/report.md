# Generation run: rerank-top10

- Model: `qwen3.5:4b` (digest `d8b0f5e9760c`), prompt `s6-3`, temperature 0, num_ctx 4096, think False
- Corpus: **186 documents, 2669 pages** (222 OCR pages)
- Questions: 55 (55 in the set), cache off

## End-to-end latency (seconds per question, retries and condense included)

| n | p50 | p95 | min | max | mean | over 20 s | over 30 s |
|---|---|---|---|---|---|---|---|
| 55 | 11.7 | 28.2 | 3.4 | 59.3 | 13.4 | 7 | 3 |

Target: about 20 s for a short follow-up, 30 s+ acceptable for a deep or long question. Measured p50 **11.7 s**, p95 **28.2 s**.

Slowest questions: `q002` 59.3 s, `q013` 42.6 s, `q039` 38.6 s. A single stalled question moves the mean, not the p50/p95.

## How the questions were handled

| | count |
|---|---|
| status `not_found` | 9 |
| status `unverified` | 4 |
| status `verified` | 42 |
| route `followup` | 2 |
| route `normal` | 40 |
| route `table` | 13 |
| attempts 1 | 47 |
| attempts 2 | 8 |

## Scores (from eval/score.py on the same run.jsonl)

- citation: 35/48
- numeric: 36/43
- not-found (a): 3/6
- not-found (b): 43/48
- passed: 37/55

| id | split | type | seconds | route | attempts | citations | status |
|---|---|---|---|---|---|---|---|
| q001 | dev | fact | 21.9 | normal | 1 | 1 | verified |
| q002 | dev | fact | 59.3 | normal | 2 | 3 | verified |
| q003 | dev | fact | 10.3 | normal | 1 | 1 | verified |
| q004 | dev | fact | 13.4 | normal | 1 | 1 | verified |
| q005 | heldout | fact | 9.0 | normal | 1 | 1 | verified |
| q006 | dev | fact | 12.3 | normal | 1 | 1 | verified |
| q007 | heldout | fact | 9.3 | normal | 1 | 1 | verified |
| q008 | dev | exact | 12.2 | normal | 1 | 1 | verified |
| q009 | dev | exact | 9.1 | normal | 1 | 1 | verified |
| q010 | heldout | exact | 9.6 | normal | 1 | 1 | verified |
| q011 | dev | exact | 16.4 | normal | 1 | 1 | verified |
| q012 | heldout | exact | 11.6 | normal | 1 | 1 | verified |
| q013 | dev | summary | 42.6 | normal | 2 | 2 | verified |
| q014 | dev | summary | 18.0 | normal | 1 | 1 | verified |
| q015 | heldout | summary | 4.1 | normal | 1 | 0 | not_found |
| q016 | dev | comparison | 14.4 | normal | 1 | 1 | verified |
| q017 | dev | comparison | 17.7 | normal | 1 | 1 | verified |
| q018 | heldout | comparison | 14.6 | normal | 1 | 1 | verified |
| q019 | dev | notfound | 3.6 | normal | 1 | 0 | not_found |
| q020 | dev | notfound | 20.5 | normal | 1 | 2 | verified |
| q021 | dev | notfound | 7.2 | normal | 2 | 0 | unverified |
| q022 | heldout | notfound | 3.4 | normal | 1 | 0 | not_found |
| q023 | dev | followup | 11.7 | followup | 1 | 1 | verified |
| q024 | heldout | followup | 14.6 | followup | 1 | 1 | verified |
| q025 | dev | table | 4.1 | table | 1 | 0 | not_found |
| q026 | dev | table | 4.4 | table | 1 | 0 | not_found |
| q027 | dev | table | 4.2 | table | 1 | 0 | not_found |
| q028 | dev | table | 12.4 | table | 2 | 0 | unverified |
| q029 | heldout | table | 13.2 | table | 1 | 1 | verified |
| q030 | heldout | table | 11.7 | table | 1 | 1 | verified |
| q031 | dev | number | 9.9 | table | 1 | 1 | verified |
| q032 | dev | number | 9.2 | normal | 1 | 1 | verified |
| q033 | dev | number | 12.7 | normal | 1 | 1 | verified |
| q034 | dev | exact | 8.4 | normal | 1 | 1 | verified |
| q035 | dev | number | 9.6 | normal | 1 | 1 | verified |
| q036 | dev | list | 3.6 | normal | 1 | 0 | not_found |
| q037 | dev | number | 8.8 | normal | 1 | 1 | verified |
| q038 | dev | comparison | 10.7 | normal | 1 | 1 | verified |
| q039 | dev | exact | 38.6 | normal | 2 | 2 | unverified |
| q040 | dev | number | 11.9 | normal | 1 | 1 | verified |
| q041 | dev | exact | 12.1 | table | 1 | 1 | verified |
| q042 | dev | fact | 10.1 | table | 1 | 1 | verified |
| q043 | dev | fact | 9.1 | normal | 1 | 1 | verified |
| q044 | dev | fact | 13.7 | normal | 1 | 1 | verified |
| q045 | dev | number | 13.3 | normal | 1 | 1 | verified |
| q046 | dev | table | 20.4 | table | 2 | 0 | unverified |
| q047 | dev | table | 11.0 | table | 1 | 1 | verified |
| q048 | dev | fact | 18.7 | normal | 1 | 2 | verified |
| q049 | dev | fact | 23.7 | normal | 1 | 3 | verified |
| q050 | dev | list | 14.6 | table | 1 | 1 | verified |
| q051 | dev | fact | 12.2 | normal | 1 | 1 | verified |
| q052 | dev | summary | 11.7 | normal | 1 | 1 | verified |
| q053 | dev | notfound | 9.7 | table | 2 | 0 | not_found |
| q054 | dev | notfound | 3.6 | normal | 1 | 0 | not_found |
| q055 | dev | notfound | 15.1 | normal | 2 | 1 | verified |
