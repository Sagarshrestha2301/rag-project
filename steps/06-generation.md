# Step 6: Generation

**Goal:** grounded answers with verified citations, a reliable "not found", and chat handling.
**Needs approval to start:** yes.

## Tasks
1. Prompt that forces citations (file + page) and quotes; 4-6 chunks in context.
2. Quote verification in code: every quote must exist in the cited chunk or page; failed answers are retried once or marked unverified.
3. "Not found" gate on the reranker score; calibrate the threshold on the dev set, using the not-found questions.
4. Rule-based intent router: greeting/off-topic, follow-up, broad summary, table lookup, normal. Different retrieval and prompt settings per route.
5. Condense-question step only when chat history exists.
6. Answer cache keyed by normalized question + index version + model versions + prompt version.
7. Full eval on dev; held-out at the end (milestone).

## Definition of done
- [ ] Citation correctness, numeric exact match and not-found accuracy (a and b) recorded in `EVAL.md`
- [ ] Regression gate (as defined in `EVAL.md`) passes against the Step 5 baseline for retrieval metrics
- [ ] Offline run: full pipeline and eval pass with the network disabled (output recorded)
- [ ] Quote verification catches an injected fake quote (test with real output)
- [ ] Cache returns a hit for a repeated question and misses after an index or prompt version change (tested)
- [ ] Latency: about 20s short follow-up, 30s+ deep (p50 and p95 reported)
- [ ] Held-out result recorded

## Context to read
This file, `ARCHITECTURE.md` (query flow), `EVAL.md`, `DECISIONS.md` (D-010, D-017, D-029, D-034), the retrieval module from Step 5, the chosen LLM from Step 2.

## Expected output
Generation module (prompt, quote verifier, not-found gate, intent router, condense step, answer cache), eval rows in `EVAL.md`, and the threshold calibration notes. Answer format example: `<answer text> [1]` then `[1] <file>, p. 12: "<verified quote>"`. Not-found example: `Not found in the indexed documents.` followed by the unreadable-pages hint when it applies.

## Verification
Owner reads 10 answers with their citations and checks them against the PDF pages.

## Risks
Threshold trades false "not found" against hallucination; small model ignoring format; condense step changing the meaning of a question.
