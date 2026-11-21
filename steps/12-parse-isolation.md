# Step 12: Parse isolation, so one bad PDF costs one document

**Goal:** make `parse_stage` run each document's parse in its own child process, so a native
crash (PyMuPDF's ONNX table detector raises `Windows fatal exception: access violation`, which
`except Exception` cannot catch) records that one document as `failed` with its exit code and
the batch carries on. Extraction itself does not change: the 97 gold pages and the live index
stay valid.
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
file. Recorded as D-075; approved by the owner in chat, not yet implemented.

## Tasks

1. Move the body of the per-document parse in `ingest/pipeline.py::parse_stage` into one
   function that takes `(path, index_dir, sha256)` and returns the small values the parent
   needs: `page_count`, `unreadable`, page hashes and `furniture_lines`. It writes the three
   shards it already writes (`search.json`, `structure.jsonl`, `summary.json`) and nothing
   else, so `assemble()` keeps its current interface.
2. Run that function in a child process per document — `multiprocessing.get_context("spawn")`,
   one `Process` at a time, `join()`ed before the next document. Spawn, not fork: Windows has
   no fork, and a fresh interpreter is the only way to survive a native crash. The child must
   be importable at module level (spawn pickles it), and the parent must keep the existing
   `__main__` guard path working for both `python -m ingest.pipeline` and the tests.
3. In the parent: `exitcode == 0` -> do what the loop does today (near-duplicate check,
   `set_status("parsed" | "duplicate")`, counters, the same progress+ETA line). Any other
   `exitcode` -> `set_status(name, "failed", error="crash: exit code N")`, count it as failed,
   print one line to stderr, and continue to the next document. Never re-run a document that
   already has an `error` beginning `crash:` in the same wave unless the file's SHA-256
   changed; the outer loop's `pending`/`failed` retry stays as it is for real exceptions.
4. Do not touch extraction: `ingest/corpus.py`, `ingest/structure.py`, `ingest/tables.py` and
   the prompt/index artifacts are out of scope, and `git diff` on them must be empty at the end.
5. Add cases to `ingest/test_pipeline.py`: (a) a child that exits non-zero mid-document leaves
   that row `failed` with the exit code and the following document still parses and assembles;
   (b) a child that raises normally still produces the same `failed` record as today; (c) the
   parent's counters (`parsed`, `failed`, `seconds`) add up over a 3-document run.
6. Re-run the pilot batch that crashed, against **throwaway** paths only, with the file put
   back in: `add-batch --wave pilot-iso --from data/raw/incoming-wave-pilot --stages
   scan,parse,assemble --corpus data/tmp-pilot-corpus-iso --index data/tmp-pilot-index-iso
   --log logs/waves-pilot-iso.jsonl`, and record the wall time, parsed/failed counts and the
   crash line. Expect 119 staged, 118 parsed, 1 failed, exit 0. The crashing PDF is still in
   the staging folder (`data/raw/incoming-wave-pilot/reports/NSO/2023_Small_Area_Estimation_
   of_Nepal_2023_Pess_Note_2b69c333a2.pdf`); only the throwaway corpus dropped it. Stages stop
   at assemble because chunk/embed and the bibliography add ~15 min and measure nothing new
   here — say that in the handoff rather than implying the full build was re-run.
7. Record in `STATUS.md`: the exit-0 result, the per-document overhead (child spawn) against
   the measured 22.5 s/document parse, and confirmation that `ingest.pipeline status` still
   prints 97 documents for the live index.

## Definition of done

- [ ] A document whose parse kills the child is `failed` with `crash: exit code N`, and the rest of the batch parses in the same run
- [ ] The 119-document pilot batch (including the crashing file, stages `scan,parse,assemble`) completes with exit 0, 118 parsed, 1 failed, wall time recorded
- [ ] `ingest/corpus.py`, `ingest/structure.py` and `ingest/tables.py` are unchanged (`git diff` empty)
- [ ] Shards for three pilot documents are byte-identical to the ones the current code wrote (SHA-256 compared)
- [ ] `ingest/test_pipeline.py` passes with the three new cases, and the existing cases still pass
- [ ] The live index still reports 97 documents, and `git status` is clean at session end

## Context to read

This file, `STATUS.md` (Step 11 row, the PyMuPDF crash bullet, D-075), `DECISIONS.md` D-075,
`ingest/pipeline.py` (`parse_stage`, `_shard`, `_write`, `build`, `add_batch`),
`ingest/test_pipeline.py`, `logs/pilot-build3.out`, `logs/pilot-build3.time`,
`logs/probe-all.out`.

## Expected output

`ingest/pipeline.py` with a module-level parse worker and a parent loop that treats a dead
child as one failed document; new cases in `ingest/test_pipeline.py`; a STATUS line with the
exit-0 pilot numbers. Nothing under `data/raw/`, `data/corpus/`, `index/` or `eval/` changes.

## Verification

Show, in the handoff:
- `ingest/test_pipeline.py` output (all cases, including the three new ones);
- the `add-batch` summary and its exit status for the pilot rerun, with the crash line for the
  NSO report and 118 parsed / 1 failed;
- `ingest.pipeline status` printing 97 documents / 97 embedded / 0 failed;
- `git diff --stat -- ingest/corpus.py ingest/structure.py ingest/tables.py` printing nothing.

No eval run is part of this step: retrieval, prompts and the index are untouched, so the
regression gate in `EVAL.md` does not apply. Say so in the handoff rather than claiming a gate.

## Risks

- **Spawn cost.** One interpreter start per document; measured parse is 22.5 s/document, so a
  spawn of a few hundred milliseconds is under 2%. Measure it and report it, do not assume.
- **Windows spawn semantics.** A module-level worker plus the `__main__` guard; passing a
  `Manifest` or an open file handle into the child will fail to pickle. Pass only paths and
  strings, and let the child open what it needs.
- **Silent data loss if the child dies after writing one of three shards.** `assemble()`
  already refuses a row whose shards are missing (`missing_shards`), so the failure surfaces
  there; do not write a partial shard set into the live index. The pilot rerun uses throwaway
  paths, and the live index is only ever rebuilt by the owner.
- **Exit code is not the error.** A native crash has no exception text; record the code and
  the file name, nothing more, so nobody later reads a guess as evidence.
- **No new dependency.** `multiprocessing` is standard library; nothing is downloaded.
