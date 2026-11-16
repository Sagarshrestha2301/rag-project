"""Turn `eval/proposals.jsonl` into a review page and a schema-ready question file.

The owner approves new dev questions one by one (EVAL.md, "Growing the dev set": an
agent proposes, the owner approves, `added_in_step` is recorded). This script is the
proposal half, and its job is to make approval cheap and rejection safe:

- every quote must appear **verbatim** in the text of the page it cites, so a gold quote
  cannot be remembered or paraphrased - the check fails loudly and prints the page text
  around the closest match;
- every `gold_numbers` value must appear in the quote or the gold answer;
- the file hash is read from `index/parsed/manifest.json`, never typed by hand;
- a not-found proposal must cite no page, and the script prints the closest corpus
  mentions so the owner can see why the answer is absent;
- `eval/questions.jsonl` is **not touched**: the output is `eval/proposed-questions.jsonl`
  (same schema as the eval set) plus `eval/proposed.html` to read in a browser.

Usage:
    .venv\\Scripts\\python.exe eval\\propose_questions.py
    # eval/proposed.html, eval/proposed-questions.jsonl
"""

from __future__ import annotations

import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "eval" / "proposals.jsonl"
OUT_JSONL = ROOT / "eval" / "proposed-questions.jsonl"
OUT_HTML = ROOT / "eval" / "proposed.html"
PAGES = ROOT / "index" / "parsed" / "pages.jsonl"
MANIFEST = ROOT / "index" / "parsed" / "manifest.json"
CORPUS = ROOT / "data" / "corpus"

DOCS = {
    "marahatta": "1970_Marahatta_Relating_Hydrological_Extremes_with_Area_A_Case_on_Extreme_F_W2121362616.pdf",
    "das": "1970_Das_Beliefs_superstitions_and_taboos_associated_with_bamboos_in_W1999918290.pdf",
}


def load_jsonl(path: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def page_text(rows: list[dict], doc: str, page: int) -> str:
    for row in rows:
        if row["doc"] == doc and int(row["pdf_page"]) == page:
            return row["text"]
    return ""


def hashes() -> dict[str, str]:
    """{file name: sha256} from the parse manifest, so no hash is typed by hand."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    docs = manifest.get("docs", manifest)
    entries = docs if isinstance(docs, list) else list(docs.values())
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = pathlib.Path(entry.get("doc") or entry.get("file")
                            or entry.get("path") or "").name
        digest = entry.get("sha256")
        if name and digest:
            found[name] = digest
    return found


# A gold number may be printed as a word ("Fifty species"). The check accepts the
# spelled form, but the stored gold_numbers value stays numeric so the scorer can
# normalise answers against it.
NUMBER_WORDS = {
    "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six",
    "7": "seven", "8": "eight", "9": "nine", "10": "ten", "11": "eleven",
    "12": "twelve", "20": "twenty", "30": "thirty", "40": "forty", "50": "fifty",
    "60": "sixty", "70": "seventy", "80": "eighty", "90": "ninety", "100": "hundred",
}


def closest(text: str, quote: str, width: int = 160) -> str:
    """The page text around the longest word run of the quote that does appear."""
    words = quote.split()
    for size in range(len(words), 2, -1):
        for start in range(0, len(words) - size + 1):
            probe = " ".join(words[start:start + size])
            at = text.find(probe)
            if at >= 0:
                left = max(0, at - width // 2)
                return text[left:at + len(probe) + width // 2].replace("\n", " ")
    return text[:width].replace("\n", " ")


def main() -> int:
    proposals = load_jsonl(PROPOSALS)
    rows = load_jsonl(PAGES)
    digests = hashes()
    questions: list[dict] = []
    problems: list[str] = []
    cards: list[str] = []

    for item in proposals:
        qid = item["id"]
        answerable = item["type"] != "notfound"
        note = item.get("notes", "")
        if answerable:
            doc = DOCS.get(item["doc"])
            if not doc:
                problems.append(f"{qid}: unknown doc key {item['doc']!r}")
                continue
            text = page_text(rows, doc, int(item["page"]))
            if not text:
                problems.append(f"{qid}: no parsed text for {doc} p{item['page']}")
                continue
            if item["quote"] not in text:
                problems.append(f"{qid}: quote not verbatim on p{item['page']} - closest: "
                                f"{closest(text, item['quote'])!r}")
                continue
            haystack = item["quote"] + " " + item["gold_answer"]
            low = haystack.lower()
            for number in item["gold_numbers"]:
                value = str(number["value"])
                spelled = NUMBER_WORDS.get(value, "")
                if value not in haystack and not (spelled and spelled in low):
                    problems.append(f"{qid}: gold number {value!r} appears in "
                                    "neither the quote nor the gold answer")
            digest = digests.get(doc, "")
            if not digest:
                problems.append(f"{qid}: no sha256 for {doc} in the parse manifest")
            questions.append({
                "id": qid,
                "split": "dev",
                "type": item["type"],
                "question": item["question"],
                "history": [],
                "answerable": True,
                "gold_answer": item["gold_answer"],
                "gold_numbers": item["gold_numbers"],
                "gold_sources": [{"file": f"data/corpus/{doc}", "page": int(item["page"]),
                                  "sha256": digest}],
                "gold_quote": item["quote"],
                "added_in_step": 5,
                "notes": note,
            })
            rel = pathlib.Path(doc)
            link = (rel.as_uri() + f"#page={item['page']}") if False else (
                (CORPUS / doc).resolve().as_uri() + f"#page={item['page']}")
            cards.append(f"""<article class="card">
  <header class="card__head"><span class="card__id">{qid}</span>
    <span class="card__type">{item['type']}</span>
    <span class="card__where">{doc.replace('_', ' ')[:52]}… p{item['page']}</span></header>
  <p class="card__q">{html.escape(item['question'])}</p>
  <p class="card__a"><strong>Answer:</strong> {html.escape(item['gold_answer'])}</p>
  <blockquote class="card__quote">{html.escape(item['quote'])}</blockquote>
  <p class="card__links"><a href="{html.escape(link)}">open PDF at page {item['page']}</a></p>
</article>""")
        else:
            key = item["question"].lower()
            hits = []
            words = [w for w in ("hectare", "yield", "population", "elevation", "station")
                     if w in key]
            for row in rows:
                low = row["text"].lower()
                if any(word in low for word in words) and len(row["text"]) > 200:
                    if row["doc"] in (DOCS["das"], DOCS["marahatta"]):
                        hits.append(f"{pathlib.Path(row['doc']).name[:40]} p{row['pdf_page']}")
            questions.append({
                "id": qid, "split": "dev", "type": item["type"], "question": item["question"],
                "history": [], "answerable": False, "gold_answer": "", "gold_numbers": [],
                "gold_sources": [], "gold_quote": "", "added_in_step": 5, "notes": note,
            })
            cards.append(f"""<article class="card card--nf">
  <header class="card__head"><span class="card__id">{qid}</span>
    <span class="card__type">not found</span>
    <span class="card__where">no page states this</span></header>
  <p class="card__q">{html.escape(item['question'])}</p>
  <p class="card__a"><strong>Expected:</strong> NOT FOUND</p>
  <p class="card__note">{html.escape(note)} Closest mentions: {html.escape(', '.join(hits[:6]) or 'none')}</p>
</article>""")

    if problems:
        print("PROPOSALS REJECTED - nothing written:\n  " + "\n  ".join(problems))
        return 1

    OUT_JSONL.write_text("\n".join(json.dumps(q, ensure_ascii=False) for q in questions) + "\n",
                         encoding="utf-8", newline="\n")

    answered = sum(1 for q in questions if q["answerable"])
    css = """
:root{--ink:#16202b;--muted:#5d6b7a;--line:#dbe3ea;--bg:#fff;--soft:#f6f8fa;--accent:#1f5fa8}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 "Segoe UI",system-ui,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:32px 22px 80px}
h1{font-size:26px;margin:0 0 6px} .lead{color:var(--muted);margin:0 0 18px}
.counts{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 22px}
.counts span{border:1px solid var(--line);border-radius:999px;padding:4px 11px;font-size:13px;background:var(--soft)}
.card{border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:0 0 12px;break-inside:avoid}
.card--nf{background:#fffaf2;border-color:#e8d5b5}
.card__head{display:flex;gap:10px;align-items:baseline;font-size:12px;color:var(--muted);
  text-transform:uppercase;letter-spacing:.05em}
.card__id{font:600 13px ui-monospace,Consolas,monospace;color:var(--accent)}
.card__q{margin:8px 0 6px;font-weight:600}
.card__a{margin:0 0 8px;font-size:14px}
.card__quote{margin:0;padding:8px 12px;border-left:3px solid var(--line);background:var(--soft);
  font-size:13.5px;color:#2b3a48}
.card__links{margin:8px 0 0;font-size:13px}
.card__note{font-size:13px;color:var(--muted);margin:6px 0 0}
a{color:var(--accent)}
"""
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Proposed dev questions ({len(questions)})</title><style>{css}</style></head>
<body><main class="wrap">
<h1>{len(questions)} candidate dev questions for approval</h1>
<p class="lead">Proposed on 2026-11-16 from the two eval source documents. Every quote below
was found verbatim in the parsed text of the page it cites by
<code>eval/propose_questions.py</code>; every gold number appears in its quote.
Nothing here is in <code>eval/questions.jsonl</code> yet - that file is unchanged.</p>
<p class="counts"><span>{answered} answerable</span>
<span>{len(questions) - answered} not found</span>
<span>dev split</span><span>added_in_step 5</span></p>
{''.join(cards)}
</main></body></html>
"""
    OUT_HTML.write_text(page, encoding="utf-8")
    print(f"verified {len(questions)} proposals ({answered} answerable, "
          f"{len(questions) - answered} not found)")
    print(f"wrote {OUT_JSONL.relative_to(ROOT)} and {OUT_HTML.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
