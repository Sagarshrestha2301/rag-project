# Generation run: 2026-11-25-step16-list-retrieval

- Model: `qwen3.5:4b` (digest `d8b0f5e9760c`), prompt `s6-5`, temperature 0, num_ctx 4096, think False
- Corpus: **186 documents, 2669 pages** (222 OCR pages)
- Questions: 55 (55 in the set), cache off

## End-to-end latency (seconds per question, retries and condense included)

| n | p50 | p95 | min | max | mean | over 20 s | over 30 s |
|---|---|---|---|---|---|---|---|
| 55 | 11.4 | 44.1 | 2.8 | 60.7 | 15.1 | 9 | 5 |

Target: about 20 s for a short follow-up, 30 s+ acceptable for a deep or long question. Measured p50 **11.4 s**, p95 **44.1 s**.

Slowest questions: `q044` 60.7 s, `q045` 46.8 s, `q048` 46.4 s. A single stalled question moves the mean, not the p50/p95.

## How the questions were handled

| | count |
|---|---|
| status `not_found` | 8 |
| status `unverified` | 8 |
| status `verified` | 39 |
| route `followup` | 2 |
| route `normal` | 40 |
| route `table` | 13 |
| attempts 1 | 43 |
| attempts 2 | 12 |

## Scores (from eval/score.py on the same run.jsonl)

- citation: 33/48
- numeric: 38/43
- not-found (a): 5/6
- not-found (b): 46/48
- passed: 38/55

| id | split | type | seconds | route | attempts | citations | status |
|---|---|---|---|---|---|---|---|
| q001 | dev | fact | 11.1 | normal | 1 | 1 | verified |
| q002 | dev | fact | 16.5 | normal | 1 | 1 | verified |
| q003 | dev | fact | 24.6 | normal | 1 | 2 | verified |
| q004 | dev | fact | 13.5 | normal | 1 | 1 | verified |
| q005 | heldout | fact | 8.4 | normal | 1 | 1 | verified |
| q006 | dev | fact | 11.2 | normal | 1 | 1 | verified |
| q007 | heldout | fact | 8.6 | normal | 1 | 1 | verified |
| q008 | dev | exact | 11.2 | normal | 1 | 1 | verified |
| q009 | dev | exact | 8.2 | normal | 1 | 1 | verified |
| q010 | heldout | exact | 7.6 | normal | 1 | 1 | verified |
| q011 | dev | exact | 10.3 | normal | 1 | 1 | verified |
| q012 | heldout | exact | 10.3 | normal | 1 | 1 | verified |
| q013 | dev | summary | 19.9 | normal | 1 | 2 | verified |
| q014 | dev | summary | 18.0 | normal | 1 | 1 | verified |
| q015 | heldout | summary | 3.2 | normal | 1 | 0 | not_found |
| q016 | dev | comparison | 15.8 | normal | 1 | 1 | verified |
| q017 | dev | comparison | 19.4 | normal | 1 | 2 | verified |
| q018 | heldout | comparison | 14.2 | normal | 1 | 1 | verified |
| q019 | dev | notfound | 3.3 | normal | 1 | 0 | not_found |
| q020 | dev | notfound | 18.0 | normal | 2 | 1 | verified |
| q021 | dev | notfound | 4.4 | normal | 1 | 0 | not_found |
| q022 | heldout | notfound | 2.9 | normal | 1 | 0 | not_found |
| q023 | dev | followup | 11.3 | followup | 1 | 1 | verified |
| q024 | heldout | followup | 14.8 | followup | 1 | 1 | verified |
| q025 | dev | table | 9.8 | table | 1 | 1 | verified |
| q026 | dev | table | 22.7 | table | 2 | 0 | unverified |
| q027 | dev | table | 18.0 | table | 2 | 0 | not_found |
| q028 | dev | table | 14.8 | table | 2 | 0 | unverified |
| q029 | heldout | table | 13.1 | table | 1 | 1 | verified |
| q030 | heldout | table | 10.4 | table | 1 | 1 | verified |
| q031 | dev | number | 9.2 | table | 1 | 1 | verified |
| q032 | dev | number | 8.4 | normal | 1 | 1 | verified |
| q033 | dev | number | 12.2 | normal | 1 | 1 | verified |
| q034 | dev | exact | 8.0 | normal | 1 | 1 | verified |
| q035 | dev | number | 8.6 | normal | 1 | 1 | verified |
| q036 | dev | list | 10.1 | normal | 1 | 1 | verified |
| q037 | dev | number | 7.0 | normal | 1 | 1 | verified |
| q038 | dev | comparison | 12.4 | normal | 1 | 1 | verified |
| q039 | dev | exact | 43.1 | normal | 2 | 3 | unverified |
| q040 | dev | number | 30.3 | normal | 2 | 2 | verified |
| q041 | dev | exact | 11.4 | table | 1 | 1 | verified |
| q042 | dev | fact | 9.6 | table | 1 | 1 | verified |
| q043 | dev | fact | 8.5 | normal | 1 | 1 | verified |
| q044 | dev | fact | 60.7 | normal | 2 | 4 | unverified |
| q045 | dev | number | 46.8 | normal | 2 | 3 | unverified |
| q046 | dev | table | 17.9 | table | 2 | 0 | unverified |
| q047 | dev | table | 18.8 | table | 2 | 1 | verified |
| q048 | dev | fact | 46.4 | normal | 2 | 3 | unverified |
| q049 | dev | fact | 21.9 | normal | 1 | 2 | verified |
| q050 | dev | list | 14.9 | table | 1 | 1 | verified |
| q051 | dev | fact | 13.2 | normal | 1 | 1 | verified |
| q052 | dev | summary | 21.7 | normal | 2 | 2 | unverified |
| q053 | dev | notfound | 5.2 | table | 1 | 0 | not_found |
| q054 | dev | notfound | 2.8 | normal | 1 | 0 | not_found |
| q055 | dev | notfound | 4.2 | normal | 1 | 0 | not_found |
