"""Re-check every unanswerable eval question against the whole corpus (Step 8 task 7).

An unanswerable question is only safe while the fact really is absent. Once the corpus
grows, one of them can quietly become answerable, and then a correct answer would be
scored as a false "not found" - the opposite of the honesty the eval is for. This
script puts the evidence in front of the owner: for each such question, the best BM25
pages with their scores, and how many pages contain every distinctive term of the
question.

It does not decide. The step requires owner confirmation, so the report ends each item
with the pages to read and a blank verdict.

Usage:
    .venv\\Scripts\\python.exe scripts\\recheck-not-found.py
    # writes reports/not-found-recheck.md and prints the table

Example of one item:
    q020 What is the population living in the Bagmati catchment?
      best BM25  1970_Marahatta_... p.1 score 9.83 - the passage mentions catchment ...
      keyword    0 of 851 pages contain "population" and "bagmati" and "catchment"
      verdict    still absent (to confirm)
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import corpus                                   # noqa: E402

QUESTIONS = ROOT / "eval" / "questions.jsonl"
OUT = ROOT / "reports" / "not-found-recheck.md"
STOPWORDS = {"what", "was", "were", "the", "is", "are", "of", "in", "on", "at", "to", "for",
             "during", "how", "many", "much", "which", "who", "when", "where", "and", "did",
             "does", "a", "an", "it", "that", "this", "by", "as", "with", "from", "be",
             "total", "time", "there", "have", "has", "had", "into", "about", "after"}
TOP_PAGES = 3


def distinctive_terms(question: str) -> list[str]:
    """The content words a page would need to carry to answer the question."""
    return [term for term in corpus.tokens(question) if term not in STOPWORDS and len(term) > 2]


def keyword_pages(index: dict, terms: list[str]) -> list[dict]:
    """Pages containing every term, so a multi-word question is not a single hit."""
    matches = []
    for page in index["pages"]:
        text = page["text"].lower()
        if all(term in text for term in terms):
            matches.append(page)
    return matches


def main() -> int:
    questions = [record for record in
                 (json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines()
                  if line.strip())
                 if not record.get("answerable", True)]
    index = corpus.build()
    page_count = len(index["pages"])

    lines = [
        "# Not-found questions re-checked against the full corpus (Step 8 task 7)",
        "",
        f"Corpus: **{len(index['docs'])} documents / {page_count} pages**. Written by",
        "`scripts/recheck-not-found.py`; the scores are page-level BM25 from `corpus.search`,",
        "the same ranking the pipeline uses.",
        "",
        "Each item lists the pages to read and a verdict for the owner to confirm (D-027:",
        "a not-found question may only be replaced with owner approval).",
        "",
    ]
    print(f"{len(questions)} unanswerable questions, {len(index['docs'])} documents, "
          f"{page_count} pages")

    for record in questions:
        terms = distinctive_terms(record["question"])
        hits = corpus.search(index, record["question"], k=TOP_PAGES)
        matches = keyword_pages(index, terms)
        lines += [f"## {record['id']} ({record.get('split', '?')})", "",
                  f"**{record['question']}**", ""]
        if hits:
            lines.append("Best BM25 pages:")
            for hit in hits:
                snippet = " ".join((hit.get("snippet") or "").split())[:180]
                lines.append(f"- `{hit['doc']}` p. {hit['page']}, score {hit['score']}: "
                             f"{snippet}")
        else:
            lines.append("Best BM25 pages: none above zero.")
        lines += ["",
                  f"Keyword search: **{len(matches)} of {page_count} pages** contain all of "
                  f"`{', '.join(terms)}`.",
                  ""]
        for page in matches[:3]:
            snippet = " ".join(page["text"].split())[:180]
            lines.append(f"- `{page['doc']}` p. {page['page']}: {snippet}")
        lines += ["", "Verdict: still absent / now answerable (owner to confirm).", ""]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
