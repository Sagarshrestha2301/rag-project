# Step 3 implementation plan (review draft — no code written)

**Status:** plan for your review. Nothing here is built, installed or approved.
Step 3 has no start approval in `APPROVALS.md`, so this document is the only
Step 3 artefact that exists.

Read with: `steps/03-parsing-sample.md`, proposal 13 in `STATUS.md`, D-005
(two-tier parsing), D-020/D-021 (unreadable pages), D-030 (corpus layout).

---

## 0. What is actually in the corpus (measured, not assumed)

| Document | Pages | Characters | Tables | Images |
|---|---|---|---|---|
| NARAYAN (liquefaction) | 4 | **0** by extraction, ~7,000 by OCR | 0 | 1 per page (scan) |
| Ahasan (rainfall trends) | 17 | 43,937 | **3** (p3, p6, p13) | 21 |
| Das (bamboo taboos) | 9 | 34,399 | **6** (p2, p3, p6, and 3 on p9) | 0 |
| Marahatta (hydrological extremes) | 5 | 11,267 | 0 | 92 figures |
| Watanabe (glaciers) | 7 | 6,462 | 0 | 7 |
| **Total** | **42** | ~96k | **9 tables on 7 pages** | — |

Table census, measured 2026-11-14 rather than assumed: PyMuPDF `find_tables`
reports **9** tables, `pdfplumber` reports **6**. The gap is exactly the assembler
case — Das p2, p3 and p6 are found only by PyMuPDF, whose cell text is corrupt.

Two facts that shape the design:

1. **The text layer is clean; table *assembly* is what breaks.** Das page 2's raw
   words include `69.85` intact, but `page.find_tables()` returns the cell as
   `6985\n.` — it merges the number with its decimal point. So the repair must
   happen at word level, not by post-processing the corrupted string.
2. **Printed page numbers ≠ PDF page indices.** Marahatta's 5 physical pages are
   printed 44-48. Every gold page in `eval/questions.jsonl` refers to the PDF
   index, so the manifest must record both and never silently "correct" one to
   the other.

## 1. Module layout

Small, single-purpose files behind one interface, registered in one place
(Code rule 2), because Step 5 will add embedders beside this and Step 8 runs it
at scale.

```
ingest/
  __init__.py
  base.py          # PageResult dataclass + Parser protocol + REGISTRY dict
  text.py          # tier 1: pymupdf4llm per page  (registered name: "pymupdf4llm")
  tables.py        # tier 2: pdfplumber + word-position assembler ("pdfplumber+words")
  ocr.py           # scan fallback: pymupdf4llm(use_ocr=True) ("rapidocr")
  manifest.py      # per-document manifest + page JSONL
  verify.py        # page-number check, table check, throughput report
  cli.py           # python -m ingest.cli build --out index/parsed
```

`base.py` contract — every parser returns the same shape, so adding Docling
later is one file plus one registry line:

```python
@dataclass
class PageResult:
    doc: str            # file name inside data/corpus/
    pdf_page: int       # 1-based index in the PDF  (what eval gold_sources uses)
    printed_label: str  # text as printed on the page, "" if none found
    text: str           # plain text for embedding/BM25
    tables: list[Table] # [{"bbox": [...], "rows": [[cell, ...], ...], "parser": "..."}]
    parser: str         # which tier produced this page
    ocr: bool           # True when the text came from OCR
    chars: int
    notes: list[str]    # e.g. "table detected by find_tables, not pdfplumber"
```

## 2. Which tier runs on which page (decision order)

For each page:

1. Extract the raw word list once (`page.get_text("words")`) — cheap, and every
   later step reads from it.
2. **Scan test**: fewer than 40 characters of text → OCR tier (`ocr.py`), the
   path already proven on NARAYAN in the UI index (~5 s/page, 4 pages, 20 s).
3. **Table test**: does `pdfplumber` find ≥1 table with ≥2 rows and ≥2 columns,
   or does PyMuPDF `find_tables` find one pdfplumber misses? If yes → tier 2.
4. Otherwise tier 1.

This is D-005's rule expressed as code: heavy parsing only on table pages, so
the 0.64 s/page figure stays the cost for 33 of the 42 pages.

## 3. The table assembler (the part worth reviewing closely)

Goal: produce cells whose text is **identical to the words in the PDF**, never
reconstructed from a UI's guess. Three cases, in order.

### Case A — pdfplumber finds the table (6 of 9: Ahasan p3/p6/p13, Das p9 ×3)

Use its `extract_tables()` directly. Measured clean on Das p9: `21.84`, `31.67`,
`78.16`. No assembly, because pdfplumber's line strategy already respects the
ruled grid.

### Case B — PyMuPDF finds the table, pdfplumber does not (3 of 9: Das p2, p3, p6)

This is the corruption case, so cells come from words, not from `find_tables`:

1. Take the table **bbox** from `find_tables()` — the geometry is right even
   though its cell text is not.
2. Collect every word whose centre lies inside the bbox, as `(x0, y0, x1, y1, text)`.
3. **Rows**: sort by `y0`, then merge consecutive words whose vertical centres
   differ by less than `0.5 × median word height` into one row. A tolerance
   relative to word height survives font-size changes inside a table.
4. **Columns**: derive x-boundaries from the *gap structure* of the header row —
   the sorted `x0` positions, keeping gaps wider than `1.2 × median word width`
   as separators. If the header row is itself merged (common in these papers),
   fall back to fixed boundaries from the bbox divided by the modal column count
   across body rows.
5. **Cells**: a word belongs to the column whose `[x_left, x_right)` range
   contains its centre; join words inside a cell with one space; keep the cell
   empty rather than filling from a neighbour.
6. **Never repair digits.** `69.85` stays `69.85` because it was one word.
   This is the whole point of the case: the numeric damage in `find_tables` is
   an assembly bug, so assembling from words cannot reproduce it.

### Case C — neither finds a table

Leave the page as tier 1 text and record `notes: ["no table structure detected"]`.
No hand-built table is ever invented.

### Cell validation (the 100% numeric box)

`verify.py` walks every table cell that matches a number pattern and checks:

- the same token appears in the page's word list (guards against any assembly
  drift), and
- for the 9 tables, against a hand-transcribed reference the owner reviews.

If numeric accuracy is below 100%, the plan is **Docling as the fallback**
(D-005 already allows it) — which means an install plus model download, and
therefore a separate approval. I am not proposing that now, because the
evidence says the failure is assembly and Case B addresses it directly.

## 4. Manifest and page output

Two artefacts per run, both resumable and deterministic:

```
index/parsed/
  manifest.json      # one entry per document
  pages.jsonl        # one line per page, the PageResult above
  tables.jsonl       # one line per table with parser + validation result
```

`manifest.json` per document:

```json
{
  "doc": "1970_Das_Beliefs_superstitions_and_taboos_associated_with_bamboos_in_W1999918290.pdf",
  "sha256": "…", "pages": 9, "text_pages": 9, "ocr_pages": 0,
  "table_pages": [2, 3, 6, 9], "tables": 6,
        "unreadable_pages": [], "printed_labels": {"1": "…"},
  "parser_pages": {"pymupdf4llm": 6, "pdfplumber+words": 3, "rapidocr": 0},
  "seconds": 4.7
}
```

The SHA-256 check runs first and hard-fails, reusing the rule in `eval/SCORE.md`
so re-converted files can never shift a gold page silently.

## 5. Verification (maps 1:1 to the step's boxes)

| DoD box | How it is met on a 5-document corpus |
|---|---|
| 50 docs parsed | **Smoke scope: 5 documents / 42 pages.** Box marked smoke-tested, full pass deferred to Stage B. Needs your agreement. |
| Page numbers verified on 20 random pages | `verify.py` prints `pdf_page`, `printed_label` and the first 80 characters for 20 sampled pages into a review HTML (same pattern as `eval/build_review.py`); you confirm 100% match in the browser. |
| ≥20 tables checked cell by cell | Corpus has **9** tables on 7 pages, so 20 is unreachable here. All 9 are transcribed by hand and compared; box marked "9/9, smoke scope". |
| LibreOffice conversion on 5 Word files | **Cannot be met — the corpus has no `.docx`.** Either you supply 5 Word files, or the box is marked N/A with that reason recorded. |
| Unreadable pages counted and share reported | Manifest counts per file; NARAYAN is 4/4 OCR'd, so the share drops from 9.5% to **0%** read, with OCR provenance recorded. |
| Pages/min per tier + full-corpus estimate | `verify.py` times each tier separately (tier 1, tier 2, OCR) and multiplies up to 100k pages. |
| Parser choice per case recorded | Appended to `DECISIONS.md` as PROPOSED: text pages → pymupdf4llm; pdfplumber-detected tables → pdfplumber; pdfplumber-missed tables → words assembler; scans → RapidOCR. |

## 6. Risks, ranked

1. **Das p2/p6 assembly** — the step's numeric box lives or dies here. Mitigated by
   validating every numeric cell against the word list, and by keeping Docling as
   an approved-fallback rather than a default.
2. **OCR numeric damage** — already observed: `calcite (5-10 %)` extracts as
   `(510 %)`, and the model "corrected" it once. The manifest marks OCR pages, so
   Step 6 can be told to distrust bare numbers from them. Not fixed by DPI (tested
   200 vs 300, identical).
3. **Duplicated OCR logic** — `ui/retrieval.py` already OCRs for the UI index. Step 3
   should own this and the UI should later read `pages.jsonl` instead of its own
   cache. Doing that switch now would be work outside this step, so it is listed as
   a follow-up, not done.
4. **Page-label detection** — guessing printed numbers from page furniture can
   silently produce wrong labels. It only *records* them; nothing downstream
   depends on them.

## 7. Effort and order of work

1. `base.py` + `text.py` + `cli.py` — parse all 42 pages tier 1, write manifest. (~1 h)
2. `tables.py` Case A, then Case B, with the Das pages as the test. (~2 h, the risky part)
3. `ocr.py` wired into the same pipeline. (~30 min, reuse from the UI work)
4. `verify.py` + review HTML + the 9-table transcription. (~1 h, owner review after)
5. Throughput numbers, DoD ticks, `DECISIONS.md` proposal, `STATUS.md` update. (~30 min)

## 8. What I need from you before starting

1. The start approval line in `APPROVALS.md` (step 03).
2. Agreement on **smoke scope** (5 documents, 9 tables) instead of 50 docs.
3. A decision on the Word-files box: supply 5 `.docx`, or mark it N/A.
4. Confirmation that Docling stays uninstalled unless the cell check fails.
