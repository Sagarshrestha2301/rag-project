# Scores: run

55 questions; one question is worth: dev 2.22 points, heldout 10.0 points

- recall@5: 44/48 (91.7%) [answerable only]
- recall@10: 45/48 (93.8%) [answerable only]
- recall@30: 45/48 (93.8%) [answerable only]
- MRR: 0.769
- citation: 35/48 (72.9%)
- numeric: 36/43 (83.7%)
- notfound_a [dev]: 3/6 (50.0%)
- notfound_b: 43/48 (89.6%)
- passed: 37/55 (67.3%)

## By split

| split | n | recall@5 | MRR | citation | numeric | nf(a) | nf(b) | passed |
|---|---|---|---|---|---|---|---|---|
| dev | 45 | 36/39 | 0.797 | 28/39 | 29/35 | 3/6 | 35/39 | 30/45 |
| heldout | 10 | 8/9 | 0.648 | 7/9 | 7/8 | 1/1 | 8/9 | 7/10 |

| id | type | rank | cite | numeric | not-found | verdict |
|---|---|---|---|---|---|---|
| q001 | fact | 1 | ok | ok | ok | PASS |
| q002 | fact | 2 | FAIL | ok | ok | FAIL |
| q003 | fact | 5 | ok | ok | ok | PASS |
| q004 | fact | 1 | ok | ok | ok | PASS |
| q005 | fact | 4 | ok | ok | ok | PASS |
| q006 | fact | 1 | ok | ok | ok | PASS |
| q007 | fact | 1 | ok | ok | ok | PASS |
| q008 | exact | 1 | ok | ok | ok | PASS |
| q009 | exact | 1 | ok | ok | ok | PASS |
| q010 | exact | 3 | ok | ok | ok | PASS |
| q011 | exact | 1 | ok | ok | ok | PASS |
| q012 | exact | 1 | ok | ok | ok | PASS |
| q013 | summary | 1 | ok | n/a | ok | PASS |
| q014 | summary | 1 | ok | ok | ok | PASS |
| q015 | summary | - | FAIL | n/a | FAIL | FAIL |
| q016 | comparison | 1 | ok | ok | ok | PASS |
| q017 | comparison | 1 | ok | ok | ok | PASS |
| q018 | comparison | 1 | ok | ok | ok | PASS |
| q019 | notfound | - | n/a | n/a | ok | PASS |
| q020 | notfound | 1 | n/a | n/a | FAIL | FAIL |
| q021 | notfound | - | n/a | n/a | FAIL | FAIL |
| q022 | notfound | 3 | n/a | n/a | ok | PASS |
| q023 | followup | 1 | ok | ok | ok | PASS |
| q024 | followup | 1 | ok | ok | ok | PASS |
| q025 | table | - | FAIL | FAIL | FAIL | FAIL |
| q026 | table | 3 | FAIL | FAIL | FAIL | FAIL |
| q027 | table | 2 | FAIL | FAIL | FAIL | FAIL |
| q028 | table | 1 | FAIL | ok | ok | FAIL |
| q029 | table | 1 | ok | FAIL | ok | FAIL |
| q030 | table | 4 | FAIL | ok | ok | FAIL |
| q031 | number | 1 | ok | ok | ok | PASS |
| q032 | number | 1 | ok | ok | ok | PASS |
| q033 | number | 1 | ok | ok | ok | PASS |
| q034 | exact | 1 | ok | ok | ok | PASS |
| q035 | number | 2 | ok | ok | ok | PASS |
| q036 | list | 5 | FAIL | FAIL | FAIL | FAIL |
| q037 | number | 5 | ok | ok | ok | PASS |
| q038 | comparison | 1 | ok | ok | ok | PASS |
| q039 | exact | 1 | FAIL | ok | ok | FAIL |
| q040 | number | 1 | ok | ok | ok | PASS |
| q041 | exact | 1 | ok | ok | ok | PASS |
| q042 | fact | 1 | ok | FAIL | ok | FAIL |
| q043 | fact | 1 | ok | n/a | ok | PASS |
| q044 | fact | 1 | ok | n/a | ok | PASS |
| q045 | number | 1 | ok | ok | ok | PASS |
| q046 | table | 6 | FAIL | ok | ok | FAIL |
| q047 | table | - | FAIL | FAIL | ok | FAIL |
| q048 | fact | 1 | FAIL | n/a | ok | FAIL |
| q049 | fact | 2 | FAIL | ok | ok | FAIL |
| q050 | list | 1 | ok | ok | ok | PASS |
| q051 | fact | 1 | ok | ok | ok | PASS |
| q052 | summary | 1 | ok | ok | ok | PASS |
| q053 | notfound | - | n/a | n/a | ok | PASS |
| q054 | notfound | - | n/a | n/a | ok | PASS |
| q055 | notfound | - | n/a | n/a | FAIL | FAIL |
