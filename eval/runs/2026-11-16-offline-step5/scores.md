# Retrieval baseline: offline-step5

- Corpus: **97 documents, 851 pages** (86 OCR pages, 8 files with unreadable pages)
- Questions: 30 (26 answerable, 4 not-found)
- Index: BM25 over pages, k=30 (`ui/retrieval.py`), question text only

| metric | count | share |
|---|---|---|
| recall@5 | 25/26 | 96.2% |
| recall@10 | 25/26 | 96.2% |
| recall@30 | 25/26 | 96.2% |
| MRR | 0.885 | |

| split | n | recall@5 | MRR |
|---|---|---|---|
| dev | 20 | 17/17 | 0.926 |
| heldout | 10 | 8/9 | 0.806 |

Gold page missed entirely by the top 30: **1** of 26 answerable questions.

| id | type | first gold rank |
|---|---|---|
| q001 | fact | 1 |
| q002 | fact | 4 |
| q003 | fact | 1 |
| q004 | fact | 1 |
| q005 | fact | 4 |
| q006 | fact | 1 |
| q007 | fact | 1 |
| q008 | exact | 1 |
| q009 | exact | 1 |
| q010 | exact | 1 |
| q011 | exact | 1 |
| q012 | exact | 1 |
| q013 | summary | 1 |
| q014 | summary | 1 |
| q015 | summary | miss |
| q016 | comparison | 1 |
| q017 | comparison | 1 |
| q018 | comparison | 1 |
| q019 | notfound | 3 |
| q020 | notfound | 1 |
| q021 | notfound | 1 |
| q022 | notfound | 2 |
| q023 | followup | 1 |
| q024 | followup | 1 |
| q025 | table | 2 |
| q026 | table | 1 |
| q027 | table | 1 |
| q028 | table | 1 |
| q029 | table | 1 |
| q030 | table | 1 |

## Missed questions

- q015: What does the paper recommend about where equations (1) to (4) may be applied?
