# Source documents in the corpus (Step 1)

All five are native PDFs hardlinked from `data/raw/` into `data/corpus/` (verified: same inode, `nlink=2`, so no extra disk is used and the originals are untouched — D-030).

| # | Corpus file | Pages | Text chars | Tables found | SHA-256 |
|---|---|---|---|---|---|
| 1 | `0_NARAYAN_Investigation_of_Soil_Liquefaction_in_Kathmandu_Valley_and_R_W7208248247.pdf` | 4 | **0** | 0 | `cac871c39036953c39daf020a603e6650fa71b88f21e9203098733aa477ffd6d` |
| 2 | `1970_Ahasan_Variability_and_Trends_of_Summer_Monsoon_Rainfall_over_Bangl_W2100745337.pdf` | 17 | 43,937 | 3 | `87ff3ffdd8ed03bd630a88db82b15aca4b4086a6c49682e202ed2980f53abbf0` |
| 3 | `1970_Das_Beliefs_superstitions_and_taboos_associated_with_bamboos_in_W1999918290.pdf` | 9 | 34,399 | 6 | `a483da15858555cf0a6106167201bb9ff572f1e4dbb73beb47f80a499ff88cd2` |
| 4 | `1970_Marahatta_Relating_Hydrological_Extremes_with_Area_A_Case_on_Extreme_F_W2121362616.pdf` | 5 | 11,267 | 0 | `1b42e67f590451c37499c5e065b39eb53b3d8497df961e3d8c75656ec6f5eb64` |
| 5 | `1976_Watanabe_On_the_Types_of_Glaciers_in_the_Nepal_Himalayas_and_their_Ch_W2313269276.pdf` | 7 | 6,462 | 0 | `431bdf24f28c4a64c08204c0fe7e2294be30c1654a84ac2b60dbf974db302cd1` |

Sources: #1, #2, #3 are Journal of Hydrology and Meteorology (SOHAM-Nepal) papers; #4 is Marahatta & Bhusal (2009), *Relating Hydrological Extremes with Area*, J. Hydrology and Meteorology 6(1), printed pages 44-48; #5 is Watanabe (1976) on glacier types in the Nepal Himalayas.

## Documents used by the eval set

`eval/questions.jsonl` draws on **#4 Marahatta** (floods and rainfall, 24 questions) and **#3 Das** (tables, 6 questions). Documents #2 Ahasan and #5 Watanabe are deliberately unused as question sources: they act as realistic distractors, so retrieval has to choose between five documents instead of one. #1 NARAYAN contributes no questions.

## Page numbering

Gold pages are always the **physical** PDF page (1-based). Printed page numbers differ per document (Marahatta: physical 1 = printed 44; Das: physical 2 = printed 64), and the offset is not constant, so the physical page is the only safe anchor (D-030).

## Document #1 is a scanned PDF with no text layer

`0_NARAYAN_...pdf` has 4 pages and **0 extractable characters**. Under D-020 it is flagged, not OCR'd. Consequences:

- It cannot supply eval questions, and none were written from it.
- It makes a realistic "unreadable page" case that the Step 7 UI warning (D-021) must report: an answer that is "not found" should say that 4 pages of this file are unreadable, otherwise a missing answer looks like absence of evidence.
- Step 3 must record per-file unreadable page counts in the manifest; this file is the first entry with a non-zero count.

## Table extraction note (for Step 3)

The Das tables are correct in the **text layer** (`Believe in taboos and superstitions 139 69.85 79 37.96 16 39.02`), but PyMuPDF's `page.find_tables()` returns cell text with the decimal point displaced (`7.29` becomes two cells `729` and `.`). Table questions therefore use whole-number counts, and Step 3 must not trust `find_tables()` cell values without normalising that artefact.
