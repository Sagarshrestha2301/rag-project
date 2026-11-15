# Owner checklist

Everything here is yours to decide or do. Nothing in this list has been done by an
agent. Measurements are from this repository and are reproducible with the commands
quoted; nothing here is an estimate dressed up as a number.

## A. Fill in the six decision variables in `apply-owner-actions.ps1`

Each variable starts as `'PENDING'` and the script refuses to run while any of them
is still `'PENDING'`. Set each to `'APPROVE'` or `'REJECT'`. My recommendation and
the one-line evidence are below; the reasoning is in `DECISIONS.md`.

| Variable | Recommendation | One-line evidence |
|---|---|---|
| `$D038` staged corpus growth | APPROVE | Already how it went: the corpus grew Stage A (one document) → Stage B (97 documents, 851 pages), and `EVAL.md` was re-baselined at each growth, which is what the decision asked for. |
| `$D040` generator = your `qwen2.5` 7B, fallback 1.5B | APPROVE | Measured on your card: 496.8 tok/s prompt, 8.6 tok/s generation, 3,505 MiB of 4,096 MiB VRAM peak, oracle 15/30 citations and 22/24 numeric exact. The 7B does not fit with headroom for a reranker, which D-004 already keeps on CPU. |
| `$D042` runtime = Ollama, llama.cpp removed | APPROVE | Same weights, same 3,394-token prompt: Ollama 499.1 tok/s prompt / 9.43 tok/s generation against llama-server 293.1 / 7.46, and the deletion already happened. |
| `$D043` chat UI before Step 7 | APPROVE | The UI exists in `ui/`, answers questions and streams; it is ungrounded until the index is used by Step 5, and it says so on screen. |
| `$D044` page-level BM25 prototype in the UI | APPROVE | 25/26 recall@5 with MRR 0.885 at page level, which is still better than every dense embedding measured so far (best: 23/26, 0.723). It is a prototype, not Step 5. |
| `$D054` embedder = `bge-small-en-v1.5` | **Your call, not mine** (rule 9) | bge and e5 tie on recall@5 (23/26 vs 23/26) and differ by 0.021 MRR; bge wins only on size, 134 MB against 493 MB. The table is in `DECISIONS.md` and `reports/embedder-comparison.md`. |
| `$D039` three-model download | SUPERSEDE with D-040 | You declined the 8.38 GB download; the script writes the "superseded" line D-039 needs, so it never looks like an open question again. |

`$AcceptStep2` stays `$false` unless you consider Step 2 finished: its comparison table
has one measured model by your own instruction, which is the stated deviation in D-040.

## B. Two things only you can do by hand

1. **The 20-page review** — open `artifacts\step3\review.html`, click each PDF link and
   confirm the text shown is the page it claims. 18 of 20 pages were confirmed earlier;
   the 2 that were not are pages with no text layer, so there is nothing to compare by
   eye. Its new pre-triage banner names them and says which rows to look at first.
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
- **Step 4's DoD** still has open boxes (see `STATUS.md`); approving `$D054` fixes only
  the "embedder chosen" box.

## D. After the script

```powershell
git tag                      # step-00-approved, step-01-approved
git log --oneline -3         # two OWNER: commits
```

Then hand the agent the Step 4 sub-task you want next, in the TASK/CONTEXT/OUTPUT form
from `AGENTS.md`.
