"""Score the Step 5 hybrid retriever on the eval set and compare it with the baseline.

Same questions, same scorer and the same page-level definition of a hit as
`eval/run_retrieval.py`, so the two runs are comparable question by question. The
report states the baseline it compared against and the rank of every gold page in
both, because the regression gate is per question ("no unexplained pass -> fail, no
metric down by more than one question"), not a single averaged number.

Usage:
    .venv\\Scripts\\python.exe eval\\run_hybrid.py --label hybrid-bge
    # compares against the newest run in eval/runs/ that is not itself a hybrid run
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

import score                                   # noqa: E402
from retrieval import hybrid                   # noqa: E402

RUNS = ROOT / "eval" / "runs"


def corpus_paths() -> dict[str, str]:
    """{bare file name: corpus-relative path}, refusing duplicate names."""
    corpus = ROOT / "data" / "corpus"
    by_name: dict[str, str] = {}
    for pdf in sorted(corpus.rglob("*.pdf")):
        if pdf.name in by_name:
            raise SystemExit(f"duplicate corpus file name: {pdf.name}")
        by_name[pdf.name] = pdf.relative_to(corpus).as_posix()
    return by_name


def previous_run(skip: pathlib.Path) -> dict | None:
    """The newest retrieval scores.json that is not this run, for the comparison."""
    candidates = sorted(
        (path for path in RUNS.glob("*/scores.json")
         if path.parent != skip and "hybrid" not in path.parent.name),
        key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        return None
    data = json.loads(candidates[0].read_text(encoding="utf-8"))
    data["_path"] = str(candidates[0].parent.relative_to(ROOT))
    return data


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_hybrid")
    parser.add_argument("--label", default="hybrid-bge")
    parser.add_argument("--questions", default=score.DEFAULT_QUESTIONS)
    parser.add_argument("--k", type=int, default=30)
    parser.add_argument("--baseline", action="store_true",
                        help="BM25 only (skip the dense side)")
    args = parser.parse_args()

    questions = score.load_jsonl(pathlib.Path(args.questions))
    paths = corpus_paths()
    started = time.perf_counter()
    index = hybrid.build(use_dense=not args.baseline)
    if index["dense"] is None and not args.baseline:
        raise SystemExit("dense index unavailable, refusing to label a BM25 run 'hybrid'")

    rows = []
    for question in questions:
        hits = hybrid.search(index, question["question"], k=args.k)
        rows.append({"id": question["id"], "retrieved": [
            {"file": f"data/corpus/{paths[hit['doc']]}", "page": hit["page"],
             "score": hit["score"], "context": hit["context"]}
            for hit in hits]})
    elapsed = round(time.perf_counter() - started, 1)

    problems = score.check_integrity(questions, rows, ROOT / "data" / "corpus")
    if problems:
        raise SystemExit("integrity check failed:\n  " + "\n  ".join(problems))

    results = [score.score_question(q, row) for q, row in zip(questions, rows)]
    summary = score.summarize(results, questions)

    out = RUNS / f"{time.strftime('%Y-%m-%d')}-{args.label}"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "retrieval.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    baseline = previous_run(out)
    answered = sum(1 for q in questions if q["answerable"])
    lines = [
        f"# Hybrid retrieval: {args.label}",
        "",
        f"- Index: {'BM25 + bge-small dense over chunks, RRF k=60' if index['dense'] else 'BM25 only over chunks'}",
        f"- Corpus: {len(index['chunks'])} chunks from the built chunk index",
        f"- Questions: {len(questions)} ({answered} answerable)",
        f"- Built and scored in {elapsed} s",
        "",
        "| metric | count | share |",
        "|---|---|---|",
    ]
    for key in ("recall@5", "recall@10", "recall@30"):
        value = summary["retrieval"][key]["pass"]
        lines.append(f"| {key} | {value['count']}/{value['of']} | {value['pct']}% |")
    lines.append(f"| MRR | {summary['mrr']} | |")

    if baseline:
        mine = {row["id"]: row["first_rank"] for row in results}
        lines += ["", f"## Against the page-level BM25 baseline ({baseline['_path']})", "",
                  "| metric | baseline | hybrid | delta |", "|---|---|---|---|"]
        for key in ("recall@5", "recall@10", "recall@30"):
            was = baseline["retrieval"][key]["pass"]["count"]
            now = summary["retrieval"][key]["pass"]["count"]
            lines.append(f"| {key} | {was} | {now} | {now - was:+d} |")
        lines.append(f"| MRR | {baseline['mrr']} | {summary['mrr']} | "
                     f"{summary['mrr'] - baseline['mrr']:+.3f} |")

        # Per-question ranks, scored with the same function as the metrics, so a
        # "no worse on any question" claim can be checked line by line.
        base_dir = ROOT / baseline["_path"]
        base_rows = [json.loads(line) for line in
                     (base_dir / "retrieval.jsonl").read_text(encoding="utf-8").splitlines()
                     if line.strip()]
        base_rank = {q["id"]: score.score_question(q, r)["first_rank"]
                     for q, r in zip(questions, base_rows)}
        moved = [(row["id"], row["first_rank"], base_rank.get(row["id"])) for row in results]
        better = sum(1 for _, now, then in moved
                     if now and (not then or now < then))
        worse = [(qid, now, then) for qid, now, then in moved
                 if then and (not now or now > then)]
        lines += ["", f"Questions ranked better: **{better}**; worse: **{len(worse)}**.", ""]
        if worse:
            lines += ["| id | hybrid rank | baseline rank |", "|---|---|---|"]
            lines += [f"| {qid} | {now or 'miss'} | {then} |" for qid, now, then in worse]
            lines.append("")
        lines += ["| id | hybrid first gold rank | page baseline rank |", "|---|---|---|"]
        for qid, now, then in moved:
            lines.append(f"| {qid} | {now or 'miss'} | {then or 'miss'} |")

    (out / "scores.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "scores.json").write_text(json.dumps({
        "label": args.label,
        "mode": "hybrid" if index["dense"] else "bm25-chunks",
        "retrieval": summary["retrieval"], "mrr": summary["mrr"],
        "by_split": {split: {"n": m["n"], "retrieval": m["retrieval"], "mrr": m["mrr"]}
                     for split, m in summary["by_split"].items()},
        "chunks": len(index["chunks"]), "seconds": elapsed,
    }, indent=2), encoding="utf-8")

    print("\n".join(lines))
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
