"""Retrieval baseline over the current corpus, scored with the eval set.

This is the "re-baseline" run EVAL.md asks for whenever the corpus grows: the
same 30 questions, the same BM25 page index the UI uses, no answers generated.
It records recall@5/10/30 and MRR for the answerable questions, plus the first
rank of every gold page so a later step can compare question by question.

Answer metrics (citation, numeric, not-found) are deliberately not reported
here: with no answer there is nothing to score, and printing 0/30 would look
like a regression instead of an unmeasured field.

The index returns a bare file name; gold sources are corpus-relative paths
(`data/corpus/<folder>/<file>.pdf`). `corpus_paths()` joins the two and refuses
to guess when two documents share a name.

Usage:
    .venv\\Scripts\\python.exe eval\\run_retrieval.py --label 2026-11-14-97docs
    # then, for the end-to-end baseline (retrieval + answers):
    .venv\\Scripts\\python.exe benchmarks/llm/oracle_run.py --retrieval-run eval/runs/<date>-2026-11-14-97docs/retrieval.jsonl --out eval/runs/<same>/run.jsonl
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

import score  # noqa: E402  (after the path fix, this is how eval/ modules import)
import corpus  # noqa: E402
from corpus import build, search  # noqa: E402

CORPUS = ROOT / "data" / "corpus"
RUNS = ROOT / "eval" / "runs"


def corpus_paths() -> dict[str, str]:
    """{bare file name: corpus-relative path}, refusing duplicate names."""
    return corpus.relpaths(CORPUS)


def retrieve(questions: list[dict], paths: dict[str, str], k: int) -> tuple[list[dict], dict]:
    """Top-k pages per question, plus the index that produced them."""
    index = build()
    rows = []
    for question in questions:
        hits = search(index, question["question"], k=k)
        rows.append({
            "id": question["id"],
            "retrieved": [
                {"file": f"data/corpus/{paths[hit['doc']]}", "page": hit["page"],
                 "score": hit["score"], "context": hit["context"]}
                for hit in hits
            ],
        })
    return rows, index


def report(summary: dict, results: list[dict], questions: list[dict], index: dict,
           label: str) -> str:
    by_id = {q["id"]: q for q in questions}
    answered = [r for r in results if by_id[r["id"]]["answerable"]]
    misses = [r for r in answered if not r["first_rank"]]
    lines = [
        f"# Retrieval baseline: {label}",
        "",
        f"- Corpus: **{len(index['docs'])} documents, {len(index['pages'])} pages** "
        f"({index['ocr_pages']} OCR pages, {len(index['unreadable'])} files with unreadable pages)",
        f"- Questions: {len(questions)} ({len(answered)} answerable, "
        f"{len(questions) - len(answered)} not-found)",
        f"- Index: BM25 over pages, k=30 (`corpus.py`), question text only",
        "",
        "| metric | count | share |",
        "|---|---|---|",
    ]
    for key in ("recall@5", "recall@10", "recall@30"):
        value = summary["retrieval"][key]["pass"]
        lines.append(f"| {key} | {value['count']}/{value['of']} | {value['pct']}% |")
    lines.append(f"| MRR | {summary['mrr']} | |")
    lines += ["", "| split | n | recall@5 | MRR |", "|---|---|---|---|"]
    for split, metrics in summary["by_split"].items():
        value = metrics["retrieval"]["recall@5"]["pass"]
        lines.append(f"| {split} | {metrics['n']} | {value['count']}/{value['of']} | {metrics['mrr']} |")
    lines += ["", f"Gold page missed entirely by the top 30: "
                  f"**{len(misses)}** of {len(answered)} answerable questions."]

    lines += ["", "| id | type | first gold rank |", "|---|---|---|"]
    for row in results:
        lines.append(f"| {row['id']} | {row['type']} | {row['first_rank'] or 'miss'} |")

    if misses:
        lines += ["", "## Missed questions", ""]
        for row in misses:
            lines.append(f"- {row['id']}: {by_id[row['id']]['question']}")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_retrieval")
    parser.add_argument("--label", required=True, help="name for the run folder")
    parser.add_argument("--questions", default=score.DEFAULT_QUESTIONS)
    parser.add_argument("--k", type=int, default=30)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    questions = score.load_jsonl(pathlib.Path(args.questions))
    paths = corpus_paths()
    started = time.perf_counter()
    rows, index = retrieve(questions, paths, args.k)
    elapsed = round(time.perf_counter() - started, 1)

    problems = score.check_integrity(questions, rows, pathlib.Path("data/corpus"))
    if problems:
        raise SystemExit("integrity check failed:\n  " + "\n  ".join(problems))

    results = [score.score_question(q, row) for q, row in zip(questions, rows)]
    summary = score.summarize(results, questions)

    out = pathlib.Path(args.out) if args.out else RUNS / f"{time.strftime('%Y-%m-%d')}-{args.label}"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "retrieval.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    text = report(summary, results, questions, index, args.label)
    (out / "scores.md").write_text(text, encoding="utf-8")
    (out / "scores.json").write_text(
        json.dumps({"label": args.label, "retrieval": summary["retrieval"],
                    "mrr": summary["mrr"],
                    "by_split": {split: {"n": m["n"], "retrieval": m["retrieval"],
                                         "mrr": m["mrr"]}
                                 for split, m in summary["by_split"].items()},
                    "corpus": {"documents": len(index["docs"]), "pages": len(index["pages"]),
                               "ocr_pages": index["ocr_pages"]},
                    "seconds": elapsed}, indent=2), encoding="utf-8")

    print(text)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
