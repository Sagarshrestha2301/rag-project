# Step 3: Parsing sample (50 docs)

**Goal:** prove the two-tier parsing gives correct text, tables and real page numbers, and measure its speed.
**Needs approval to start:** yes. Word to PDF uses LibreOffice headless (D-019). Unreadable pages: flag only, with a 1-2% threshold rule for OCR (D-020).

## Tasks
1. Build the 50-doc sample: all eval source documents plus a mix of types, lengths and table density.
2. Convert Word files to PDF first with the pinned LibreOffice headless and store them in `data/corpus/` as the full original file name plus `.pdf`, e.g. `report.docx.pdf` (reuse the Step 1 conversions for eval documents; never convert them again, D-023). Hardlink the native PDFs of the sample into `data/corpus/` (D-030). Parse only from `data/corpus/`, so citations have real page numbers. Test on at least 5 of the owner's real Word files: record page counts and check that headings, tables and page breaks look right. The converted PDF is kept and is the file the UI opens.
3. PyMuPDF4LLM on all pages.
4. Detect table pages; re-parse only those with Docling or pdfplumber. Compare both on the same pages and pick one per table style.
5. Flag pages with no text layer (list only, no OCR). Store them per file (file, page numbers) for the manifest and the UI warning (D-021). Compute the share of unreadable pages.
6. Save per-page output with file, page number, parser and parser version.
7. Measure time per page for each tier and extrapolate to 100k pages.

## Definition of done
- [ ] 50 docs parsed; all eval source docs included
- [ ] Page numbers verified against the PDF viewer on at least 20 random pages (100% match)
- [ ] At least 20 tables checked cell by cell against the source; numeric cell accuracy reported
- [ ] LibreOffice conversion tested on at least 5 real Word files; page counts recorded; owner confirms the converted PDFs look right
- [ ] Flagged no-text pages counted and listed per file; share of unreadable pages reported against the 1-2% threshold (below: keep flagging; above: propose a separate OCR step to the owner)
- [ ] Pages per minute per tier measured; full-corpus time estimate written in `STATUS.md`
- [ ] Parser choice per case recorded in `DECISIONS.md`

## Context to read
This file, `ARCHITECTURE.md` (ingestion flow), `DECISIONS.md` (D-005, D-019, D-020, D-023, D-030), `eval/source_documents.md`, `STATUS.md` (pinned versions).

## Expected output
Parsed pages as `data/parsed/<document>/page-NNN.md` plus a metadata record per page (file, page, parser, parser version, table page yes/no, unreadable yes/no); `reports/parsing-sample.md` with table accuracy, unreadable-page share, pages per minute per tier and the full-corpus time estimate. Parsed page header example: `file: data/corpus/<name>.pdf | page: 12 | parser: pymupdf4llm <version> | table: yes`.

## Verification
Owner reviews 5 sample tables side by side with the original pages.

## Risks
Multi-column layouts reading in wrong order; merged table cells; Word conversion shifting page breaks (citations then refer to the converted PDF, which must be kept and served).
