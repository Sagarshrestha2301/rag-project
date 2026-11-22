# Generation run: wave01-full

- Model: `qwen3.5:4b` (digest `d8b0f5e9760c`), prompt `s6-3`, temperature 0, num_ctx 4096, think False
- Corpus: **215 documents, 3126 pages** (231 OCR pages)
- Questions: 55 (55 in the set), cache off

## End-to-end latency (seconds per question, retries and condense included)

| n | p50 | p95 | min | max | mean | over 20 s | over 30 s |
|---|---|---|---|---|---|---|---|
| 55 | 12.4 | 29.3 | 2.8 | 47.2 | 15.1 | 11 | 3 |

Target: about 20 s for a short follow-up, 30 s+ acceptable for a deep or long question. Measured p50 **12.4 s**, p95 **29.3 s**.

Slowest questions: `q045` 47.2 s, `q048` 46.2 s, `q002` 32.9 s. A single stalled question moves the mean, not the p50/p95.

## How the questions were handled

| | count |
|---|---|
| status `not_found` | 4 |
| status `unverified` | 13 |
| status `verified` | 38 |
| route `followup` | 2 |
| route `normal` | 40 |
| route `table` | 13 |
| attempts 1 | 39 |
| attempts 2 | 16 |

## Scores (from eval/score.py on the same run.jsonl)

- citation: 33/48
- numeric: 35/43
- not-found (a): 2/6
- not-found (b): 47/48
- passed: 33/55

| id | split | type | seconds | route | attempts | citations | status |
|---|---|---|---|---|---|---|---|
| q001 | dev | fact | 17.9 | normal | 1 | 1 | verified |
| q002 | dev | fact | 32.9 | normal | 2 | 0 | unverified |
| q003 | dev | fact | 22.7 | normal | 1 | 2 | verified |
| q004 | dev | fact | 13.4 | normal | 1 | 1 | verified |
| q005 | heldout | fact | 8.5 | normal | 1 | 1 | verified |
| q006 | dev | fact | 11.3 | normal | 1 | 1 | verified |
| q007 | heldout | fact | 8.7 | normal | 1 | 1 | verified |
| q008 | dev | exact | 11.2 | normal | 1 | 1 | verified |
| q009 | dev | exact | 8.4 | normal | 1 | 1 | verified |
| q010 | heldout | exact | 7.7 | normal | 1 | 1 | verified |
| q011 | dev | exact | 10.4 | normal | 1 | 1 | verified |
| q012 | heldout | exact | 10.5 | normal | 1 | 1 | verified |
| q013 | dev | summary | 19.9 | normal | 1 | 2 | verified |
| q014 | dev | summary | 18.1 | normal | 1 | 1 | verified |
| q015 | heldout | summary | 6.5 | normal | 2 | 0 | unverified |
| q016 | dev | comparison | 15.9 | normal | 1 | 1 | verified |
| q017 | dev | comparison | 12.9 | normal | 1 | 1 | verified |
| q018 | heldout | comparison | 14.3 | normal | 1 | 1 | verified |
| q019 | dev | notfound | 27.8 | normal | 2 | 2 | unverified |
| q020 | dev | notfound | 18.6 | normal | 2 | 1 | verified |
| q021 | dev | notfound | 6.6 | normal | 2 | 0 | unverified |
| q022 | heldout | notfound | 2.8 | normal | 1 | 0 | not_found |
| q023 | dev | followup | 11.5 | followup | 1 | 1 | verified |
| q024 | heldout | followup | 14.7 | followup | 1 | 1 | verified |
| q025 | dev | table | 9.4 | table | 1 | 1 | verified |
| q026 | dev | table | 20.6 | table | 2 | 0 | unverified |
| q027 | dev | table | 23.0 | table | 2 | 0 | unverified |
| q028 | dev | table | 15.1 | table | 2 | 0 | unverified |
| q029 | heldout | table | 13.1 | table | 1 | 1 | verified |
| q030 | heldout | table | 10.4 | table | 1 | 1 | verified |
| q031 | dev | number | 9.3 | table | 1 | 1 | verified |
| q032 | dev | number | 8.3 | normal | 1 | 1 | verified |
| q033 | dev | number | 12.4 | normal | 1 | 1 | verified |
| q034 | dev | exact | 11.9 | normal | 1 | 1 | verified |
| q035 | dev | number | 8.7 | normal | 1 | 1 | verified |
| q036 | dev | list | 3.1 | normal | 1 | 0 | not_found |
| q037 | dev | number | 7.0 | normal | 1 | 1 | verified |
| q038 | dev | comparison | 12.6 | normal | 1 | 1 | verified |
| q039 | dev | exact | 26.5 | normal | 2 | 1 | unverified |
| q040 | dev | number | 17.3 | normal | 1 | 2 | verified |
| q041 | dev | exact | 11.6 | table | 1 | 1 | verified |
| q042 | dev | fact | 9.6 | table | 1 | 1 | verified |
| q043 | dev | fact | 8.4 | normal | 1 | 1 | verified |
| q044 | dev | fact | 9.4 | normal | 1 | 1 | verified |
| q045 | dev | number | 47.2 | normal | 2 | 3 | unverified |
| q046 | dev | table | 18.1 | table | 2 | 0 | unverified |
| q047 | dev | table | 18.6 | table | 2 | 1 | verified |
| q048 | dev | fact | 46.2 | normal | 2 | 3 | unverified |
| q049 | dev | fact | 25.1 | normal | 1 | 3 | verified |
| q050 | dev | list | 14.3 | table | 1 | 1 | verified |
| q051 | dev | fact | 27.5 | normal | 1 | 3 | verified |
| q052 | dev | summary | 26.5 | normal | 2 | 2 | unverified |
| q053 | dev | notfound | 10.9 | table | 2 | 0 | not_found |
| q054 | dev | notfound | 4.5 | normal | 1 | 0 | not_found |
| q055 | dev | notfound | 9.8 | normal | 2 | 0 | unverified |
