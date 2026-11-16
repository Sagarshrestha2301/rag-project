"""Ablation for Step 5: each ranked list alone, then the weight grid around the fusion.

Step 5's definition of done asks for an ablation table with recall@5/10/30 and MRR for
each configuration. An earlier session reported the grid's result ("24 weightings, best
24/26 at MRR 0.486") from a shell session, without an artifact; this script exists so
that number can be reproduced from a file instead of a claim.

One dense encode per question is paid once (`hybrid.lists`), then only the fusion is
repeated for each weight combination - the grid is cheap, and every configuration is
scored with the same `eval/score.py` as the baseline.

Usage:
    .venv\\Scripts\\python.exe eval\\run_sweep.py
    # eval/runs/<date>-sweep/{sweep.json,sweep.md}
"""

from __future__ import annotations

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
BASELINE = RUNS / "2026-11-15-2026-11-14-97docs" / "scores.json"
PAGES = (0.0, 0.5, 1.0, 2.0, 3.0)
CHUNKS = (0.0, 0.5, 1.0, 2.0)
DENSE = (0.0, 0.5, 0.7, 1.0)     # 0.7 is the weight the code ships with


def corpus_paths() -> dict[str, str]:
    """{bare file name: corpus-relative path}, refusing duplicate names."""
    corpus = ROOT / "data" / "corpus"
    by_name: dict[str, str] = {}
    for pdf in sorted(corpus.rglob("*.pdf")):
        if pdf.name in by_name:
            raise SystemExit(f"duplicate corpus file name: {pdf.name}")
        by_name[pdf.name] = pdf.relative_to(corpus).as_posix()
    return by_name


def label_for(weights: dict[str, float]) -> str:
    return "page {page:g} / chunk {chunk:g} / dense {dense:g}".format(**weights)


def measure(hits: list[dict], question: dict, paths: dict[str, str]) -> dict:
    row = {"id": question["id"], "retrieved": [
        {"file": f"data/corpus/{paths[hit['doc']]}", "page": hit["page"],
         "score": hit["score"], "context": hit["context"]} for hit in hits]}
    result = score.score_question(question, row)
    return result


def run_config(index: dict, cached: list[tuple[dict, list, dict]], questions: list[dict],
               paths: dict[str, str], weights: dict[str, float], k: int) -> dict:
    results = []
    for question, terms, ranked in cached:
        hits = hybrid.fuse(index, ranked, terms, k=k, weights=weights)
        results.append(measure(hits, question, paths))
    summary = score.summarize(results, questions)
    return {
        "weights": weights,
        "recall@5": summary["retrieval"]["recall@5"]["pass"]["count"],
        "recall@10": summary["retrieval"]["recall@10"]["pass"]["count"],
        "recall@30": summary["retrieval"]["recall@30"]["pass"]["count"],
        "mrr": summary["mrr"],
        # Per split as well: Step 5's DoD asks for the held-out result, and a row in
        # EVAL.md that cannot state it would be a row with a hole in it.
        "by_split": {split: {
            "n": m["n"],
            "recall@5": m["retrieval"]["recall@5"]["pass"]["count"],
            "recall@30": m["retrieval"]["recall@30"]["pass"]["count"],
            "mrr": m["mrr"],
        } for split, m in summary["by_split"].items()},
    }


def main() -> int:
    questions = score.load_jsonl(ROOT / "eval" / "questions.jsonl")
    paths = corpus_paths()
    started = time.perf_counter()
    index = hybrid.build(use_dense=True)
    if index["dense"] is None:
        raise SystemExit("dense index unavailable: run `python -m chunk.dense` first")

    # One pass per question: the three lists do not depend on the weights.
    cached = []
    for question in questions:
        terms, ranked = hybrid.lists(index, question["question"])
        cached.append((question, terms, ranked))

    configs: list[dict] = []
    seen: set[tuple] = set()

    def add(weights: dict[str, float]) -> None:
        key = tuple(sorted(weights.items()))
        if key in seen or not any(weights.values()):
            return
        seen.add(key)
        configs.append(run_config(index, cached, questions, paths, weights, k=30))

    # Each list alone first: this is what makes the fusion's contribution readable.
    add({"page": 1.0, "chunk": 0.0, "dense": 0.0})
    add({"page": 0.0, "chunk": 1.0, "dense": 0.0})
    add({"page": 0.0, "chunk": 0.0, "dense": 1.0})
    for page in PAGES:
        for chunk in CHUNKS:
            for dense in DENSE:
                add({"page": page, "chunk": chunk, "dense": dense})
    # The weights in the code belong in the grid, or its rank below is a lie: an
    # earlier version measured it separately and printed "rank None of 59".
    add(dict(hybrid.WEIGHTS))
    shipped = next(c for c in configs if c["weights"] == dict(hybrid.WEIGHTS))
    elapsed = round(time.perf_counter() - started, 1)

    baseline = {}
    if BASELINE.exists():
        data = json.loads(BASELINE.read_text(encoding="utf-8"))
        baseline = {"recall@5": data["retrieval"]["recall@5"]["pass"]["count"],
                    "recall@10": data["retrieval"]["recall@10"]["pass"]["count"],
                    "recall@30": data["retrieval"]["recall@30"]["pass"]["count"],
                    "mrr": data["mrr"],
                    "_path": str(BASELINE.parent.relative_to(ROOT))}

    ranked = sorted(configs, key=lambda c: (-c["recall@5"], -c["mrr"]))
    best = ranked[0]

    def row(config: dict) -> str:
        w = config["weights"]
        return (f"| {label_for(w)} | {config['recall@5']}/26 | {config['recall@10']}/26 | "
                f"{config['recall@30']}/26 | {config['mrr']:.3f} |")

    lines = [
        "# Step 5 ablation: one list at a time, then the fusion",
        "",
        f"- Corpus: {len(index['chunks'])} chunks; page index over "
        f"{len(index['pages']['pages'])} pages",
        f"- Questions: {len(questions)} ({sum(1 for q in questions if q['answerable'])} answerable)",
        f"- {len(configs)} configurations scored in {elapsed} s, one dense encode per question",
        f"- Weights are RRF multipliers: `weight / (60 + rank)` per list, fused per page",
        "",
        "## Each signal alone",
        "",
        "| weights | recall@5 | recall@10 | recall@30 | MRR |",
        "|---|---|---|---|---|",
    ]
    for weights in ({"page": 1.0, "chunk": 0.0, "dense": 0.0},
                    {"page": 0.0, "chunk": 1.0, "dense": 0.0},
                    {"page": 0.0, "chunk": 0.0, "dense": 1.0}):
        match = next((c for c in configs if c["weights"] == weights), None)
        if match:
            lines.append(row(match))

    lines += ["", f"## Best 10 of {len(configs)} configurations", "",
              "| weights | recall@5 | recall@10 | recall@30 | MRR |", "|---|---|---|---|---|"]
    lines += [row(config) for config in ranked[:10]]

    rank_of_shipped = next((i for i, c in enumerate(ranked, 1)
                            if c["weights"] == shipped["weights"]),
                           None)
    lines += ["", "## The configuration in the code", "", row(shipped), "",
              f"That is rank {rank_of_shipped} of {len(ranked)} by recall@5, then MRR.", ""]

    if baseline:
        lines += ["## Against the page-level BM25 baseline", "",
                  f"Baseline (`{baseline['_path']}`): recall@5 {baseline['recall@5']}/26, "
                  f"recall@10 {baseline['recall@10']}/26, recall@30 "
                  f"{baseline['recall@30']}/26, MRR {baseline['mrr']:.3f}.", ""]
        beats = [c for c in configs if c["recall@5"] > baseline["recall@5"]
                 or (c["recall@5"] == baseline["recall@5"] and c["mrr"] > baseline["mrr"])]
        if beats:
            lines.append(f"**{len(beats)} configuration(s) beat the baseline** on recall@5, "
                          "then MRR. Step 5's rule is to keep the simpler one when it ties, "
                          "so this needs the owner's eye before anything is wired in; the "
                          "weights would also be fitted to these 26 questions.")
        else:
            lines.append("**No configuration beats the baseline.** The measured decision is "
                          "to keep page-level BM25, which is what the UI runs (D-056).")
        lines.append("")

    out = RUNS / f"{time.strftime('%Y-%m-%d')}-sweep"
    out.mkdir(parents=True, exist_ok=True)
    (out / "sweep.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "sweep.json").write_text(json.dumps({
        "chunks": len(index["chunks"]), "questions": len(questions),
        "seconds": elapsed, "baseline": baseline, "shipped": shipped,
        "best": best, "configs": configs,
    }, indent=2), encoding="utf-8")

    print("\n".join(lines))
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
