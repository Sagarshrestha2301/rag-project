# Generation run: step16-list-format

- Model: `qwen3.5:4b` (digest `d8b0f5e9760c`), prompt `s6-4`, temperature 0, num_ctx 4096, think False
- Corpus: **186 documents, 2669 pages** (222 OCR pages)
- Questions: 55 (55 in the set), cache off

## End-to-end latency (seconds per question, retries and condense included)

| n | p50 | p95 | min | max | mean | over 20 s | over 30 s |
|---|---|---|---|---|---|---|---|
| 55 | 11.9 | 48.9 | 3.1 | 104.2 | 17.6 | 14 | 7 |

Target: about 20 s for a short follow-up, 30 s+ acceptable for a deep or long question. Measured p50 **11.9 s**, p95 **48.9 s**.

Slowest questions: `q051` 104.2 s, `q044` 55.0 s, `q039` 49.7 s. A single stalled question moves the mean, not the p50/p95.

## How the questions were handled

| | count |
|---|---|
| status `not_found` | 8 |
| status `unverified` | 6 |
| status `verified` | 41 |
| route `followup` | 2 |
| route `normal` | 40 |
| route `table` | 13 |
| attempts 1 | 47 |
| attempts 2 | 8 |

## Scores (from eval/score.py on the same run.jsonl)

- citation: 30/48
- numeric: 39/43
- not-found (a): 5/6
- not-found (b): 46/48
- passed: 35/55

| id | split | type | seconds | route | attempts | citations | status |
|---|---|---|---|---|---|---|---|
| q001 | dev | fact | 11.9 | normal | 1 | 1 | verified |
| q002 | dev | fact | 21.3 | normal | 2 | 1 | unverified |
| q003 | dev | fact | 10.5 | normal | 1 | 1 | verified |
| q004 | dev | fact | 19.8 | normal | 1 | 2 | verified |
| q005 | heldout | fact | 9.0 | normal | 1 | 1 | verified |
| q006 | dev | fact | 19.3 | normal | 1 | 2 | verified |
| q007 | heldout | fact | 9.4 | normal | 1 | 1 | verified |
| q008 | dev | exact | 12.5 | normal | 1 | 1 | verified |
| q009 | dev | exact | 9.2 | normal | 1 | 1 | verified |
| q010 | heldout | exact | 8.3 | normal | 1 | 1 | verified |
| q011 | dev | exact | 11.2 | normal | 1 | 1 | verified |
| q012 | heldout | exact | 28.7 | normal | 1 | 3 | verified |
| q013 | dev | summary | 48.6 | normal | 2 | 3 | verified |
| q014 | dev | summary | 19.2 | normal | 1 | 1 | verified |
| q015 | heldout | summary | 3.3 | normal | 1 | 0 | not_found |
| q016 | dev | comparison | 15.3 | normal | 1 | 1 | verified |
| q017 | dev | comparison | 12.7 | normal | 1 | 1 | verified |
| q018 | heldout | comparison | 15.7 | normal | 1 | 1 | verified |
| q019 | dev | notfound | 3.4 | normal | 1 | 0 | not_found |
| q020 | dev | notfound | 31.9 | normal | 2 | 2 | verified |
| q021 | dev | notfound | 4.8 | normal | 1 | 0 | not_found |
| q022 | heldout | notfound | 3.3 | normal | 1 | 0 | not_found |
| q023 | dev | followup | 12.7 | followup | 1 | 1 | verified |
| q024 | heldout | followup | 22.6 | followup | 1 | 2 | verified |
| q025 | dev | table | 8.7 | table | 1 | 1 | verified |
| q026 | dev | table | 28.7 | table | 1 | 4 | verified |
| q027 | dev | table | 20.2 | table | 2 | 0 | unverified |
| q028 | dev | table | 10.7 | table | 2 | 0 | unverified |
| q029 | heldout | table | 10.4 | table | 1 | 1 | verified |
| q030 | heldout | table | 11.4 | table | 1 | 1 | verified |
| q031 | dev | number | 9.7 | table | 1 | 1 | verified |
| q032 | dev | number | 8.9 | normal | 1 | 1 | verified |
| q033 | dev | number | 13.0 | normal | 1 | 1 | verified |
| q034 | dev | exact | 8.5 | normal | 1 | 1 | verified |
| q035 | dev | number | 9.4 | normal | 1 | 1 | verified |
| q036 | dev | list | 3.2 | normal | 1 | 0 | not_found |
| q037 | dev | number | 7.4 | normal | 1 | 1 | verified |
| q038 | dev | comparison | 17.4 | normal | 1 | 1 | verified |
| q039 | dev | exact | 49.7 | normal | 2 | 3 | unverified |
| q040 | dev | number | 32.4 | normal | 2 | 2 | unverified |
| q041 | dev | exact | 13.0 | table | 1 | 1 | verified |
| q042 | dev | fact | 10.3 | table | 1 | 1 | verified |
| q043 | dev | fact | 9.1 | normal | 1 | 1 | verified |
| q044 | dev | fact | 55.0 | normal | 1 | 8 | verified |
| q045 | dev | number | 29.2 | normal | 1 | 3 | verified |
| q046 | dev | table | 9.9 | table | 1 | 1 | verified |
| q047 | dev | table | 10.0 | table | 1 | 1 | verified |
| q048 | dev | fact | 47.1 | normal | 2 | 3 | unverified |
| q049 | dev | fact | 25.1 | normal | 1 | 3 | verified |
| q050 | dev | list | 15.2 | table | 1 | 1 | verified |
| q051 | dev | fact | 104.2 | normal | 1 | 3 | verified |
| q052 | dev | summary | 12.0 | normal | 1 | 1 | verified |
| q053 | dev | notfound | 4.2 | table | 1 | 0 | not_found |
| q054 | dev | notfound | 3.1 | normal | 1 | 0 | not_found |
| q055 | dev | notfound | 4.8 | normal | 1 | 0 | not_found |
