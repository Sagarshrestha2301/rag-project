# The "not found" gate (Step 6, task 3)

**Decision: D-058.** The generator decides "not found"; retrieval contributes one cheap
floor that only catches degenerate retrieval. There is no score threshold, and this note
exists so that statement can be checked rather than believed.

Reproduce every number below with:

```powershell
.venv\Scripts\python.exe eval\calibrate_gate.py
.venv\Scripts\python.exe eval\calibrate_gate.py --floor 15
```

## Why a threshold cannot do this

`eval/calibrate_gate.py` reads the saved re-based run
(`eval/runs/2026-11-16-rebased-2026-11-16/retrieval.jsonl`) and prints how each candidate
floor would trade the two error types on the dev split — 39 answerable questions and 6
not-found ones:

| floor | not-found refused | answerable wrongly refused |
|---|---|---|
| 0–15 | 0/6 | 0/39 |
| 20 | 2/6 | 2/39 |
| 25 | 5/6 | 4/39 |
| **30** | **6/6** | **12/39** |
| 35 | 6/6 | 18/39 |
| 40 | 6/6 | 22/39 |
| 50 | 6/6 | 32/39 |

Answerable top-1 spans 18.43 to 80.52 (median 37.77); not-found spans 18.01 to 29.97. The
ranges overlap, and one not-found question (q019, 29.97) outranks a dozen answerable ones.
Any floor that catches the not-found questions therefore costs answerable questions, which
D-029 and D-034 forbid. Margin (top1−top2) and ratio (top1/top2) overlap the same way:
0.10–26.93 against 0.01–6.25, and 1.01–2.20 against 1.00–1.39.

The reason is in the questions, not the retriever: these not-found questions read like the
corpus — same journal, same vocabulary — so BM25 confidence carries no information about
whether the corpus can answer them.

## What is shipped

`generation/gate.py`, `FLOOR = 15.0`:

1. **Floor, before the model.** If the best passage scores below 15, the answer is the
   refusal and the model is never called. On the dev set this costs 0/39 answerable and
   refuses 0/6 not-found: it is a guard against empty or off-topic retrieval, not a
   judgement about content.
2. **Refusal, after the model.** Above the floor the model reads five passages and either
   answers with verified quotations or refuses in the exact words the prompt demands. A
   failed verification is reported as `unverified`, never as "not found", so a model that
   drifted cannot pass as a corpus that is silent.

## Four real outcomes (`artifacts/step6/gate-run.jsonl`)

`qwen3.5:4b`, thinking off, temperature 0, five passages, 2026-11-16:

| question | best score | model called | outcome | time |
|---|---|---|---|---|
| "hello there" | 3.56 | no | `not_found` (floor) | 0.22 s |
| "Who won the 2018 football World Cup?" | 10.68 | no | `not_found` (floor) | 0.00 s |
| "How many tractors were sold in Chitwan district in 2019?" | 15.38 | **yes** | `not_found` (the model refused) | 1.58 s |
| "What was the 24-hour rainfall depth at Tistung?" | 36.19 | yes | `verified` | 9.43 s |

The third row is the case the design turns on: a near-topic question that retrieval scores
just above the floor. The floor lets it through; the model reads the passages and refuses.
No floor that would have refused it on score alone could have kept the fourth row.

## Known limit

The gate judges quotations, not the numbers in the answer prose: a sentence can read
"720 mm [1]" while quoting "540 mm" from the page. That is `TODO(step-06)` in
`generation/verify.py`, and the numeric metric in `EVAL.md` is what catches it at eval
time. Until task 7 runs the eval, that metric is unmeasured for the generator.
