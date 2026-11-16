# Retrieval baseline: rebased-2026-11-16

- Corpus: **97 documents, 851 pages** (86 OCR pages, 8 files with unreadable pages)
- Questions: 55 (48 answerable, 7 not-found)
- Index: BM25 over pages, k=30 (`ui/retrieval.py`), question text only

| metric | count | share |
|---|---|---|
| recall@5 | 45/48 | 93.8% |
| recall@10 | 47/48 | 97.9% |
| recall@30 | 47/48 | 97.9% |
| MRR | 0.829 | |

| split | n | recall@5 | MRR |
|---|---|---|---|
| dev | 45 | 37/39 | 0.834 |
| heldout | 10 | 8/9 | 0.806 |

Gold page missed entirely by the top 30: **1** of 48 answerable questions.

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
| q031 | number | 1 |
| q032 | number | 1 |
| q033 | number | 1 |
| q034 | exact | 1 |
| q035 | number | 1 |
| q036 | list | 1 |
| q037 | number | 4 |
| q038 | comparison | 2 |
| q039 | exact | 1 |
| q040 | number | 1 |
| q041 | exact | 2 |
| q042 | fact | 1 |
| q043 | fact | 1 |
| q044 | fact | 1 |
| q045 | number | 8 |
| q046 | table | 6 |
| q047 | table | 4 |
| q048 | fact | 1 |
| q049 | fact | 2 |
| q050 | list | 1 |
| q051 | fact | 1 |
| q052 | summary | 2 |
| q053 | notfound | miss |
| q054 | notfound | miss |
| q055 | notfound | miss |

## Missed questions

- q015: What does the paper recommend about where equations (1) to (4) may be applied?
