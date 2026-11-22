"""Measure what the reranker does to retrieval alone, without the local model.

Generation is slow (about 25 minutes for the 55-question set); retrieval is seconds. This
replays the shipped retrieval path - the router's own `k`, page BM25, then `rerank.apply`
- and reports recall@5 and MRR the way `eval/score.py` computes them, for several rerank
settings side by side. It cannot say whether an answer passes; it says whether the gold
page is still in the list and still near the front, which is the part reranking changes.

Example:
    python scripts/measure-rerank.py --settings bm25,rerank10,anchor3
      setting      recall@5   recall@10   MRR
      bm25         45/48      46/48       0.839
      rerank10     44/48      46/48       0.769
      anchor3      46/48      47/48       0.851
"""

import argparse
import json
import pathlib
import os
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from corpus import build, search  # noqa: E402
from generation import router  # noqa: E402
from retrieval import rerank  # noqa: E402

QUESTIONS = ROOT / "eval" / "questions.jsonl"
SUMMARY_TYPES = {"summary", "multi"}


def settings(name: str) -> dict:
    """`bm25`, or `rerank<N>` / `anchor<N>` with the depth fixed at 10."""
    if name == "bm25":
        return {}
    if name.startswith("rerank"):
        return {"enabled": True, "depth": int(name[6:] or 10), "anchor": 0}
    if name.startswith("anchor"):
        return {"enabled": True, "depth": 10, "anchor": int(name[6:])}
    raise SystemExit(f"unknown setting {name}: use bm25, rerank10 or anchor3")


def run(index: dict, questions: list[dict], setting: dict) -> dict:
    """Recall@5/@10 and MRR over the answerable questions for one rerank setting."""
    os.environ.pop(rerank.FLAG, None)
    if setting.get("enabled"):
        os.environ[rerank.FLAG] = "1"
        os.environ["CHAT_RERANK_DEPTH"] = str(setting["depth"])
        os.environ["CHAT_RERANK_ANCHOR"] = str(setting["anchor"])
    try:
        scores = []
        for q in questions:
            k = router.route(q["question"], None)["k"]
            depth = max(k, rerank.depth()) if rerank.enabled() else k
            hits = search(index, q["question"], k=depth)
            if rerank.enabled():
                hits = rerank.apply(hits, q["question"], k=k)
            pairs = [(pathlib.PurePosixPath(hit["doc"]).name, hit["page"]) for hit in hits]
            gold = {(pathlib.PurePosixPath(s["file"]).name, s["page"])
                    for s in q["gold_sources"]}
            ranks = [i for i, pair in enumerate(pairs, start=1) if pair in gold]
            first = min(ranks) if ranks else None
            row = {"recall": {}}
            for limit in (5, 10):
                if q["type"] in SUMMARY_TYPES:
                    hit = len(set(pairs[:limit]) & gold)
                    row["recall"][limit] = hit / len(gold) >= 0.5 if gold else False
                else:
                    row["recall"][limit] = bool(first and first <= limit)
            row["mrr"] = 1.0 / first if first else 0.0
            scores.append(row)
        return {"recall@5": sum(1 for r in scores if r["recall"][5]),
                "recall@10": sum(1 for r in scores if r["recall"][10]),
                "mrr": round(sum(r["mrr"] for r in scores) / len(scores), 3),
                "of": len(scores)}
    finally:
        for key in (rerank.FLAG, "CHAT_RERANK_DEPTH", "CHAT_RERANK_ANCHOR"):
            os.environ.pop(key, None)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="measure-rerank.py")
    parser.add_argument("--settings", default="bm25,rerank10,anchor3")
    parser.add_argument("--questions", default=str(QUESTIONS))
    args = parser.parse_args(argv)

    questions = [q for q in map(json.loads, open(args.questions, encoding="utf-8"))
                 if q["answerable"]]
    index = build()
    print(f"{len(questions)} answerable questions\n")
    print(f"{'setting':12s} {'recall@5':>10s} {'recall@10':>10s} {'MRR':>7s}")
    for name in args.settings.split(","):
        result = run(index, questions, settings(name.strip()))
        print(f"{name.strip():12s} {result['recall@5']:>4}/{result['of']:<5} "
              f"{result['recall@10']:>4}/{result['of']:<5} {result['mrr']:>7.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
