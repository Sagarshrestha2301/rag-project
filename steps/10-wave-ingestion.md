# Step 10: Batch ingestion (add-batch)

**Goal:** one command brings a staged folder of local PDFs into `data/corpus/` safely, so a
wave of the 20k set can be added without a per-file script and without a half-landed batch.
**Needs approval to start:** yes.

## Tasks
1. Add `add-batch` to `ingest/pipeline.py`'s CLI:
   `.venv\Scripts\python.exe -m ingest.pipeline add-batch --from <dir> --wave NN`
   with `--index`, `--corpus`, `--stages`, `--limit` and `--no-build` passthroughs.
2. **Pre-flight the whole batch before placing one file.** Walk `--from` for `*.pdf`,
   sorted; refuse the batch, list every reason, place nothing, exit 1, when any of these
   holds:
   - `--from` is not a directory, or is not inside `data/raw` (`ingest/drive.py::mirror`
     keeps the path relative to `data/raw`, D-030);
   - a non-PDF file is present (Word files are converted to `<name>.docx.pdf` with the
     pinned LibreOffice at staging time, rule 11 - this command converts nothing);
   - a source file is already inside `data/corpus`;
   - two files in the batch share a name;
   - a name already exists in `data/corpus` **and is not the same bytes** (a rerun of the
     same batch must not hit this: same name + same SHA-256 counts as `unchanged`);
   - a SHA-256 already appears in the manifest under another name (`manifest.upsert`
     keys by `path` and `name` is UNIQUE, and `corpus.files()` raises on duplicate names
     after the fact; both must be caught before a link is made);
   - a SHA-256 appears twice in the batch.
3. Place accepted files with `ingest/drive.py::mirror()` (hardlink, copy on failure) and
   append one row per file to `logs/wave-additions.jsonl` with the batch folder, wave,
   SHA-256, size, link mode and path, reusing `ingest/drive.py::record()`.
4. Record the wave in the manifest's existing `meta` table (`wave-NN` -> documents,
   bytes, timestamp) with `Manifest.set_meta`. No schema migration in this step.
5. Run `build` over the requested stages unless `--no-build`; return its exit code and
   print a JSON summary (`added`, `unchanged`, `refused`, `bytes`, `wave`, `build`).
6. Tests in `ingest/test_pipeline.py`, using its existing temp-corpus `workspace()` /
   `run()` pattern and synthetic PDFs, never the real corpus:
   - a batch of two PDFs is linked and appears in the built index;
   - a duplicate name inside the batch refuses everything (nothing placed);
   - a duplicate name against the corpus refuses everything;
   - the same bytes under a different name is refused against the manifest;
   - re-running the same batch reports `unchanged` and adds nothing;
   - a file outside `data/raw` (or a `.docx`) is refused with the LibreOffice message;
   - `os.link` failure falls back to a copy (monkeypatch `os.link` inside the test; there
     is no existing drive test to borrow this from).

## Definition of done
- [ ] `add-batch` exists with the behaviour above and a docstring usage example
- [ ] Refusal is all-or-nothing: one bad file leaves the corpus unchanged
- [ ] Rerunning a landed batch is a no-op that reports `unchanged`
- [ ] All seven test cases pass, and the existing 12 `ingest/test_pipeline.py` cases still pass
- [ ] `RUNBOOK.md` "add documents" section mentions `add-batch` for multi-file batches
- [ ] `STATUS.md` records the command, its measured time on the pilot batch, and any TODO
- [ ] Owner reviews a refusal message and a landed batch before sign-off

## Context to read
This file, `reports/20k-ingestion-plan.md` (sections 4, 5.1, 8), `ingest/pipeline.py`,
`ingest/drive.py`, `corpus.py::files`, `scripts/add-document.ps1` (the single-file precedent),
`ingest/test_pipeline.py`, `STATUS.md`.

## Expected output
`add-batch` is a thin command over existing parts: `corpus.files` name rules, `Manifest`,
`drive.mirror`, `drive.record`, `pipeline.build`. Example:

```
$ python -m ingest.pipeline add-batch --from data/raw/incoming-wave-00 --wave 00
{"wave": "00", "added": 200, "unchanged": 0, "refused": [], "bytes": 101_000_000,
 "build": {"counts": {"embedded": 297, ...}}}
```

A batch with one duplicate name prints every offending file and exits 1 with
`"added": 0`, and `git status` shows no new corpus file.

## Verification
Run the refused cases and the real pilot folder: the first places nothing, the second
places exactly the accepted files, and `python -m ingest.pipeline status` shows them
`embedded` with the expected page count. Record the command's wall time.

## Risks
- `mirror()` silently returns `"already there"` for an existing target; the pre-flight must
  run first, or a name collision is accepted quietly.
- A batch that is 200 files deep in the folder tree keeps `data/raw`'s relative structure;
  a flat staging folder puts every file at the corpus root (fine, but it must be stated).
- `data/raw` is owner-only (rule 5): the command reads it and hardlinks out of it, never
  writes to it.
