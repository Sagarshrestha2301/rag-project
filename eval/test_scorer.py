"""Prove the scorer against fixture runs whose scores follow from the gold data itself.

Five cases (Step 1 task 7):
    perfect      every question answered from its gold page with its gold quote
    empty        nothing retrieved, "not found" everywhere
    partial      perfect for the first half of the set, broken for the second
    outside      citing data/raw/ is rejected, no scores written
    bad_hash     a gold hash that does not match the file is rejected

Nothing here is frozen to a question count. The earlier version hardcoded the 30-question
set (30 passed, 20 dev, 26 answerable, 5 dev points, q016-q030 regressing), so it reported
10 failures the day the set grew to 55 even though the scorer was right.

What the test asserts now is **per-question agreement between the scorer and the gold
data**, computed independently of `eval/score.py`: a `perfect` row can only pass if its
`gold_quote` really is on the gold page and every `gold_numbers` value really appears in
`gold_answer`. Three questions in the current set cannot be perfect for that reason (q042
and q050 spell their number as a word, q044's gold quote lost a hyphen), and the test
names them and their reason instead of pretending otherwise. If the gold data is repaired,
the expectation moves with it; if the scorer drifts, the disagreement is the failure.

Fixtures are rebuilt whenever their row count no longer matches the question set.

Usage:
    .venv\\Scripts\\python.exe eval\\test_scorer.py
"""

from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import pymupdf

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
import score  # noqa: E402  (the rule cases below call it directly)
PY = ROOT / ".venv" / "Scripts" / "python.exe"
FIXTURES = ROOT / "eval" / "fixtures"
QUESTIONS = ROOT / "eval" / "questions.jsonl"

failures: list[str] = []


def load_questions() -> list[dict]:
    return [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def norm(text: str) -> str:
    """Whitespace-collapsed text, the comparison the scorer's quote rule uses."""
    return re.sub(r"\s+", " ", text or "").strip()


_PAGES: dict[tuple[str, int], str] = {}


def page_text(file: str, page: int) -> str:
    key = (file, page)
    if key not in _PAGES:
        path = ROOT / file
        try:
            with pymupdf.open(path) as doc:
                _PAGES[key] = (norm(doc[page - 1].get_text())
                               if 1 <= page <= doc.page_count else "")
        except Exception:                     # a missing file is "not on the page"
            _PAGES[key] = ""
    return _PAGES[key]


def gold_limits(questions: list[dict]) -> dict[str, list[str]]:
    """The questions a `perfect` fixture cannot pass, with the gold-data reason why.

    Read from the PDFs and the gold fields, not from `eval/score.py`: this is the
    independent expectation the scorer is checked against.
    """
    limits: dict[str, list[str]] = {}
    for question in questions:
        if not question["answerable"]:
            continue
        reasons: list[str] = []
        source = question["gold_sources"][0]
        if norm(question["gold_quote"]) not in page_text(source["file"], source["page"]):
            reasons.append("gold_quote is not on the gold page")
        answer = question["gold_answer"]
        for number in question.get("gold_numbers") or []:
            value = str(number.get("value"))
            if value not in answer and value.replace(".", "") not in answer.replace(",", ""):
                reasons.append(f"gold number {value} is not written in gold_answer")
                break
        if reasons:
            limits[question["id"]] = reasons
    return limits


def facts(questions: list[dict]) -> dict:
    """What the fixtures imply, read off the question set they were built from."""
    dev = [q for q in questions if q["split"] == "dev"]
    held = [q for q in questions if q["split"] == "heldout"]
    answerable = [q for q in questions if q["answerable"]]
    notfound = [q for q in questions if not q["answerable"]]
    nf_dev = [q for q in notfound if q["split"] == "dev"]
    limits = gold_limits(questions)
    half = len(questions) // 2
    first, second = questions[:half], questions[half:]
    limited = set(limits)
    return {
        "n": len(questions),
        "dev": len(dev),
        "heldout": len(held),
        "answerable": len(answerable),
        "notfound": len(notfound),
        "notfound_dev": len(nf_dev),
        "limits": limits,
        "perfect_passed": len(questions) - len(limits),
        "citation_failures": [q["id"] for q in answerable
                              if any("quote" in r for r in limits.get(q["id"], []))],
        "numeric_failures": [q["id"] for q in answerable
                             if any("number" in r for r in limits.get(q["id"], []))],
        # `partial` is perfect for questions[:half] and broken after it.
        "partial_half": half,
        "partial_passed": (len([q for q in first if q["id"] not in limited])
                           + len([q for q in second if not q["answerable"]])),
        "partial_to_fail": [q["id"] for q in second
                            if q["answerable"] and q["id"] not in limited],
        "points": {"dev": round(100 / len(dev), 2) if dev else 0.0,
                   "heldout": round(100 / len(held), 2) if held else 0.0},
    }


def ensure_fixtures(n: int) -> None:
    """Rebuild the fixtures when they are missing or were built for another set size."""
    counts = {}
    for name in ("perfect.jsonl", "empty.jsonl", "partial.jsonl", "outside.jsonl"):
        path = FIXTURES / name
        counts[name] = (len(path.read_text(encoding="utf-8").splitlines())
                        if path.exists() else -1)
    if counts and all(count == n for count in counts.values()):
        return
    print(f"fixtures do not match the {n}-question set ({counts}); rebuilding")
    sys.path.insert(0, str(ROOT / "eval"))
    import make_fixtures
    make_fixtures.main()


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
    questions = load_questions()
    want = facts(questions)
    ensure_fixtures(want["n"])
    print(f"{want['n']} questions: {want['dev']} dev, {want['heldout']} held-out, "
          f"{want['answerable']} answerable, {want['notfound']} not-found "
          f"({want['notfound_dev']} of them dev)")
    if want["limits"]:
        print("gold data that no perfect fixture can pass:")
        for qid, reasons in want["limits"].items():
            print(f"  {qid}: {'; '.join(reasons)}")

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="scorer-test-"))
    try:
        # ---------------------------------------------------------- perfect
        print("case 1: perfect run")
        out = tmp / "perfect"
        r = run_score(FIXTURES / "perfect.jsonl", out)
        check("exit 0", r.returncode == 0,
              r.stdout.strip().splitlines()[0] if r.stdout else r.stderr[:120])
        if r.returncode == 0:
            data = scores_of(out)
            s = data["summary"]
            check(f"passed {want['perfect_passed']}/{want['n']} (gold data allows no more)",
                  s["passed"]["count"] == want["perfect_passed"],
                  f"{s['passed']['count']}/{want['n']}")
            agree = [row["id"] for row in data["results"]
                     if row["passed"] != (row["id"] not in want["limits"])]
            check("every question agrees with the gold-data expectation", not agree,
                  f"disagree: {agree}" if agree else "all agree")
            check(f"citation {s['citation']['count']}/{s['citation']['of']}",
                  s["citation"]["of"] - s["citation"]["count"] == len(want["citation_failures"]),
                  f"{s['citation']['count']}/{s['citation']['of']}, "
                  f"gold limits {want['citation_failures']}")
            check(f"numeric {s['numeric']['count']}/{s['numeric']['of']}",
                  s["numeric"]["of"] - s["numeric"]["count"] == len(want["numeric_failures"]),
                  f"{s['numeric']['count']}/{s['numeric']['of']}, "
                  f"gold limits {want['numeric_failures']}")
            check(f"recall@5 {want['answerable']}/{want['answerable']}",
                  s["retrieval"]["recall@5"]["pass"]["count"] == want["answerable"],
                  f"{s['retrieval']['recall@5']['pass']['count']}/{want['answerable']}")
            check("MRR 1.0", s["mrr"] == 1.0, str(s["mrr"]))
            check(f"not-found (a) dev {want['notfound_dev']}/{want['notfound_dev']}",
                  s["notfound_a"]["count"] == want["notfound_dev"]
                  and s["notfound_a"]["of"] == want["notfound_dev"],
                  f"{s['notfound_a']['count']}/{s['notfound_a']['of']} "
                  f"scope={s['notfound_a_scope']}")
            points = {split: round(value, 2)
                      for split, value in s["points_per_question_by_split"].items()}
            check("points derive from the split sizes", points == want["points"],
                  f"{points} expected {want['points']}")
            check(f"split blocks {want['dev']}/{want['heldout']}",
                  (s["by_split"]["dev"]["n"], s["by_split"]["heldout"]["n"])
                  == (want["dev"], want["heldout"]),
                  f"{s['by_split']['dev']['n']} dev / {s['by_split']['heldout']['n']} held-out")

        # ---------------------------------------------------------- empty
        print("case 2: empty run")
        out = tmp / "empty"
        r = run_score(FIXTURES / "empty.jsonl", out)
        check("exit 0", r.returncode == 0, "scored")
        if r.returncode == 0:
            s = scores_of(out)["summary"]
            check(f"passed {want['notfound']}/{want['n']} (only refusals pass)",
                  s["passed"]["count"] == want["notfound"],
                  f"{s['passed']['count']}/{want['n']}")
            check(f"recall@5 0/{want['answerable']}",
                  s["retrieval"]["recall@5"]["pass"]["count"] == 0,
                  f"{s['retrieval']['recall@5']['pass']['count']}/{want['answerable']}")
            check("MRR 0.0", s["mrr"] == 0.0, str(s["mrr"]))
            check(f"not-found (a) dev {want['notfound_dev']}/{want['notfound_dev']}",
                  s["notfound_a"]["count"] == want["notfound_dev"],
                  f"{s['notfound_a']['count']}/{want['notfound_dev']}")
            check(f"not-found (b) 0/{want['answerable']}",
                  s["notfound_b"]["count"] == 0, f"{s['notfound_b']['count']}/{want['answerable']}")

        # ---------------------------------------------------------- partial
        print("case 3: partial run, with diff against perfect")
        out = tmp / "partial"
        r = run_score(FIXTURES / "partial.jsonl", out, baseline=FIXTURES / "perfect.jsonl")
        check("exit 0", r.returncode == 0, "scored")
        if r.returncode == 0:
            data = scores_of(out)
            s, d = data["summary"], data["diff"]
            check(f"passed {want['partial_passed']}/{want['n']}",
                  s["passed"]["count"] == want["partial_passed"],
                  f"{s['passed']['count']}/{want['n']}")
            check(f"{len(want['partial_to_fail'])} pass -> fail",
                  d["pass_to_fail"] == want["partial_to_fail"],
                  f"{len(d['pass_to_fail'])} regressions: {d['pass_to_fail'][:3]}...")
            check("0 fail -> pass", len(d["fail_to_pass"]) == 0, str(d["fail_to_pass"]))
            check("no phantom ids", not d["only_in_current"] and not d["only_in_baseline"],
                  "ids match")

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
        target = questions[0]["gold_sources"][0]["file"]
        for q in questions:
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

        # ------------------------------------------------ extra pages (step 18, D-097)
        print("case 6: a verified extra page is allowed, capped at two")
        base_q = next(q for q in questions if q["id"] == "q001")
        src = base_q["gold_sources"][0]
        gold_c = {"file": src["file"], "page": src["page"], "quote": base_q["gold_quote"]}
        with pymupdf.open(ROOT / src["file"]) as doc:
            page_count = doc.page_count
        others = [p for p in range(1, page_count + 1) if p != src["page"]][:3]
        extras = [{"file": src["file"], "page": p, "quote": page_text(src["file"], p)[:60]}
                  for p in others]

        def row(citations: list[dict]) -> dict:
            return {"id": "q001",
                    "retrieved": [{"file": src["file"], "page": src["page"], "score": 1.0}],
                    "answer": base_q["gold_answer"], "citations": citations,
                    "said_not_found": False}

        paraphrase = {"file": src["file"], "page": others[0],
                      "quote": "this text is not on the page"}
        for name, citations, want_ok, want_extra in (
            ("gold only", [gold_c], True, 0),
            ("gold + one verified extra", [gold_c, extras[0]], True, 1),
            ("gold + two verified extras", [gold_c, extras[0], extras[1]], True, 2),
            ("gold + three verified extras", [gold_c] + extras, False, 3),
            ("gold + a paraphrase on the extra page", [gold_c, paraphrase], False, 1),
            ("extra page but no gold page", [extras[0]], False, 1),
        ):
            got = score.score_question(base_q, row(citations))
            check(f"{name}: citation_ok={want_ok}, extras={want_extra}",
                  got["citation_ok"] is want_ok and got["extra_citations"] == want_extra,
                  f"citation_ok={got['citation_ok']} extras={got['extra_citations']} "
                  f"passed={got['passed']}")

        # ---------------------------------------- one page-text reader (step 19, D-098)
        print("case 7: the scorer reads a page the way the verifier does")
        check("the scorer uses corpus.page_text",
              score.shared_page_text.__module__ == "corpus",
              f"{score.shared_page_text.__module__}.{score.shared_page_text.__name__}")
        # A scanned page: no text layer, so the indexed OCR text is the only text there is.
        scan = ("0_NARAYAN_Investigation_of_Soil_Liquefaction_in_Kathmandu_Valley_and_R"
                "_W7208248247.pdf")
        scan_file = f"data/corpus/{scan}"
        if (ROOT / scan_file).exists():
            ocr_quote = norm(score.shared_page_text(scan, 1))[:80]
            raw_text = page_text(scan_file, 1)
            scan_q = {"id": "scan", "type": "fact", "answerable": True, "gold_numbers": [],
                      "gold_sources": [{"file": scan_file, "page": 1, "sha256": ""}]}
            scan_row = {"id": "scan", "said_not_found": False, "answer": "a fact",
                        "retrieved": [{"file": scan_file, "page": 1, "score": 1.0}],
                        "citations": [{"file": scan_file, "page": 1, "quote": ocr_quote}]}
            check("that page has no text layer to quote", not raw_text,
                  f"raw characters on the page: {len(raw_text)}")
            got = score.score_question(scan_q, scan_row)
            check("a quote from the OCR text verifies", got["citation_ok"] is True,
                  f"citation_ok={got['citation_ok']}")
        else:
            check("the scanned test document is present", False, "data/corpus file missing")
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
