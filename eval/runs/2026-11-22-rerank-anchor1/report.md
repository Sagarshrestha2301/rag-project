# Generation run: rerank-anchor1

- Model: `qwen3.5:4b` (digest `d8b0f5e9760c`), prompt `s6-3`, temperature 0, num_ctx 4096, think False
- Corpus: **186 documents, 2669 pages** (222 OCR pages)
- Questions: 55 (55 in the set), cache off

## End-to-end latency (seconds per question, retries and condense included)

| n | p50 | p95 | min | max | mean | over 20 s | over 30 s |
|---|---|---|---|---|---|---|---|
| 55 | 12.3 | 39.4 | 3.5 | 60.1 | 15.3 | 10 | 5 |

Target: about 20 s for a short follow-up, 30 s+ acceptable for a deep or long question. Measured p50 **12.3 s**, p95 **39.4 s**.

Slowest questions: `q002` 60.1 s, `q045` 50.8 s, `q013` 41.7 s. A single stalled question moves the mean, not the p50/p95.

## How the questions were handled

| | count |
|---|---|
| status `not_found` | 9 |
| status `unverified` | 6 |
| status `verified` | 40 |
| route `followup` | 2 |
| route `normal` | 40 |
| route `table` | 13 |
| attempts 1 | 43 |
| attempts 2 | 12 |

## Scores (from eval/score.py on the same run.jsonl)

- citation: 34/48
- numeric: 36/43
- not-found (a): 4/6
- not-found (b): 44/48
- passed: 37/55

| id | split | type | seconds | route | attempts | citations | status |
|---|---|---|---|---|---|---|---|
| q001 | dev | fact | 18.8 | normal | 1 | 1 | verified |
| q002 | dev | fact | 60.1 | normal | 2 | 3 | verified |
| q003 | dev | fact | 9.8 | normal | 1 | 1 | verified |
| q004 | dev | fact | 13.2 | normal | 1 | 1 | verified |
| q005 | heldout | fact | 8.9 | normal | 1 | 1 | verified |
| q006 | dev | fact | 12.1 | normal | 1 | 1 | verified |
| q007 | heldout | fact | 9.1 | normal | 1 | 1 | verified |
| q008 | dev | exact | 11.9 | normal | 1 | 1 | verified |
| q009 | dev | exact | 9.0 | normal | 1 | 1 | verified |
| q010 | heldout | exact | 8.6 | normal | 1 | 1 | verified |
| q011 | dev | exact | 15.9 | normal | 1 | 1 | verified |
| q012 | heldout | exact | 11.4 | normal | 1 | 1 | verified |
| q013 | dev | summary | 41.7 | normal | 2 | 2 | verified |
| q014 | dev | summary | 17.4 | normal | 1 | 1 | verified |
| q015 | heldout | summary | 3.8 | normal | 1 | 0 | not_found |
| q016 | dev | comparison | 14.1 | normal | 1 | 1 | verified |
| q017 | dev | comparison | 17.6 | normal | 1 | 1 | verified |
| q018 | heldout | comparison | 14.2 | normal | 1 | 1 | verified |
| q019 | dev | notfound | 3.5 | normal | 1 | 0 | not_found |
| q020 | dev | notfound | 22.9 | normal | 1 | 2 | verified |
| q021 | dev | notfound | 38.5 | normal | 2 | 0 | not_found |
| q022 | heldout | notfound | 3.5 | normal | 1 | 0 | not_found |
| q023 | dev | followup | 11.4 | followup | 1 | 1 | verified |
| q024 | heldout | followup | 14.3 | followup | 1 | 1 | verified |
| q025 | dev | table | 4.0 | table | 1 | 0 | not_found |
| q026 | dev | table | 14.9 | table | 2 | 0 | unverified |
| q027 | dev | table | 4.4 | table | 1 | 0 | not_found |
| q028 | dev | table | 20.9 | table | 2 | 0 | unverified |
| q029 | heldout | table | 13.0 | table | 1 | 1 | verified |
| q030 | heldout | table | 20.6 | table | 2 | 0 | unverified |
| q031 | dev | number | 9.6 | table | 1 | 1 | verified |
| q032 | dev | number | 9.1 | normal | 1 | 1 | verified |
| q033 | dev | number | 12.3 | normal | 1 | 1 | verified |
| q034 | dev | exact | 8.2 | normal | 1 | 1 | verified |
| q035 | dev | number | 9.3 | normal | 1 | 1 | verified |
| q036 | dev | list | 3.6 | normal | 1 | 0 | not_found |
| q037 | dev | number | 9.4 | normal | 1 | 1 | verified |
| q038 | dev | comparison | 13.6 | normal | 1 | 1 | verified |
| q039 | dev | exact | 37.8 | normal | 2 | 2 | unverified |
| q040 | dev | number | 11.7 | normal | 1 | 1 | verified |
| q041 | dev | exact | 12.5 | table | 1 | 1 | verified |
| q042 | dev | fact | 10.1 | table | 1 | 1 | verified |
| q043 | dev | fact | 8.9 | normal | 1 | 1 | verified |
| q044 | dev | fact | 13.5 | normal | 1 | 1 | verified |
| q045 | dev | number | 50.8 | normal | 2 | 0 | unverified |
| q046 | dev | table | 18.4 | table | 2 | 0 | unverified |
| q047 | dev | table | 22.2 | table | 2 | 1 | verified |
| q048 | dev | fact | 18.4 | normal | 1 | 2 | verified |
| q049 | dev | fact | 22.9 | normal | 1 | 3 | verified |
| q050 | dev | list | 14.1 | table | 1 | 1 | verified |
| q051 | dev | fact | 12.3 | normal | 1 | 1 | verified |
| q052 | dev | summary | 11.8 | normal | 1 | 1 | verified |
| q053 | dev | notfound | 10.8 | table | 2 | 0 | not_found |
| q054 | dev | notfound | 3.6 | normal | 1 | 0 | not_found |
| q055 | dev | notfound | 15.0 | normal | 2 | 1 | verified |
