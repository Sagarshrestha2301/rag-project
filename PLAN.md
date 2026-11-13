# Plan

Rule: one step at a time. A step starts only after the owner approves it. A step is done only when its definition of done is verified and the owner approves.

| # | Step | Output | Depends on |
|---|---|---|---|
| 0 | Environment check (GPU, CUDA, llama.cpp) | env report, pinned versions | docs approved |
| 1 | Eval set (30 questions) + scoring spec | `eval/questions.jsonl`, metrics | 0 |
| 2 | LLM benchmark (3 candidates) | chosen model + fallback, latency numbers | 0, 1 |
| 3 | Parsing sample (50 docs) | parsed pages, table-quality report, speed per page | 1 (sample includes eval source docs) |
| 4 | Chunking, metadata, embeddings | chunker, embedder chosen on eval | 1, 3 |
| 5 | Hybrid retrieval + reranker + parent context | retrieval baseline (recall@k, MRR) | 4 |
| 6 | Generation: citations, not-found gate, router, condense, cache | answer metrics | 2, 5 |
| 7 | Web UI | streaming chat, PDF click-through, debug view | 6 |
| 8 | Full ingestion | 100k pages indexed, eval re-run at scale | 7 |
| 9 | Tuning and docs | final docs, runbook | 8 |

Details: `steps/NN-name.md`.

## Gates
- Order: the owner creates the git repository and first commit (`OWNER: initial docs`), then records the docs approval, then the Step 0 start approval (see `APPROVALS.md`). After that each step needs its own start and completion approval.
- Regression gate (see `EVAL.md`): a change is accepted only with no unexplained pass-to-fail question and no metric dropping by more than one question, measured against the last accepted baseline and the start-of-step baseline; not-found (a) must not drop at all.
- Eval re-run is required at the end of Steps 5, 6 and 8, each with an offline proof run (network disabled).
- Approvals are written only by the owner, in `APPROVALS.md` (start approval and completion approval), and the owner alone creates the git tag `step-NN-approved`. Agents never write or tag them.
- Before a completion approval the owner runs the tamper checks in `APPROVALS.md`: owner-only files show only `OWNER:` commits; agent-editable protected files show only appended rows, PROPOSED entries and ticked boxes; `git tag` lists only the owner's tags.
- Protected files are owner-only edits (see `AGENTS.md` rule 13). The owner commits their own edits first (`OWNER:` message) so agents never see a dirty tree.

## Experiments backlog and rejected items
See `ARCHITECTURE.md`.
