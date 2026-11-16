"""Print the not-found gate table from a saved run, so D-058's numbers can be re-derived.

The gate's floor is the one number in Step 6 that could quietly cost accuracy, so it must
be reproducible from an artifact rather than quoted from a chat message. This reads a
saved `retrieval.jsonl` (top-1 scores per question) and shows, for each candidate floor,
how many not-found questions it refuses and how many answerable ones it wrongly refuses.

Usage:
    .venv\\Scripts\\python.exe eval\\calibrate_gate.py
    .venv\\Scripts\\python.exe eval\\calibrate_gate.py --run eval/runs/<label>/retrieval.jsonl \\
        --split dev --floor 15

Example output (2026-11-16 re-based run, 45 dev questions):
    floor  nf caught  answerable lost
       15       0/6             0/39
       25       5/6             4/39
       30       6/6            12/39
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from eval.score import load_jsonl                  # noqa: E402  (no eval/__init__.py)

DEFAULT_RUN = "eval/runs/2026-11-16-rebased-2026-11-16/retrieval.jsonl"
CANDIDATES = (0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="calibrate_gate", description=__doc__)
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--questions", default="eval/questions.jsonl")
    parser.add_argument("--split", default="dev", choices=("dev", "heldout", "all"))
    parser.add_argument("--floor", type=float, default=None,
                        help="report the effect of this one floor and exit")
    args = parser.parse_args(argv)

    run_path = pathlib.Path(args.run)
    if not run_path.exists():
        print(f"STOP: no saved run at {run_path}; run eval/run_retrieval.py first")
        return 2

    questions = {q["id"]: q for q in load_jsonl(pathlib.Path(args.questions))}
    top: dict[str, float] = {}
    for line in run_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        retrieved = row.get("retrieved") or []
        top[row["id"]] = max((float(item.get("score") or 0) for item in retrieved), default=0.0)

    ids = [qid for qid in top
           if args.split == "all" or questions[qid]["split"] == args.split]
    answerable = [top[qid] for qid in ids if questions[qid]["answerable"]]
    unanswerable = [top[qid] for qid in ids if not questions[qid]["answerable"]]

    print(f"run   {run_path}")
    print(f"split {args.split}: {len(answerable)} answerable, {len(unanswerable)} not found")
    print()
    print(f"  answerable top-1   min {min(answerable, default=0):7.2f}   "
          f"median {statistics.median(answerable) if answerable else 0:7.2f}")
    print(f"  not-found top-1    min {min(unanswerable, default=0):7.2f}   "
          f"max {max(unanswerable, default=0):7.2f}")
    print()
    print("  floor  nf caught  answerable lost   verdict")
    for floor in CANDIDATES:
        caught = sum(1 for s in unanswerable if s < floor)
        lost = sum(1 for s in answerable if s < floor)
        note = "usable only if lost == 0" if caught == 0 else ""
        print(f"  {floor:5.0f}  {caught:4.0f}/{len(unanswerable):<5.0f}  "
              f"{lost:8.0f}/{len(answerable):<5.0f}   {note}")

    if args.floor is not None:
        caught = sum(1 for s in unanswerable if s < args.floor)
        lost = sum(1 for s in answerable if s < args.floor)
        print()
        print(f"floor {args.floor:.0f}: refuses {caught}/{len(unanswerable)} not-found, "
              f"costs {lost}/{len(answerable)} answerable")
        return 0 if lost == 0 else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
