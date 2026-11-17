# Step 7: Web UI

**Goal:** simple local chat UI that shows sources and lets the owner inspect what happened.
**Needs approval to start:** yes.

## Tasks
0. UI spec first (no UI code before the owner approves it): one page with the layout (chat area, sources panel, debug view), the font and the color palette. Proposed defaults: system fonts, one accent color, light and dark themes, large readable text.
1. Local web app bound to localhost only; no external requests (no CDN fonts or scripts).
2. Chat with streaming tokens and conversation history.
3. Citations shown as links; click opens the cited PDF at that page (served locally).
4. Debug view: route chosen, retrieved chunks with scores, reranker scores, verification result, per-stage timings.
5. Clear states for "not found", "unverified quote" and errors.
6. On "not found", show a warning about unreadable pages (D-021): the total count in the corpus, and the count per document for the top retrieved documents, e.g. "this document has N unreadable pages". Data comes from the manifest.
7. Code rules for the UI: BEM class names (`block__element--modifier`), one shared event handler per event type (event delegation), shared helper functions, no duplicated handlers (see `AGENTS.md`, Code rules).

## Definition of done
- [ ] UI spec approved by the owner before any UI code
- [ ] UI code follows the BEM and shared-handler rules (a search finds no duplicated handlers)
- [ ] Works with the network disabled (tested with Wi-Fi off)
- [ ] Citation click opens the right PDF page for 10 tested answers
- [ ] Debug view shows chunks, scores and timings
- [ ] A "not found" answer shows the unreadable-pages warning with correct counts (tested on a document with known unreadable pages)
- [ ] Server not reachable from another machine on the network
- [ ] Eval results unchanged by the UI (the UI only calls the pipeline)

## Context to read
This file, `REQUIREMENTS.md` (F1, F5, F6, N6), `DECISIONS.md` (D-020, D-021, D-036), `ARCHITECTURE.md`, the pipeline interface from Step 6, `AGENTS.md` (Code rules).

## Expected output
The approved UI spec, the UI under `src/ui/`, and a short test log (network off, citation click, debug view, not-found warning). Citation link example: `/pdf/<file>#page=12` opens the cited page of the stored corpus PDF.

## Verification
Owner runs a 5-question session including 2 follow-ups.

## Risks
Streaming stalling during long prompt processing; page links wrong for converted Word files.
