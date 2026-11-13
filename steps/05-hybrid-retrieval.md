# Step 5: Hybrid retrieval, reranker, parent context

**Goal:** the best retrieval we can measure: LanceDB dense + BM25 with RRF, CPU reranker, small-to-big.
**Needs approval to start:** yes.

## Tasks
1. LanceDB table with vectors and a BM25 full-text index; RRF fusion.
2. CPU cross-encoder reranker on top 30-50 candidates; tune the candidate count on the dev set.
3. Small-to-big: return the parent section for the best chunks within the context budget.
4. Ablation: dense only, BM25 only, hybrid, hybrid + reranker, + parent context. Metrics for each.
5. Per-stage latency on CPU.
6. Add the failures found so far as new dev questions (owner-approved) so dev reaches about 50-60, and re-baseline (see `EVAL.md`).
7. Run the eval on dev, then held-out (milestone). Lock the baseline.
8. Offline proof: run the retrieval eval once with the network disabled.

## Definition of done
- [ ] Ablation table in `EVAL.md` (recall@5/10/30, MRR for each configuration)
- [ ] Final configuration beats or equals every simpler one on dev (otherwise keep the simpler one)
- [ ] Retrieval latency per stage recorded and within budget
- [ ] Dev set grown toward 50-60 questions, all owner-approved, new baseline logged
- [ ] Held-out result recorded
- [ ] Offline run: pass (network disabled, output recorded)
- [ ] Baseline locked for the regression gate

## Context to read
This file, `EVAL.md` (metrics and regression gate), `DECISIONS.md` (D-003, D-004, D-029), `ARCHITECTURE.md` (query flow), the chunk index from Step 4.

## Expected output
Retrieval module (hybrid search, reranker, parent context) behind the common interface, an ablation table appended to the `EVAL.md` results, a per-question diff file in `eval/runs/<date>-<label>/`, and the locked baseline with its commit id. Ablation rows: `dense | bm25 | hybrid | hybrid+rerank | hybrid+rerank+parent`, each with recall@5/10/30 and MRR.

## Verification
Per-question diff versus the dense-only baseline shown; owner reviews failures.

## Risks
Reranker too slow on CPU; table chunks ranking low for numeric questions; overfitting to the 20 dev questions.
