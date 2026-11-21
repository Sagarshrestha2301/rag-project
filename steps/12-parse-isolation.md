# Step 12: Parse isolation, so one bad PDF costs one document

**Goal:** make `parse_stage` run each document's parse in its own child process, so a native
crash (PyMuPDF's ONNX table detector raises `Windows fatal exception: access violation`, which
`except Exception` cannot catch) records that one document as `failed` with its exit code and
the batch carries on. A parse that never returns is killed after a wall-clock cap and recorded
the same way, so a hang also costs one document instead of the wave. Extraction itself does not
change: the 97 gold pages and the live index stay valid.
**Needs approval to start:** yes. Owner approval line for `APPROVALS.md` (proposed):

```
2026-11-?? | start | step 12 | owner
```

## Why this step exists (measured in Step 11)

On 2026-11-21 `add-batch` over the 118-document pilot (all but one file) died at **exit 139
after 2,187 s**: `2023_Small_Area_Estimation_of_Nepal_2023_Pess_Note_2b69c333a2.pdf` crashes
reproducibly on page 6 inside `page.find_tables` -> `pymupdf/layout/onnx/BoxRFDGNN.py predict`.
The parser writes its shards *after* both parse calls succeed, so the process lost every
document it had not yet written, and every restart re-hit the same file because `parse_stage`
retries `failed` rows. All 15 other pending pilot documents passed an isolated probe, so this
is one bad file, not a class — but a 20k wave cannot afford a whole-process restart per bad
file. Recorded as D-075 and implemented on 2026-11-21 (child process: D-076; watchdog: D-077).

## Tasks

1. Move the body of the per-document parse in `ingest/pipeline.py::parse_stage` into one
   function that takes `(path, index_dir, sha256)` and returns the small values the parent
   needs: `page_count`, `unreadable`, page hashes and `furniture_lines`. It writes the three
   shards it already writes (`search.json`, `structure.jsonl`, `summary.json`) and nothing
   else, so `assemble()` keeps its current interface.
2. Run that function in a child process per document, one child at a time and waited for
   before the next document: a fresh `python -m ingest.pipeline parse-one` process, started with
   `subprocess.run`, with the parent's `sys.executable` and `cwd` at the project root, and the
   result passed back through a temp JSON file. A subprocess, not
   `multiprocessing.get_context("spawn")` as originally written: spawn was built and measured to
   stall PyMuPDF's table detector on the 198-page pilot report (1,442 s CPU, then no progress;
   `logs/iso-one.err`) where a plain new interpreter parsed the same file in 308 s (D-076).
   Route the child's stdout to the parent's stderr, so `build`/`add-batch` still print one JSON
   summary on stdout. The child must be importable at module level, and the parent must keep the
   existing `__main__` guard path working for both `python -m ingest.pipeline` and the tests.
3. In the parent: a clean child -> do what the loop does today (near-duplicate check,
   `set_status("parsed" | "duplicate")`, counters, the same progress+ETA line). A child that
   exited non-zero with no result -> `set_status(name, "failed", error="crash: exit code N")`,
   count it as failed, print one line to stderr, and continue to the next document. Never re-run
   a document that already has an `error` beginning `crash:` in the same wave unless the file's
   SHA-256 changed; the outer loop's `pending`/`failed` retry stays as it is for real
   exceptions.
4. Give the child a wall-clock limit (`PARSE_TIMEOUT`, **900 s**, about 3x the slowest measured
   document) and expose `--parse-timeout SECONDS` on `build` and `add-batch`. On expiry kill the
   child and record `failed: timeout: no result after N s; killed it`, then continue. A timeout
   row is not retried either, for the same reason as a crash row, and its partial shards must
   never be assembled: `assemble` only reads rows at `parsed` or later, so verify that the row
   never reaches `parsed`.
5. Do not touch extraction: `ingest/corpus.py`, `ingest/structure.py`, `ingest/tables.py` and
   the prompt/index artifacts are out of scope, and `git diff` on them must be empty at the end.
6. Add cases to `ingest/test_pipeline.py`: (a) a child that exits non-zero mid-document leaves
   that row `failed` with the exit code and the following document still parses and assembles;
   (b) a child that raises normally still produces the same `failed` record as today; (c) the
   parent's counters (`parsed`, `failed`, `seconds`) add up over a 3-document run; (d) a child
   that hangs is killed at a short `timeout=` and recorded as a timeout, the next document still
   parses, and the row is not retried on a second run.
7. Re-run the pilot batch that crashed, against **throwaway** paths only, with the file put
   back in: `add-batch --wave pilot-iso --from data/raw/incoming-wave-pilot --stages
   scan,parse,assemble --corpus data/tmp-pilot-corpus-iso --index data/tmp-pilot-index-iso
   --log logs/waves-pilot-iso.jsonl`, and record the wall time, parsed/failed counts and the
   crash line. Expect 119 staged, 118 parsed, 1 failed, and exit **1**: the batch completes, but
   `build` lists the crashed row under `failures`, so `add-batch` returns 1. Whether that exit
   code should stay 1 or become 0 is the owner's call (see the exit-code proposal in
   `STATUS.md`); record what actually happens, do not change the contract. The crashing PDF is
   still in
   the staging folder (`data/raw/incoming-wave-pilot/reports/NSO/2023_Small_Area_Estimation_
   of_Nepal_2023_Pess_Note_2b69c333a2.pdf`); only the throwaway corpus dropped it. Stages stop
   at assemble because chunk/embed and the bibliography add ~15 min and measure nothing new
   here — say that in the handoff rather than implying the full build was re-run.
8. Record in `STATUS.md`: the pilot result and its real exit status, the per-document overhead
   (child start) against the measured 22.5 s/document parse, the watchdog default and what was
   measured of it, and confirmation that `ingest.pipeline status` still prints 97 documents for
   the live index.

## Definition of done

- [x] A document whose parse kills the child is `failed` with `crash: exit code N`, and the rest of the batch parses in the same run
- [x] The 119-document pilot batch (including the crashing file, stages `scan,parse,assemble`) completes with 118 parsed, 1 failed and exit 1 (the failed row is listed under `failures`), wall time recorded
- [x] `ingest/corpus.py`, `ingest/structure.py` and `ingest/tables.py` are unchanged (`git diff` empty)
- [x] Shards for three pilot documents are byte-identical to the ones the current code wrote (`search.json` and `structure.jsonl` SHA-256 compared; `summary.json` differs only in its `seconds`/`table_seconds` fields)
- [x] A parse child that exceeds the timeout is killed, recorded as one failed document and not retried, and the next document still parses
- [x] `ingest/test_pipeline.py` passes with the four new cases, and the existing cases still pass
- [x] The live index still reports 97 documents, and `git status` is clean at session end

## Context to read

This file, `STATUS.md` (Step 11 row, the PyMuPDF crash bullet, D-075), `DECISIONS.md` D-075,
`ingest/pipeline.py` (`parse_stage`, `_shard`, `_write`, `build`, `add_batch`),
`ingest/test_pipeline.py`, `logs/pilot-build3.out`, `logs/pilot-build3.time`,
`logs/probe-all.out`.

## Expected output

`ingest/pipeline.py` with a module-level parse worker and a parent loop that treats a dead or
hung child as one failed document; new cases in `ingest/test_pipeline.py`; a STATUS line with
the pilot numbers and the real exit status. Nothing under `data/raw/`, `data/corpus/`, `index/` or `eval/` changes.

## Verification

Show, in the handoff:
- `ingest/test_pipeline.py` output (all cases, including the four new ones);
- the `add-batch` summary and its exit status for the pilot rerun, with the crash line for the
  NSO report, 118 parsed / 1 failed and exit 1;
- `ingest.pipeline status` printing 97 documents / 97 embedded / 0 failed;
- `git diff --stat -- ingest/corpus.py ingest/structure.py ingest/tables.py` printing nothing.

No eval run is part of this step: retrieval, prompts and the index are untouched, so the
regression gate in `EVAL.md` does not apply. Say so in the handoff rather than claiming a gate.

## Risks

- **Child start cost.** One interpreter start plus pipeline import per document; measured parse
  is 22.5 s/document, and the measured start is 1.04 s, ~4%. Measure it and report it, do not
  assume.
- **Process semantics.** A module-level worker plus the `__main__` guard; arguments cross a
  command line, so pass only paths and strings and let the child open what it needs. The
  `python -m` child also re-imports the pipeline, so keep module import free of side effects.
- **A cap can be wrong in both directions.** 900 s is ~3x the slowest document measured here and
  would false-fail a book-length PDF; that is why `--parse-timeout` exists. Do not treat a
  timeout row as a parsing bug without checking the file's page count first.
- **Silent data loss if the child dies after writing one of three shards.** `assemble()`
  already refuses a row whose shards are missing (`missing_shards`), so the failure surfaces
  there; do not write a partial shard set into the live index. The pilot rerun uses throwaway
  paths, and the live index is only ever rebuilt by the owner.
- **Exit code is not the error.** A native crash has no exception text; record the code and
  the file name, nothing more, so nobody later reads a guess as evidence.
- **No new dependency.** `subprocess` is standard library; nothing is downloaded.
