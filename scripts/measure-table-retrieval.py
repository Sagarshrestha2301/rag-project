"""Measure what the table pass adds, without asking the model (Step 9, D-069).

For every eval question the router sends to the `table` route, this prints the pages page
BM25 returns, the pages the table pass adds, and whether a gold (file, page) is among them
before and after. It is the cheap check between attempts: the answer-level verdict still
needs the full generation eval and `eval/gate.py`.

Usage:
    .venv\\Scripts\\python.exe scripts\\measure-table-retrieval.py
    .venv\\Scripts\\python.exe scripts\\measure-table-retrieval.py --k 6 --out artifacts/step9/table-retrieval-check.md
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

import score                                   # noqa: E402
from corpus import CORPUS, build, relpaths, search   # noqa: E402
from generation import router                   # noqa: E402
from retrieval import tables                    # noqa: E402


def gold_pages(question: dict) -> set[tuple[str, int]]:
    return {(pathlib.PurePosixPath(source["file"]).name, int(source["page"]))
            for source in question.get("gold_sources") or []}


def describe(hits: list[dict]) -> str:
    return ", ".join(f"{hit['label']} p{hit['page']}" for hit in hits) or "-"


def main() -> int:
    parser = argparse.ArgumentParser(prog="measure-table-retrieval")
    parser.add_argument("--questions", default=str(ROOT / "eval" / "questions.jsonl"))
    parser.add_argument("--k", type=int, default=6)
    parser.add_argument("--out", default=str(ROOT / "artifacts" / "step9" / "table-retrieval-check.md"))
    args = parser.parse_args()

    questions = score.load_jsonl(pathlib.Path(args.questions))
    index = build()
    paths = relpaths(CORPUS)

    rows = []
    for question in questions:
        routed = router.route(question["question"], question.get("history") or None)
        if routed["route"] != "table":
            continue
        hits = search(index, question["question"], k=args.k)
        os.environ[tables.FLAG] = "1"
        try:
            merged = tables.merge(index, question["question"], hits, k=args.k)
        finally:
            os.environ.pop(tables.FLAG, None)
        gold = gold_pages(question)
        before = gold & {(hit["doc"], hit["page"]) for hit in hits}
        after = gold & {(hit["doc"], hit["page"]) for hit in merged}
        rows.append({
            "id": question["id"],
            "split": question["split"],
            "answerable": question["answerable"],
            "question": question["question"],
            "gold": sorted(f"{name} p{page}" for name, page in gold),
            "pages": describe(hits),
            "added": describe([hit for hit in merged if hit.get("via") == "table"]),
            "gold_before": bool(before),
            "gold_after": bool(after),
        })

    lines = [
        "# Table-route retrieval, with and without the table pass (D-069)",
        "",
        f"- Questions the router sends to `table`: **{len(rows)}** of {len(questions)}",
        f"- Passages per question (k): {args.k}; the table pass may replace up to "
        f"{tables.SLOTS} of them",
        f"- Corpus: {len(index['docs'])} documents, {len(index['pages'])} pages",
        "",
        "| id | gold page(s) | BM25 pages | table pages added | gold before | gold after |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| {row['id']} | {'; '.join(row['gold']) or '-'} | {row['pages']} | "
                     f"{row['added']} | {'yes' if row['gold_before'] else 'no'} | "
                     f"{'yes' if row['gold_after'] else 'no'} |")

    gained = [row["id"] for row in rows if row["gold_after"] and not row["gold_before"]]
    lost = [row["id"] for row in rows if row["gold_before"] and not row["gold_after"]]
    lines += ["", f"Gold page gained in the top-{args.k}: **{', '.join(gained) or 'none'}**. "
                  f"Lost: **{', '.join(lost) or 'none'}**."]

    text = "\n".join(lines) + "\n"
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
