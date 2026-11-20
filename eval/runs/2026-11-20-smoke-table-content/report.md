# Generation run: smoke-table-content

- Model: `qwen3.5:4b` (digest `d8b0f5e9760c`), prompt `s6-3`, temperature 0, num_ctx 4096, think False
- Corpus: **97 documents, 851 pages** (86 OCR pages)
- Questions: 13 (13 in the set), cache off

## End-to-end latency (seconds per question, retries and condense included)

| n | p50 | p95 | min | max | mean | over 20 s | over 30 s |
|---|---|---|---|---|---|---|---|
| 13 | 14.6 | 29.5 | 2.5 | 30.4 | 15.3 | 4 | 1 |

Target: about 20 s for a short follow-up, 30 s+ acceptable for a deep or long question. Measured p50 **14.6 s**, p95 **29.5 s**.

Slowest questions: `q041` 30.4 s, `q047` 28.9 s, `q025` 25.4 s. A single stalled question moves the mean, not the p50/p95.

## How the questions were handled

| | count |
|---|---|
| status `not_found` | 6 |
| status `unverified` | 3 |
| status `verified` | 4 |
| route `table` | 13 |
| attempts 1 | 6 |
| attempts 2 | 7 |

## Scores (from eval/score.py on the same run.jsonl)

- citation: 3/12
- numeric: 4/12
- not-found (a): 1/1
- not-found (b): 7/12
- passed: 3/13

| id | split | type | seconds | route | attempts | citations | status |
|---|---|---|---|---|---|---|---|
| q025 | dev | table | 25.4 | table | 2 | 1 | verified |
| q026 | dev | table | 2.7 | table | 1 | 0 | not_found |
| q027 | dev | table | 2.5 | table | 1 | 0 | not_found |
| q028 | dev | table | 22.0 | table | 2 | 0 | not_found |
| q029 | heldout | table | 18.5 | table | 2 | 0 | not_found |
| q030 | heldout | table | 11.7 | table | 2 | 0 | not_found |
| q031 | dev | number | 10.1 | table | 1 | 1 | verified |
| q041 | dev | exact | 30.4 | table | 2 | 3 | unverified |
| q042 | dev | fact | 8.6 | table | 1 | 1 | verified |
| q046 | dev | table | 18.8 | table | 2 | 1 | unverified |
| q047 | dev | table | 28.9 | table | 2 | 3 | unverified |
| q050 | dev | list | 14.6 | table | 1 | 1 | verified |
| q053 | dev | notfound | 4.2 | table | 1 | 0 | not_found |
