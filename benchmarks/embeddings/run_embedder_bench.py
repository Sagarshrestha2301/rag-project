"""Compare the three candidate embedders on the real chunk corpus (Step 4 task 5).

Protocol (STEP4-PLAN.md §6, unchanged):

* Embed every chunk in `index/chunks.jsonl` on **CPU** (rule 10: VRAM stays free
  for the LLM), then embed each eval question and rank chunks by cosine.
* The eval set's gold is *page*-level, so a chunk hit is mapped back to the pages
  it covers (`page_start`-`page_end`) and pages are deduplicated in rank order.
  That makes these numbers directly comparable with the page-level BM25 baseline
  in `EVAL.md`.
* Measured per model: recall@5, recall@10, recall@30, MRR, chunks per minute on
  CPU, model bytes on disk, embedding dimension.

The corpus is 97 documents / 851 pages / 3,226 chunks, so recall@10 is no longer
near-ceiling: the 10-chunk result is 10 of 3,226 candidates, not 10 of 105.

Usage:
    .venv\\Scripts\\python.exe benchmarks\\embeddings\\run_embedder_bench.py
    .venv\\Scripts\\python.exe benchmarks\\embeddings\\run_embedder_bench.py --only bge-small-en-v1.5
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

CHUNKS = ROOT / "index" / "chunks.jsonl"
QUESTIONS = ROOT / "eval" / "questions.jsonl"
MODELS = ROOT / "models"
OUT = ROOT / "artifacts" / "step4" / "embedder-bench"
REPORT = ROOT / "reports" / "embedder-comparison.md"

CANDIDATES = [
    ("bge-small-en-v1.5", "BAAI/bge-small-en-v1.5"),
    ("multilingual-e5-small", "intfloat/multilingual-e5-small"),
    ("all-MiniLM-L6-v2", "sentence-transformers/all-MiniLM-L6-v2"),
]
# e5 models are trained with an instruction prefix; without it they underperform.
PREFIX = {"multilingual-e5-small": "query: ", "bge-small-en-v1.5": ""}
KS = (5, 10, 30)
TOP = 30


def load_jsonl(path: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def page_set(chunk: dict) -> set[tuple[str, int]]:
    """The (file, page) pairs a chunk supports, for page-level scoring."""
    start, end = chunk["page_start"], chunk["page_end"]
    return {(chunk["file"], page) for page in range(start, end + 1)}


def gold_pages(question: dict) -> set[tuple[str, int]]:
    return {(pathlib.Path(src["file"]).name, src["page"])
            for src in question["gold_sources"]}


def model_bytes(path: pathlib.Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def bench(folder: str, repo: str, chunks: list[dict], questions: list[dict],
          batch_size: int = 32) -> dict:
    from sentence_transformers import SentenceTransformer

    path = MODELS / folder
    if not path.exists():
        raise SystemExit(f"missing model folder: {path} (download it first)")

    began = time.perf_counter()
    model = SentenceTransformer(str(path), device="cpu")
    texts = [chunk["text"] for chunk in chunks]
    vectors = model.encode(texts, batch_size=batch_size, convert_to_numpy=True,
                           normalize_embeddings=True, show_progress_bar=False)
    encode_seconds = time.perf_counter() - began

    prefix = PREFIX.get(folder, "")
    answerable = [question for question in questions if question["answerable"]]
    queries = model.encode([f"{prefix}{q['question']}" for q in answerable],
                           batch_size=8, convert_to_numpy=True,
                           normalize_embeddings=True, show_progress_bar=False)

    scores = queries @ vectors.T                      # cosine, both normalised
    rows = []
    for position, question in enumerate(answerable):
        order = scores[position].argsort()[::-1][:TOP]
        pages: list[tuple[str, int]] = []
        seen: set[tuple[str, int]] = set()
        for index in order:
            for page in page_set(chunks[int(index)]):
                if page not in seen:
                    seen.add(page)
                    pages.append(page)
        gold = gold_pages(question)
        rank = next((i for i, page in enumerate(pages, start=1) if page in gold), None)
        rows.append({"id": question["id"], "split": question["split"],
                     "first_rank": rank, "mrr": 1.0 / rank if rank else 0.0,
                     "recall": {k: bool(rank and rank <= k) for k in KS}})

    answerable_count = len(rows)
    summary = {
        "model": folder, "repo": repo, "chunks": len(chunks),
        "dim": int(vectors.shape[1]), "model_bytes": model_bytes(path),
        "encode_seconds": round(encode_seconds, 1),
        "chunks_per_minute": round(len(chunks) / encode_seconds * 60, 1),
        "recall": {f"recall@{k}": sum(1 for r in rows if r["recall"][k]) for k in KS},
        "answerable": answerable_count,
        "mrr": round(sum(r["mrr"] for r in rows) / answerable_count, 4) if rows else 0.0,
        "by_split": {split: {
            "n": sum(1 for r in rows if r["split"] == split),
            "recall@5": sum(1 for r in rows if r["split"] == split and r["recall"][5]),
            "mrr": round(sum(r["mrr"] for r in rows if r["split"] == split)
                         / max(1, sum(1 for r in rows if r["split"] == split)), 4),
        } for split in ("dev", "heldout")},
        "misses": [r["id"] for r in rows if not r["first_rank"]],
        "rows": rows,
    }
    return summary


def all_results(fresh: list[dict]) -> list[dict]:
    """Every measured model, not only the ones this run encoded.

    `--only bge-small-en-v1.5` rewrote a three-row report as a one-row report and
    silently dropped the other two models' numbers, because the writer only saw
    this process's results. The artifacts in `OUT` are the record, so the report is
    rebuilt from them, with this run's numbers winning where the same model ran.
    """
    by_model: dict[str, dict] = {}
    for path in sorted(OUT.glob("*.json")):
        try:
            by_model[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
    for result in fresh:
        by_model[result["model"]] = result
    # Weights on disk as they are now: pruning removed the ONNX/OpenVINO copies
    # after these runs, so a stored byte count would show 401 MB for bge beside
    # 2,279 MB for e5, sizes of folders that no longer exist.
    for model, result in by_model.items():
        folder = MODELS / model
        if folder.is_dir():
            result["model_bytes"] = sum(
                path.stat().st_size for path in folder.rglob("*") if path.is_file())
    order = [folder for folder, _ in CANDIDATES]
    return sorted(by_model.values(),
                  key=lambda r: (order.index(r["model"]) if r["model"] in order
                                 else len(order), r["model"]))


def write_report(results: list[dict]) -> str:
    lines = ["# Embedder comparison (Step 4 task 5)", "",
             "Measured on the same 3,226 chunks from `index/chunks.jsonl` and the same",
             "30 questions (26 answerable). Chunk hits are mapped back to pages and",
             "deduplicated, so these numbers are comparable with the page-level BM25",
             "row in `EVAL.md`. Embeddings run on **CPU**; throughput is chunks per",
             "minute for the encode pass only (model load included). Model size is the",
             "folder on disk after pruning (ONNX/OpenVINO copies removed).", "",
             "| Model | Recall@5 | Recall@10 | Recall@30 | MRR | Chunks/min (CPU) | Model size | Dim |",
             "|---|---|---|---|---|---|---|---|"]
    for result in results:
        lines.append(
            f"| `{result['model']}` | {result['recall']['recall@5']}/{result['answerable']} | "
            f"{result['recall']['recall@10']}/{result['answerable']} | "
            f"{result['recall']['recall@30']}/{result['answerable']} | "
            f"{result['mrr']:.3f} | {result['chunks_per_minute']:.0f} | "
            f"{result['model_bytes'] / 1e6:.0f} MB | {result['dim']} |")
    lines += ["", "| Model | dev recall@5 | dev MRR | heldout recall@5 | heldout MRR | Missed entirely |",
              "|---|---|---|---|---|---|"]
    for result in results:
        dev, held = result["by_split"]["dev"], result["by_split"]["heldout"]
        lines.append(f"| `{result['model']}` | {dev['recall@5']}/{dev['n']} | {dev['mrr']:.3f} | "
                     f"{held['recall@5']}/{held['n']} | {held['mrr']:.3f} | "
                     f"{', '.join(result['misses']) or 'none'} |")
    lines += ["", "All three models are 384-dimensional, so the comparison is about",
              "quality and speed only, not index size.", ""]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default=None, help="one model folder name")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args(argv)

    chunks = load_jsonl(CHUNKS)
    questions = load_jsonl(QUESTIONS)
    if not chunks:
        raise SystemExit("no chunks: run `python -m chunk.cli build` first")
    OUT.mkdir(parents=True, exist_ok=True)

    results = []
    for folder, repo in CANDIDATES:
        if args.only and folder != args.only:
            continue
        print(f"=== {folder} ===", flush=True)
        result = bench(folder, repo, chunks, questions, args.batch_size)
        (OUT / f"{folder}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
        results.append(result)
        print(f"  recall@5 {result['recall']['recall@5']}/{result['answerable']}  "
              f"recall@10 {result['recall']['recall@10']}/{result['answerable']}  "
              f"MRR {result['mrr']:.3f}  {result['chunks_per_minute']:.0f} chunks/min",
              flush=True)

    if results:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(write_report(all_results(results)), encoding="utf-8")
        print(f"\nwrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
