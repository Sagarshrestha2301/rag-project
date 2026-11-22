"""List the indexed documents that are not mostly Latin script.

The pipeline is English (BM25 over page text plus `bge-small-en-v1.5`), so a document
written in Devanagari can be indexed and still never be retrieved from an English
question. This prints one row per document with the share of the page text's letters
that are ASCII, and optionally writes the document names to a file.

Example:
    python scripts/find-non-english-docs.py --below 0.5 --names data/non-english-docs.txt
      2025_national_tiger_survey.pdf          0.00   12 pages   2.1% of pages
      1970_Adhikari_Tehri_Dam.pdf             0.99   31 pages
      ...
      29 documents under 0.50 Latin (of 214); 12 under 0.30
"""

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def latin_share(pages: list[dict]) -> float:
    """Share of the document's letters that are ASCII, weighted by page length."""
    letters = ascii_letters = 0
    for page in pages:
        for char in page.get("text") or "":
            if char.isalpha():
                letters += 1
                if char.isascii():
                    ascii_letters += 1
    return ascii_letters / letters if letters else 0.0


def report(index_path: pathlib.Path, below: float) -> list[dict]:
    """Every document with its Latin share, sorted from least to most Latin."""
    index = json.loads(index_path.read_text(encoding="utf-8"))
    by_doc: dict[str, list[dict]] = {}
    for page in index["pages"]:
        by_doc.setdefault(page["doc"], []).append(page)
    rows = []
    for doc, pages in by_doc.items():
        share = latin_share(pages)
        letters = sum(1 for page in pages for char in (page.get("text") or "")
                      if char.isalpha())
        rows.append({"doc": doc, "latin": round(share, 3), "pages": len(pages),
                     "letters": letters, "below": share < below})
    return sorted(rows, key=lambda row: (row["latin"], row["doc"]))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="find-non-english-docs.py")
    parser.add_argument("--index", default=str(ROOT / "index" / "pages.json"))
    parser.add_argument("--below", type=float, default=0.5,
                        help="latin share under which a document counts as non-English")
    parser.add_argument("--names", default=None,
                        help="write the matching document names, one per line, here")
    args = parser.parse_args(argv)

    rows = report(pathlib.Path(args.index), args.below)
    for row in rows:
        if row["below"]:
            print(f"{row['doc'][:60]:60s} {row['latin']:.3f}  {row['pages']:>4} pages  "
                  f"{row['letters']:>8} letters")
    under = [row for row in rows if row["below"]]
    print(f"\n{len(under)} documents under {args.below:.2f} Latin (of {len(rows)}); "
          f"{sum(1 for row in under if row['latin'] < 0.3)} under 0.30")
    if args.names:
        target = pathlib.Path(args.names)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("".join(row["doc"] + "\n" for row in under), encoding="utf-8")
        print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
