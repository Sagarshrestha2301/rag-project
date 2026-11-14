# Step 4 implementation plan (review draft — no code written)

**Status:** plan for your review. Nothing here is built, installed or approved.
Step 4 has no start approval in `APPROVALS.md`, so this document is the only
Step 4 artefact that exists.

Read with: `steps/04-chunking-embeddings.md`, `STEP3-PLAN.md`, D-003 (hybrid,
LanceDB), D-009 (per-document context), OD-3 (embedder candidates), the parsed
output in `index/parsed/`, `reports/parsing-sample.md`.

---

## 0. What Step 3 actually handed over (measured 2026-11-14)

| Document | Pages | Characters | Tables | Text structure |
|---|---|---|---|---|
| NARAYAN (liquefaction) | 4 | 6,984 | 0 | OCR, mixed Japanese/English |
| Ahasan (rainfall trends) | 17 | 43,337 | 3 | flattened |
| Das (bamboo taboos) | 9 | 34,277 | 6 | flattened |
| Marahatta (hydrological extremes) | 5 | 12,074 | 0 | flattened |
| Watanabe (glaciers) | 7 | 5,844 | 0 | flattened |
| **Total** | **42** | **102,516** | **9** | — |

Table sizes are small: the largest is **1,087 characters / 19 rows** (Das p2), and
all nine fit in one chunk. Field-by-field, `pages.jsonl` gives `doc, pdf_page,
chars, parser, ocr, printed_label, text, tables, notes`, and `tables.jsonl` gives
`doc, pdf_page, table, rows, bbox, parser, headers_from, notes`.

Three facts decide the design, and the first one is a gap I have to own:

1. **The stored text has no structure at all.** `ingest/text.py::normalise()` was
   written for BM25, and it does `re.sub(r"[|#*_`]+", " ", text)` then
   `re.sub(r"\s+", " ", text)`. Measured consequence: **0 heading lines** in the
   whole parsed corpus, no paragraph breaks, no table pipes. Chunking "by
   heading, paragraph and table" (tasks 1-2) needs structure that Step 3 threw
   away. There are 215 matches for a section-numbering pattern in the flattened
   text, and the samples show why a regex cannot recover it: `2015 April
   earthquake provided`, `2 Department of Physics`, `2 December` and
   `1. INtrODUCtION` all score the same. See §1 for the two ways out — **and
   note that Option A has since been implemented, so heading structure now
   exists in `PageResult.blocks` while `text` still has none.**
2. **Tables are structured but caption-less.** The cells are correct (393/393
   numeric tokens verified), and each table carries a `bbox`. What is missing is
   what makes a table retrievable: caption, units, footnotes. They do exist in
   the page text — Ahasan p3 contains `table-1:` (lowercase, hyphenated) — so
   they can be recovered by geometry from the `bbox`, but only if the chunker
   reads the PDF again, not `pages.jsonl`.
3. **Page-level metadata is free and good.** `pdf_page`, `printed_label`
   (Das 63-71, Marahatta 44-47, Watanabe 10-16), the `ocr` flag and the parser
   name all survive. Year and publisher come from the file name and the running
   header: `1970_…`, `Banko Janakari, Vol. 15, No. 2`, `Seppyo, 1976`.

## 1. The structure gap, and the two ways out

**Update, 2026-11-14: Option A is done and verified.** `PageResult.blocks` now
carries line-preserving blocks (38 of 42 pages, median 10 per page; the 4 empty
pages are the OCR ones), running headers/footers are stripped by line from each
page's edge blocks, and the flattened `text` is byte-identical to before. So §3
to §5 below are buildable as written, with three measured corrections: headings arrive in **two
shapes** (8 blocks put the number and title on one line, 34 put the number alone
on the first line with the title beneath it, and most of those 34 are decimal
table cells rather than headings), only **5 of 9 table captions** are recoverable
from blocks (Das p3 and the three p9 tables have none), and the furniture rule
must stay limited to edge blocks or it eats figure axis labels. §3 item 2 has the
numbers and the rule they imply.

**Option A — fix it while Step 3 is still open (recommended).** Step 3 has not
been approved complete: four of its boxes are still open. Its `text` field was
built for BM25 and it is the wrong field for chunking. Add one field to
`PageResult` — `blocks: list[str]`, the line-preserving output of
`page.get_text("blocks")` with running headers/footers removed — and keep the
flattened `text` exactly as it is. Cost: ~30 lines in `ingest/text.py`, one
re-run of `build` (49 s), one extra key in `pages.jsonl`. Nothing downstream
reads `blocks` yet, so no regression is possible. This also keeps chunking out
of the business of re-parsing PDFs that Step 3 already parsed.

**Option B — Step 4 re-reads the PDFs.** `chunk/structure.py` opens each PDF and
rebuilds lines from `page.get_text("dict")` itself. No Step 3 change, but the
corpus is parsed twice by two pieces of code, which is exactly the duplication
Code rule 1 forbids, and any future parser change has to be made in both.

**My recommendation is A**, proposed in `STATUS.md` as an owner decision. The
plan below assumes A; under B, only `chunk/structure.py` changes.

## 2. Module layout

Same shape as `ingest/`: small files behind one interface, registered once
(Code rule 2), because Step 5 adds embedders beside this and Step 8 runs it at
scale.

```
chunk/
  __init__.py
  base.py        # Chunk dataclass + Chunker protocol + REGISTRY
  structure.py   # page blocks -> sections: heading detection, furniture removal
  text.py        # paragraphs -> text chunks        (registered: "text")
  tables.py      # table + caption + units + notes   (registered: "table")
  meta.py        # year, publisher, doc_type, page range, section path
  context.py     # one 2-line LLM summary per document (D-009)
  embed.py       # embedder registry + LanceDB writer
  bench.py       # recall@k / MRR / speed against the eval set
  cli.py         # python -m chunk.cli build | bench
```

`base.py` contract — the fields are exactly the step's "Expected output", no
more:

```python
@dataclass
class Chunk:
    chunk_id: str          # f"{doc_stem}:p{page_start}-{page_end}:{seq:04d}"
    file: str              # name inside data/corpus/
    page_start: int        # PDF index, never the printed label
    page_end: int
    section_path: list[str]  # ["2. Data used and methodology", "Table 1"]
    section_path_source: str = "heading"  # "heading" | "none" (§3 item 3)
    type: str              # "text" | "table"
    text: str              # what gets embedded, prefix included
    caption: str = ""
    units: str = ""
    footnotes: list[str] = field(default_factory=list)
    year: int | None = None
    publisher: str = ""
    doc_type: str = ""     # "journal-article" | "thesis-summary" | ...
    doc_context: str = ""  # the D-009 two-liner
    ocr: bool = False      # inherited from the page
    chunker_version: str = "step4-v1"
```

## 3. Section and paragraph rules (tasks 1-2)

1. **Furniture is already gone (done in Step 3).** `ingest.text.strip_furniture()`
   removes header/footer lines from `blocks` before Step 4 sees them: a line that
   recurs on ≥60% of a document's pages, with digits normalised so the page number
   does not break the match. Measured effect: 137 lines off Ahasan, 172 off Das,
   38 off Marahatta, 50 off Watanabe, 0 off the scan — Ahasan's `M. N. Ahasan,
   Md. A.M. Chowdhary & D. A. Quadir` alone appeared on 17 of 17 pages.

   Two limits to respect rather than rediscover: only lines in a page's **first or
   last block** may become furniture — matching every line deleted **201** lines
   from Watanabe's 7 figure-heavy pages, because repeated axis labels are
   frequent but are content. And matching is exact after digit-normalisation, so
   a header that reflows differently on each page can survive: Watanabe p4 still
   opens with `Seppyo, / Watanabe`. Step 4 must not trust the first block to be
   clean.
2. **Headings come in two shapes, and the rule must handle both.** Measured on
   the real blocks (2026-11-14):
   - **Shape A — number and title on one line: 8 blocks.** Five are real
     (`1. BACKGROUND`, `2. STUDY AREA`, `3. RAINFALL DATA`, `4. ANALYSIS AND
     RESULTS`, `5. CONCLUSION`, all Marahatta); three are the affiliation trap on
     Ahasan page 1 (`1 SAARC Meteorological Research Centre (SMRC), Agargaon,
     Dhaka, Bangladesh`), which looks exactly like a heading to a regex.
   - **Shape B — the number alone on the first line, title beneath: 34 blocks,
     of which only 15 are headings.** All 15 are Ahasan's 14 (`1.`+
     `INTRODUCTION` … `3.9`+`Wet (active) and dry`) plus one Marahatta block whose
     title line is a private-use glyph (`\uf8fa\uf8fb`). The other 19 are decimal
     table cells that the naive pattern reads as numbers: `21.84`/`31.67` on
     Das p9, `0.48`/`0.48` on p3, `54.27`/`50.00` on p2.

   So the rule is: a heading needs an **integer** section number (1-2 digits,
   optional `.`-separated parts — decimals are rejected outright), a title of
   ≤ 12 words, and no terminal period. A shape-B title becomes part of the same
   heading, so `"2."` is never emitted as a section on its own. Reject a title
   that contains a comma or parenthesis *and* sits on page 1 of the document:
   that is the affiliation pattern, the only false positive shape A produced.
   Capitalisation is not a signal at all — the PDF damages it (`DAtA USED AND
   MEtHODOLOGY`, `rESULtS AND DISCUSSION`, `INtrODUCtION`), so a rule that
   requires capitals would silently lose most headings in this corpus.
3. **Sections** are the span between headings; `section_path` accumulates the
   numbered levels (`["2. Data used and methodology", "2.1 Sources"]`). A chunk
   is built from paragraphs of one section only. **No chunk crosses a heading**
   — that box is checked mechanically in `bench.py` by asserting every chunk's
   paragraphs share one `section_path`.

   **Two of the five documents have no headings at all** once the decimal table
   cells are excluded: Das (only table captions and numbered list items) and
   Watanabe (figure labels), plus the four OCR pages. Those chunk by paragraph
   runs with `section_path: []`, and their chunks are labelled
   `section_path_source: "none"` so a later reviewer can tell a real section
   path from a missing one. This is expected, not a bug: a paper with no section
   numbering has no sections to respect.
4. **Sizes — built and measured (2026-11-14).** Target 1,000 characters when
   packing several paragraphs, hard cap 1,500, 15% overlap in whole sentences
   *within* a section only. **A paragraph is never split unless it alone exceeds
   the cap**, which is why the corpus median came out at **1,267 characters**
   rather than 1,000: pages here are made of ~1,200-1,400 character paragraphs and
   cutting one mid-way buys nothing. Measured result over the real corpus: 202
   chunks, mean 1,099, max 1,496, **0 over cap**. The cap wins over the overlap:
   the first implementation let a 1,469-character body carry a 148-character tail
   into 1,617, and the carry is now shortened to fit or dropped.
5. **Prefix.** Every chunk's embedded text starts with
   `"{year} {publisher} | {doc_type} | {section_path} | p{pages}"`. This is task
   1's "prefix every chunk with its section path", and it is what lets a chunk
   from page 6 still say it is about bamboo taboos.
6. **OCR pages** (NARAYAN, 4 pages) get no heading logic: heading detection on
   OCR text is guesswork. They are chunked by paragraph runs and marked
   `ocr=True`, so Step 6 can distrust bare numbers from them (the `calcite
   (5-10 %)` → `(510 %)` case).
7. **Equations.** Marahatta's equations (1)-(4) extract as garbled text, already
   recorded in D-038. They are kept inside their paragraph, never split out.

## 4. How tables get chunked (the part worth reviewing closely)

**Update, 2026-11-14: built as specified, with four corrections the corpus
forced.** `chunk/tables.py` produces 9 table chunks (199 chunks total with 190
text), 5 captions recovered. Bbox exclusion alone was **not enough**: the detected
bbox misses table text on Das p2/p9, a Chi-Square statistics row below table 1 is
table content with only 7% cell words, that row is really a footnote, and blocks
were tracked page-locally while the text chunker filters document-locally. Each is
now a test. Caption search also has to accept `Table 2 Level of beliefs…` (no
colon) and `Table-3: …` (hyphen), not just the colon form assumed below.

**One table is one chunk.** All nine tables fit (largest 1,087 characters), and
a table split across chunks answers nothing — half a table is a wrong answer.
Table chunks do **not** get overlapping text chunks over the same region; the
table content appears once, as a table chunk.

**What the chunk text looks like** — caption, then the grid, then the notes,
because that is the order a reader uses:

```
Table 1 | El Nino / La Nina years used in this study | units: none
| Weak | Moderate | Strong | Weak | Moderate | Strong |
|---|---|---|---|---|---|
| 1963 | 1968 | 1969 | ... |
```

Rules, in order:

1. **Caption.** Lines whose `y1` sits within 60 pt *above* the table `bbox` and
   whose text matches `(?i)^table[\s\-–]?\d+` are the caption. Measured need:
   the actual string is `table-1:` — lowercase with a hyphen — so the regex must
   be case-insensitive and accept `-`/`–`/space; the other styles present are
   `Table 2 Level of beliefs…` (no colon) and `Table-3: Correlation
   coefficients…`. Measured now: **5 of 9** captions are found this way, so four
   tables (Das p3 and the three on p9) get `caption: ""` and are still chunked.
   If nothing matches, `caption` stays `""` and `notes` gets `"no caption
   found above bbox"`. A caption is
   never invented and never taken from the neighbouring figure.
2. **Units.** Taken from the header cells first (`(%)`, `(mm)`, `('000)`, or a
   `Unit`/`Units` cell), then from the caption. Recorded as a string; `""` when
   absent. This matters because Das's tables mix a count with two percentages in
   columns that are currently merged (see 4).
3. **Footnotes.** Lines below the `bbox` down to the next paragraph, matching
   `^(\*|†|‡|Note|Source)` or a bare 1-2 letter marker. Stored as a list and
   appended to the chunk text under `notes:`.
4. **Header row.** The first row is the header when `headers_from == "cells"`
   (true for all 9). It is repeated as the first row of every split piece and
   also written as the caption's second line, so a retrieved chunk is readable
   without its neighbours.
5. **Long tables** (> ~1,500 characters or > 25 rows): split into row groups of
   at most 15 body rows, each piece repeating the header row, each carrying
   `"{caption} (rows 16-30 of 42)"` in its text and `part: "2/3"` in metadata.
   **No table in this corpus triggers this**, so the code path is proven by a
   unit test with a synthetic 60-row table, and the plan says so rather than
   claiming corpus evidence.
6. **Never reformat a cell.** `69.85` stays `69.85`; cells are emitted as
   strings exactly as Step 3 verified them against the page's words. The chunker
   is not allowed to parse numbers, add thousands separators, or re-align.
7. **Known defect, carried forward honestly.** Das p9's three tables are 4×3 in
   `tables.jsonl` but are really 7 columns wide (Count, % of row, % of column per
   group); the sub-columns are merged, values intact in order. The chunker will
   **not** guess a split. It records `notes: ["merged sub-columns, 3 values per
   cell"]` and a `TODO(step-04)`, and the chunk is still usable for retrieval
   because the numbers are all present in reading order.

**Table chunk ordering.** Table chunks are emitted in page order interleaved
with the text chunks of the same page, so a reader scanning the index sees the
document as printed.

## 5. Metadata and the one document context (tasks 3-4)

`meta.py`, all programmatic, no model involved:

| Field | Source | Example (measured) |
|---|---|---|
| `year` | file-name prefix, else the running header | `1970`, `1976` |
| `publisher` | journal line on page 1 | `Banko Janakari, Vol. 15, No. 2`; `Seppyo` |
| `doc_type` | shape of page 1 | `journal-article`, `thesis-summary` (NARAYAN: `Dissertation Summary`) |
| `file` | the corpus file name | `1970_Das_…_W1999918290.pdf` |
| `page_start/end` | from the blocks the chunk was built from | `2-2`, `6-7` |

`context.py` generates **one** 2-line context per document (D-009), not per
chunk: 5 calls to `qwen3.5:4b`, thinking off, temperature 0, max 60 tokens. The
prompt and model tag are recorded in `STATUS.md` and the generated text is stored
once per document in `index/chunks/doc_context.json`. Failure is tolerated: if
the model is not running, `doc_context` stays `""` and the build logs it, because
a missing two-liner must not block chunking.

## 6. Embedder benchmark (task 5) — and the sample-size problem

Candidates, all already supported by the installed `sentence-transformers
6.3.0` (no new library), all 384-dimensional so the comparison is about quality
and speed only:

| Candidate | Size on disk | Why it is a candidate |
|---|---|---|
| `BAAI/bge-small-en-v1.5` | ~130 MB | best-documented small English retrieval model |
| `intfloat/multilingual-e5-small` | ~470 MB | the corpus has one Japanese/English OCR document |
| `sentence-transformers/all-MiniLM-L6-v2` | ~90 MB | the cheap baseline; fast on CPU |

All three are **downloads**, which rule 2 forbids unless the step lists them —
Step 4 task 5 does list benchmarking three embedders, so the downloads are
sanctioned once Step 4 is approved. Each will be fetched deliberately into
`models/` with `HF_HUB_OFFLINE=1` set afterwards, and name, source, version,
SHA-256 and path recorded in `STATUS.md` (rule 6).

Measured for each: **recall@5, recall@10, MRR**, chunks per minute on CPU, and
bytes per chunk on disk. The eval set's gold is *page*-level, so a chunk hit is
scored by mapping the chunk back to its page (deduplicated per page) — the
numbers are therefore comparable with the page-level BM25 prototype in
`ui/retrieval.py` (D-044), which becomes the baseline row.

**The honest caveat, and the biggest decision in this plan.** With 105 chunks
over 42 pages, recall@10 is close to ceiling for any competent embedder, so the
benchmark cannot separate them, and D-038 already says so: Stage B (30-50
documents) is supposed to happen **before** the Step 4 embedder benchmark. The
corpus is still Stage A. So either the benchmark is run now and every number is
labelled **"smoke baseline, embedder choice provisional"**, or the corpus grows
first and the benchmark is run once, meaningfully. My recommendation is to run it
now for the machinery (so the pipeline and the report exist and are proven) and
re-run it after the corpus grows, with the final choice made on Stage B numbers.

## 7. Verification (maps 1:1 to the step's boxes)

| DoD box | How it is met |
|---|---|
| Chunker tested: no chunk crosses a heading; table chunks keep caption/units/footnotes | `bench.py assert` walks every chunk and fails the build if a chunk's paragraphs span two `section_path`s. Caption/units/footnotes presence is asserted for table chunks, and 9/9 tables are inspected by eye in the review sheet. |
| Every chunk has file, page range, section path and metadata | Schema check over all chunks; any missing field fails the build. |
| Embedder comparison table (recall@k, MRR, speed, size) in `DECISIONS.md` | `reports/embedder-comparison.md` + one PROPOSED entry. |
| Embedder chosen; dense-only baseline in `EVAL.md` | One appended row per embedder, dense-only, against the same 30 questions. |
| Index size per 1k pages measured, extrapolated to 100k | Bytes written to LanceDB per 1k chunks, times the measured chunks-per-page, extrapolated. |

Owner inspection: 10 random chunks (3 tables) in `artifacts/step4/review.html`,
same sheet pattern as Step 3.

## 8. Risks, ranked

1. **Heading detection fails and every chunk's `section_path` is wrong.** This is
   the whole-batch failure mode, because the prefix goes into the embedded text.
   Mitigated by the furniture removal, the font-size signal, and an assertion
   that the number of detected sections per document is >1 and <40; the review
   sheet shows 10 chunks so you can see it.
2. **Caption geometry picks up the wrong line** (a figure caption or the running
   header). Mitigated by the 60 pt window and the `table` prefix rule; a miss
   leaves `caption: ""` rather than a wrong caption.
3. **The embedder choice is not identified** at 42 pages (§6). Declared, not
   hidden.
4. **OCR chunks pollute retrieval** with `(510 %)`-class errors. Marked
   `ocr=True` in metadata so Step 5 can down-weight or Step 6 can caveat.
5. **Nothing new needs installing.** `lancedb==0.41.0` and `sentence-transformers==6.3.0` are both already in `requirements.txt`/`requirements.lock.txt` and import cleanly (verified: `lancedb 0.41.0`, torch is the CPU build). The only step-4 additions are the three model folders under `models/`. Without them there is nothing to import.

## 9. Effort and order of work

1. Option A: `blocks` field in `ingest/text.py`, re-run build. (~30 min)
2. `chunk/base.py` + `structure.py` (furniture, headings, sections). (~2 h, the risky part)
3. `chunk/text.py` with the size/overlap/prefix rules. (~1 h)
4. `chunk/tables.py` caption/units/footnotes + the synthetic long-table test. (~2 h)
5. `chunk/meta.py` + `context.py` (5 LLM calls). (~1 h)
6. `chunk/embed.py` + `bench.py`: download 3 models, LanceDB table, the comparison report. (~2-3 h, mostly downloads and runs)
7. Review sheet, DoD ticks, `DECISIONS.md` proposal, `STATUS.md`, commit. (~1 h)

## 10. What I need from you before starting

1. The start approval line in `APPROVALS.md` (step 04).
2. **A decision on §1**: add the line-preserving `blocks` field to Step 3 now
   (while Step 3 is still open), or have Step 4 re-parse the PDFs.
3. **A decision on §6**: run the embedder benchmark now as a labelled smoke
   baseline, or grow the corpus to 30-50 documents first (D-038's own rule).
4. Approval to download the three embedder models (~690 MB total) into
   `models/`, with name, source, version, SHA-256 and path added to `STATUS.md`
   and `HF_HUB_OFFLINE=1` set in the scripts afterwards. No package installs are
   needed — `lancedb 0.41.0` and `sentence-transformers 6.3.0` are already
   installed and importing.
5. How to handle the four Step 3 boxes still open (50 docs, 20 tables, 5 Word
   files, page-number check) — Step 4's sample needs to be a corpus you have
   accepted, not one mid-review.
