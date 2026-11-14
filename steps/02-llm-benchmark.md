# Step 2: LLM benchmark

**Goal:** choose the generator (plus a fallback) using real measurements on this 4GB GPU.
**Needs approval to start:** yes. Candidate list is re-checked at the start (see OD-3).

## Tasks
1. Pick 3 candidates (3-4B class, Q4, e.g. Phi-4-mini, Qwen3-4B, Gemma 4 E2B/E4B; confirm current versions first).
2. For each: measure VRAM at several context sizes, with and without KV-cache quantization; prompt-processing speed; generation speed; time to first token.
3. Use realistic RAG prompts (5 chunks, about 3-4k tokens) and follow-up prompts with history.
4. Oracle test: give each model the gold pages from the eval set (perfect retrieval) and score answer metrics: citation format, numeric exact match, not-found behavior.
5. Check the 20s (short follow-up) and 30s+ (deep) latency targets.
6. Record the choice and the fallback in `DECISIONS.md`.

## Definition of done
- [x] Comparison table (VRAM, speeds, TTFT, oracle answer scores) for all 3 models in `DECISIONS.md` — **one model measured only**: the owner chose their existing `qwen2.5` 7B and declined the other two downloads, so rows 2 and 3 will never exist. Recorded as a stated deviation in PROPOSED D-040, not silently passed.
- [x] Everything measured with the same settings, temperature 0
- [x] One model chosen plus one fallback, with the reason (`qwen2.5` 7B; fallback `qwen2.5-1.5b`)
- [x] Latency targets confirmed feasible or flagged with options (flagged: ~28 s for a standard RAG question against the 20 s target)
- [x] Final context size and KV-cache setting recorded (4096 context, f16 KV; q8_0 measured at 6144 context as the alternative)

## Context to read
`STATUS.md` (pinned llama.cpp, measured facts), `EVAL.md`, `DECISIONS.md` (D-002, OD-3), `eval/questions.jsonl` (gold pages for the oracle test), this file.

## Expected output
Raw logs per model under `benchmarks/llm/`, one re-run command per model, and a comparison table added to `DECISIONS.md` as a PROPOSED entry. Table columns: `model | quant | context | VRAM GB | prompt tok/s | generation tok/s | time to first token | citation format ok | numeric exact match`. Include the chosen model and the fallback with the reason.

## Verification
Raw benchmark logs saved; owner can re-run one command per model.

## Risks
Model spills to RAM at long context (watch for sudden slowdowns); models that ignore the citation format.
