# Generation run: step9-cite-evidence

- Model: `qwen3.5:4b` (digest `d8b0f5e9760c`), prompt `s6-3`, temperature 0, num_ctx 4096, think False
- Corpus: **97 documents, 851 pages** (86 OCR pages)
- Questions: 55 (55 in the set), cache off

## End-to-end latency (seconds per question, retries and condense included)

| n | p50 | p95 | min | max | mean | over 20 s | over 30 s |
|---|---|---|---|---|---|---|---|
| 55 | 13.4 | 27.7 | 2.9 | 48.3 | 14.7 | 10 | 3 |

Target: about 20 s for a short follow-up, 30 s+ acceptable for a deep or long question. Measured p50 **13.4 s**, p95 **27.7 s**.

Slowest questions: `q048` 48.3 s, `q039` 37.8 s, `q049` 30.4 s. A single stalled question moves the mean, not the p50/p95.

## How the questions were handled

| | count |
|---|---|
| status `not_found` | 6 |
| status `unverified` | 7 |
| status `verified` | 42 |
| route `followup` | 2 |
| route `normal` | 40 |
| route `table` | 13 |
| attempts 1 | 46 |
| attempts 2 | 9 |

## Scores (from eval/score.py on the same run.jsonl)

- citation: 35/48
- numeric: 36/43
- not-found (a): 3/6
- not-found (b): 46/48
- passed: 36/55

| id | split | type | seconds | route | attempts | citations | status |
|---|---|---|---|---|---|---|---|
| q001 | dev | fact | 14.5 | normal | 1 | 1 | verified |
| q002 | dev | fact | 14.6 | normal | 1 | 1 | verified |
| q003 | dev | fact | 12.1 | normal | 1 | 1 | verified |
| q004 | dev | fact | 16.6 | normal | 1 | 1 | verified |
| q005 | heldout | fact | 10.7 | normal | 1 | 1 | verified |
| q006 | dev | fact | 14.6 | normal | 1 | 1 | verified |
| q007 | heldout | fact | 13.2 | normal | 1 | 1 | verified |
| q008 | dev | exact | 15.6 | normal | 1 | 1 | verified |
| q009 | dev | exact | 14.5 | normal | 1 | 1 | verified |
| q010 | heldout | exact | 13.8 | normal | 1 | 1 | verified |
| q011 | dev | exact | 11.9 | normal | 1 | 1 | verified |
| q012 | heldout | exact | 12.0 | normal | 1 | 1 | verified |
| q013 | dev | summary | 19.2 | normal | 1 | 1 | verified |
| q014 | dev | summary | 20.5 | normal | 1 | 1 | verified |
| q015 | heldout | summary | 4.3 | normal | 1 | 0 | not_found |
| q016 | dev | comparison | 16.7 | normal | 1 | 1 | verified |
| q017 | dev | comparison | 22.5 | normal | 1 | 2 | verified |
| q018 | heldout | comparison | 19.0 | normal | 1 | 1 | verified |
| q019 | dev | notfound | 3.4 | normal | 1 | 0 | not_found |
| q020 | dev | notfound | 25.8 | normal | 2 | 1 | verified |
| q021 | dev | notfound | 18.6 | normal | 2 | 0 | unverified |
| q022 | heldout | notfound | 3.0 | normal | 1 | 0 | not_found |
| q023 | dev | followup | 20.5 | followup | 1 | 1 | verified |
| q024 | heldout | followup | 16.6 | followup | 1 | 1 | verified |
| q025 | dev | table | 10.6 | table | 1 | 1 | verified |
| q026 | dev | table | 26.5 | table | 2 | 0 | unverified |
| q027 | dev | table | 17.8 | table | 2 | 0 | unverified |
| q028 | dev | table | 13.4 | table | 2 | 0 | unverified |
| q029 | heldout | table | 12.9 | table | 1 | 1 | verified |
| q030 | heldout | table | 10.4 | table | 1 | 1 | verified |
| q031 | dev | number | 9.3 | table | 1 | 1 | verified |
| q032 | dev | number | 8.7 | normal | 1 | 1 | verified |
| q033 | dev | number | 12.1 | normal | 1 | 1 | verified |
| q034 | dev | exact | 8.4 | normal | 1 | 1 | verified |
| q035 | dev | number | 9.1 | normal | 1 | 1 | verified |
| q036 | dev | list | 2.9 | normal | 1 | 0 | not_found |
| q037 | dev | number | 7.6 | normal | 1 | 1 | verified |
| q038 | dev | comparison | 16.6 | normal | 1 | 1 | verified |
| q039 | dev | exact | 37.8 | normal | 2 | 2 | unverified |
| q040 | dev | number | 12.2 | normal | 1 | 1 | verified |
| q041 | dev | exact | 11.5 | table | 1 | 1 | verified |
| q042 | dev | fact | 9.7 | table | 1 | 1 | verified |
| q043 | dev | fact | 9.0 | normal | 1 | 1 | verified |
| q044 | dev | fact | 9.5 | normal | 1 | 1 | verified |
| q045 | dev | number | 24.0 | normal | 1 | 3 | verified |
| q046 | dev | table | 14.3 | table | 1 | 1 | verified |
| q047 | dev | table | 13.8 | table | 2 | 0 | unverified |
| q048 | dev | fact | 48.3 | normal | 2 | 3 | verified |
| q049 | dev | fact | 30.4 | normal | 1 | 4 | verified |
| q050 | dev | list | 13.9 | table | 1 | 1 | verified |
| q051 | dev | fact | 26.4 | normal | 1 | 3 | verified |
| q052 | dev | summary | 13.3 | normal | 1 | 1 | verified |
| q053 | dev | notfound | 3.8 | table | 1 | 0 | not_found |
| q054 | dev | notfound | 3.5 | normal | 1 | 0 | not_found |
| q055 | dev | notfound | 6.0 | normal | 2 | 0 | unverified |
