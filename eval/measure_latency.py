"""Latency per retrieval stage (Step 5 DoD: "retrieval latency per stage, within budget").

Measures the retriever the ablation and the UI both use, stage by stage: page BM25,
chunk BM25, the dense encode + vector search, and the RRF fusion, plus the one-off index
build. Timings come from `hybrid.lists()` itself (it fills a `timings` dict), so this
report cannot drift from the ranking code.

Budget, from the owner's targets: a standard question must answer within 20 s end to
end, and retrieval is meant to be a fraction of that. The generator is measured
separately (13.5 tokens/s, ~3.7 s for a short answer), so this report states retrieval's
share rather than claiming the total.

Usage:
    .venv\\Scripts\\python.exe eval\\measure_latency.py
    # reports/latency-step5.md  (and the same table on stdout)
"""

from __future__ import annotations

import pathlib
import statistics
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

import score                                   # noqa: E402
from retrieval import hybrid                   # noqa: E402

REPORT = ROOT / "reports" / "latency-step5.md"
STAGES = ("page_bm25", "chunk_bm25", "dense", "fuse")
END_TO_END_BUDGET = 20.0      # seconds, owner's target for a standard question


def percentile(values: list[float], share: float) -> float:
    """Nearest-rank percentile: no interpolation, so every number is a measured run."""
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(share * (len(ordered) - 1))))
    return ordered[index]


def millis(value: float) -> str:
    return f"{value * 1000:.1f}"


def main() -> int:
    questions = score.load_jsonl(ROOT / "eval" / "questions.jsonl")

    started = time.perf_counter()
    index = hybrid.build(use_dense=True)
    build_seconds = time.perf_counter() - started
    if index["dense"] is None:
        raise SystemExit("dense index unavailable: run `python -m chunk.dense` first")

    samples: dict[str, list[float]] = {stage: [] for stage in STAGES}
    totals: list[float] = []
    for question in questions:
        timings: dict[str, float] = {}
        began = time.perf_counter()
        terms, ranked = hybrid.lists(index, question["question"], timings=timings)
        fused_at = time.perf_counter()
        hybrid.fuse(index, ranked, terms, k=30)
        finished = time.perf_counter()
        timings["fuse"] = finished - fused_at
        for stage in STAGES:
            samples[stage].append(timings.get(stage, 0.0))
        totals.append(finished - began)

    rows = []
    for stage in STAGES:
        values = samples[stage]
        rows.append(f"| {stage} | {millis(statistics.median(values))} | "
                    f"{millis(percentile(values, 0.95))} | {millis(max(values))} |")
    rows.append(f"| **retrieval total** | {millis(statistics.median(totals))} | "
                f"{millis(percentile(totals, 0.95))} | {millis(max(totals))} |")

    lines = [
        "# Retrieval latency per stage (Step 5)",
        "",
        f"- Corpus: {len(index['chunks'])} chunks, page index over "
        f"{len(index['pages']['pages'])} pages",
        f"- Questions timed: {len(questions)} (same set as the eval)",
        f"- One-off index build: **{build_seconds:.1f} s** (page BM25 + chunk BM25 + "
        f"opening the LanceDB table and loading bge)",
        "- Timed on this machine, CPU only, with the dense model warm after the build; "
        "the first encode is inside the build figure, not in the per-question rows",
        "",
        "| stage | p50 ms | p95 ms | max ms |",
        "|---|---|---|---|",
        *rows,
        "",
        f"**Budget:** retrieval p95 is {millis(percentile(totals, 0.95))} ms against a "
        f"{END_TO_END_BUDGET:.0f} s end-to-end target for a standard question, so retrieval "
        "is not the bottleneck: generation is, at 13.5 tokens/s (about 3.7 s for a short "
        "cited answer). The dense stage dominates retrieval at roughly "
        f"{millis(statistics.median(samples['dense']))} ms p50, because it encodes the "
        "question with bge on the CPU - moving it to the GPU would contend with the model "
        "for the 4 GB card (D-004 keeps embeddings on the CPU).",
        "",
        "Not measured here: BM25 index build time split by stage, memory, and latency under "
        "concurrent requests. The UI answers one question at a time.",
        "",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"wrote {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
