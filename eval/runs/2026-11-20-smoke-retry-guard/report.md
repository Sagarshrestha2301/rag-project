# Generation run: smoke-retry-guard

- Model: `qwen3.5:4b` (digest `d8b0f5e9760c`), prompt `s6-3`, temperature 0, num_ctx 4096, think False
- Corpus: **97 documents, 851 pages** (86 OCR pages)
- Questions: 4 (4 in the set), cache off

## End-to-end latency (seconds per question, retries and condense included)

| n | p50 | p95 | min | max | mean | over 20 s | over 30 s |
|---|---|---|---|---|---|---|---|
| 4 | 20.9 | 26.4 | 16.8 | 26.9 | 21.4 | 2 | 0 |

Target: about 20 s for a short follow-up, 30 s+ acceptable for a deep or long question. Measured p50 **20.9 s**, p95 **26.4 s**.

Slowest questions: `q027` 26.9 s, `q026` 23.3 s, `q028` 18.6 s. A single stalled question moves the mean, not the p50/p95.

## How the questions were handled

| | count |
|---|---|
| status `unverified` | 3 |
| status `verified` | 1 |
| route `table` | 4 |
| attempts 2 | 4 |

## Scores (from eval/score.py on the same run.jsonl)

- citation: 1/4
- numeric: 2/4
- not-found (a): 0/0
- not-found (b): 4/4
- passed: 1/4

| id | split | type | seconds | route | attempts | citations | status |
|---|---|---|---|---|---|---|---|
| q026 | dev | table | 23.3 | table | 2 | 0 | unverified |
| q027 | dev | table | 26.9 | table | 2 | 0 | unverified |
| q028 | dev | table | 18.6 | table | 2 | 0 | unverified |
| q047 | dev | table | 16.8 | table | 2 | 1 | verified |
