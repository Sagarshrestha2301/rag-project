"""Group a run's failing questions by cause, for Step 9 task 1.

The eval already says *that* a question failed; this says *why*, using the rules
`eval/score.py` applied and the pipeline record that produced the answer. One question
can have more than one cause (a retrieval miss usually carries a citation failure with
it), so the report lists every cause a failing question has and groups by the first.

Usage:
    .venv\\Scripts\\python.exe eval\\failures.py --run eval\\runs\\2026-11-19-step8-full
    # writes reports/failures.md

Example of the summary it prints:
    failing questions: 22
    retrieval miss      2
    citation           12
    number              1
    not found           3
    verification        4
"""

from __future__ import annotations

import argparse
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAUSES = ("retrieval miss", "citation", "number", "false not found",
          "answered an unanswerable question", "verification failed")


def load(run_dir: pathlib.Path) -> tuple[list[dict], list[dict], dict[str, str]]:
    """(scored results, pipeline rows, {id: question}) from one run folder.

    The question wording is not repeated in `run.jsonl`, so it comes from the run
    folder's own `questions.jsonl` when a run was made from a copy, and from
    `eval/questions.jsonl` otherwise.
    """
    scores = json.loads((run_dir / "scores.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in
            (run_dir / "run.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    source = run_dir / "questions.jsonl"
    if not source.exists():
        source = ROOT / "eval" / "questions.jsonl"
    wording = {record["id"]: record.get("question", "") for record in
               (json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()
                if line.strip())}
    return scores["results"], rows, wording


def causes_for(result: dict, row: dict) -> list[str]:
    """Every reason this question failed, in the order the scorer checks them."""
    found: list[str] = []
    if result.get("retrieval_scored") and not result["recall"]["5"][1]:
        found.append("retrieval miss")
    if result.get("notfound_case") and not result.get("notfound_correct"):
        found.append("false not found" if result.get("answerable")
                     else "answered an unanswerable question")
    if result.get("citation_ok") is False:
        found.append("citation")
    if result.get("numeric_ok") is False:
        found.append("number")
    if row.get("status") == "unverified":
        found.append("verification failed")
    return found or ["unscored failure"]


def build_report(run_dir: pathlib.Path, out: pathlib.Path) -> dict:
    results, rows, wording = load(run_dir)
    by_id = {row["id"]: row for row in rows}
    failing = []
    for result in results:
        if result["passed"]:
            continue
        row = by_id.get(result["id"], {})
        failing.append({
            "id": result["id"],
            "type": result.get("type"),
            "answerable": result.get("answerable"),
            "causes": causes_for(result, row),
            "status": row.get("status"),
            "question": wording.get(result["id"], row.get("question", "")),
            "answer": (row.get("answer") or "").strip().replace("\n", " ")[:240],
            "gold_pages": result.get("gold_pages") or result.get("gold") or [],
            "first_rank": result.get("first_rank"),
        })

    counts: dict[str, int] = {}
    for item in failing:
        counts[item["causes"][0]] = counts.get(item["causes"][0], 0) + 1

    lines = [
        "# Remaining failures, grouped by cause (Step 9 task 1)",
        "",
        f"Source run: `{run_dir.as_posix()}`. Written by `python eval/failures.py`;",
        "the causes are the rules `eval/score.py` applied, not a reading of the answers.",
        "",
        "| Cause | Questions |",
        "|---|---|",
    ]
    for cause in CAUSES + ("unscored failure",):
        if counts.get(cause):
            lines.append(f"| {cause} | {counts[cause]} |")
    lines.append(f"| **total failing** | **{len(failing)}** |")

    for cause in CAUSES + ("unscored failure",):
        group = [item for item in failing if item["causes"][0] == cause]
        if not group:
            continue
        lines += ["", f"## {cause} ({len(group)})", ""]
        for item in group:
            extra = ", ".join(item["causes"][1:])
            lines.append(f"- **{item['id']}** ({item['type']}, {item['status']}"
                         f"{', also: ' + extra if extra else ''}) - {item['question']}")
            lines.append(f"  - answer: {item['answer'] or '(empty)'}")
    lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")

    return {"run": str(run_dir), "failing": len(failing), "counts": counts,
            "report": str(out)}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="eval.failures")
    parser.add_argument("--run", required=True, help="run folder with run.jsonl and scores.json")
    parser.add_argument("--out", default=str(ROOT / "reports" / "failures.md"))
    args = parser.parse_args(argv)

    summary = build_report(pathlib.Path(args.run), pathlib.Path(args.out))
    print(f"failing questions: {summary['failing']}")
    for cause, count in summary["counts"].items():
        print(f"  {cause:38s} {count}")
    print(f"wrote {summary['report']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
