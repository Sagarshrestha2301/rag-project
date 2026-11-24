# Generation run: repro-b

- Model: `qwen3.5:4b` (digest `d8b0f5e9760c`), prompt `s6-3`, temperature 0, num_ctx 4096, think False
- Corpus: **186 documents, 2669 pages** (222 OCR pages)
- Questions: 55 (55 in the set), cache off

## End-to-end latency (seconds per question, retries and condense included)

| n | p50 | p95 | min | max | mean | over 20 s | over 30 s |
|---|---|---|---|---|---|---|---|
| 55 | 12.2 | 47.0 | 3.0 | 64.2 | 16.1 | 11 | 5 |

Target: about 20 s for a short follow-up, 30 s+ acceptable for a deep or long question. Measured p50 **12.2 s**, p95 **47.0 s**.

Slowest questions: `q044` 64.2 s, `q045` 49.2 s, `q048` 48.7 s. A single stalled question moves the mean, not the p50/p95.

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
| q001 | dev | fact | 11.8 | normal | 1 | 1 | verified |
| q002 | dev | fact | 17.8 | normal | 1 | 1 | verified |
| q003 | dev | fact | 25.9 | normal | 1 | 2 | verified |
| q004 | dev | fact | 14.0 | normal | 1 | 1 | verified |
| q005 | heldout | fact | 8.5 | normal | 1 | 1 | verified |
| q006 | dev | fact | 11.9 | normal | 1 | 1 | verified |
| q007 | heldout | fact | 9.9 | normal | 1 | 1 | verified |
| q008 | dev | exact | 11.9 | normal | 1 | 1 | verified |
| q009 | dev | exact | 8.8 | normal | 1 | 1 | verified |
| q010 | heldout | exact | 8.0 | normal | 1 | 1 | verified |
| q011 | dev | exact | 11.0 | normal | 1 | 1 | verified |
| q012 | heldout | exact | 11.7 | normal | 1 | 1 | verified |
| q013 | dev | summary | 21.0 | normal | 1 | 2 | verified |
| q014 | dev | summary | 19.1 | normal | 1 | 1 | verified |
| q015 | heldout | summary | 3.5 | normal | 1 | 0 | not_found |
| q016 | dev | comparison | 16.8 | normal | 1 | 1 | verified |
| q017 | dev | comparison | 20.6 | normal | 1 | 2 | verified |
| q018 | heldout | comparison | 15.3 | normal | 1 | 1 | verified |
| q019 | dev | notfound | 3.3 | normal | 1 | 0 | not_found |
| q020 | dev | notfound | 19.1 | normal | 2 | 1 | verified |
| q021 | dev | notfound | 7.5 | normal | 2 | 0 | unverified |
| q022 | heldout | notfound | 3.1 | normal | 1 | 0 | not_found |
| q023 | dev | followup | 12.2 | followup | 1 | 1 | verified |
| q024 | heldout | followup | 16.2 | followup | 1 | 1 | verified |
| q025 | dev | table | 10.5 | table | 1 | 1 | verified |
| q026 | dev | table | 24.6 | table | 2 | 0 | unverified |
| q027 | dev | table | 19.4 | table | 2 | 0 | unverified |
| q028 | dev | table | 16.2 | table | 2 | 0 | unverified |
| q029 | heldout | table | 15.0 | table | 1 | 1 | verified |
| q030 | heldout | table | 11.0 | table | 1 | 1 | verified |
| q031 | dev | number | 10.1 | table | 1 | 1 | verified |
| q032 | dev | number | 9.5 | normal | 1 | 1 | verified |
| q033 | dev | number | 13.4 | normal | 1 | 1 | verified |
| q034 | dev | exact | 8.6 | normal | 1 | 1 | verified |
| q035 | dev | number | 9.8 | normal | 1 | 1 | verified |
| q036 | dev | list | 3.3 | normal | 1 | 0 | not_found |
| q037 | dev | number | 8.5 | normal | 1 | 1 | verified |
| q038 | dev | comparison | 13.0 | normal | 1 | 1 | verified |
| q039 | dev | exact | 46.3 | normal | 2 | 3 | unverified |
| q040 | dev | number | 32.8 | normal | 2 | 2 | verified |
| q041 | dev | exact | 12.0 | table | 1 | 1 | verified |
| q042 | dev | fact | 10.1 | table | 1 | 1 | verified |
| q043 | dev | fact | 8.9 | normal | 1 | 1 | verified |
| q044 | dev | fact | 64.2 | normal | 2 | 4 | unverified |
| q045 | dev | number | 49.2 | normal | 2 | 3 | unverified |
| q046 | dev | table | 19.6 | table | 2 | 0 | unverified |
| q047 | dev | table | 19.5 | table | 2 | 1 | verified |
| q048 | dev | fact | 48.7 | normal | 2 | 3 | unverified |
| q049 | dev | fact | 22.4 | normal | 1 | 2 | verified |
| q050 | dev | list | 14.8 | table | 1 | 1 | verified |
| q051 | dev | fact | 15.1 | normal | 1 | 1 | verified |
| q052 | dev | summary | 23.2 | normal | 2 | 2 | unverified |
| q053 | dev | notfound | 6.9 | table | 2 | 0 | not_found |
| q054 | dev | notfound | 3.0 | normal | 1 | 0 | not_found |
| q055 | dev | notfound | 6.8 | normal | 2 | 0 | unverified |
