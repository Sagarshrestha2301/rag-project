# Scorer specification (Step 1, task 6)

Implements the metrics defined in `EVAL.md`. Written before any retrieval or generation code exists, so the metrics are fixed before results can influence them.

## Inputs

- `eval/questions.jsonl` — the frozen question set.
- A **run file**: one JSON object per question, produced by whatever ran (retrieval only, or full pipeline):

```json
{"id": "q001",
 "retrieved": [{"file": "data/corpus/<name>.pdf", "page": 2, "score": 0.83}, ...],
 "answer": "540 mm",
 "citations": [{"file": "data/corpus/<name>.pdf", "page": 2, "quote": "..."}],
 "said_not_found": false,
 "timings": {"retrieve_s": 0.4, "rerank_s": 0.2, "generate_s": 1.1}}
```

- `eval/source_documents.md` — the corpus files and their pinned SHA-256.

## Integrity check (must run first, must stop the run)

For every distinct file in `gold_sources` **and** every file in the run's `retrieved`/`citations`:

1. The path must resolve inside `data/corpus/`.
2. Its SHA-256 must equal the recorded hash.
3. If a file is missing or the hash differs, print the expected/actual pair and **exit non-zero without writing results**.

This is what catches a re-converted Word file silently shifting pages (D-023, D-030).

## Metrics

All are reported as a **count and a percentage** (`17/20`, `85%`), never a percentage alone.

**Retrieval**
- `recall@k` for k = 5, 10, 30: a question passes if at least one gold `(file, page)` appears in the top k retrieved items. For `summary` and `comparison` questions with several gold sources, the value is the fraction of gold sources found and the question passes at `>= 0.5`.
- `MRR`: reciprocal rank of the first retrieved `(file, page)` that is a gold source; `0` if none.

**Answer**
- `citation_correct` **(changed 2026-11-26, D-097, step 18)**: **at least one** cited `(file, page)` is in `gold_sources`, **every** cited quote exists in the parsed text of the page it names after whitespace normalisation, and **at most two** cited pages lie outside `gold_sources` (`MAX_EXTRA_CITATIONS` in `eval/score.py`). A run with no citations, or with no gold page among them, fails.

  `extra_citations` records how many cited pages were outside the gold set — per question, and per set as a total, a maximum and a count of answers with any. It is a diagnostic, not a penalty: it keeps citation padding visible now that a padded answer can still pass.

  **The gold-page clause was relaxed on 2026-11-26** because five questions failed with every quotation verbatim on the page it named, only because a second cited page was not in the gold set (`reports/citation-contract-rescore-2026-11-26.md`). The quote check is still strict and still applies to every cited page; the cap of two and the counter are the safeguards the owner accepted (D-097).

  **Matching is strict, by the owner's decision (2026-11-13, D-041).** Surrounding quotation marks are *not* stripped and a hyphen the PDF split across a line (`East- Rapti`) is *not* joined, so both count as failures. Do not "fix" this in a later step: on the `qwen2.5` oracle run the strict rule scores citations 14/26 against 19/26 for the lenient one, and the stricter number is the one the project agreed to track. The fix belongs in the Step 6 prompt, which must return unquoted verbatim sentences.
- `numeric_exact`: after normalisation (strip thousands separators, unify `m3/s` / `m3 s-1` / `m³ s⁻¹`, unify `mm h-1` / `mm/h` / `mm per hour`), every gold number appears with the same value; units must match after the same normalisation.
- `not_found_a`: on `answerable: false` questions, the run said "not found" (or returned no answer). Reported on the dev set; zero tolerance in the gate (`EVAL.md`, D-029, D-034).
- `not_found_b`: on `answerable: true` questions, the run did **not** falsely say "not found".

**Secondary, never a gate**
- `faithfulness` from a local LLM judge.
- Latency p50/p95 per stage and end to end.

## Point values

One question is worth `100 / N` points for the set being scored. With the current set: dev N=20 → 5 points per question; held-out N=10 → 10. Not-found (a) on dev rests on 3 questions, so one flip is 33 points — which is why it has zero tolerance.

## Which questions a metric counts

`recall@k`, `MRR` and `citation_correct` are scored on **answerable questions only**. A not-found question has no page that has to be retrieved and nothing to cite, so scoring it there would fail every run by construction. Not-found questions are covered by `not_found_a` alone.

`numeric_exact` counts only questions that have gold numbers. Units are required for physical measures (`mm`, `m3/s`, `km2`, `mm/h`) but not for counts, years or coefficients, where the prose legitimately says `households`, `growers` or nothing at all.

Every metric is also reported **per split** (dev / held-out), because the gate uses dev and the held-out figure is the honest one.

## Output

- Per-question table: `id`, type, `answerable`, recall@{5,10,30}, rank, citation ok, numeric ok, said-not-found, verdict.
- Summary line per metric with counts and percentages.
- A **per-question diff** against a named baseline (`--baseline <run.json>`): lists pass→fail and fail→pass questions explicitly. The gate needs this list, not just totals.
- Written to `eval/runs/<date>-<label>/scores.json` and `scores.md`.

## Fake-output test (task 7, runs before real results exist)

The scorer is tested on three hand-made run files against `eval/questions.jsonl`:

| Fixture | Expected |
|---|---|
| `perfect` — gold answer, correct citation and quote on every question | 30/30 pass, recall 26/26, MRR 1.0, citation 26/26, numeric 24/24, not-found (a) dev 3/3, (b) 26/26 |
| `empty` — no retrieval, no answer, says "not found" everywhere | 4/30 pass, retrieval 0, not-found (a) dev 3/3, (b) 0/26 |
| `partial` — correct on the first half, wrong page and wrong number on the rest | 15/30 pass; the diff against `perfect` lists exactly q016-q030 as pass→fail |

Plus two integrity fixtures: a run file citing a corpus path whose hash is wrong, and one citing a path outside `data/corpus/`. Both must exit non-zero.

## Not in this spec

- Chunking, k-selection and reranker depth are retrieval parameters, not metrics; they are tuned in Step 5 against this scorer.
- The judge prompt for faithfulness is written in Step 6, when a generator exists.
