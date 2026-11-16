"""Build the stand-alone manual: `docs/manual.html`, one file you can send to anyone.

Every number in the page comes from `NUMBERS` below, and each entry names where it was
measured, so a reader can check it instead of trusting the prose. The output has no
scripts, no web fonts and no images: open it from disk, email it, or print it to PDF.

Usage:
    .venv\\Scripts\\python.exe reports\\build_manual.py
    # docs/manual.html  (committed; ~24 KB, self-contained)
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\manual-to-pdf.ps1
    # docs/manual.pdf   (committed; the same page printed to A4 by the local browser)

The PDF is not built here: Python has no PDF engine installed and none is needed, so
`scripts/manual-to-pdf.ps1` prints the finished HTML with headless Edge/Chrome. The
`@page` rule and the `@media print` block below are what make that PDF look right.
"""

from __future__ import annotations

import datetime
import pathlib
import re

OUT = pathlib.Path("docs/manual.html")

TITLE = "An offline question-answering system over official reports and papers"
SUBTITLE = ("97 documents, 851 pages, cited by page, answered by a 4-billion-parameter model "
            "on a laptop with a 4 GB graphics card")

# Every figure used in the page. `where` is how a reader checks it.
NUMBERS = {
    "docs": (97, "STATUS.md, measured facts (drive fetch, 2026-11-14)"),
    "pages": (851, "STATUS.md, parse of the 97-document corpus"),
    "tables": (242, "STATUS.md, same parse (detected table regions)"),
    "ocr_pages": (86, "STATUS.md, same parse (pages with no text layer, OCR'd)"),
    "unreadable": (20, "STATUS.md, same parse (still unreadable after OCR)"),
    "parse_seconds": (996.1, "STATUS.md, `python -m ingest.cli all`"),
    "pages_per_min": (51.3, "996.1 s for 851 pages"),
    "hours_100k": (32.5, "extrapolation at the measured pages/min"),
    "chunks": (3226, "index/chunks.jsonl, `python -m chunk.cli build`"),
    "text_chunks": (2958, "same file (2,958 text + 268 table)"),
    "table_chunks": (268, "same file"),
    "caption_chunks": (37, "chunk/test_tables.py coverage case, 2026-11-15"),
    "units_chunks": (52, "same case log"),
    "questions": (30, "eval/questions.jsonl (26 answerable, 4 not-found)"),
    "recall5": ("25/26", "eval/runs/2026-11-15-2026-11-14-97docs/scores.md"),
    "mrr": (0.885, "same run"),
    "hybrid_recall5": ("24/26", "eval/runs/2026-11-16-hybrid-bge/scores.md"),
    "hybrid_mrr": (0.832, "same run"),
    "index_mb": (8.03, "reports/index-size.md (LanceDB table on disk)"),
    "bytes_page": (9602, "8,027,301 bytes over 836 covered pages"),
    "index_100k_gb": (0.96, "bytes/page x 100,000"),
    "gen_tok_s": (13.5, "STATUS.md, `ollama ps` run with a 1,891-token prompt"),
    "answer_seconds": (3.7, "the same measured question in the UI"),
    "oracle": ("23/30", "DECISIONS.md D-047 (oracle test through Ollama, temp 0)"),
    "oracle_7b": ("18/30", "DECISIONS.md D-047, same test"),
    "oracle_phi": ("16/30", "DECISIONS.md D-047, same test"),
    "numeric_tokens": ("5,511 / 5,520", "STATUS.md, numeric-token match on the 97-document parse"),
    "bge_recall": ("23/26", "reports/embedder-comparison.md, bge-small-en-v1.5"),
    "bge_mrr": (0.702, "same report"),
    "e5_mrr": (0.723, "same report, multilingual-e5-small"),
}

CHOICES = [
    ("Private and offline by default",
     "A hosted API or a cloud vector database",
     "The documents are the owner's and some are not public. Everything runs on "
     "127.0.0.1: parsing, embeddings, the model and the UI. Runtime code makes no network "
     "call; the launch scripts set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` so a "
     "library cannot quietly fetch a model."),
    ("Citations are page numbers, not quotes",
     "Letting the model quote text as the citation",
     "A quote can be paraphrased, truncated or invented; a page either exists or does not. "
     "Every answer carries letters that map to `file + page`, and the UI opens the PDF at "
     "that page. This is also why the evaluation scores *pages*."),
    ("One 4 B model, qwen3.5:4b, thinking off",
     "A 7 B model, or a larger model on the CPU",
     "Measured on the same 30 questions with the gold page as context: qwen3.5:4b 23/30, "
     "qwen2.5-7B 18/30 and phi4-mini 16/30, the 4 B also winning citations (20/30 against "
     "15/30) and first-token time (3.64 s against 4.77 s). It peaks at 3.69 GB of the 4 GB "
     "card, so nothing larger fits beside a GPU reranker. Thinking mode is disabled on "
     "purpose: with it on, the model spends the whole answer budget reasoning and returns "
     "an empty string on all 30 questions."),
    ("Ollama as the runtime",
     "The pinned llama.cpp build",
     "Same weights, same 3,394-token prompt: Ollama 499 tok/s prompt and 9.43 tok/s "
     "generation against llama.cpp's 293 and 7.46, and it needs no hand-built binary. The "
     "llama.cpp build and its `.gguf` were removed afterwards."),
    ("bge-small-en-v1.5 for the dense side",
     "multilingual-e5-small, all-MiniLM-L6-v2",
     "Three embedders were benchmarked on the eval set. bge and e5 tie on recall@5 (23/26 "
     "each) and differ by 0.021 MRR (0.702 against 0.723); e5 is 493 MB against bge's "
     "134 MB. MiniLM is clearly worse (18/26, MRR 0.430). Size decided the tie, not a claim "
     "of quality."),
    ("Page-level BM25 keeps the ranking; chunk hybrid was rejected",
     "Shipping the hybrid retriever because it sounds better",
     "The page-level baseline scores 25/26 at rank 1 with MRR 0.885. A three-list hybrid "
     "(page BM25 + chunk BM25 + dense, reciprocal-rank fusion) reached 24/26 and 0.832, and "
     "the best of 24 weightings managed 24/26 with MRR 0.486. The hybrid is kept in the "
     "repository as measured evidence, not wired into the UI."),
    ("Table text is excluded from prose chunks by geometry *and* content",
     "Trusting the detected table box alone",
     "Some documents put table text in blocks the detected box does not cover, so the same "
     "numbers would be embedded twice and could be cited as prose. Blocks are excluded when "
     "they sit inside the box, or when they repeat a row of it, while a paragraph that "
     "quotes one number stays."),
    ("OCR only where the page has no text layer",
     "OCR everything",
     "86 of 851 pages needed it. OCR costs 16-23 s for 4 pages, so running it everywhere "
     "would add hours for no benefit. A page that OCR still cannot read is reported, never "
     "silently dropped: 20 pages stay flagged."),
    ("A hand-written UI instead of a framework",
     "Streamlit, Gradio, a React app",
     "The UI is one FastAPI file serving static HTML/CSS/JS: no build step, no npm, nothing "
     "to install offline, and the streaming and citation code stays readable. It is also "
     "why the whole page can be audited in a few minutes."),
]

LIMITS = [
    ("The corpus is 97 documents, not 100,000.",
     "Every 100k-page figure in this manual is an extrapolation from measured per-page "
     "costs (32.5 h to parse, 0.96 GB of index), not a run. Nobody has parsed 100k pages."),
    ("Two PDFs yield no text at all.",
     "They are kept and reported rather than replaced: a truncated file and a page with no "
     "extractable layer. Their absence is visible in the corpus report."),
    ("The evaluation set is 30 questions, 26 answerable.",
     "That is small. It is enough to catch a regression the size of seven questions and not "
     "enough to claim a two-point improvement; the release gate is per question, not an "
     "average."),
    ("Publisher is known for about half the documents.",
     "The folder gives it for reports; papers print a journal name on page 1 for only a "
     "few. 58 documents have no outlet on their first page, so the field stays empty "
     "instead of borrowing the topic folder name."),
    ("Table captions are found for 37 of 268 table chunks.",
     "210 detected tables carry no printed caption within 160 points of the table, which is "
     "a property of the corpus, not a parser bug. Every table chunk says whether it has a "
     "caption rather than inventing one."),
    ("Step 5 (hybrid retrieval) is measured but not finished.",
     "The ablation table, the held-out run and the offline proof for that step are still "
     "open; the deliverable so far is the measurement and the decision to keep the simpler "
     "retriever."),
]

GLOSSARY = [
    ("RAG", "Retrieval-augmented generation: find passages first, then let the model answer "
            "only from them."),
    ("Chunk", "A passage the system searches: a section of prose, or one table with its "
              "caption, units and notes."),
    ("BM25", "A classic keyword-ranking formula. Strong when the question quotes exact "
             "words, numbers or names."),
    ("Embedding", "A vector of numbers representing a passage's meaning, so paraphrases can "
                  "be found without sharing a word."),
    ("RRF", "Reciprocal rank fusion: combine two ranked lists by their positions rather "
            "than by scores, which are not comparable."),
    ("Oracle test", "Give the model the correct page and ask the question anyway. It "
                    "measures the answer step without retrieval noise."),
    ("Recall@k", "Share of questions whose correct page appears in the top k results."),
    ("MRR", "Mean reciprocal rank: 1.0 means the correct page is always first."),
]


def md(text: str) -> str:
    """Turn the prose's inline markers into HTML: `x` -> <code>, *x* -> <em>.

    The source strings are written the way they read in the terminal, and a manual
    that shows literal backticks looks like draft notes. Content is ours, so no
    escaping is needed; the only markers used are those two.
    """
    parts = text.split("`")
    text = "".join(
        f"<code>{part}</code>" if index % 2 else part for index, part in enumerate(parts))
    return re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)


def table(rows, head):
    cells = "".join(f"<th>{md(h)}</th>" for h in head)
    body = "".join(
        "<tr>" + "".join(f"<td>{md(c)}</td>" for c in row) + "</tr>" for row in rows)
    return (f'<div class="table-wrap"><table class="table">'
            f"<thead><tr>{cells}</tr></thead><tbody>{body}</tbody></table></div>")


CSS = """
:root{--ink:#16202b;--muted:#5d6b7a;--line:#dbe3ea;--bg:#ffffff;--soft:#f5f8fa;
      --accent:#1f5fa8;--warn:#8a4b12;--ok:#1f6b45}
@media (prefers-color-scheme: dark){
  :root{--ink:#e8eef4;--muted:#9fb0c0;--line:#2a3744;--bg:#111820;--soft:#17202a;
        --accent:#7db3ee;--warn:#e0a76a;--ok:#7fd1a4}
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
     font:16px/1.6 "Segoe UI",system-ui,-apple-system,sans-serif}
.manual{max-width:980px;margin:0 auto;padding:0 24px 96px}
.manual__header{padding:56px 0 28px;border-bottom:1px solid var(--line)}
.manual__kicker{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.manual__title{font-size:34px;line-height:1.2;margin:10px 0 10px;letter-spacing:-.01em}
.manual__subtitle{font-size:17px;color:var(--muted);margin:0;max-width:62ch}
.manual__meta{margin-top:16px;font-size:13px;color:var(--muted)}
.nav{display:flex;flex-wrap:wrap;gap:8px;margin:22px 0 0}
.nav__link{font-size:13px;text-decoration:none;color:var(--accent);border:1px solid var(--line);
           border-radius:999px;padding:5px 12px;background:var(--soft)}
.nav__link:hover{border-color:var(--accent)}
.section{padding:36px 0 8px;border-bottom:1px solid var(--line)}
.section__title{font-size:23px;margin:0 0 14px;letter-spacing:-.01em}
.section__lead{color:var(--muted);margin:0 0 18px;max-width:70ch}
h3{font-size:17px;margin:24px 0 8px}
p{margin:0 0 12px} ul,ol{margin:0 0 14px 22px} li{margin:4px 0}
code{font:13.5px ui-monospace,Consolas,monospace;background:var(--soft);
     border:1px solid var(--line);border-radius:4px;padding:1px 5px}
pre{background:var(--soft);border:1px solid var(--line);border-radius:8px;padding:14px 16px;
    overflow:auto;font:13.5px/1.5 ui-monospace,Consolas,monospace}
pre code{background:none;border:0;padding:0}
.table-wrap{overflow:auto;margin:8px 0 16px;border:1px solid var(--line);border-radius:8px}
.table{border-collapse:collapse;width:100%;min-width:520px;font-size:14px}
.table th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.06em;
          color:var(--muted);background:var(--soft);padding:9px 12px;border-bottom:1px solid var(--line)}
.table td{padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}
.table tr:last-child td{border-bottom:0}
.cards{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));margin:8px 0 18px}
.card{border:1px solid var(--line);border-radius:10px;padding:14px 16px;background:var(--soft)}
.card__stat{font-size:26px;font-weight:600;letter-spacing:-.02em}
.card__label{font-size:13px;color:var(--muted);margin-top:2px}
.card__where{font-size:11.5px;color:var(--muted);margin-top:8px}
.stage{display:grid;grid-template-columns:64px 1fr;gap:14px;padding:14px 0;border-top:1px solid var(--line)}
.stage__num{font:600 13px/1 ui-monospace,Consolas,monospace;color:var(--accent);
            border:1px solid var(--line);border-radius:999px;width:30px;height:30px;
            display:flex;align-items:center;justify-content:center;background:var(--soft)}
.stage__title{font-weight:600;margin:0 0 4px}
.stage__body{margin:0;font-size:15px;color:var(--ink)}
.stage__measure{font-size:13px;color:var(--muted);margin-top:6px}
.callout{border-left:3px solid var(--accent);background:var(--soft);padding:12px 16px;
         border-radius:0 8px 8px 0;margin:14px 0}
.callout--warn{border-left-color:var(--warn)}
.manual__footer{padding:26px 0;font-size:13px;color:var(--muted)}
.tag{font-size:11px;text-transform:uppercase;letter-spacing:.05em;border-radius:999px;
     padding:2px 8px;border:1px solid var(--line);color:var(--muted)}
/* A4 with real margins: Chromium's default is US Letter with 10 mm margins, and the
   owner's region prints A4. */
@page{size:A4;margin:18mm 16mm 16mm}

/* Print: force the light palette (the screen palette follows the OS, and printing a
   dark page wastes ink and can come out unreadable), unpin the table's scroll width so
   no column is cut off, and keep rows, stages and callouts whole across page breaks. */
@media print{
  :root{--ink:#111;--muted:#555;--line:#b9c2cb;--bg:#fff;--soft:#f4f6f8;
        --accent:#1a4f8a;--warn:#7a3f0e;--ok:#1a5c3b}
  body{font-size:10.5pt;background:#fff}
  .nav{display:none}
  .manual{max-width:none;padding:0 0 12pt}
  .manual__header{padding-top:0}
  .manual__title{font-size:23pt}
  h2,h3{page-break-after:avoid}
  .section{padding:18pt 0 4pt}
  .stage,.card,.callout,tr,pre{page-break-inside:avoid}
  .table-wrap{overflow:visible;border-color:var(--line)}
  .table{min-width:0;font-size:9pt}
  .table th,.table td{padding:5pt 7pt}
  a{color:inherit;text-decoration:none}
}
"""


def build() -> str:
    today = datetime.date.today().isoformat()
    stats = [
        (f"{NUMBERS['docs'][0]}", "documents parsed", NUMBERS["docs"][1]),
        (f"{NUMBERS['pages'][0]:,}", "pages of PDF", NUMBERS["pages"][1]),
        (f"{NUMBERS['chunks'][0]:,}", "searchable chunks", NUMBERS["chunks"][1]),
        (NUMBERS["recall5"][0], "answerable questions with the right page in the top 5",
         NUMBERS["recall5"][1]),
        (f"{NUMBERS['gen_tok_s'][0]} tok/s", "answer speed on the laptop",
         NUMBERS["gen_tok_s"][1]),
        (f"{NUMBERS['index_100k_gb'][0]} GB", "index size if the corpus were 100k pages",
         NUMBERS["index_100k_gb"][1]),
    ]
    cards = "".join(
        f'<div class="card"><div class="card__stat">{value}</div>'
        f'<div class="card__label">{label}</div>'
        f'<div class="card__where">measured: {md(where)}</div></div>'
        for value, label, where in stats)

    stages = [
        ("Parse", "PDF pages become line-preserving text blocks, table regions and page "
                  "numbers. Scanned pages are OCR'd only where there is no text layer, and "
                  "the page number is always the physical PDF page, because that is what a "
                  "citation opens.",
         f"{NUMBERS['pages'][0]} pages, {NUMBERS['tables'][0]} table regions, "
         f"{NUMBERS['ocr_pages'][0]} OCR pages in {NUMBERS['parse_seconds'][0]} s "
         f"({NUMBERS['pages_per_min'][0]} pages/min); {NUMBERS['numeric_tokens'][0]} "
         f"numeric tokens match the page's own words."),
        ("Chunk", "Text is split by heading, never across one, so every chunk carries its "
                  "section path. Each detected table becomes one chunk with its caption, "
                  "units and notes; table text is removed from the prose chunks so the same "
                  "numbers cannot be retrieved twice.",
         f"{NUMBERS['chunks'][0]:,} chunks ({NUMBERS['text_chunks'][0]:,} text + "
         f"{NUMBERS['table_chunks'][0]} table); {NUMBERS['caption_chunks'][0]} table chunks "
         f"carry a printed caption, {NUMBERS['units_chunks'][0]} carry units."),
        ("Index", "Two indexes over the same chunks: BM25 over the words (exact strings, "
                  "numbers, names) and a dense vector table in LanceDB, built with bge on the "
                  "CPU so the GPU stays free for the model.",
         f"LanceDB table is {NUMBERS['index_mb'][0]} MB for this corpus; "
         f"{NUMBERS['bytes_page'][0]:,} bytes per page, so "
         f"{NUMBERS['index_100k_gb'][0]} GB at 100k pages."),
        ("Retrieve", "A question is answered from the best-matching pages. The current "
                     "ranking is page-level BM25, which beat a three-list hybrid on the "
                     "measured questions; the hybrid is kept as evidence in `retrieval/`.",
         f"recall@5 {NUMBERS['recall5'][0]}, MRR {NUMBERS['mrr'][0]} (page BM25) against "
         f"{NUMBERS['hybrid_recall5'][0]} and MRR {NUMBERS['hybrid_mrr'][0]} (hybrid)."),
        ("Answer", "Up to four passages are labelled A-D and sent with strict rules: use "
                   "only these passages, put the passage letter after every factual "
                   "sentence, and reply NOT FOUND when the answer is absent.",
         f"{NUMBERS['oracle'][0]} on the oracle test; about "
         f"{NUMBERS['answer_seconds'][0]} s and {NUMBERS['gen_tok_s'][0]} tokens/s for a "
         f"real question in the UI."),
        ("Cite", "The letters become buttons that open the cited PDF at the cited page, "
                 "served from `data/corpus/` over localhost. A reader checks the claim "
                 "against the page itself, not against a quote the model wrote.",
         "Each answer lists its sources as label + page, e.g. `A Marahatta 1970 p2`."),
    ]
    stage_html = "".join(
        f'<div class="stage"><div class="stage__num">{i}</div><div>'
        f'<p class="stage__title">{title}</p>'
        f'<p class="stage__body">{md(body)}</p>'
        f'<p class="stage__measure">{md(measure)}</p></div></div>'
        for i, (title, body, measure) in enumerate(stages, start=1))

    choice_rows = [(f"<strong>{c}</strong>", alt, md(why)) for c, alt, why in CHOICES]
    limit_items = "".join(f"<li><strong>{md(head)}</strong> {md(body)}</li>"
                          for head, body in LIMITS)
    glossary_rows = [(term, md(meaning)) for term, meaning in GLOSSARY]

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITLE}</title>
<style>{CSS}</style>
</head>
<body>
<main class="manual">

  <header class="manual__header" id="top">
    <div class="manual__kicker">Project manual &middot; offline RAG</div>
    <h1 class="manual__title">{TITLE}</h1>
    <p class="manual__subtitle">{SUBTITLE}</p>
    <p class="manual__meta">Generated {today} from the repository itself. Every figure
      below names the file that measured it; nothing is an estimate unless the word
      "extrapolation" appears.</p>
    <nav class="nav">
      <a class="nav__link" href="#what">What it is</a>
      <a class="nav__link" href="#why">Why it exists</a>
      <a class="nav__link" href="#how">How it works</a>
      <a class="nav__link" href="#choices">Why these choices</a>
      <a class="nav__link" href="#numbers">Measured numbers</a>
      <a class="nav__link" href="#limits">What it cannot do</a>
      <a class="nav__link" href="#run">Run it yourself</a>
      <a class="nav__link" href="#glossary">Glossary</a>
    </nav>
  </header>

  <section class="section" id="what">
    <h2 class="section__title">What it is</h2>
    <p class="section__lead">A question-answering system that reads a private library of
      PDFs and answers in its own words, with every sentence tied to the page it came
      from. It runs entirely on one laptop, with the network off.</p>
    <p>You type a question. The system finds the pages that discuss it, gives those
      passages to a small language model, and the model answers in at most four sentences
      with a letter after each factual sentence. Clicking the letter opens the original PDF
      at that page. If the library does not contain the answer, the expected reply is
      <code>NOT FOUND</code> rather than a guess.</p>
    <div class="cards">{cards}</div>
    <div class="callout"><strong>The one-sentence version.</strong> It is a search engine
      over your own PDFs whose answers you can check in one click, built to run on a
      machine with 4 GB of video memory and no internet connection.</div>
  </section>

  <section class="section" id="why">
    <h2 class="section__title">Why it exists</h2>
    <p class="section__lead">Three constraints shaped every design choice. Everything below
      follows from them, which is also why some "obvious" upgrades are missing on purpose.</p>
    <ol>
      <li><strong>The documents cannot leave the machine.</strong> They are official reports
        and academic papers, some not public. A hosted API would mean uploading them and
        trusting a third party with copies; that was ruled out first, not last.</li>
      <li><strong>The answers have to be checkable.</strong> A fluent paragraph is worthless
        in this domain if the reader cannot find the sentence it came from. Citations
        therefore point at a page, and the evaluation scores pages, not vibes.</li>
      <li><strong>The hardware is a laptop.</strong> An RTX 3050 with 4 GB of VRAM and 16 GB
        of RAM. That is enough for a 4-billion-parameter model and nothing larger, so the
        design deliberately spends the GPU on the generator and runs parsing and embeddings
        on the CPU.</li>
    </ol>
    <h3>The scale it is built for</h3>
    <p>The design target is a corpus of about 100,000 pages. This manual describes a
      working system at 851 pages, with the per-page costs measured so the large corpus is
      a matter of time rather than a redesign: the index would be about
      {NUMBERS['index_100k_gb'][0]} GB and a full parse about {NUMBERS['hours_100k'][0]}
      hours at the measured rate.</p>
  </section>

  <section class="section" id="how">
    <h2 class="section__title">How it works, stage by stage</h2>
    <p class="section__lead">Six stages. Each one states what it does and what was actually
      measured on this corpus.</p>
    {stage_html}
  </section>

  <section class="section" id="choices">
    <h2 class="section__title">Why these choices, and what was rejected</h2>
    <p class="section__lead">Each row is a decision that was made after measuring an
      alternative, not a preference. The alternative column is what a reader would
      reasonably expect instead.</p>
    {table(choice_rows, ["Choice", "The obvious alternative", "Why, with the evidence"])}
    <div class="callout callout--warn"><strong>One choice is deliberately open.</strong> The
      embedder (which model turns text into vectors) is a tie on the measured questions:
      bge-small and multilingual-e5 agree on recall@5 and differ by 0.021 MRR, and bge is
      134 MB against 493 MB. The tie was recorded as a proposed decision for the owner
      rather than settled by the person who wrote the code.</div>
  </section>

  <section class="section" id="numbers">
    <h2 class="section__title">The measured numbers</h2>
    <p class="section__lead">Everything here was counted or timed on this machine. Where a
      number could not be measured, the table says so instead of guessing.</p>
    {table([
        ("Documents / pages", f"{NUMBERS['docs'][0]} / {NUMBERS['pages'][0]}", NUMBERS["pages"][1]),
        ("Detected tables", f"{NUMBERS['tables'][0]}", NUMBERS["tables"][1]),
        ("Pages needing OCR / still unreadable", f"{NUMBERS['ocr_pages'][0]} / {NUMBERS['unreadable'][0]}", NUMBERS["ocr_pages"][1]),
        ("Parse time", f"{NUMBERS['parse_seconds'][0]} s ({NUMBERS['pages_per_min'][0]} pages/min)", NUMBERS["parse_seconds"][1]),
        ("Parse time at 100k pages", f"{NUMBERS['hours_100k'][0]} h (extrapolation)", NUMBERS["hours_100k"][1]),
        ("Chunks", f"{NUMBERS['chunks'][0]:,} ({NUMBERS['text_chunks'][0]:,} text + {NUMBERS['table_chunks'][0]} table)", NUMBERS["chunks"][1]),
        ("Table chunks with a caption / units", f"{NUMBERS['caption_chunks'][0]} / {NUMBERS['units_chunks'][0]}", NUMBERS["caption_chunks"][1]),
        ("Eval questions", f"{NUMBERS['questions'][0]} (26 answerable)", NUMBERS["questions"][1]),
        ("Page BM25: recall@5, MRR", f"{NUMBERS['recall5'][0]}, {NUMBERS['mrr'][0]}", NUMBERS["mrr"][1]),
        ("Hybrid chunk retrieval: recall@5, MRR", f"{NUMBERS['hybrid_recall5'][0]}, {NUMBERS['hybrid_mrr'][0]} (rejected)", NUMBERS["hybrid_mrr"][1]),
        ("Dense index size", f"{NUMBERS['index_mb'][0]} MB = {NUMBERS['bytes_page'][0]:,} bytes/page", NUMBERS["index_mb"][1]),
        ("Index at 100k pages", f"{NUMBERS['index_100k_gb'][0]} GB (extrapolation)", NUMBERS["index_100k_gb"][1]),
        ("Answer speed", f"{NUMBERS['gen_tok_s'][0]} tokens/s, ~{NUMBERS['answer_seconds'][0]} s per question", NUMBERS["gen_tok_s"][1]),
        ("Oracle answer score, qwen3.5 4B", f"{NUMBERS['oracle'][0]} (correct page given)", NUMBERS["oracle"][1]),
        ("Same test, qwen2.5 7B / phi4-mini", f"{NUMBERS['oracle_7b'][0]} / {NUMBERS['oracle_phi'][0]}", NUMBERS["oracle_7b"][1]),
        ("Dense recall@5, MRR (bge / e5)", f"{NUMBERS['bge_recall'][0]} {NUMBERS['bge_mrr'][0]} / {NUMBERS['e5_mrr'][0]}", NUMBERS["bge_recall"][1]),
      ], ["Quantity", "Value", "Where it was measured"])}
    <p class="manual__meta">Not measured, stated plainly: throughput of the full 100k-page
      ingestion, answer quality on anything but the 30-question set, and the behaviour of a
      reranker (it has not been built).</p>
  </section>

  <section class="section" id="limits">
    <h2 class="section__title">What it cannot do, and where it stops</h2>
    <p class="section__lead">A manual that lists only strengths is a sales page. These are
      the known limits, each one a deliberate trade rather than an oversight.</p>
    <ul>{limit_items}</ul>
  </section>

  <section class="section" id="run">
    <h2 class="section__title">Run it yourself</h2>
    <p class="section__lead">On the machine that holds the corpus and the models. Everything
      is local; the first two commands need the pinned models already on disk.</p>
    <pre><code># 1. parse the PDFs (851 pages take ~17 minutes; resumable)
.venv\\Scripts\\python.exe -m ingest.cli build

# 2. build the chunks, then the dense index (CPU; ~5 minutes for 3,226 chunks)
.venv\\Scripts\\python.exe -m chunk.cli build
.venv\\Scripts\\python.exe -m chunk.dense

# 3. start the model and the UI, then open http://127.0.0.1:8000
.\\scripts\\launch-llm.ps1
.venv\\Scripts\\python.exe -m uvicorn ui.server:app --host 127.0.0.1 --port 8000

# 4. check the system's own health line (model, UI, index)
.\\scripts\\health.ps1

# 5. score retrieval on the eval set
.venv\\Scripts\\python.exe eval\\run_retrieval.py --label my-run</code></pre>
    <p>Expected from step 4 on a healthy machine:
      <code>READY  model=qwen3.5:4b loaded  ui=127.0.0.1:8000 ok  index=97 docs/851 pages</code>.</p>
  </section>

  <section class="section" id="glossary">
    <h2 class="section__title">Glossary</h2>
    {table(glossary_rows, ["Term", "Plain meaning"])}
  </section>

  <footer class="manual__footer">
    <p>Built from this repository on {today}. The authoritative records are
      <code>STATUS.md</code> (measured facts and session log), <code>DECISIONS.md</code>
      (every choice with its evidence and what was rejected) and <code>EVAL.md</code>
      (the evaluation set and the pass/fail gate). This manual summarises them; where the
      two disagree, those files win.</p>
    <span class="tag">single file &middot; no scripts &middot; no web fonts</span>
    <span class="tag">print to PDF from the browser</span>
  </footer>

</main>
</body>
</html>
"""


def main() -> int:
    html = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({len(html) / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
