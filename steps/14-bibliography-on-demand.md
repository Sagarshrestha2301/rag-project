# Step 14: The bibliography is on demand, not part of a wave

**Goal:** stop `build` and `add-batch` from spending one local-model call per document
(**8.2 s measured**, ~45 h over the ten waves to 20,000) on metadata that only the evidence
rail shows. `bibliography` becomes an opt-in stage, filled on demand by
`python -m ingest.bibliography build`. A document without a record keeps its label, which is
derived from the file name, so the UI reads the same and answers/citations do not change.

**Needs approval to start:** yes. Owner approval line for `APPROVALS.md`:

```
2026-11-22 | start | step 14 | owner
```

## Why this step exists (measured)

Step 11 re-timed the bibliography with Ollama up: **866.3 s for 106 documents = 8.2 s/document**,
which is **45.1 h** for the 19,813 documents still to come — more than parsing (~35 h) and
~10x embedding (~6 h). The artifact it writes, `index/bibliography.json`, holds
title/authors/year/venue/DOI and is read only by `ui/pipeline.py::sources()` for the rail's
reference line; retrieval, prompts, the gate and citations never read it. Meanwhile a wave
paid that cost on every document whether or not anyone opened the rail.

## Tasks

1. Remove `bibliography` from the default stage tuple in `ingest/pipeline.py::build` and
   `::add_batch`, and from the `--stages` defaults of the `build` and `add-batch`
   sub-commands. Keep the stage itself working when asked for by name, and keep
   `python -m ingest.bibliography build` as the on-demand path.
2. Split the CLI parser out of `main()` into `_parser()` so a test can read the real
   defaults instead of a docstring, and assert them for both commands.
3. Do **not** change `ingest/bibliography.py` itself: it already resumes per document by
   SHA-256 and tolerates a dead model.
4. Verify the UI fallback that makes this safe: `ui/pipeline.py::sources()` returns
   `reference: null` when a document has no record, and `ui/static/app.js` renders
   `reference || label || doc`. The label comes from `corpus.label_for(file name)`, so a
   wave without metadata shows file-name labels instead of blanks. Add an assertion to the
   existing UI test if the chain is not already covered.
5. Correct the parse ETA printed by `parse_stage`: it divided the per-document estimate by
   `jobs` even though `position` already counts completed documents, so a `--jobs 8` wave
   printed an ETA ~8x too low (observed: "eta 290s" for a run of ~20 min). Print the
   throughput-based estimate and comment why.
6. Update `RUNBOOK.md` (the stage list) and `reports/20k-download-and-rag-guide.md`
   (§1 diagram, §3 expectation, §B.1) so the procedure matches the defaults.
7. Add a case to `ingest/test_pipeline.py` asserting the defaults of `build`, `add_batch` and
   both parsed command lines exclude `bibliography` while the flag still reaches it, and
   that `embed`/`parse` stay in.
8. Record in `STATUS.md`: the default change, the measured cost it removes, the test count,
   and that no eval applies (the index and retrieval are untouched).

## Definition of done

- [x] `build` and `add-batch` default to `scan,parse,assemble,chunk,embed`, by function default and by parsed command line
- [x] `--stages ...,bibliography,...` and `python -m ingest.bibliography build` both still fill the artifact
- [x] A document with no bibliographic record yields `reference: null` and keeps its file-name label through the UI source list
- [x] The parse ETA for a `--jobs 8` run is no longer divided by `jobs` twice (comment says why)
- [x] `ingest/test_pipeline.py` passes with the new case and every existing case, and `ui/test_pipeline.py` still passes
- [x] `RUNBOOK.md` and the 20k guide match the defaults; `ingest/corpus.py`, `ingest/structure.py`, `ingest/tables.py`, `ingest/bibliography.py` unchanged
- [x] Live index untouched and `git status` clean at session end

## Context to read

This file, `STATUS.md` (Step 11 bibliography timing, the 2026-11-22 speed fact),
`ingest/pipeline.py` (`build`, `add_batch`, `_parser`, `main`), `ingest/bibliography.py`
(`build`, `_build`, `load`), `ui/pipeline.py` (`sources`), `ui/static/app.js` (the
`reference || label || doc` chain), `RUNBOOK.md` §4, `reports/20k-download-and-rag-guide.md`.

## Expected output

`ingest/pipeline.py` with the bibliography out of the defaults and a testable `_parser()`;
one new case in `ingest/test_pipeline.py`; `RUNBOOK.md` and the guide updated. Nothing under
`data/`, `index/` or `eval/` changes.

## Verification

Show in the handoff: `test_pipeline.py` output with the new case named; the parsed defaults
printed for both commands; the UI test output; `git diff --stat` empty for the extraction and
bibliography modules; `ingest.pipeline status` unchanged.

No eval run: retrieval, prompts and the index are untouched, so the `EVAL.md` gate does not
apply. Say so rather than claiming a gate.

## Risks

- **A wave's UI rail loses its reference lines** until someone runs the on-demand command.
  That is the trade the owner asked for; the label fallback keeps every source identifiable.
- **People may read "no bibliography" as "metadata is lost".** It is not written, not lost:
  the stage is resumable and idempotent per document.
- **Defaults are what every run uses.** A test asserts them at the function and the command
  line, so a later refactor cannot silently put the 45 h back.
