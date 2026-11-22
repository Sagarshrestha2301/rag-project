# Step 13: Parse several documents at once, so a wave is not serial

**Goal:** give `parse_stage` a `--jobs N` option that parses up to N documents in parallel
(each still a child process, D-075), with **N = 1 as the default so today's behaviour and output
are unchanged**. Measured on 2026-11-22: 20 real corpus documents take **202.2 s serially
(87.9 pages/min)** and **132.2 s at 8 at once (134.3 pages/min, 1.53x)**, with identical page
counts. That is 19 h off a 20,000-document build (`reports/20k-download-and-rag-guide.md` §6.1).
Extraction does not change: no file moves, no index is rebuilt, the 97 gold pages stay valid.

**Needs approval to start:** yes. Owner approval line for `APPROVALS.md` (proposed):

```
2026-11-22 | start | step 13 | owner
```

## Why this step exists (measured)

`parse_stage` walks `todo` and calls `_run_isolated` once per document, waiting each time. The
machine has **16 logical cores** and every parse is already its own `python -m` child, so the
waiting is pure waste: the same 20 documents finish in 132.2 s when 8 children run at once.
Past 8 the gain stops (4x2 / 8x1 / 8x2 / 16x1 threads = 41.1 / 43.7 / 43.2 / 43.9 s against
72.0 s serial), because each child's table detector and OCR are already threaded and they
contend. **So the option is a throughput knob around 8, not a core-count knob.**

## Tasks

1. In `ingest/pipeline.py`, keep the per-document child call exactly as it is and add a small
   helper that runs it and returns `(state, payload, seconds)`, so the serial and parallel paths
   share one function instead of two copies (Code rule 1).
2. `parse_stage(..., jobs: int = 1)`: when `jobs == 1`, iterate as today. When `jobs > 1`, submit
   each document to a `ThreadPoolExecutor(max_workers=jobs)` (a thread pool is enough: the work
   is a blocking `subprocess.run`, and `multiprocessing` spawn was measured to stall PyMuPDF,
   D-076) and **consume the futures in plan order**, so the manifest is written by the parent
   thread only and near-duplicate decisions and counters come out the same as a serial run.
   Cap `jobs` at `len(todo)`; reject a value below 1 with a clear `SystemExit`.
3. Measure and print honestly: per-document `seconds` is that document's own child wall time;
   the stage `seconds` is wall time; the progress/ETA line divides the remaining estimate by
   `jobs`, because the loop is no longer one-at-a-time. Keep one line per document and keep
   stdout to the single JSON summary.
4. Thread `jobs` through `build(..., parse_jobs: int = 1)` and
   `add_batch(..., parse_jobs: int = 1)` so `add-batch` can drive a wave, and add
   `--jobs N` to the `build` and `add-batch` sub-commands (default 1, help text naming the
   measured 8).
5. Do not touch `ingest/corpus.py`, `ingest/structure.py`, `ingest/tables.py` or the
   bibliography: `git diff --stat` on them must be empty.
6. Add cases to `ingest/test_pipeline.py`:
   (a) `jobs=8` over 6 synthetic documents produces the same manifest rows (status, pages, page
   hashes) and the same `pages.json` as `jobs=1`;
   (b) with `jobs=3` the fake crashing child still leaves that row `failed` with
   `crash: exit code 17` while the other documents parse, and a rerun does not retry it;
   (c) a `jobs=0` / negative value stops with a clear message instead of hanging.
7. Measure on real data, throwaway paths only: the same 20 documents used on 2026-11-22,
   stages `scan,parse` into `data/tmp-par-jobs-1` and `data/tmp-par-jobs-8` (or two temp dirs
   under `data/`), report wall time, pages/min and that the page counts match. Do **not** touch
   `data/corpus`, `index/` or the live manifest.
8. Record in `STATUS.md`: the code change, the new test count, the measured serial-vs-8 numbers
   (and whether they reproduce 1.53x), and the fact that no eval applies.

## Definition of done

- [ ] `--jobs N` exists on `build` and `add-batch`, default 1, and a `jobs=1` run prints the same per-document lines and summary keys as today
- [ ] `jobs=8` yields the same manifest rows and `pages.json` as `jobs=1` on the same synthetic documents
- [ ] Under `jobs=3` a crashing child is still `failed` with its exit code, the rest of the batch parses, and the crash row is not retried
- [ ] Measured on 20 real corpus documents against throwaway paths: wall time and pages/min for `--jobs 1` and `--jobs 8`, page counts identical
- [ ] `ingest/test_pipeline.py` passes with the new cases and every existing case still passes
- [ ] `ingest/corpus.py`, `ingest/structure.py`, `ingest/tables.py` unchanged (`git diff` empty)
- [ ] The live index is untouched (`ingest.pipeline status` still reports its current counts) and `git status` is clean at session end

## Context to read

This file, `STATUS.md` (the 2026-11-22 speed fact), `reports/20k-download-and-rag-guide.md` §6.1,
`ingest/pipeline.py` (`_run_isolated`, `parse_document`, `parse_stage`, `build`, `add_batch`,
`main`), `ingest/test_pipeline.py` (the fake parser and the four isolation cases), `DECISIONS.md`
D-075/D-076.

## Expected output

`ingest/pipeline.py` with one shared per-document child call, a `jobs` parameter and the two CLI
flags; new cases in `ingest/test_pipeline.py`; a STATUS line with the measured speedup. Nothing
under `data/raw/`, `data/corpus/`, `index/` or `eval/` changes.

## Verification

Show, in the handoff:
- `ingest/test_pipeline.py` output (all cases, new ones named);
- the real-data comparison: `--jobs 1` and `--jobs 8` wall time, pages/min, identical page counts;
- `python -m ingest.pipeline build --help` and `... add-batch --help` showing `--jobs`;
- `git diff --stat -- ingest/corpus.py ingest/structure.py ingest/tables.py` printing nothing;
- `python -m ingest.pipeline status` still reporting the live index's current counts.

No eval run is part of this step: extraction, prompts and retrieval are untouched, so the
regression gate in `EVAL.md` does not apply. Say so rather than claiming a gate.

## Risks

- **Ordering.** Parallel completion order must not leak into the manifest: results are consumed
  in plan order so a near-duplicate is compared against exactly the rows a serial run would
  have recorded. Do not "improve" that into as-completed order.
- **Memory.** Each child holds a PDF plus OCR models; 8 at once is measured safe on 16 GB-class
  machines at these file sizes, but a wave of scanned reports is the case to watch. `--jobs` is
  a knob precisely because the right number depends on the files.
- **Diminishing returns are real.** Do not report the option as "8x faster": the measured figure
  is 1.53x at 8 and no better at 16.
- **The default must not change.** A `jobs=1` run is the reference every existing log, test and
  `STATUS.md` number was produced with; if its output or record changes, the change is wrong.
- **No new dependency.** `concurrent.futures` is standard library.
