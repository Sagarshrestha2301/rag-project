# Generation run: prewave-corrected-gold

- Model: `qwen3.5:4b` (digest `d8b0f5e9760c`), prompt `s6-3`, temperature 0, num_ctx 4096, think False
- Corpus: **97 documents, 851 pages** (86 OCR pages)
- Questions: 55 (55 in the set), cache off

## End-to-end latency (seconds per question, retries and condense included)

| n | p50 | p95 | min | max | mean | over 20 s | over 30 s |
|---|---|---|---|---|---|---|---|
| 55 | 12.3 | 56.3 | 3.0 | 82.0 | 17.8 | 13 | 5 |

Target: about 20 s for a short follow-up, 30 s+ acceptable for a deep or long question. Measured p50 **12.3 s**, p95 **56.3 s**.

Slowest questions: `q049` 82.0 s, `q044` 66.6 s, `q048` 57.8 s. A single stalled question moves the mean, not the p50/p95.

## How the questions were handled

| | count |
|---|---|
| status `not_found` | 7 |
| status `unverified` | 10 |
| status `verified` | 38 |
| route `followup` | 2 |
| route `normal` | 40 |
| route `table` | 13 |
| attempts 1 | 43 |
| attempts 2 | 12 |

## Scores (from eval/score.py on the same run.jsonl)

- citation: 34/48
- numeric: 37/43
- not-found (a): 4/6
- not-found (b): 46/48
- passed: 38/55

| id | split | type | seconds | route | attempts | citations | status |
|---|---|---|---|---|---|---|---|
| q001 | dev | fact | 11.9 | normal | 1 | 1 | verified |
| q002 | dev | fact | 12.1 | normal | 1 | 1 | verified |
| q003 | dev | fact | 10.3 | normal | 1 | 1 | verified |
| q004 | dev | fact | 27.1 | normal | 1 | 2 | verified |
| q005 | heldout | fact | 9.3 | normal | 1 | 1 | verified |
| q006 | dev | fact | 16.9 | normal | 1 | 1 | verified |
| q007 | heldout | fact | 10.3 | normal | 1 | 1 | verified |
| q008 | dev | exact | 11.8 | normal | 1 | 1 | verified |
| q009 | dev | exact | 8.8 | normal | 1 | 1 | verified |
| q010 | heldout | exact | 8.4 | normal | 1 | 1 | verified |
| q011 | dev | exact | 11.4 | normal | 1 | 1 | verified |
| q012 | heldout | exact | 11.2 | normal | 1 | 1 | verified |
| q013 | dev | summary | 17.7 | normal | 1 | 1 | verified |
| q014 | dev | summary | 16.5 | normal | 1 | 1 | verified |
| q015 | heldout | summary | 3.8 | normal | 1 | 0 | not_found |
| q016 | dev | comparison | 14.8 | normal | 1 | 1 | verified |
| q017 | dev | comparison | 21.2 | normal | 1 | 2 | verified |
| q018 | heldout | comparison | 18.5 | normal | 1 | 1 | verified |
| q019 | dev | notfound | 3.5 | normal | 1 | 0 | not_found |
| q020 | dev | notfound | 25.2 | normal | 2 | 2 | verified |
| q021 | dev | notfound | 20.1 | normal | 2 | 0 | unverified |
| q022 | heldout | notfound | 3.1 | normal | 1 | 0 | not_found |
| q023 | dev | followup | 12.3 | followup | 1 | 1 | verified |
| q024 | heldout | followup | 15.4 | followup | 1 | 1 | verified |
| q025 | dev | table | 10.6 | table | 1 | 1 | verified |
| q026 | dev | table | 24.7 | table | 2 | 0 | unverified |
| q027 | dev | table | 19.5 | table | 2 | 0 | unverified |
| q028 | dev | table | 15.7 | table | 2 | 0 | unverified |
| q029 | heldout | table | 13.7 | table | 1 | 1 | verified |
| q030 | heldout | table | 11.4 | table | 1 | 1 | verified |
| q031 | dev | number | 10.1 | table | 1 | 1 | verified |
| q032 | dev | number | 9.6 | normal | 1 | 1 | verified |
| q033 | dev | number | 12.9 | normal | 1 | 1 | verified |
| q034 | dev | exact | 9.4 | normal | 1 | 1 | verified |
| q035 | dev | number | 9.8 | normal | 1 | 1 | verified |
| q036 | dev | list | 3.0 | normal | 1 | 0 | not_found |
| q037 | dev | number | 7.6 | normal | 1 | 1 | verified |
| q038 | dev | comparison | 17.6 | normal | 1 | 1 | verified |
| q039 | dev | exact | 45.9 | normal | 2 | 3 | unverified |
| q040 | dev | number | 12.3 | normal | 1 | 1 | verified |
| q041 | dev | exact | 12.2 | table | 1 | 1 | verified |
| q042 | dev | fact | 10.6 | table | 1 | 1 | verified |
| q043 | dev | fact | 11.1 | normal | 1 | 1 | verified |
| q044 | dev | fact | 66.6 | normal | 2 | 4 | unverified |
| q045 | dev | number | 55.7 | normal | 2 | 3 | unverified |
| q046 | dev | table | 26.5 | table | 2 | 0 | unverified |
| q047 | dev | table | 26.2 | table | 2 | 1 | verified |
| q048 | dev | fact | 57.8 | normal | 2 | 3 | unverified |
| q049 | dev | fact | 82.0 | normal | 2 | 0 | unverified |
| q050 | dev | list | 20.1 | table | 1 | 1 | verified |
| q051 | dev | fact | 18.4 | normal | 1 | 1 | verified |
| q052 | dev | summary | 17.9 | normal | 1 | 1 | verified |
| q053 | dev | notfound | 6.2 | table | 1 | 0 | not_found |
| q054 | dev | notfound | 5.9 | normal | 1 | 0 | not_found |
| q055 | dev | notfound | 5.3 | normal | 1 | 0 | not_found |
