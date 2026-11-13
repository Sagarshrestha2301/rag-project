# Source documents used by the eval set (Step 1)

Stage A of the staged corpus plan: one document, used as a plumbing test.

| # | Corpus file | Type | SHA-256 | Pages | Printed pages |
|---|---|---|---|---|---|
| 1 | `data/corpus/1970_Marahatta_Relating_Hydrological_Extremes_with_Area_A_Case_on_Extreme_F_W2121362616.pdf` | native PDF, hardlinked from `data/raw/` | `1b42e67f590451c37499c5e065b39eb53b3d8497df961e3d8c75656ec6f5eb64` | 5 | 44-48 |

**Citation:** Marahatta, S. and Bhusal, J. K. (2009). *Relating Hydrological Extremes with Area - A Case on Extreme Floods in South Central Nepal.* Journal of Hydrology and Meteorology, Vol. 6, No. 1, SOHAM-Nepal.

## Provenance

- Hardlink from `data/raw/` into `data/corpus/`, verified in Step 0: same inode, `links=2`, so no extra disk is used and the original is untouched (D-030).
- Physical PDF page numbers are 1-5; the printed page numbers are 44-48, an offset of 43. Gold pages in `eval/questions.jsonl` are always the **physical** page (D-030, `EVAL.md`).
- Every gold source in the eval set points at this file with the SHA-256 above. A mismatch must stop the scorer.

## Known limitations of this document for eval purposes

Recorded so no later step mistakes the results for accuracy:

1. **No tables.** The paper has figures and equations but no real tables, so the six "table lookup" questions required by the composition in `EVAL.md` cannot be built from this document.
2. **Equations extract as garbled text.** Equations (1)-(4) come out as character soup from the text layer; questions must be about what the surrounding prose says about the equations, not about reading the equations themselves.
3. **Dropped spaces.** The text layer loses some spaces ("duringthe", "byfloods"), which will hurt BM25 matching. This is a parsing-quality observation for Step 3, not an eval question.
4. **Figures 4-6 are images** with no extractable text, so no questions may depend on them.
5. **Only 5 pages.** recall@k is close to 100% whatever the retrieval method does, so any result from this set is a **smoke baseline**, never an accuracy figure.
