# Step 11: Pilot wave download and gate rehearsal

**Goal:** fetch a ~200-document pilot from the known Drive tree into a staging folder, run
`add-batch` over it against a throwaway index, and record the real per-document timing the
20k plan projects from. The live 97-document corpus and index are not touched.
**Needs approval to start:** yes.

## Tasks
1. Add a `--dest` staging root to `ingest/drive.py`. With `--dest` set, `plan` fills that
   tree instead of `data/raw`, and `fetch` downloads there **without** mirroring into
   `data/corpus` and **without** writing `logs/drive-downloads.jsonl`; it records to
   `logs/drive-pilot.jsonl` instead. Default behaviour (`--dest` absent) is unchanged.
2. `plan` against Drive root `1ew-Pj4ry2vIzYpFMA3h3LiGZT-87YvnP` with `--per-category 7`
   and `--dest data/raw/incoming-wave-pilot`, then `fetch`. That is 7 PDFs per leaf folder
   (32 leaf folders, so at most 224 files) and is resumable: files already on disk are
   skipped.
3. Remove staged files whose bytes are already in the manifest. The first two files per
   leaf folder are the 97 documents already indexed; leaving them in would make
   `add-batch` refuse the whole batch (duplicate content), which is the correct behaviour
   and the reason this cleaning step exists. Report how many were removed.
4. Run `add-batch --wave pilot --from data/raw/incoming-wave-pilot` against a temporary
   `--corpus` and `--index` (never the live ones), with the default stages, and record:
   wall time, build seconds, documents/pages/chunks, parse seconds per document, and
   failures. Compare the per-document rates with the plan's projections.
5. Write the result into `STATUS.md` and `reports/20k-ingestion-plan.md` (measured vs
   projected). No eval run is part of this step.

## Definition of done
- [ ] `--dest` downloads without writing the corpus or the default download log
- [ ] The pilot folder holds ~200 real PDFs, each with a SHA-256 in `logs/drive-pilot.jsonl`
- [ ] Staged duplicates of indexed documents removed and counted
- [ ] `add-batch` over the pilot succeeds into a throwaway corpus/index, with wall time recorded
- [ ] The live index still reports 97 documents afterwards
- [ ] Measured per-document rates recorded next to the projections

## Context to read
This file, `reports/20k-ingestion-plan.md` sections 1-3 and 8, `ingest/drive.py`,
`ingest/pipeline.py` (`add_batch`), `STATUS.md`, `logs/drive-tree.json`.

## Expected output
A staged pilot folder under `data/raw/` (owner-only originals stay untouched), a JSON
summary from `add-batch`, and a STATUS line with the measured wall time and per-document
rates. Nothing is added to the live corpus or the eval set.

## Verification
`ingest.pipeline status` still prints 97 documents; the pilot summary reports the exact
number added and the build's own `seconds`; a rerun of `add-batch --no-build` reports every
file `unchanged`.

## Risks
- Drive throttling or an HTML interstitial instead of a PDF: `download()` already rejects
  a non-PDF body and retries.
- 224 files at a few MB each is a network job of minutes to tens of minutes; it is
  resumable and logged, so stopping is safe.
- A wrong folder id would stage the wrong documents; the id and the 22,887-file tree are
  recorded in `logs/drive-tree.json`.
