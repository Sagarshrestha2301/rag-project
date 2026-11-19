# Step 7 UI spec — proposed, awaiting owner approval

Written 2026-11-17 by the coding agent at the owner's instruction, before any Step 7 UI
code. It replaces the prototype's own prompt path with the pipeline `eval/` measures.

Sources: `steps/07-web-ui.md`, `REQUIREMENTS.md` (F1, F5, F6, N6), `DECISIONS.md`
(D-020, D-021, D-036), `ARCHITECTURE.md`, and the record that `generation/answer.py`
returns today.

**No UI code is written until the owner approves this document.** Section 12 lists the
six choices that need a verdict; each has a recommended default, so "approve all
recommended" is a complete answer.

---

## 1. What the UI is

One page in the local browser, served from `127.0.0.1` by a FastAPI process. Static
HTML, one CSS file, one JS file, no build step, no framework, no external request of any
kind. The server is the only component that talks to Ollama.

Every answer comes from `generation.answer`: router, condensation, cache, retrieval,
gate, prompt, verifier and the retry are the shipped Step 6 code, not a second copy.
The UI adds a streaming wrapper and a debug payload, and nothing else that could change
what the eval scores.

Not in scope: accounts or multi-user access (out of scope in `REQUIREMENTS.md`),
document upload (Step 8), corpus or index editing, non-English documents, mobile-native
layouts.

## 2. Where the code lives

Proposal: keep `ui/`, do not create `src/ui/`. `DECISIONS.md` D-043 already records a
working UI in `ui/`, the repository's code sits in top-level packages (`corpus.py`,
`generation/`, `ingest/`, `eval/`) and not under `src/`, and copying or moving the
prototype would leave two chat screens in the tree. The step text says `src/ui/`; a
move is possible in one commit if the owner prefers it (question 1 in section 12).

| File | Role |
|---|---|
| `ui/server.py` | FastAPI app, routes, localhost binding, static files, PDF serving |
| `ui/pipeline.py` | streaming wrapper around `generation.answer` (route → search → gate → prompt → stream → verify → retry → debug); the stream is the same call, via `on_token`, not a second prompt path |
| `ui/static/index.html` | the page shell |
| `ui/static/app.css` | all styling, both themes |
| `ui/static/step7.css` | Step 7 components (evidence rail, five states, unreadable warning, debug view); loaded after `app.css` so the working layout rules are untouched |
| `ui/static/app.js` | rendering, streaming client, event delegation |
| `ui/test_pipeline.py` | payload, D-021 counts and event order, with the model stubbed |
| `ui/test_server.py` | routes, CSP, PDF resolution and the chat stream, with the model stubbed |
| `ui/SPEC.md` | this document |

## 3. Layout

Three columns on a wide screen, collapsing to one on a narrow one. Nothing scrolls
sideways; the thread and the evidence rail scroll independently.

```
┌──────────────┬───────────────────────────────────────┬───────────────────────────┐
│ .sidebar     │ .chat                                 │ .evidence                 │
│              │                                       │                           │
│ Local RAG    │ .chat__header                         │ [Sources] [Debug]         │
│ + New chat   │  chat title · health dot · Save chat   │                           │
│              │                                       │ .source  [1]              │
│ ▸ 2026-11-17 │ .thread                               │  label · page 3 · 18.4    │
│   floods     │  .message--user     "Compare the…"    │  "snippet…"  Open PDF     │
│ ▸ 2026-11-16 │  .message--assistant                  │                           │
│   rainfall   │   .message__meta  qwen3.5:4b · 8.6 s  │ .source  [2]              │
│              │   .message__state verified · 2 quotes │  …                        │
│              │   .message__body   answer + [1] [2]   │                           │
│              │   .message__actions  Copy Regenerate  │                           │
│              │                                       │                           │
│ .sidebar__   │ .composer                             │ (Debug tab shows the      │
│  footer      │  textarea · Send                      │  JSON tree of §7)         │
└──────────────┴───────────────────────────────────────┴───────────────────────────┘
```

Grid: `264px | minmax(0, 1fr) | 360px`. The sidebar collapses to `0` exactly as it does
today (`.app--collapsed`). The evidence rail collapses to `0` too
(`.chat--evidence-hidden`), toggled from the header and remembered per browser.

Below 1080px the evidence rail stops being a column and becomes a bottom sheet over the
thread (`.evidence--sheet`), with the same two tabs; below 760px the sidebar is an
overlay drawer. The layout never drops a control — every action stays reachable.

BEM blocks: `.sidebar`, `.chat`, `.thread`, `.message`, `.composer`, `.evidence`,
`.source`, `.debug`, `.state-badge`, `.unreadable-warning`, `.empty`. Elements and
modifiers follow `block__element--modifier` exactly; no bare utility classes.

## 4. Palette

Two themes on `html[data-theme]`, defaulting to the operating system's preference and
switchable from the sidebar footer (as today). The tokens below are the current values
plus five new state colours; the accent stays terracotta.

| Token | Light | Dark | Used for |
|---|---|---|---|
| `--bg` | `#ffffff` | `#17181a` | page |
| `--bg-soft` | `#f6f7f8` | `#1e1f22` | rails, headers |
| `--bg-raised` | `#ffffff` | `#202124` | cards, evidence |
| `--ink` | `#1c1c1e` | `#edeeef` | body text |
| `--ink-soft` | `#5f6368` | `#a8adb5` | secondary text |
| `--ink-faint` | `#8a8f98` | `#787e87` | meta only, never body |
| `--line` | `#e6e7ea` | `#2c2e33` | borders |
| `--line-strong` | `#d3d6db` | `#3a3d43` | focus, active tab |
| `--accent` | `#b4603a` | `#d98b62` | links, active tab, send |
| `--accent-soft` | `#f7ede7` | `#2a2119` | citation chip background |
| `--state-ok` | `#2e7d4f` | `#74c69d` | verified |
| `--state-warn` | `#9a6b1f` | `#e0b062` | unverified / retracted |
| `--state-info` | `#3d5a80` | `#9db4d0` | not found |
| `--state-bad` | `#b3261e` | `#f28b82` | error |

Rules:

- One accent, and it means "interactive": links, chips, the active tab, the send button.
  State colours never decorate anything but a state badge and its 3px left border.
- Colour is never the only signal. Every state also carries a word and a glyph
  (`✓ verified`, `! unverified`, `∅ not found`, `× error`, `… streaming`), so the view
  survives colour blindness and a greyscale screenshot.
- Contrast is measured during implementation, not assumed here: every text/background
  pair is run through a contrast checker and the ratios are recorded in `STATUS.md`.
  `--ink-faint` is only ever used at 12.5px for meta text, never for an answer or a
  citation.
- Unreadable-page warnings (D-021) use `--state-info`, not red: nothing failed, the
  corpus cannot read part of a page.

## 5. Typography

System fonts only. A webfont would be an external request and break N1 offline
enforcement, so the stack is what Windows already has.

```
--font: "Segoe UI", ui-sans-serif, system-ui, -apple-system, sans-serif;
--mono: "Cascadia Mono", Consolas, ui-monospace, monospace;
```

| Role | Size / line-height | Weight | Notes |
|---|---|---|---|
| Answer body | 15px / 1.65 | 400 | max measure 72ch, never justified |
| User message | 15px / 1.55 | 400 | in the soft bubble, as today |
| Chat title (h1) | 22px / 1.25 | 600 | one per page |
| Section heading in an answer (h2/h3) | 17px / 1.4 | 600 | from the model's `##`/`###` |
| Meta line, timings | 12.5px / 1.4 | 400 | `--ink-faint` |
| Citation chip, state badge | 12px / 1 | 600 | tabular numbers |
| Quote in the sources rail | 13px / 1.5 | 400 | mono, page text verbatim |
| Debug JSON | 13px / 1.5 | 400 | mono, 2-space indent |

Paragraph spacing 0.75em, lists inherit the body size, code blocks `--code-bg` at 13px.
Numbers in scores and timings use `font-variant-numeric: tabular-nums`, so a column of
scores lines up.

## 6. The five answer states

One `data-state` attribute on `.message--assistant` drives everything; no state is
inferred from text. The mapping from the pipeline's `status` field is exact, and each
state is also reachable from the client's own failures.

| # | `data-state` | When | The reader sees | Controls |
|---|---|---|---|---|
| 1 | `streaming` | after the server's `start` event, before verification | tokens appearing in the body, a caret, meta line with model and elapsed time; **no citation chips yet**; badge `… streaming` | Stop (replaces Send); Copy/Regenerate disabled |
| 2 | `verified` | `done` event with `status: "verified"` | the answer, numbered chips `[1] [2]` linking to the PDF page, badge `✓ verified · 2 quotes`, meta `8.6 s · 14.4 tok/s · 1818 prompt`, sources rail filled, Debug tab enabled | Copy, Regenerate, every chip |
| 3 | `not_found` | `status: "not_found"` (gate refusal before the model, or the model's refusal) | the refusal sentence in the body, badge `∅ not found`, then `.unreadable-warning` with the D-021 counts (§7.3); sources rail shows the passages that were offered with their scores and the gate's reason | Copy, Regenerate; no chips |
| 4 | `unverified` | `status: "unverified"` — the text was streamed, then the verifier failed it after the one retry | the streamed text stays visible but marked: 3px `--state-warn` left border, body at `--ink-soft`, badge `! unverified — retracted`, one line "Retracted: <first problem>", the full problem list, chips shown but disabled | Copy (with a warning in the label), Regenerate (primary) |
| 5 | `error` | transport or server failure: Ollama unreachable, non-200, timeout, empty stream, malformed event | badge `× error`, the message, no sources, Debug tab shows the error object | Retry |

Two more pipeline outcomes need a rule, and neither is a sixth state:

- **`greeting`** (`status: "greeting"`, no model call, no passages): rendered with the
  `verified` layout but no chips, no sources and the badge `no lookup`.
- **cache hit** (`cached: true`): there is nothing to stream, so the message goes from
  nothing to `verified`/`not_found` in one step, with `cached` in the meta line. The
  `streaming` state is never shown for a cache hit.

Transitions: `streaming → verified | unverified | not_found | error`, and `unverified →
streaming` on Regenerate. A message never changes state twice except through
Regenerate. `aria-live="polite"` on `.thread` announces the state word once when it
changes, not on every token; the streaming caret is `aria-hidden`.

The retraction rule in state 4 is a deliberate choice, and question 3 in §12 is its
verdict: F1 asks for streaming, so the text arrives before it is verified, and the
verifier's failure then retracts it in place rather than erasing it. Hiding the text
until verification would be safer to look at but would make the UI slower than the
measured pipeline for no accuracy gain, and the failure would still exist — just
invisible.

## 7. Debug payload

Delivered as one JSON object in the `done` event, stored with the message, and shown in
the Debug tab as a labelled tree with a "copy JSON" button. It is versioned so the view
can refuse a shape it does not know.

### 7.1 Schema

```json
{
  "debug_version": 1,
  "status": "verified",
  "cached": false,
  "question": "Compare the Bagmati and East-Rapti peak floods.",
  "search_question": "Compare the Bagmati and East-Rapti peak floods.",
  "condensed": false,
  "route": {
    "route": "normal",
    "k": 5,
    "prompt_mode": "normal",
    "condense": false,
    "reason": "no greeting, no back-reference, no table marker"
  },
  "model": {
    "name": "qwen3.5:4b",
    "digest": "d8b0f5e9760c",
    "prompt_version": "s6-2",
    "num_ctx": 4096,
    "temperature": 0.0
  },
  "retrieval": {
    "k": 5,
    "passages": [
      {
        "n": 1,
        "rank": 1,
        "doc": "1970_Marahatta_Relating_Hydrological_Extremes_with_Area_A_Case_on_Extreme_F_W2121362616.pdf",
        "page": 3,
        "label": "Marahatta 1970 · paper",
        "score": 18.42,
        "rerank_score": null
      }
    ]
  },
  "gate": {
    "top": 18.42,
    "floor": 15.0,
    "refused": false,
    "decision": "answer",
    "reason": "top page scores above the floor and every quotation was found"
  },
  "verification": {
    "ok": true,
    "said_not_found": false,
    "verified_quotes": 2,
    "attempts": 1,
    "citations": [
      {
        "n": 1,
        "doc": "1970_Marahatta_…_W2121362616.pdf",
        "page": 3,
        "quote": "In the study area, P0 is 540 mm and 600 mm observed in 1993",
        "verified": true
      }
    ],
    "problems": []
  },
  "timings_ms": {
    "route": 1.2,
    "condense": 0.0,
    "cache_lookup": 14.0,
    "retrieval": 41.0,
    "gate": 0.4,
    "prompt_build": 2.0,
    "model_total": 8600.0,
    "model_ttft": 6200.0,
    "verify": 38.0,
    "total": 8700.0
  },
  "tokens": { "prompt": 1818, "answer": 104 },
  "unreadable": {
    "corpus": {
      "documents": 97,
      "pages": 851,
      "documents_with_unreadable": 8,
      "unreadable_pages": 19,
      "ocr_pages": 86
    },
    "top_documents": [
      { "doc": "…", "label": "…", "count": 4, "pages": [1, 2, 3, 4] }
    ]
  },
  "sources": [
    { "n": 1, "doc": "…", "page": 3, "label": "…", "score": 18.42, "snippet": "…", "ocr": false }
  ],
  "error": null
}
```

### 7.2 Where each field comes from

| Field | Source today | Work needed |
|---|---|---|
| `status`, `cached`, `question`, `search_question`, `condensed`, `route`, `attempts` | `generation.answer` record, already returned | none |
| `retrieval.passages[].n/doc/page/label/score` | `record["passages"]` (`_passages()`) | add `rank` (= list order) in the wrapper |
| `retrieval.passages[].rerank_score` | **not measured** — the shipped retrieval is page-level BM25 (`EVAL.md`, 2026-11-16); no cross-encoder reranker is in the pipeline | field is `null`; it exists so the view does not change when a reranker is added |
| `gate.*` | `record["gate"]` — `pre_ask()` output merged with `resolve()` (`top`, `floor`, `refused`, `decision`, `reason`) | none |
| `verification.*` | `record["citations"]`, `record["problems"]`, `record["attempts"]` | none; `verified` is true for the citations the verifier accepted |
| `model.*` | `record["model"]`, `record["prompt_version"]`, plus `model_digest()` | none |
| `timings_ms.model_total/model_ttft` | `record["timing"]["total_ms"/"ttft_ms"]` (Ollama's own counters) | none |
| `timings_ms.total` | `record["seconds"] * 1000` | none |
| `timings_ms.route/condense/cache_lookup/retrieval/gate/prompt_build/verify` | **not in the record today** | add a `timings` dict to `_record()` in `generation/answer.py`, one `perf_counter()` per stage; no text, no prompt, no retrieval change, so the eval is unaffected (question 2) |
| `tokens.*` | `record["timing"]["prompt_tokens"/"answer_tokens"]` | none |
| `unreadable.corpus.*` | `index/pages.json`: `docs`, `pages`, `unreadable`, `ocr_pages` — measured 2026-11-17: 97 documents, 851 pages, 8 documents with unreadable pages, 19 unreadable pages, 86 OCR'd pages | one helper in the wrapper; the numbers are computed at request time, never hard-coded |
| `unreadable.top_documents[]` | the same `unreadable` map, filtered to the retrieved passages' documents | join in the wrapper |
| `sources[]` | derived from `passages` plus the page text (`snippet`, `ocr`) | reuse `public_sources()` from `ui/server.py` |

The payload never contains `data/raw` paths, absolute paths, the system prompt, or the
model's hidden reasoning. Page text in `snippet`/`quote` is the corpus text the reader
can also open in the PDF.

### 7.3 The unreadable-pages warning (D-021)

Shown in state 3 only, under the refusal, and always with numbers rather than prose
alone:

```
∅ not found — the retrieved passages do not contain this.
8 of 97 documents have pages with no text layer (19 of 851 pages, 86 pages read by OCR).
  • 2005_Choudhary_Trans_boundary_Floods… has 4 unreadable pages: 1, 2, 3, 4
```

The corpus line is always shown. The per-document lines are shown for the retrieved
documents that have unreadable pages, capped at five, with "and N more" beyond that.
Both numbers come from the index (§7.2), so a corpus rebuild updates them without a
code change. A document whose unreadable pages were OCR'd is reported as OCR'd, not
missing — `ocr_pages` exists precisely so the two are not confused.

## 8. Citations and the PDF route

A chip renders `[n]` and links to `/pdf/<file name>#page=<page>`. The server resolves
the name against the whole corpus, subfolders included (`corpus_by_name()` already does
this, because 92 of 97 PDFs sit below `data/corpus/`). The link opens in a new tab; the
PDF route sets `Content-Disposition: inline`.

If the file is missing or outside the corpus, the chip is rendered disabled with a
title explaining why — never a link to nowhere. `#page=N` is the page number of the
stored corpus PDF, which for a converted Word file is the `.docx.pdf` page (D-023), and
the labels in the sources rail say so.

## 9. Offline, localhost, and the browser's blast radius

- The server binds `127.0.0.1` only; a request from another machine must fail (a DoD
  item, tested from the LAN address).
- No CDN, no webfont, no analytics, no favicon fetched from anywhere. Every asset is
  served from `/static`.
- A Content-Security-Policy header on every response:
  `default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'`.
  No inline `<script>` and no inline `style` attribute, so the policy needs no exception.
- The browser never talks to Ollama directly; `connect-src 'self'` makes that a rule the
  browser enforces, not a convention.
- The offline proof for this step is the Wi-Fi-off run of a full 5-question session.

## 10. BEM and event rules (D-036)

- Blocks: `.sidebar`, `.chat`, `.thread`, `.message`, `.composer`, `.evidence`,
  `.source`, `.debug`, `.state-badge`, `.unreadable-warning`, `.empty`. Existing
  elements keep their names (`message__meta`, `message__body`, `sidebar__header`, …).
- Event delegation: **one** `addEventListener` per event type for the whole app —
  `click`, `submit`, `keydown`, `input`, `change` at most — attached to `#app` or
  `document`, dispatching on `data-action`. No handler inside a render function, no
  per-message listener. A `grep -c addEventListener ui/static/app.js` is part of the
  review and must be ≤ 5.
- Shared helpers only: `el()`, `markdown()`, `formatStats()`, `chipNode()`,
  `stateBadge()`, `evidenceNode()`, `postChat()`. A render path that needs a tweak
  changes the helper, never a copy of it.
- Rendering is text-first: every string from the model passes through `escapeHtml` before
  the small markdown pass, exactly as today. No `innerHTML` with unescaped model text.

## 11. Acceptance checks (mirrors the step's definition of done)

| Check | How it is shown |
|---|---|
| Spec approved before code | the owner's approval line in `APPROVALS.md` naming this file |
| BEM and one handler per event | the class list above in the diff, plus the `addEventListener` count |
| Works with the network off | a 5-question session with Wi-Fi off, output pasted into `STATUS.md` |
| Citation click opens the right page, 10 answers | 10 answers, each chip opened, page number compared with the citation |
| Debug shows chunks, scores, timings | one screenshot-free dump of the Debug tab's JSON per state |
| Not-found warning has correct counts | a question whose top document has unreadable pages, counts compared with `index/pages.json` |
| Not reachable from another machine | `curl http://<LAN-IP>:8000/` fails, `curl http://127.0.0.1:8000/` succeeds |
| Eval unchanged by the UI | the 55-question run repeated after the UI ships, compared with `EVAL.md` |

## 12. Decisions needed from the owner

**Approved by the owner on 2026-11-17: all six recommended options** (instruction in chat, "approve all the remaining"). Code stays in `ui/`; stage timings go into the `generation.answer` record; a streamed answer that fails verification is retracted in place; the terracotta accent stays; Debug is a tab in the evidence rail; the rail is open above 1280px and closed below it, remembered per browser. Decisions D-061 and D-062 in `DECISIONS.md` carry the first two.
Recommended answers are first; "approve all recommended" is enough.

1. **Code location.** Keep `ui/` (recommended, see §2) or move it to `src/ui/` as the
   step text says. A move is one commit and changes no behaviour.
2. **Stage timings.** Add a `timings` dict to the `generation.answer` record so the UI
   shows real pipeline timings (recommended), or measure them in the UI wrapper and leave
   the pipeline untouched. The wrapper cannot time what happens inside `answer()` —
   retrieval and verification — so the recommended option is the only one that fills the
   whole `timings_ms` block.
3. **Retraction model.** Stream the text and retract it if verification fails
   (recommended, §6) or hold the text back until it is verified.
4. **Accent.** Keep the terracotta `#b4603a` / `#d98b62` (recommended) or go neutral with
   the state colours as the only colour.
5. **Debug placement.** A tab next to Sources in the evidence rail (recommended) or a
   third column that is always open.
6. **Evidence rail default.** Open on screens wider than 1280px (recommended), closed
   below that, remembered per browser.

No UI code, and no change to `ui/` files, until this is approved.
