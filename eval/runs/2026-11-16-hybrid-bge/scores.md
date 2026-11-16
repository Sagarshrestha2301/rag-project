# Hybrid retrieval: hybrid-bge

- Index: BM25 + bge-small dense over chunks, RRF k=60
- Corpus: 3226 chunks from the built chunk index
- Questions: 30 (26 answerable)
- Built and scored in 14.6 s

| metric | count | share |
|---|---|---|
| recall@5 | 18/26 | 69.2% |
| recall@10 | 25/26 | 96.2% |
| recall@30 | 26/26 | 100.0% |
| MRR | 0.464 | |

## Against the page-level BM25 baseline (eval\runs\2026-11-15-2026-11-14-97docs)

| metric | baseline | hybrid | delta |
|---|---|---|---|
| recall@5 | 25 | 18 | -7 |
| recall@10 | 25 | 25 | +0 |
| recall@30 | 25 | 26 | +1 |
| MRR | 0.885 | 0.464 | -0.421 |

Questions ranked better: **4**; worse: **17**.

| id | hybrid rank | baseline rank |
|---|---|---|
| q001 | 5 | 1 |
| q002 | 6 | 4 |
| q004 | 6 | 1 |
| q007 | 6 | 1 |
| q008 | 3 | 1 |
| q009 | 6 | 1 |
| q010 | 2 | 1 |
| q011 | 2 | 1 |
| q012 | 3 | 1 |
| q014 | 3 | 1 |
| q016 | 4 | 1 |
| q017 | 9 | 1 |
| q018 | 5 | 1 |
| q023 | 6 | 1 |
| q024 | 2 | 1 |
| q025 | 6 | 2 |
| q029 | 5 | 1 |

| id | hybrid first gold rank | page baseline rank |
|---|---|---|
| q001 | 5 | 1 |
| q002 | 6 | 4 |
| q003 | 1 | 1 |
| q004 | 6 | 1 |
| q005 | 2 | 4 |
| q006 | 1 | 1 |
| q007 | 6 | 1 |
| q008 | 3 | 1 |
| q009 | 6 | 1 |
| q010 | 2 | 1 |
| q011 | 2 | 1 |
| q012 | 3 | 1 |
| q013 | 1 | 1 |
| q014 | 3 | 1 |
| q015 | 11 | miss |
| q016 | 4 | 1 |
| q017 | 9 | 1 |
| q018 | 5 | 1 |
| q019 | 1 | 3 |
| q020 | 1 | 1 |
| q021 | 1 | 1 |
| q022 | 1 | 2 |
| q023 | 6 | 1 |
| q024 | 2 | 1 |
| q025 | 6 | 2 |
| q026 | 1 | 1 |
| q027 | 1 | 1 |
| q028 | 1 | 1 |
| q029 | 5 | 1 |
| q030 | 1 | 1 |
