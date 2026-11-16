# Owner checklist

Everything here is yours to decide or do. Nothing in this list has been done by an
agent. Measurements are from this repository and are reproducible with the commands
quoted; nothing here is an estimate dressed up as a number.

**Scope:** all 19 decisions that `DECISIONS.md` still lists as `PROPOSED`, one row each.
D-041 is not here because you already rejected it on 2026-11-13, and D-057 was added on
2026-11-16 to withdraw two figures that did not reproduce.

## A. The 19 decisions in `apply-owner-actions.ps1`

Each entry in the `$Decisions` table at the top of the script starts as `'PENDING'`.
Set it to `'APPROVE'`, `'REJECT'` or `'SUPERSEDE'`; the script refuses to run while
anything is `'PENDING'`, because a decision approved by a script is not an approval.
Line numbers are where the entry starts today, before the script inserts its verdict
lines above them.

| Decision | `DECISIONS.md` | Recommendation | One line of evidence |
|---|---|---|---|
| **Step 2 — which model answers** | | | |
| D-039 three-model download | 98 | APPROVE | Two of the three candidates were downloaded and measured after all — `qwen3.5:4b` (3.3 GB) and `phi4-mini` (2.5 GB) — and their rows are in D-047. Gemma 4 E2B was not downloaded. The kit used to say "never downloaded"; that was written before D-047 and is corrected here. |
| D-040 generator = your `qwen2.5` 7B | 96 | APPROVE | Measured on your card: 496.8 tok/s prompt, 8.6 tok/s generation, 3,505 MiB of 4,096 MiB peak. It stands as the 2026-11-13 decision, with D-048 moving the generator on measured evidence. |
| D-046 comparison table, two rows blank | 83 | **SUPERSEDE by D-047** | Its title says two models "never will be" measured. D-047 measured them on 2026-11-14, so approving both would record two contradictory statements. |
| D-047 three-model comparison | 72 | APPROVE | Oracle 23/30 (`qwen3.5` 4B, thinking off), 18/30 (7B), 16/30 (`phi4-mini`); citations 20/30, 15/30, 14/30; first token 3.64 s, 4.77 s, 2.32 s. |
| D-048 switch to `qwen3.5:4b`, thinking off | 82 | APPROVE | 23/30 against 18/30 and 0.9 s faster to first token; this is already how the UI runs, and thinking on returned an empty answer on all 30 questions. |
| **Step 3 — how pages are read** | | | |
| D-045 OCR at index build | 92 | APPROVE | 86 of 851 pages need it, at 16-23 s per 4 pages; 20 pages stay reported as unreadable rather than dropped. |
| D-049 parser per page type | 62 | APPROVE | Filling PyMuPDF's grid from the page's own words fixed `69.85` → `6985 .` and friends: 393/393 numeric tokens on table pages, 5,511/5,520 across the corpus. |
| **Step 4 — chunks, metadata, embedder** | | | |
| D-038 staged corpus growth | 99 | APPROVE | Already how it went: one document, then 97 documents / 851 pages, with the eval re-baselined at each growth. |
| D-050 chunk shape | 100 | APPROVE | 3,226 chunks from 95 documents: section-bounded text, one table per chunk. |
| D-051 heading detection | 101 | APPROVE | Two heading shapes, four trap families rejected; 0 chunks cross a heading across the 16 structure cases. |
| D-052 chunk sizing | 102 | APPROVE | Paragraph-atomic with the cap stronger than the overlap: no chunk ends mid-sentence, 0 bad page ranges. |
| D-053 one table = one chunk, table text excluded | 103 | APPROVE | 268 table chunks; table text is kept out of prose chunks by geometry *and* content, so one number cannot be retrieved twice. |
| D-054 embedder = `bge-small-en-v1.5` | 104 | APPROVE — **yours alone**, rule 9 | Ties `multilingual-e5-small` on recall@5 (23/26 each), differs by 0.021 MRR (0.702 vs 0.723), and is 134 MB against 493 MB. |
| D-055 captions, units, footnotes | 113 | APPROVE | Captions 32 → 37 and units 37 → 52 of 268 table chunks; 210 detected tables print no caption within 160 points, and each such chunk says so. |
| **Step 5 — retrieval** | | | |
| D-056 keep page BM25, reject the hybrid | 115 | APPROVE | Over 79 saved configurations: page BM25 alone 25/26 at MRR 0.885, best fusion 23/26 at 0.432, no fusion beats the baseline. The hybrid stays as evidence in `retrieval/`. |
| D-057 withdraw two figures from D-056 | end of file | APPROVE | D-056 quoted 24/26 at 0.832 and 24/26 at 0.486; neither reproduces and neither had an artifact. The saved sweep replaces them and the decision is unchanged. |
| **Runtime and UI** | | | |
| D-042 runtime = Ollama | 95 | APPROVE | Same weights, same prompt: 499.1 tok/s prompt and 9.43 tok/s generation against llama-server's 293.1 and 7.46. |
| D-043 chat UI before Step 7 | 94 | APPROVE | The UI answers and streams, and says on screen when an answer is ungrounded instead of pretending to cite. |
| D-044 page-level BM25 prototype in the UI | 93 | APPROVE | 25/26 at MRR 0.885, better than every dense embedding measured so far (best 23/26 at 0.723). |

**The one judgement call in the table.** Every row is `APPROVE` except D-046, which is
`SUPERSEDE by D-047`. If you want D-046 recorded as approved as well, change that one
entry to `'APPROVE'` — the script will write it, and the record will then contain both
the claim and its correction.

`$AcceptStep2`, `$AcceptStep4` and `$AcceptStep5` are all `$true`, so the run also
records the completion of steps 02, 04 and 05 and tags `step-02-approved`,
`step-04-approved` and `step-05-approved`: Step 2's five DoD boxes are ticked and the
comparison you asked for exists, Step 4 was built, measured and inspected (your 10-chunk
review, approved in chat 2026-11-16), and Step 5's seven boxes are all ticked with the
baseline re-based on the 45-question dev set.

## B. Two things only you can do by hand

1. **The 20-page review** — open `artifacts\step3\review.html`, click each PDF link and
   confirm the text shown is the page it claims. 18 of 20 pages were confirmed earlier;
   the 2 that were not are pages with no text layer, so there is nothing to compare by
   eye. Its pre-triage banner names them and says which rows to look at first.
2. **The 20-table review** — open `artifacts\step3\tables-review.html`. The corpus holds
   242 detected tables and the page offers 5 to check cell by cell; 116 of 144 numeric
   cells on the checked pages matched (80.6%), and every miss is in one legacy-font
   (Preeti) table, which the pre-triage banner is marked for extra attention.

Then tick the Step 3 boxes (`steps/03-parsing-sample.md`) that your review confirms, and
only those. Two of the remaining three DoD boxes are the two reviews above; the third,
the Word-conversion box, cannot be met at all because the corpus holds no `.docx` —
`step-file-edits.patch` removes it, and applying that patch is your edit to make.

## C. What I could not verify for you

- **Page numbers on the 2 OCR pages**: OCR gives text but not a printed page number, so
  "100% match" cannot be shown for them by eye. They stay unconfirmed rather than assumed.
- **The Preeti table**: the values extract as legacy-font glyphs (`/fli6«o jg gLlt`), so
  the 4 of 32 missing cells cannot be checked without reading the printed page yourself.
- **Whether D-048 should have been D-040 edited instead**: rule 9 keeps existing entries
  untouched, so the change is recorded as a new decision that supersedes, never as a
  rewrite of the old one.

## D. After the script

```powershell
git tag                      # step-00, 01, 02, 04 and 05 -approved
git log --oneline -3         # two OWNER: commits
git status                   # clean
```

The run also adds **two `completion` lines** to `APPROVALS.md`, for steps 04 and 05, so
neither stays a step that was finished but never recorded, and the **start line for
step 06** (`$StartStep6`, `$true` by default), which is what opens the next step. A start
creates no tag: Step 6 gets `step-06-approved` only when its own definition of done is
finished.

Expect **19 verdict lines** in `DECISIONS.md` — 18 `APPROVED` and 1 `SUPERSEDED D-046 by
D-047` — each placed directly *above* the entry it answers, so the entry keeps its body.

Then hand the agent the Step 4 sub-task you want next, in the TASK/CONTEXT/OUTPUT form
from `AGENTS.md`. Steps 6-9 still have no start line and no approval, and Step 5's DoD is
not finished: the seven boxes in `steps/05-hybrid-retrieval.md` remain open.
