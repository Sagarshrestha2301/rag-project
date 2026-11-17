# Step 7 UI spec — approved

Approved by the owner on 2026-11-17 using the recommended defaults in section 12. This
spec records UI decisions not already defined by `AGENTS.md`, `steps/07-web-ui.md`, or
`DECISIONS.md`. The implementation stays in `ui/`; existing route and static-asset paths
remain in place.

## Surface and answer path

- One local browser app, served by FastAPI at `127.0.0.1:8000`; no external requests.
- Keep `ui/server.py`, `ui/static/index.html`, `ui/static/app.css`, and
  `ui/static/app.js`. Preserve `/`, `/static`, `/api/health`, `/api/docs`, `/api/chat`,
  `/api/config`, and `/pdf/{name}`. PDF links keep the form
  `/pdf/<file>#page=<page>` and resolve only inside `data/corpus/`.
- Every answer uses `generation.answer`; the UI does not create another prompt,
  retrieval, gate, verifier, or retry path.
- **Streaming mechanism:** Step 7 task 2 will add an optional token callback to
  `generation.answer`. `_ask` will stream Ollama output through the shared think filter
  and call it as visible tokens arrive. Before a verifier retry, a reset callback will
  tell the client to replace the first attempt. The returned record still contains the
  final answer and verification result. `eval/run_generation.py` will call this same
  `generation.answer` implementation without callbacks, so the evaluated pipeline is
  the one the UI uses.
- Conversation history is passed to `generation.answer`; its existing router decides
  whether to condense a follow-up. Cache hits, greetings, and gate refusals may finish
  without model tokens and are sent as complete results.

## Approved presentation

- Three areas: conversation list, chat, and an evidence rail with Sources and Debug tabs.
  The rail is open above 1280px, closed below that, and its preference is remembered.
  Below 1080px it becomes a bottom sheet; below 760px the conversation list is a drawer.
- Light and dark themes; system fonts only:
  `"Segoe UI", ui-sans-serif, system-ui, -apple-system, sans-serif`, with a monospace
  stack for quotes and debug data.
- Keep terracotta as the only interactive accent (`#b4603a` light, `#d98b62` dark).
  State colours are separate and never the sole indicator: verified green, warning
  amber, not-found blue, and error red. Each state also has a label and glyph.
- The five answer states are `streaming`, `verified`, `not_found`, `unverified`, and
  `error`. A failed streamed answer is replaced on retry; if the final attempt remains
  unverified, show it marked as retracted with its verification problems. A greeting
  uses the verified presentation without sources; a cache hit skips the streaming state.
- Citation numbers use the answer's source mapping; legacy letter markers display as
  numbers without changing the model-facing citation keys. Only cited sources appear.
  Clicking a number reveals the quotation for that citation, with a link to the stored
  corpus PDF at its physical page. A not-found answer shows the D-021 unreadable-page
  counts from the index: corpus totals and counts for retrieved documents with unreadable
  pages.

## Debug contract

The `done` event carries `debug_version: 1` with the pipeline status, cache flag,
question and condensed search question, route, model and prompt version, retrieved
passages and scores, gate decision, verification citations/problems/attempts, stage
timings, token counts, unreadable-page counts, and the same sources used by citation
links. `rerank_score` is `null` until a reranker exists. Timings are collected in
`generation.answer`, not duplicated in the UI.

## Section 12 — owner-approved defaults

Keep the code in `ui/`; add stage timings to the `generation.answer` record; stream
tokens and replace failed attempts; keep the terracotta accent; put Debug beside Sources
in the evidence rail; and open that rail only on screens wider than 1280px, remembering
the user's choice.
