# Step 8: Full ingestion

**Goal:** index all 100k+ pages reliably, then prove accuracy holds at full scale.
**Needs approval to start:** yes. Owner confirms free disk and that the PC can run for hours.

## Tasks
1. SQLite manifest: file hash, parser version, embedding model version, status, error, duplicate-of, unreadable pages (page numbers per file).
2. Resumable pipeline: kill it at any point and it continues without redoing finished work.
3. Near-duplicate detection (flag and skip, never silently delete).
4. GPU embedding during the bulk build only if Step 4 showed it is faster; the LLM is not running then.
5. Dry run on 1,000 pages, then the full run in batches with progress and ETA.
6. Incremental add: add 5 new files and confirm only those are processed.
7. Re-check every not-found question against the full corpus (keyword and BM25 search plus owner confirmation) to be sure the answer is still absent. If one is now answerable, propose a replacement of the same type for owner approval; never change it silently (D-027).
8. Re-run the full eval (dev, then held-out) on the full index.
9. Offline proof: run the full pipeline and eval once with the network disabled.

## Definition of done
- [x] All files in the manifest are `done` or `failed` with a reason; failures listed
- [x] Unreadable pages counted over the full corpus and compared with the 1-2% threshold (D-020); result reported to the owner
- [x] Kill-and-resume test passed
- [x] Incremental add test passed
- [x] Index size and RAM use at full scale recorded; query latency at full scale within budget
- [x] Every not-found question re-checked against the full corpus; result listed (still absent / replaced with owner approval)
- [x] Eval on full index recorded; compared with the sample-scale results; any drop analyzed
- [ ] Offline run: pass (network disabled, output recorded)
- [x] All corpus files in `data/corpus/` have a recorded SHA-256 in the manifest
- [x] Backup of the index and manifest made and a restore tested

## Context to read
This file, `ARCHITECTURE.md` (manifest fields), `DECISIONS.md` (D-020, D-023, D-027, D-030), `EVAL.md`, the parsing, chunking and embedding modules, `STATUS.md` (speed measurements from Steps 3 and 4).

## Expected output
Ingestion script with resume, the SQLite manifest, `reports/full-ingestion.md` (counts per status, failures with reasons, unreadable-page share, total time, index size), eval rows for the full index, and a tested backup. Manifest row example: `file | sha256 | pages | parser_version | embedding_model | status=done | unreadable_pages=[3,4]`.

## Verification
Manifest summary counts shown with real output; owner spot-checks 5 random pages.

## Risks
Parser crashes on a few files; recall drop from distractors; disk full; the PC sleeping during a long run (disable sleep).
