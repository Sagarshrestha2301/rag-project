"""Merge owner-approved proposals into `eval/questions.jsonl`.

EVAL.md makes the owner the approver of every new question, so this script does not
decide anything: it refuses to run without an explicit id list or `--all`, refuses an
unknown id, refuses a duplicate, and refuses a proposal that would change an existing
question. It only appends, and it stamps each appended question with the approval date.

It also does the arithmetic the process asks for afterwards: the dev set grows, so the
locked configuration has to be re-baselined on the new set (`--run-baseline`), and the
one-question-per-N-points table in EVAL.md is printed with the new N.

Usage:
    # what would happen, changing nothing
    .venv\\Scripts\\python.exe eval\\apply_proposals.py --all --dry-run

    # approve all 25, then re-baseline the locked configuration on the larger dev set
    .venv\\Scripts\\python.exe eval\\apply_proposals.py --all --run-baseline

    # approve a subset
    .venv\\Scripts\\python.exe eval\\apply_proposals.py --ids q031,q034,q041
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "eval" / "questions.jsonl"
PROPOSED = ROOT / "eval" / "proposed-questions.jsonl"


def load_jsonl(path: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(prog="apply_proposals")
    parser.add_argument("--ids", default="", help="comma-separated ids to approve")
    parser.add_argument("--all", action="store_true", help="approve every proposal")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    parser.add_argument("--run-baseline", action="store_true",
                        help="re-run the locked page-BM25 baseline on the new dev set")
    parser.add_argument("--questions", default=str(QUESTIONS),
                        help="target file (a copy, for testing)")
    args = parser.parse_args()

    if not args.all and not args.ids:
        parser.error("say which questions are approved: --ids q031,q032 or --all")

    # Resolved, because the messages below print the path relative to the project root.
    target = pathlib.Path(args.questions).resolve()
    existing = load_jsonl(target)
    proposals = load_jsonl(PROPOSED)
    by_id = {item["id"]: item for item in proposals}

    wanted = list(by_id) if args.all else [part.strip() for part in args.ids.split(",")
                                           if part.strip()]
    unknown = [qid for qid in wanted if qid not in by_id]
    if unknown:
        raise SystemExit("not a proposal id: " + ", ".join(unknown))

    taken = {question["id"] for question in existing}
    clashes = [qid for qid in wanted if qid in taken]
    if clashes:
        raise SystemExit("already in the eval set: " + ", ".join(clashes))

    stamp = time.strftime("%Y-%m-%d")
    added = []
    for qid in wanted:
        item = dict(by_id[qid])
        item["notes"] = f"approved by owner {stamp}; proposed 2026-11-16"
        added.append(item)

    dev_now = sum(1 for q in existing if q["split"] == "dev")
    dev_after = dev_now + sum(1 for q in added if q["split"] == "dev")
    unanswerable = sum(1 for q in added if not q["answerable"])

    print(f"proposals approved: {len(added)} ({len(added) - unanswerable} answerable, "
          f"{unanswerable} not found)")
    print(f"dev questions: {dev_now} -> {dev_after}"
          f" (one question is worth {100 / dev_after:.1f} points)")
    print(f"not-found share of dev after: "
          f"{100 * (sum(1 for q in existing if q['split'] == 'dev' and not q['answerable']) + unanswerable) / dev_after:.1f}%")
    if dev_after < 50:
        print(f"NOTE: EVAL.md targets 50-60 dev questions by the end of Step 5; "
              f"this leaves {50 - dev_after} to go.")

    if args.dry_run:
        print("dry run: nothing written")
        return 0

    with target.open("a", encoding="utf-8", newline="\n") as fh:
        for item in added:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    shown = target.relative_to(ROOT) if target.is_relative_to(ROOT) else target
    print(f"appended {len(added)} questions to {shown}")

    if args.run_baseline:
        if target != QUESTIONS:
            print("skipping the baseline: it must run against eval/questions.jsonl")
            return 0
        label = "rebased-" + time.strftime("%Y-%m-%d")
        print(f"re-baselining the locked configuration as {label} ...")
        result = subprocess.run([sys.executable, str(ROOT / "eval" / "run_retrieval.py"),
                                 "--label", label], cwd=ROOT)
        if result.returncode != 0:
            print("baseline run FAILED; the questions are appended but no baseline exists")
            return result.returncode
        print("Baseline written. Record it in the EVAL.md Results table and in STATUS.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
