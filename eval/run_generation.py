"""Answer every eval question through `generation.answer` and record the run (Step 6 task 7).

This is the end-to-end measurement, not a demo: the real router, condense step, gate,
prompt, local model and quote verifier run on every question, with the answer cache off
so each question is answered, not replayed. One line per question is written in the shape
`eval/score.py` reads, plus the details a failure needs (route, attempts, status, seconds).

Nothing here repairs an answer. A question that fails is recorded as it failed; the
scorer decides what that costs.

Usage:
    .venv\\Scripts\\python.exe eval\\run_generation.py --label step6-full
    .venv\\Scripts\\python.exe eval\\run_generation.py --label smoke --only q001,q023
    .venv\\Scripts\\python.exe eval\\run_generation.py --label step6-full --resume
    .venv\\Scripts\\python.exe eval\\score.py --run eval/runs/<dir>/run.jsonl --out eval/runs/<dir>

Model and runtime come from the same environment variables as `generation.answer`
(OLLAMA_URL, CHAT_MODEL, CHAT_NUM_CTX, CHAT_THINK); the run fails before the first
question if the model is not being served.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import pathlib
import statistics
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

import score  # noqa: E402  (after the path fix, this is how eval/ modules import)
from corpus import relpaths  # noqa: E402
from generation import answer as generator  # noqa: E402

CORPUS = ROOT / "data" / "corpus"
CORPUS_PREFIX = "data/corpus"
RUNS = ROOT / "eval" / "runs"


def percentile(values: list[float], fraction: float) -> float:
    """Linear-interpolated percentile; 0.0 for an empty list."""
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def citations_for(record: dict, paths: dict[str, str]) -> list[dict]:
    """The verifier's citations, rewritten as corpus-relative paths for the scorer.

    `verify` keeps the file name the model wrote. The scorer compares against gold
    paths, so a name that is in the corpus is translated here; a name that is not is
    left alone on purpose, and `eval/score.py` refuses the run rather than scoring a
    citation nobody can open.
    """
    out = []
    for citation in record["citations"]:
        name = pathlib.PurePosixPath(str(citation["file"]).replace("\\", "/")).name
        rel = paths.get(name)
        file = f"{CORPUS_PREFIX}/{rel}" if rel else str(citation["file"])
        out.append({"file": file, "page": citation["page"], "quote": citation["quote"],
                    "n": citation["n"], "raw": citation.get("raw", "")})
    return out


def row_for(question: dict, record: dict, paths: dict[str, str]) -> dict:
    """One scorer-shaped line, plus what a reader needs to understand a failure."""
    return {
        "id": question["id"],
        "retrieved": [
            {"file": f"{CORPUS_PREFIX}/{paths[passage['doc']]}",
             "page": passage["page"], "score": passage.get("score")}
            for passage in record["passages"]
        ],
        "answer": record["answer"],
        "citations": citations_for(record, paths),
        "said_not_found": (record["status"] == "not_found"
                           or generator.verify.said_not_found(record["answer"])),
        "status": record["status"],
        "route": (record.get("route") or {}).get("route"),
        "attempts": record["attempts"],
        "retry_dropped_answer": bool(record.get("retry_dropped_answer")),
        "search_question": record["search_question"],
        "seconds": record["seconds"],
        "timing": record["timing"],
    }


def write_meta(out: pathlib.Path, args, questions: list[dict], index: dict,
               digest: str | None) -> dict:
    """Everything needed to reproduce the run, written next to it."""
    questions_sha = hashlib.sha256(
        pathlib.Path(args.questions).read_bytes()).hexdigest()[:16]
    meta = {
        "label": args.label,
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": args.model,
        "model_digest": digest,
        "prompt_version": generator.prompt.PROMPT_VERSION,
        "num_ctx": generator.NUM_CTX,
        "temperature": 0.0,
        "seed": generator.SEED,
        "think": generator.THINK,
        "cache": "off",
        # A retrieval change behind a flag must be visible in the run it produced.
        "table_retrieval": generator.table_retrieval.enabled(),
        "questions": len(questions),
        "questions_sha256": questions_sha,
        "corpus": {"documents": len(index["docs"]), "pages": len(index["pages"]),
                   "ocr_pages": index["ocr_pages"]},
        "routes": {name: settings["k"] for name, settings in generator.router.SETTINGS.items()},
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def write_report(out: pathlib.Path, rows: list[dict], questions: list[dict], meta: dict,
                 summary: dict, integrity: list[str]) -> str:
    """Latency, routes and refusals for a human; the scores live in score.py's files."""
    seconds = [row["seconds"] for row in rows]
    p50, p95 = percentile(seconds, 0.50), percentile(seconds, 0.95)
    statuses = collections.Counter(row["status"] for row in rows)
    routes = collections.Counter(row["route"] for row in rows)
    attempts = collections.Counter(row["attempts"] for row in rows)
    over20 = sum(1 for value in seconds if value > 20)
    over30 = sum(1 for value in seconds if value > 30)

    lines = [
        f"# Generation run: {meta['label']}",
        "",
        f"- Model: `{meta['model']}` (digest `{(meta['model_digest'] or 'unknown')[:12]}`), "
        f"prompt `{meta['prompt_version']}`, temperature 0, num_ctx {meta['num_ctx']}, "
        f"think {meta['think']}",
        f"- Corpus: **{meta['corpus']['documents']} documents, {meta['corpus']['pages']} pages** "
        f"({meta['corpus']['ocr_pages']} OCR pages)",
        f"- Questions: {len(rows)} ({meta['questions']} in the set), cache off",
        "",
        "## End-to-end latency (seconds per question, retries and condense included)",
        "",
        "| n | p50 | p95 | min | max | mean | over 20 s | over 30 s |",
        "|---|---|---|---|---|---|---|---|",
        f"| {len(seconds)} | {p50:.1f} | {p95:.1f} | {min(seconds, default=0):.1f} | "
        f"{max(seconds, default=0):.1f} | {statistics.mean(seconds) if seconds else 0:.1f} | "
        f"{over20} | {over30} |",
        "",
        f"Target: about 20 s for a short follow-up, 30 s+ acceptable for a deep or long "
        f"question. Measured p50 **{p50:.1f} s**, p95 **{p95:.1f} s**.",
        "",
        "Slowest questions: " + ", ".join(
            f"`{row['id']}` {row['seconds']:.1f} s"
            for row in sorted(rows, key=lambda row: row["seconds"], reverse=True)[:3])
        + ". A single stalled question moves the mean, not the p50/p95.",
        "",
        "## How the questions were handled",
        "",
        "| | count |",
        "|---|---|",
    ]
    for key, value in sorted(statuses.items()):
        lines.append(f"| status `{key}` | {value} |")
    for key, value in sorted(routes.items(), key=lambda item: str(item[0])):
        lines.append(f"| route `{key}` | {value} |")
    for key, value in sorted(attempts.items()):
        lines.append(f"| attempts {key} | {value} |")
    lines += ["", "## Scores (from eval/score.py on the same run.jsonl)", "",
              f"- citation: {summary['citation']['count']}/{summary['citation']['of']}",
              f"- numeric: {summary['numeric']['count']}/{summary['numeric']['of']}",
              f"- not-found (a): {summary['notfound_a']['count']}/{summary['notfound_a']['of']}",
              f"- not-found (b): {summary['notfound_b']['count']}/{summary['notfound_b']['of']}",
              f"- passed: {summary['passed']['count']}/{summary['passed']['of']}"]
    if integrity:
        lines += ["", "## Integrity problems (the run is not scorable as written)", ""]
        lines += [f"- {problem}" for problem in integrity]

    lines += ["", "| id | split | type | seconds | route | attempts | citations | status |",
              "|---|---|---|---|---|---|---|---|"]
    by_id = {question["id"]: question for question in questions}
    for row in rows:
        question = by_id.get(row["id"], {})
        lines.append(f"| {row['id']} | {question.get('split', '-')} | {question.get('type', '-')} | "
                     f"{row['seconds']:.1f} | {row['route']} | {row['attempts']} | "
                     f"{len(row['citations'])} | {row['status']} |")
    text = "\n".join(lines) + "\n"
    (out / "report.md").write_text(text, encoding="utf-8")
    return text


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_generation", description=__doc__)
    parser.add_argument("--label", required=True, help="name for the run folder")
    parser.add_argument("--questions", default=str(ROOT / score.DEFAULT_QUESTIONS))
    parser.add_argument("--model", default=generator.MODEL)
    parser.add_argument("--only", default="", help="comma-separated question ids, for a smoke run")
    parser.add_argument("--resume", action="store_true",
                        help="keep finished lines in run.jsonl and answer only the rest")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    questions = score.load_jsonl(pathlib.Path(args.questions))
    if args.only:
        wanted = {part.strip() for part in args.only.split(",") if part.strip()}
        unknown = wanted - {question["id"] for question in questions}
        if unknown:
            raise SystemExit(f"unknown question id(s): {sorted(unknown)}")
        questions = [question for question in questions if question["id"] in wanted]

    out = pathlib.Path(args.out) if args.out else RUNS / f"{time.strftime('%Y-%m-%d')}-{args.label}"
    out.mkdir(parents=True, exist_ok=True)
    run_path = out / "run.jsonl"

    done: list[dict] = []
    if args.resume and run_path.exists():
        done = score.load_jsonl(run_path)
    finished = {row["id"] for row in done}
    todo = [question for question in questions if question["id"] not in finished]

    digest = generator.model_digest(args.model)
    if digest is None:
        raise SystemExit(
            f"STOP: Ollama at {generator.OLLAMA_URL} is not serving model {args.model!r}. "
            "Start it with `ollama serve` and check `ollama list`.")

    index = generator.index()
    paths = relpaths(CORPUS)
    meta = write_meta(out, args, questions, index, digest)

    rows = list(done)
    mode = "a" if done else "w"
    with run_path.open(mode, encoding="utf-8", newline="\n") as handle:
        for position, question in enumerate(todo, start=1):
            record = generator.answer(
                question["question"], index=index, model=args.model, use_cache=False,
                history=question.get("history") or None)
            row = row_for(question, record, paths)
            rows.append(row)
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            print(f"[{position}/{len(todo)}] {row['id']} {row['status']:<10} "
                  f"{row['seconds']:>5.1f} s  route={row['route']} attempts={row['attempts']}",
                  flush=True)

    problems = score.check_integrity(questions, rows, CORPUS)
    by_id = {row["id"]: row for row in rows}
    results = [score.score_question(question, by_id.get(question["id"]))
               for question in questions]
    summary = score.summarize(results, questions)
    text = write_report(out, rows, questions, meta, summary, problems)
    print()
    print(text)
    if problems:
        print("STOP: integrity problems above; run.jsonl is kept, no scores written")
        return 3
    print(f"wrote {out / 'run.jsonl'}, {out / 'meta.json'}, {out / 'report.md'}")
    print(f"next: .venv\\Scripts\\python.exe eval\\score.py --run {run_path} --out {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
