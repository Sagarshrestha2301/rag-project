# Scores: oracle qwen3.5:4b via Ollama

30 questions; one question is worth: dev 5.0 points, heldout 10.0 points

- recall@5: 26/26 (100.0%) [answerable only]
- recall@10: 26/26 (100.0%) [answerable only]
- recall@30: 26/26 (100.0%) [answerable only]
- MRR: 1.0
- citation: 0/26 (0.0%)
- numeric: 0/24 (0.0%)
- notfound_a [dev]: 3/3 (100.0%)
- notfound_b: 0/26 (0.0%)
- passed: 4/30 (13.3%)

## By split

| split | n | recall@5 | MRR | citation | numeric | nf(a) | nf(b) | passed |
|---|---|---|---|---|---|---|---|---|
| dev | 20 | 17/17 | 1.0 | 0/17 | 0/16 | 3/3 | 0/17 | 3/20 |
| heldout | 10 | 9/9 | 1.0 | 0/9 | 0/8 | 1/1 | 0/9 | 1/10 |

| id | type | rank | cite | numeric | not-found | verdict |
|---|---|---|---|---|---|---|
| q001 | fact | 1 | FAIL | FAIL | FAIL | FAIL |
| q002 | fact | 1 | FAIL | FAIL | FAIL | FAIL |
| q003 | fact | 1 | FAIL | FAIL | FAIL | FAIL |
| q004 | fact | 1 | FAIL | FAIL | FAIL | FAIL |
| q005 | fact | 1 | FAIL | FAIL | FAIL | FAIL |
| q006 | fact | 1 | FAIL | FAIL | FAIL | FAIL |
| q007 | fact | 1 | FAIL | FAIL | FAIL | FAIL |
| q008 | exact | 1 | FAIL | FAIL | FAIL | FAIL |
| q009 | exact | 1 | FAIL | FAIL | FAIL | FAIL |
| q010 | exact | 1 | FAIL | FAIL | FAIL | FAIL |
| q011 | exact | 1 | FAIL | FAIL | FAIL | FAIL |
| q012 | exact | 1 | FAIL | FAIL | FAIL | FAIL |
| q013 | summary | 1 | FAIL | n/a | FAIL | FAIL |
| q014 | summary | 1 | FAIL | FAIL | FAIL | FAIL |
| q015 | summary | 1 | FAIL | n/a | FAIL | FAIL |
| q016 | comparison | 1 | FAIL | FAIL | FAIL | FAIL |
| q017 | comparison | 1 | FAIL | FAIL | FAIL | FAIL |
| q018 | comparison | 1 | FAIL | FAIL | FAIL | FAIL |
| q019 | notfound | 1 | n/a | n/a | ok | PASS |
| q020 | notfound | 1 | n/a | n/a | ok | PASS |
| q021 | notfound | 1 | n/a | n/a | ok | PASS |
| q022 | notfound | 1 | n/a | n/a | ok | PASS |
| q023 | followup | 1 | FAIL | FAIL | FAIL | FAIL |
| q024 | followup | 1 | FAIL | FAIL | FAIL | FAIL |
| q025 | table | 1 | FAIL | FAIL | FAIL | FAIL |
| q026 | table | 1 | FAIL | FAIL | FAIL | FAIL |
| q027 | table | 1 | FAIL | FAIL | FAIL | FAIL |
| q028 | table | 1 | FAIL | FAIL | FAIL | FAIL |
| q029 | table | 1 | FAIL | FAIL | FAIL | FAIL |
| q030 | table | 1 | FAIL | FAIL | FAIL | FAIL |
