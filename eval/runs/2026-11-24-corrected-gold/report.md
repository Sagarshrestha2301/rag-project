# Generation run: corrected-gold

- Model: `qwen3.5:4b` (digest `d8b0f5e9760c`), prompt `s6-3`, temperature 0, num_ctx 4096, think False
- Corpus: **186 documents, 2669 pages** (222 OCR pages)
- Questions: 55 (55 in the set), cache off

## End-to-end latency (seconds per question, retries and condense included)

| n | p50 | p95 | min | max | mean | over 20 s | over 30 s |
|---|---|---|---|---|---|---|---|
| 55 | 13.3 | 54.2 | 3.0 | 117.2 | 18.7 | 13 | 6 |

Target: about 20 s for a short follow-up, 30 s+ acceptable for a deep or long question. Measured p50 **13.3 s**, p95 **54.2 s**.

Slowest questions: `q001` 117.2 s, `q044` 65.6 s, `q048` 63.2 s. A single stalled question moves the mean, not the p50/p95.

## How the questions were handled

| | count |
|---|---|
| status `not_found` | 6 |
| status `unverified` | 11 |
| status `verified` | 38 |
| route `followup` | 2 |
| route `normal` | 40 |
| route `table` | 13 |
| attempts 1 | 40 |
| attempts 2 | 15 |

## Scores (from eval/score.py on the same run.jsonl)

- citation: 32/48
- numeric: 37/43
- not-found (a): 3/6
- not-found (b): 46/48
- passed: 35/55

| id | split | type | seconds | route | attempts | citations | status |
|---|---|---|---|---|---|---|---|
| q001 | dev | fact | 117.2 | normal | 1 | 1 | verified |
| q002 | dev | fact | 17.5 | normal | 1 | 1 | verified |
| q003 | dev | fact | 26.4 | normal | 1 | 2 | verified |
| q004 | dev | fact | 14.1 | normal | 1 | 1 | verified |
| q005 | heldout | fact | 9.0 | normal | 1 | 1 | verified |
| q006 | dev | fact | 12.2 | normal | 1 | 1 | verified |
| q007 | heldout | fact | 9.4 | normal | 1 | 1 | verified |
| q008 | dev | exact | 12.5 | normal | 1 | 1 | verified |
| q009 | dev | exact | 8.7 | normal | 1 | 1 | verified |
| q010 | heldout | exact | 8.2 | normal | 1 | 1 | verified |
| q011 | dev | exact | 10.7 | normal | 1 | 1 | verified |
| q012 | heldout | exact | 12.0 | normal | 1 | 1 | verified |
| q013 | dev | summary | 21.0 | normal | 1 | 2 | verified |
| q014 | dev | summary | 19.8 | normal | 1 | 1 | verified |
| q015 | heldout | summary | 3.8 | normal | 1 | 0 | not_found |
| q016 | dev | comparison | 17.7 | normal | 1 | 1 | verified |
| q017 | dev | comparison | 20.6 | normal | 1 | 2 | verified |
| q018 | heldout | comparison | 15.4 | normal | 1 | 1 | verified |
| q019 | dev | notfound | 3.3 | normal | 1 | 0 | not_found |
| q020 | dev | notfound | 19.6 | normal | 2 | 1 | verified |
| q021 | dev | notfound | 7.0 | normal | 2 | 0 | unverified |
| q022 | heldout | notfound | 3.0 | normal | 1 | 0 | not_found |
| q023 | dev | followup | 12.2 | followup | 1 | 1 | verified |
| q024 | heldout | followup | 19.5 | followup | 1 | 1 | verified |
| q025 | dev | table | 12.2 | table | 1 | 1 | verified |
| q026 | dev | table | 25.0 | table | 2 | 0 | unverified |
| q027 | dev | table | 19.7 | table | 2 | 0 | unverified |
| q028 | dev | table | 16.2 | table | 2 | 0 | unverified |
| q029 | heldout | table | 14.1 | table | 1 | 1 | verified |
| q030 | heldout | table | 11.2 | table | 1 | 1 | verified |
| q031 | dev | number | 10.4 | table | 1 | 1 | verified |
| q032 | dev | number | 9.5 | normal | 1 | 1 | verified |
| q033 | dev | number | 13.8 | normal | 1 | 1 | verified |
| q034 | dev | exact | 8.7 | normal | 1 | 1 | verified |
| q035 | dev | number | 9.8 | normal | 1 | 1 | verified |
| q036 | dev | list | 3.5 | normal | 1 | 0 | not_found |
| q037 | dev | number | 8.7 | normal | 1 | 1 | verified |
| q038 | dev | comparison | 13.3 | normal | 1 | 1 | verified |
| q039 | dev | exact | 48.4 | normal | 2 | 3 | unverified |
| q040 | dev | number | 34.5 | normal | 2 | 2 | verified |
| q041 | dev | exact | 12.7 | table | 1 | 1 | verified |
| q042 | dev | fact | 10.5 | table | 1 | 1 | verified |
| q043 | dev | fact | 9.0 | normal | 1 | 1 | verified |
| q044 | dev | fact | 65.6 | normal | 2 | 4 | unverified |
| q045 | dev | number | 50.3 | normal | 2 | 3 | unverified |
| q046 | dev | table | 21.0 | table | 2 | 0 | unverified |
| q047 | dev | table | 19.9 | table | 2 | 1 | verified |
| q048 | dev | fact | 63.2 | normal | 2 | 3 | unverified |
| q049 | dev | fact | 24.2 | normal | 1 | 2 | verified |
| q050 | dev | list | 15.7 | table | 1 | 1 | verified |
| q051 | dev | fact | 14.3 | normal | 1 | 1 | verified |
| q052 | dev | summary | 23.1 | normal | 2 | 2 | unverified |
| q053 | dev | notfound | 7.2 | table | 2 | 0 | not_found |
| q054 | dev | notfound | 3.0 | normal | 1 | 0 | not_found |
| q055 | dev | notfound | 6.8 | normal | 2 | 0 | unverified |
