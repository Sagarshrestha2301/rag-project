# Manual test questions by category

Seven question types are in the eval set: **fact, exact, table, comparison, summary, notfound, followup**. This sheet gives one question per type to ask in the chat UI by hand, with the answer the corpus actually supports and the citation it should produce.

Every expected answer below was read out of the PDF, not invented: the page named in "Expected citation" was opened and searched for the quoted words. The "Observed 2026-11-15" column is what the running system answered with `qwen3.5:4b`, temperature 0, top-k 4, page-level BM25 over 97 documents / 851 pages.

## How to run one test

1. Start the model and the UI: `.\scripts\launch-llm.ps1`, then `.\scripts\open-chat.ps1 -Start`.
2. Open <http://127.0.0.1:8000> and type the question from the table.
3. Check the answer against **Expected answer** and check the chips under it against **Expected citation**.
4. Click the chip. The PDF must open at that page; confirm the page shows the quoted words.
5. Record pass/fail. A test passes on all three: right answer, right document and page, page text contains the fact.

Citations are chips labelled `[A]`, `[B]`, `[C]`, `[D]` and the answer's bracketed letters must match the chip. Clicking one opens `/pdf/<file>#page=N`.

## The seven categories

| # | Category | Ask this | Expected answer (verified in the PDF) | Expected citation | Observed 2026-11-15 |
|---|---|---|---|---|---|
| 1 | **fact** | In what month and year were Andrew Irvine's partial remains discovered, and where? | September 2024, on the Central Rongbuk Glacier in Tibet; a boot with a sock and the skeletal remains of a foot. | `0_Westaway_Human_Remains_Everest_…_W7130241212.pdf` **p1** — "In September 2024 the National Geographic explorer Jimmy Chin revealed … on the Central Rongbuk Glacier in Tibet" | Pass — answered correctly, chip `[A]` = p1; `/pdf/…` returned 200, page 1 text contains "September 2024" and "Central Rongbuk" |
| 2 | **exact** | What resolution does the National Elevation Data set have? | One arc-second (about 30 metres) for the conterminous US, Hawaii and Puerto Rico; two arc-seconds for Alaska. | `2007_Digital_outlines_and_topography_of_the_glaciers_of_the_American_West_80092.pdf` **p8** — "a resolution of one arc-second (approximately 30 meters)" | Pass — correct, chip `[A]` = p8 |
| 3 | **table** | According to Table 1, what is the USGS name for its derived vector data product? | Digital line graph (DLG). USFS equivalent is "cartographic feature file"; the scanned-map products are DRG (USGS) and Softcopy (USFS). | same USGS report **p9**, Table 1 "Lineage and naming conventions…" | Pass — correct, chip `[A]` = p9 |
| 4 | **comparison** | Which was found first, Irvine's ice axe or Maurice Wilson's body? | The ice axe: Percy Wyn Harris found it in 1933. Wilson's body was found in July 1935, so about two years later. | `0_Westaway_Human_Remains_Everest_…_W7130241212.pdf` **p4** — "In 1933 Percy Wyn Harris … recovering Sandy Irvine's ice axe" and "In July 1935 … the body of Maurice Wilson" | Pass — correct order and years, chip `[A]` = p4 |
| 5 | **summary** | What does the paper argue about human remains on Everest? | Three points: remains move from subject to physical object in the cryosphere; they become "uncanny" and disrupt normal disposal practices; the ice that holds them is framed through climate change. | `0_Westaway_Human_Remains_Everest_…_W7130241212.pdf` **p3** (with p21) | Pass — all three points present, nothing invented; chips `[B]` = p3, `[A]` = p21 |
| 6 | **notfound** | What is the population living in the Bagmati catchment? | Not in the corpus. Expected reply: `NOT FOUND` and one line naming what is missing (the paper gives basin area and flood peaks, no population figures). | nearest page `1970_Marahatta_…_W2121362616.pdf` **p2**, which has the area but no population | Pass with a wording note — refused correctly, but it wrote a sentence of explanation *before* the `NOT FOUND` line; the system prompt asks for `NOT FOUND` first |
| 7 | **followup** (two turns) | Turn 1: question 1. Turn 2: "And who found the ice axe in 1933?" | Percy Wyn Harris. | `0_Westaway_Human_Remains_Everest_…_W7130241212.pdf` **p4** | Pass — resolved the follow-up without repeating the first question, chip `[A]` = p4 |

## Regression pair from the original five documents

Keep testing these two so the old corpus path does not silently break while the new 92 documents are added.

| Category | Ask this | Expected answer | Expected citation |
|---|---|---|---|
| fact | What was the 24-hour rainfall depth recorded at Tistung on 20 July 1993? | 540 mm (482 mm at Ghantemadi, same morning) | `1970_Marahatta_…_W2121362616.pdf` p2 |
| table | According to Table 1, how many Terai households believe in taboos and superstitions associated with bamboos? | 139 households, 69.85% of Terai households | `1970_Das_…_W1999918290.pdf` p2 |

## Known limitation to test, with the answer that is currently correct behaviour

**Legacy-font Nepali reports are unsearchable.** Ask *"What are the objectives of the national forest policy 2075?"*

- The PDF `reports/…/2018_national_forest_policy_2075_efe9910b55.pdf` has a text layer in the old Preeti encoding: page 1 extracts as `/fli6«o jg gLlt @)&% …`, which is "राष्ट्रिय वन नीति २०७५" in a non-Unicode font.
- Expected today: `NOT FOUND` — and that is what happened (it cited an agroforestry policy instead and said the forest policy objectives were missing).
- This is the right failure mode (no invented answer) but the document is effectively absent from retrieval. Fixing it needs a font-decoding or OCR pass, which is not in any approved step yet.

## What a failure looks like

- Answer is right but the chip opens a different page, or the page does not contain the words: **citation bug**, report it with the question and the chip.
- Answer cites a document without the fact, or gives a number the page does not contain: **faithfulness failure**, note the invented value.
- An answerable question returns `NOT FOUND`: **retrieval miss**, note which document should have been found.
- A `NOT FOUND` question is answered from partial text: **false answer**, the worst case.
