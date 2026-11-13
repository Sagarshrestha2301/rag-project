"""Prove the scorer against fixture runs whose scores are known in advance.

Five cases (Step 1 task 7):
    perfect      all 30 pass
    empty        only the 4 not-found questions pass
    partial      15 pass, and the diff names exactly the 15 that regressed
    outside      citing data/raw/ is rejected, no scores written
    bad_hash     a gold hash that does not match the file is rejected

Usage:
    .venv\\Scripts\\python.exe eval\\test_scorer.py
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(".").resolve()
PY = ROOT / ".venv" / "Scripts" / "python.exe"
FIXTURES = ROOT / "eval" / "fixtures"
QUESTIONS = ROOT / "eval" / "questions.jsonl"

failures: list[str] = []


def run_score(run: pathlib.Path, out: pathlib.Path, questions: pathlib.Path | None = None,
              baseline: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    cmd = [str(PY), str(ROOT / "eval" / "score.py"), "--run", str(run), "--out", str(out)]
    if questions:
        cmd += ["--questions", str(questions)]
    if baseline:
        cmd += ["--baseline", str(baseline)]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)


def check(name: str, condition: bool, detail: str) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}: {detail}")
    if not condition:
        failures.append(f"{name}: {detail}")


def scores_of(out: pathlib.Path) -> dict:
    return json.loads((out / "scores.json").read_text(encoding="utf-8"))


def main() -> int:
    if not FIXTURES.exists():
        print("fixtures missing, building them with eval/make_fixtures.py")
        sys.path.insert(0, str(ROOT / "eval"))
        import make_fixtures
        make_fixtures.main()

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="scorer-test-"))
    try:
        # ---------------------------------------------------------- perfect
        print("case 1: perfect run")
        out = tmp / "perfect"
        r = run_score(FIXTURES / "perfect.jsonl", out)
        check("exit 0", r.returncode == 0, r.stdout.strip().splitlines()[0] if r.stdout else r.stderr[:120])
        if r.returncode == 0:
            s = scores_of(out)["summary"]
            check("passed 30/30", s["passed"]["count"] == 30, f"{s['passed']['count']}/30")
            check("citation 26/26 (answerable only)", s["citation"]["count"] == 26 and s["citation"]["of"] == 26,
                  f"{s['citation']['count']}/{s['citation']['of']}")
            check("numeric all", s["numeric"]["count"] == s["numeric"]["of"], f"{s['numeric']['count']}/{s['numeric']['of']}")
            check("recall@5 26/26", s["retrieval"]["recall@5"]["pass"]["count"] == 26,
                  f"{s['retrieval']['recall@5']['pass']['count']}/26")
            check("MRR 1.0", s["mrr"] == 1.0, str(s["mrr"]))
            check("not-found (a) dev 3/3", s["notfound_a"]["count"] == 3 and s["notfound_a"]["of"] == 3,
                  f"{s['notfound_a']['count']}/{s['notfound_a']['of']} scope={s['notfound_a_scope']}")
            check("points: dev 5, held-out 10", s["points_per_question_by_split"] == {"dev": 5.0, "heldout": 10.0},
                  str(s["points_per_question_by_split"]))
            check("split blocks 20/10", (s["by_split"]["dev"]["n"], s["by_split"]["heldout"]["n"]) == (20, 10),
                  f"{s['by_split']['dev']['n']} dev / {s['by_split']['heldout']['n']} held-out")

        # ---------------------------------------------------------- empty
        print("case 2: empty run")
        out = tmp / "empty"
        r = run_score(FIXTURES / "empty.jsonl", out)
        check("exit 0", r.returncode == 0, "scored")
        if r.returncode == 0:
            s = scores_of(out)["summary"]
            check("passed 4/30", s["passed"]["count"] == 4, f"{s['passed']['count']}/30")
            check("recall@5 0/26", s["retrieval"]["recall@5"]["pass"]["count"] == 0,
                  f"{s['retrieval']['recall@5']['pass']['count']}/26")
            check("MRR 0.0", s["mrr"] == 0.0, str(s["mrr"]))
            check("not-found (a) dev 3/3", s["notfound_a"]["count"] == 3, f"{s['notfound_a']['count']}/3")
            check("not-found (b) 0/26", s["notfound_b"]["count"] == 0, f"{s['notfound_b']['count']}/26")

        # ---------------------------------------------------------- partial
        print("case 3: partial run, with diff against perfect")
        out = tmp / "partial"
        r = run_score(FIXTURES / "partial.jsonl", out, baseline=FIXTURES / "perfect.jsonl")
        check("exit 0", r.returncode == 0, "scored")
        if r.returncode == 0:
            data = scores_of(out)
            s, d = data["summary"], data["diff"]
            check("passed 15/30", s["passed"]["count"] == 15, f"{s['passed']['count']}/30")
            check("15 pass -> fail", len(d["pass_to_fail"]) == 15, f"{len(d['pass_to_fail'])} regressions")
            check("0 fail -> pass", len(d["fail_to_pass"]) == 0, str(d["fail_to_pass"]))
            check("no phantom ids", not d["only_in_current"] and not d["only_in_baseline"],
                  "ids match")
            expected = [f"q{i:03d}" for i in range(16, 31)]
            check("regressions are q016-q030", d["pass_to_fail"] == expected,
                  d["pass_to_fail"][:3] + ["..."] if d["pass_to_fail"] else "empty")

        # ---------------------------------------------------------- outside
        print("case 4: run citing outside the corpus")
        out = tmp / "outside"
        r = run_score(FIXTURES / "outside.jsonl", out)
        check("exit 3", r.returncode == 3, f"exit {r.returncode}")
        check("rejected with reason", "outside corpus root" in r.stdout, r.stdout.strip()[:90])
        check("no scores written", not (out / "scores.json").exists(), "scores.json absent")

        # ---------------------------------------------------------- bad hash
        print("case 5: gold hash that does not match the file")
        # tamper every record of one file, so the failure is a hash mismatch rather
        # than the conflicting-hashes path (many questions share a document)
        bad_questions = tmp / "questions_badhash.jsonl"
        lines = []
        first = json.loads(QUESTIONS.read_text(encoding="utf-8").splitlines()[0])
        target = first["gold_sources"][0]["file"]
        for line in QUESTIONS.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            q = json.loads(line)
            for src in q["gold_sources"]:
                if src["file"] == target:
                    src["sha256"] = "0" * 64
            lines.append(json.dumps(q, ensure_ascii=False))
        bad_questions.write_text("\n".join(lines) + "\n", encoding="utf-8")

        out = tmp / "badhash"
        r = run_score(FIXTURES / "perfect.jsonl", out, questions=bad_questions)
        check("exit 3", r.returncode == 3, f"exit {r.returncode}")
        check("reports SHA-256 mismatch", "SHA-256 mismatch" in r.stdout, r.stdout.strip()[:90])
        check("no scores written", not (out / "scores.json").exists(), "scores.json absent")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if failures:
        print(f"{len(failures)} check(s) FAILED")
        for f in failures:
            print("  -", f)
        return 1
    print("all scorer checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
