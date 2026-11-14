# Scores: oracle qwen3.5 4B via Ollama, thinking disabled

30 questions; one question is worth: dev 5.0 points, heldout 10.0 points

- recall@5: 26/26 (100.0%) [answerable only]
- recall@10: 26/26 (100.0%) [answerable only]
- recall@30: 26/26 (100.0%) [answerable only]
- MRR: 1.0
- citation: 20/26 (76.9%)
- numeric: 23/24 (95.8%)
- notfound_a [dev]: 3/3 (100.0%)
- notfound_b: 26/26 (100.0%)
- passed: 23/30 (76.7%)

## By split

| split | n | recall@5 | MRR | citation | numeric | nf(a) | nf(b) | passed |
|---|---|---|---|---|---|---|---|---|
| dev | 20 | 17/17 | 1.0 | 14/17 | 16/16 | 3/3 | 17/17 | 17/20 |
| heldout | 10 | 9/9 | 1.0 | 6/9 | 7/8 | 1/1 | 9/9 | 6/10 |

| id | type | rank | cite | numeric | not-found | verdict |
|---|---|---|---|---|---|---|
| q001 | fact | 1 | ok | ok | ok | PASS |
| q002 | fact | 1 | ok | ok | ok | PASS |
| q003 | fact | 1 | ok | ok | ok | PASS |
| q004 | fact | 1 | ok | ok | ok | PASS |
| q005 | fact | 1 | ok | ok | ok | PASS |
| q006 | fact | 1 | ok | ok | ok | PASS |
| q007 | fact | 1 | ok | ok | ok | PASS |
| q008 | exact | 1 | ok | ok | ok | PASS |
| q009 | exact | 1 | ok | ok | ok | PASS |
| q010 | exact | 1 | ok | ok | ok | PASS |
| q011 | exact | 1 | FAIL | ok | ok | FAIL |
| q012 | exact | 1 | ok | ok | ok | PASS |
| q013 | summary | 1 | ok | n/a | ok | PASS |
| q014 | summary | 1 | ok | ok | ok | PASS |
| q015 | summary | 1 | FAIL | n/a | ok | FAIL |
| q016 | comparison | 1 | FAIL | ok | ok | FAIL |
| q017 | comparison | 1 | ok | ok | ok | PASS |
| q018 | comparison | 1 | ok | ok | ok | PASS |
| q019 | notfound | 1 | n/a | n/a | ok | PASS |
| q020 | notfound | 1 | n/a | n/a | ok | PASS |
| q021 | notfound | 1 | n/a | n/a | ok | PASS |
| q022 | notfound | 1 | n/a | n/a | ok | PASS |
| q023 | followup | 1 | ok | ok | ok | PASS |
| q024 | followup | 1 | FAIL | ok | ok | FAIL |
| q025 | table | 1 | ok | ok | ok | PASS |
| q026 | table | 1 | ok | ok | ok | PASS |
| q027 | table | 1 | ok | ok | ok | PASS |
| q028 | table | 1 | FAIL | ok | ok | FAIL |
| q029 | table | 1 | ok | FAIL | ok | FAIL |
| q030 | table | 1 | FAIL | ok | ok | FAIL |
