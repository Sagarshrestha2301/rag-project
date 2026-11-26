# Scores: step6-heldout

10 questions; one question is worth: dev 0.0 points, heldout 10.0 points

- recall@5: 8/9 (88.9%) [answerable only]
- recall@10: 8/9 (88.9%) [answerable only]
- recall@30: 8/9 (88.9%) [answerable only]
- MRR: 0.806
- citation: 7/9 (77.8%)
- numeric: 7/8 (87.5%)
- notfound_a [dev]: 0/0 (0.0%)
- notfound_b: 8/9 (88.9%)
- passed: 7/10 (70.0%)
- extra citations: 4 page(s) across 3 answer(s), max 2 (cap 2)

## By split

| split | n | recall@5 | MRR | citation | numeric | nf(a) | nf(b) | passed |
|---|---|---|---|---|---|---|---|---|
| dev | 0 | 0/0 | 0.0 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 |
| heldout | 10 | 8/9 | 0.806 | 7/9 | 7/8 | 1/1 | 8/9 | 7/10 |

| id | type | rank | cite | numeric | not-found | verdict |
|---|---|---|---|---|---|---|
| q005 | fact | 4 | ok | ok | ok | PASS |
| q007 | fact | 1 | ok | ok | ok | PASS |
| q010 | exact | 1 | ok | ok | ok | PASS |
| q012 | exact | 1 | ok | ok | ok | PASS |
| q015 | summary | - | FAIL | n/a | FAIL | FAIL |
| q018 | comparison | 1 | ok | ok | ok | PASS |
| q022 | notfound | 2 | n/a | n/a | ok | PASS |
| q024 | followup | 1 | ok | ok | ok | PASS |
| q029 | table | 1 | ok | FAIL | ok | FAIL |
| q030 | table | 1 | FAIL | ok | ok | FAIL |
