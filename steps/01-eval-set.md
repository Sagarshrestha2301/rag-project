# Step 1: Eval set

**Goal:** a trusted, owner-approved test set and exact metric definitions, before anything is built.
**Needs approval to start:** yes.

## Tasks
1. Owner picks real documents and supplies or approves 30 questions (composition in `EVAL.md`: fact 7, exact lookup 5, table 6, summary 3, comparison 3, not-found 4, follow-up 2).
2. Convert any Word source documents to PDF first with the pinned LibreOffice and store them in `data/corpus/` as the full original file name plus `.pdf`, e.g. `report.docx.pdf` (D-023, D-030). Native PDFs used by the eval are hardlinked (or copied) into `data/corpus/` the same way. For each question record gold answer, gold numbers (value + unit), gold sources (corpus file + physical PDF page + file SHA-256) and a short exact gold quote. Gold pages always refer to the stored corpus file.
3. Not-found questions: confirm the answer is truly absent from the sample and later the full corpus.
4. Split 20 dev / 10 held-out, stratified by type; freeze the split.
5. List every source document used (these must be inside the Step 3 sample).
6. Write the scoring script spec for: recall@k (5, 10, 30), MRR, citation correctness, numeric exact match, not-found accuracy (a and b), latency per stage.
7. After approval of the spec, implement the scorer and test it on hand-made fake outputs (known right and wrong). The scorer must stop if a corpus file's SHA-256 does not match the gold record.
8. Write down the process for adding new dev questions later (agent proposes, owner approves, tagged `added_in_step`, re-baseline) as in `EVAL.md`.

## Definition of done
- [ ] `eval/questions.jsonl` has 30 questions, each approved by the owner
- [ ] Split frozen and recorded; number of not-found questions on dev counted (expected about 3) and the one-question point values reported
- [ ] Every gold source points to a file in `data/corpus/` with its SHA-256; the scorer fails on a hash mismatch (tested)
- [ ] Source document list saved
- [ ] Scorer gives the expected scores on hand-made fake outputs (perfect, empty, partly wrong)
- [ ] Metric definitions match `EVAL.md`; any change recorded in `DECISIONS.md`

## Context to read
`EVAL.md`, `REQUIREMENTS.md` (F2-F4), this file, `DECISIONS.md` (D-013 to D-015, D-022, D-023, D-030), the documents the owner chose.

## Expected output
`eval/questions.jsonl`, `eval/source_documents.md`, `eval/SCORER.md` (metric spec), the scorer code and its test on fake outputs. One question looks like this (placeholders):
`{"id":"q001","split":"dev","type":"table","question":"...","history":[],"answerable":true,"gold_answer":"...","gold_numbers":[{"value":"...","unit":"..."}],"gold_sources":[{"file":"data/corpus/<name>.pdf","page":12,"sha256":"..."}],"gold_quote":"...","added_in_step":1,"notes":""}`

## Verification
Owner spot-checks at least 5 questions against the source pages. Scorer test table shown with real output.

## Risks
Questions that are too easy or ambiguous; gold page numbers off by one (the physical PDF page is used, not the printed page number; record the printed number in notes if useful).
