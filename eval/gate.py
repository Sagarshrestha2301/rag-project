"""Enforce EVAL.md's regression gate on saved runs.

EVAL.md, "Regression gate": a change is accepted only if, against **two** baselines on
the dev set (the last accepted baseline and the start-of-step baseline),

  1. no question went from pass to fail without a written explanation,
  2. no count metric dropped by more than one question against the last accepted
     baseline (a drop of 2 or more fails), and MRR by no more than 1/N,
  3. the same holds against the start-of-step baseline (no drift over a step),
  4. not-found accuracy (a) does not drop at all against either baseline.

This script does exactly that and exits 0 only when every rule holds. It re-scores the
saved raw runs with `eval/score.py` (never the stored `scores.json`, which may have been
produced by an older scorer), so all three runs are measured the same way today.

A metric is compared only when both runs measured it: a retrieval-only run has no
answers, so its citation, numeric and not-found figures are not zeros, they are
unmeasured, and the gate says so instead of inventing a regression. Runs must cover the
same questions; a different dev set is an error, not a pass (EVAL.md: re-baseline).

Usage:
    .venv\\Scripts\\python.exe eval\\gate.py --current eval/runs/2026-11-16-step6-full \\
        --baseline eval/runs/2026-11-16-rebased-2026-11-16 \\
        --start eval/runs/2026-11-16-rebased-2026-11-16

    # a pass-to-fail question is allowed only with a written reason
    .venv\\Scripts\\python.exe eval\\gate.py ... --explain q029="table row is absent from the six passages"

    # milestone check on held-out instead of dev
    .venv\\Scripts\\python.exe eval\\gate.py ... --milestone

Exit codes: 0 every rule holds, 1 a rule is broken, 2 the inputs cannot be compared.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

import score  # noqa: E402  (after the path fix, this is how eval/ modules import)

RUN_FILES = ("run.jsonl", "retrieval.jsonl")
COUNT_METRICS = ("recall@5", "recall@10", "recall@30", "citation", "numeric",
                 "notfound_b", "passed")
ANSWER_METRICS = ("citation", "numeric", "notfound_a", "notfound_b", "passed")
TOLERANCE = 1          # "a drop of 2 or more questions fails"


class InputError(Exception):
    """The runs cannot be compared; this is not a gate verdict."""


def load_run(directory: pathlib.Path) -> tuple[list[dict], str, bool]:
    """Rows, the file they came from, and whether this run generated answers."""
    if not directory.is_dir():
        raise InputError(f"not a run directory: {directory}")
    for name in RUN_FILES:
        path = directory / name
        if path.exists():
            rows = score.load_jsonl(path)
            if not rows:
                raise InputError(f"{path} is empty")
            has_answers = all("answer" in row for row in rows)
            return rows, name, has_answers
    raise InputError(f"no {' or '.join(RUN_FILES)} in {directory}")


def load_questions(path: pathlib.Path, run_ids: set[str]) -> list[dict]:
    questions = score.load_jsonl(path)
    known = {q["id"] for q in questions}
    unknown = sorted(run_ids - known)
    if unknown:
        raise InputError(f"run has question id(s) not in {path}: {', '.join(unknown)}")
    return [q for q in questions if q["id"] in run_ids]


def measure(directory: pathlib.Path, questions_path: pathlib.Path) -> dict:
    """Score one run and return what the gate needs, per split."""
    rows, filename, has_answers = load_run(directory)
    run_ids = {row["id"] for row in rows}
    questions = load_questions(questions_path, run_ids)
    by_id = {row["id"]: row for row in rows}
    results = [score.score_question(q, by_id.get(q["id"])) for q in questions]
    summary = score.summarize(results, questions)
    return {
        "label": directory.name,
        "directory": directory,
        "file": filename,
        "has_answers": has_answers,
        "ids": {q["id"] for q in questions},
        "splits": {q["id"]: q["split"] for q in questions},
        "results": {r["id"]: r for r in results},
        "summary": summary,
    }


def metric_value(run: dict, split: str, metric: str) -> tuple[int, int]:
    """(count, of) for a count metric on one split."""
    section = run["summary"]["by_split"][split]
    if metric in ("recall@5", "recall@10", "recall@30"):
        passed = section["retrieval"][metric]["pass"]
        return passed["count"], passed["of"]
    value = section[metric]
    return value["count"], value["of"]


def measurable(run: dict, metric: str) -> bool:
    """False when the run never generated answers, so the metric has no meaning."""
    return run["has_answers"] or metric not in ANSWER_METRICS


def fmt(count: int, of: int) -> str:
    return f"{count}/{of}" if of else "n/a"


def metric_line(run: dict, split: str, metric: str) -> str:
    count, of = metric_value(run, split, metric)
    return fmt(count, of)


def checks_for(run: dict, qid: str) -> dict[str, bool] | None:
    """The checks this run can speak to for one question.

    A retrieval-only run has no answers, so citation, number, not-found and the overall
    verdict do not exist there: they are absent, not false. Only checks that both runs
    measured may be compared, which is what keeps a retrieval baseline from looking like
    45 regressions.
    """
    result = run["results"].get(qid)
    if result is None:
        return None
    checks: dict[str, bool] = {}
    if result["retrieval_scored"]:
        checks["retrieval"] = result["recall"][5][1]
    if run["has_answers"]:
        checks["citation"] = bool(result["citation_ok"])
        checks["numeric"] = bool(result["numeric_ok"])
        checks["not_found"] = bool(result["notfound_correct"])
        checks["verdict"] = bool(result["passed"])
    return checks


def flipped(baseline: dict, current: dict, qid: str) -> list[str]:
    """Checks that went true -> false in both runs, and checks that moved any way."""
    before, after = checks_for(baseline, qid), checks_for(current, qid)
    if before is None or after is None:
        return []
    common = [name for name in before if name in after]
    return [name for name in common if before[name] and not after[name]]


def diff_table(baseline: dict, current: dict, ids: list[str]) -> list[str]:
    """One line per question where a check both runs measured moved."""
    lines = []
    for qid in ids:
        before, after = checks_for(baseline, qid), checks_for(current, qid)
        if before is None or after is None:
            continue
        moved = [name for name in before if name in after and before[name] != after[name]]
        if not moved:
            continue
        lost = flipped(baseline, current, qid)
        arrow = "PASS -> fail" if lost else "fail -> PASS"
        lines.append(f"    {qid}  {arrow}  ({', '.join(moved)})")
    return lines


def rule_pass_to_fail(explained: dict[str, str], baselines: dict[str, dict],
                      current: dict, ids: list[str]) -> list[str]:
    """Rule 1: a pass-to-fail question needs a written explanation."""
    problems = []
    for name, baseline in baselines.items():
        for qid in ids:
            lost = flipped(baseline, current, qid)
            if lost and qid not in explained:
                problems.append(f"rule 1: {qid} passed {', '.join(lost)} in '{name}' and fails "
                                f"now, with no explanation")
    return problems


def check_mrr(name: str, baseline: dict, current: dict, split: str) -> list[str]:
    """Rules 2 and 3 for MRR: at most 1/N, one question's worth."""
    before = baseline["summary"]["by_split"][split]["mrr"]
    after = current["summary"]["by_split"][split]["mrr"]
    denominator = baseline["summary"]["by_split"][split]["retrieval"]["recall@5"]["pass"]["of"]
    if not denominator:
        return []
    allowed = 1.0 / denominator
    drop = round(before - after, 6)
    if drop > allowed + 1e-9:
        return [f"MRR against '{name}' dropped {drop:.3f}, more than one question "
                f"({allowed:.3f} = 1/{denominator}): {before:.3f} -> {after:.3f}"]
    return []


def check_counts(name: str, baseline: dict, current: dict, split: str) -> list[str]:
    """Rules 2 and 3 for every count metric: a drop of two or more questions fails."""
    problems = []
    for metric in COUNT_METRICS:
        if not measurable(baseline, metric) or not measurable(current, metric):
            continue
        before, of_before = metric_value(baseline, split, metric)
        after, of_after = metric_value(current, split, metric)
        if not of_before or not of_after:
            continue
        drop = before - after
        if drop >= TOLERANCE + 1:
            problems.append(f"{metric} against '{name}' dropped {drop} questions "
                            f"({fmt(before, of_before)} -> {fmt(after, of_after)})")
    return problems


def check_notfound_a(name: str, baseline: dict, current: dict, split: str) -> list[str]:
    """Rule 4: not-found (a) freezes; it may not drop at all."""
    if not measurable(baseline, "notfound_a") or not measurable(current, "notfound_a"):
        return []
    before, of_before = metric_value(baseline, split, "notfound_a")
    after, of_after = metric_value(current, split, "notfound_a")
    if not of_before or not of_after:
        return []
    if after < before:
        return [f"not-found (a) against '{name}' dropped {before - after} question(s) "
                f"({fmt(before, of_before)} -> {fmt(after, of_after)}); it may not drop at all"]
    return []


def check_same_set(runs: dict[str, dict], split: str) -> list[str]:
    """EVAL.md: the gate only compares runs on the same question set."""
    problems = []
    reference_name, reference = next(iter(runs.items()))
    expected = {qid for qid, sp in reference["splits"].items() if sp == split}
    for name, run in runs.items():
        found = {qid for qid, sp in run["splits"].items() if sp == split}
        if found != expected:
            missing = sorted(expected - found)
            extra = sorted(found - expected)
            problems.append(f"the {split} question set differs between '{reference_name}' and "
                            f"'{name}' (missing: {', '.join(missing) or 'none'}; "
                            f"extra: {', '.join(extra) or 'none'}); re-baseline instead")
    return problems


def parse_explanations(values: list[str], path: pathlib.Path | None) -> dict[str, str]:
    """'q015: reason' pairs from the command line and from a file, comments allowed."""
    explained: dict[str, str] = {}
    for chunk in values:
        qid, _, reason = chunk.partition("=")
        if not reason.strip():
            raise InputError(f"explanation for {qid!r} has no text; use q015=\"reason\"")
        explained[qid.strip()] = reason.strip()
    if path is not None:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise InputError(f"cannot read {path}: {exc.strerror or exc}") from exc
        for number, line in enumerate(lines, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            qid, sep, reason = line.partition(":")
            if not sep or not reason.strip():
                raise InputError(f"{path}:{number}: expected 'q015: reason'")
            explained[qid.strip()] = reason.strip()
    return explained


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gate", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--current", required=True, type=pathlib.Path)
    parser.add_argument("--baseline", required=True, type=pathlib.Path,
                        help="the last accepted baseline")
    parser.add_argument("--start", required=True, type=pathlib.Path,
                        help="the baseline from the start of the current step")
    parser.add_argument("--questions", default=str(ROOT / score.DEFAULT_QUESTIONS),
                        type=pathlib.Path)
    parser.add_argument("--explain", action="append", default=[], metavar="qID=REASON")
    parser.add_argument("--explanations", type=pathlib.Path, default=None,
                        help="file of 'qID: reason' lines for pass-to-fail questions")
    parser.add_argument("--milestone", action="store_true",
                        help="gate held-out instead of dev (end of Steps 5, 6, 8)")
    args = parser.parse_args(argv)

    split = "heldout" if args.milestone else "dev"
    try:
        current = measure(args.current, args.questions)
        baselines = {"last accepted": measure(args.baseline, args.questions),
                     "start of step": measure(args.start, args.questions)}
        explained = parse_explanations(args.explain, args.explanations)
    except InputError as exc:
        print(f"STOP: {exc}")
        return 2

    problems: list[str] = []
    print(f"gate on the {split} set: current '{current['label']}' "
          f"vs last accepted '{baselines['last accepted']['label']}' "
          f"and start of step '{baselines['start of step']['label']}'")

    same_set = check_same_set({"current": current, **baselines}, split)
    problems += same_set
    print(f"  [{'PASS' if not same_set else 'FAIL'}] same question set "
          f"({len([q for q in current['splits'].values() if q == split])} {split} questions)")

    ids = sorted(qid for qid, sp in current["splits"].items() if sp == split)

    rule1 = rule_pass_to_fail(explained, baselines, current, ids)
    problems += rule1
    print(f"  [{'PASS' if not rule1 else 'FAIL'}] rule 1: no unexplained pass-to-fail question")
    for name, baseline in baselines.items():
        table = diff_table(baseline, current, ids)
        if table:
            print(f"    against '{name}':")
            print("\n".join(table))

    for name, baseline in baselines.items():
        rule = "rule 2" if name == "last accepted" else "rule 3"
        found = check_counts(name, baseline, current, split) + check_mrr(name, baseline, current, split)
        problems += found
        print(f"  [{'PASS' if not found else 'FAIL'}] {rule}: no metric drops by more than "
              f"one question against '{name}'")
        for item in found:
            print(f"    {item}")

    rule4: list[str] = []
    for name, baseline in baselines.items():
        rule4 += check_notfound_a(name, baseline, current, split)
    problems += rule4
    skipped = (not measurable(current, "notfound_a")
               or any(not measurable(b, "notfound_a") for b in baselines.values()))
    marker = "SKIP" if skipped and not rule4 else ("PASS" if not rule4 else "FAIL")
    print(f"  [{marker}] rule 4: not-found (a) does not drop at all")
    if skipped:
        print("    not measured: at least one run generated no answers")
    for item in rule4:
        print(f"    {item}")

    print()
    print("metrics (current | last accepted | start of step)")
    for metric in ("recall@5", "citation", "numeric", "notfound_a", "notfound_b", "passed"):
        cells = [metric_line(run, split, metric) if measurable(run, metric) else "unmeasured"
                 for run in (current, baselines["last accepted"], baselines["start of step"])]
        print(f"  {metric:<11} {' | '.join(cells)}")
    mrrs = [f"{run['summary']['by_split'][split]['mrr']:.3f}" for run in
            (current, baselines["last accepted"], baselines["start of step"])]
    print(f"  {'MRR':<11} {' | '.join(mrrs)}")

    print()
    if problems:
        print(f"GATE FAILS: {len(problems)} problem(s)")
        for item in problems:
            print(f"  - {item}")
        return 1
    print("GATE PASSES: every rule holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
