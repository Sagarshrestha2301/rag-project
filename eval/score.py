"""Score a run against the eval set (implements eval/SCORER.md).

Usage:
    .venv\\Scripts\\python.exe eval\\score.py --run eval/runs/<label>/run.jsonl --out eval/runs/<label>
    .venv\\Scripts\\python.exe eval\\score.py --run <run.jsonl> --baseline <baseline.jsonl> --out <dir>

Quotations are checked with `corpus.page_text`, the same reader the verifier uses: the PDF's
text, and the indexed OCR text for a page that has no text layer. A quotation may differ from
the page only in the case of its first letter, through the same `corpus.quote_case_variant`
the verifier uses (step 20, D-100).

Exits non-zero, without writing any scores, if a referenced corpus file is
missing, outside the corpus root, or its SHA-256 differs from the gold record.
That is the guard against a re-converted document silently shifting pages.

Example (one run line):
    {"id": "q001",
     "retrieved": [{"file": "data/corpus/x.pdf", "page": 2, "score": 0.9}],
     "answer": "540 mm",
     "citations": [{"file": "data/corpus/x.pdf", "page": 2, "quote": "The 24-hour rainfall depth of 540 mm at Tistung"}],
     "said_not_found": false}
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

# The project root, so the scorer can use the corpus module's page reader (step 19, D-098):
# a quotation is checked against the same text `generation/verify.py` checks it against.
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from corpus import page_text as shared_page_text, quote_case_variant  # noqa: E402

DEFAULT_QUESTIONS = "eval/questions.jsonl"
DEFAULT_CORPUS_ROOT = "data/corpus"
RECALL_KS = (5, 10, 30)
SUMMARY_TYPES = {"summary", "comparison"}
# How many cited pages may lie outside the gold set before the citation is a failure
# (step 18, D-097). The widest answer that passes today uses two, so two is the cap;
# the point is to stop an answer being built from unrelated pages, not to count citations.
MAX_EXTRA_CITATIONS = 2


# ---------------------------------------------------------------- normalisation

def norm_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


# Units that must appear alongside the number. Counts, years and coefficients are
# deliberately not required: "139 households" and "71 growers" are the same
# quantity, and a bare coefficient has no unit in prose.
_UNIT_ALIASES = [
    (r"m\s*3\s*[/\s]*s\s*-?\s*1?\s*[/\s]*km\s*-?\s*(?:2|\^2)|m3s-1\s*km-2", "m3/s/km2"),
    (r"m\s*3\s*[/\s]*s\s*-?\s*1?\b|m3s\s*-?\s*1|cumec", "m3/s"),
    (r"mm\s*(?:h\s*-?\s*1|/\s*h|per\s+hour)", "mm/h"),
    (r"km\s*-?\s*(?:2|\^2)", "km2"),
    (r"\bhouseholds?\b|\bhh\b", "household"),
]
REQUIRED_UNITS = {"mm", "m3/s", "m3/s/km2", "km2", "mm/h"}


def norm_measures(text: str) -> str:
    """Lowercase, drop thousands separators, and fold unit spellings."""
    t = norm_space(text).lower().replace(",", "")
    for pattern, repl in _UNIT_ALIASES:
        t = re.sub(pattern, repl, t)
    return t


def norm_unit(unit: str) -> str:
    return norm_measures(unit).strip()


def norm_number(value: str) -> str:
    v = norm_space(str(value)).replace(",", "").replace(" ", "")
    try:
        return str(float(v)).rstrip("0").rstrip(".")
    except ValueError:
        return v.lower()


def answer_has_number(answer: str, value: str, unit: str) -> bool:
    """True if the answer contains the value and, for a physical measure, its unit."""
    a = norm_measures(answer)
    target = re.escape(norm_number(value))
    if not re.search(rf"(?<![\d.]){target}(?![\d])", a):
        return False
    u = norm_unit(unit)
    if u not in REQUIRED_UNITS:
        return True
    return u in a


# ---------------------------------------------------------------- integrity

def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_integrity(questions: list[dict], run: list[dict], corpus_root: pathlib.Path) -> list[str]:
    """Return a list of problems. Non-empty means the run must be rejected."""
    root = corpus_root.resolve()
    # a file may appear in many questions: keep every recorded hash, not the last
    expected: dict[str, set[str]] = {}
    for q in questions:
        for src in q["gold_sources"]:
            expected.setdefault(src["file"], set()).add(src["sha256"])

    referenced = set(expected)
    for row in run:
        for key in ("retrieved", "citations"):
            for item in row.get(key) or []:
                referenced.add(item["file"])

    problems = []
    for rel in sorted(referenced):
        path = pathlib.Path(rel)
        if not path.exists():
            problems.append(f"missing file: {rel}")
            continue
        if root not in path.resolve().parents:
            problems.append(f"outside corpus root: {rel}")
            continue
        if rel in expected:
            actual = sha256_file(path)
            if len(expected[rel]) > 1:
                problems.append(f"conflicting gold hashes recorded for {rel}: {sorted(expected[rel])}")
            if actual not in expected[rel]:
                problems.append(f"SHA-256 mismatch: {rel}\n  expected {sorted(expected[rel])[0]}\n  actual   {actual}")
    return problems


# ---------------------------------------------------------------- scoring

def gold_pairs(q: dict) -> set[tuple[str, int]]:
    return {(s["file"], s["page"]) for s in q["gold_sources"]}


def score_question(q: dict, row: dict | None) -> dict:
    retrieved = (row or {}).get("retrieved") or []
    answer = (row or {}).get("answer") or ""
    citations = (row or {}).get("citations") or []
    said_not_found = bool((row or {}).get("said_not_found"))
    gold = gold_pairs(q)

    ranks = []
    for i, item in enumerate(retrieved, start=1):
        if (item["file"], item["page"]) in gold:
            ranks.append(i)
    first_rank = min(ranks) if ranks else None

    out: dict = {"id": q["id"], "type": q["type"], "answerable": q["answerable"],
                 "retrieval_scored": q["answerable"], "first_rank": first_rank, "recall": {}}

    for k in RECALL_KS:
        if q["type"] in SUMMARY_TYPES:
            needed = len(gold)
            hit = len({(i["file"], i["page"]) for i in retrieved[:k]} & gold)
            frac = hit / needed if needed else 0.0
            out["recall"][k] = (frac, frac >= 0.5)
        else:
            out["recall"][k] = (1.0 if first_rank and first_rank <= k else 0.0,
                                bool(first_rank and first_rank <= k))

    out["mrr"] = 1.0 / first_rank if first_rank else 0.0

    # Citation correctness (step 18, D-097): the answer must cite at least one gold page,
    # every quotation must exist on the page it names, and at most MAX_EXTRA_CITATIONS cited
    # pages may lie outside the gold set. The gold page is still required, because that is
    # what stops an answer being sourced from a distractor page; the cap stops the opposite
    # failure, an answer padded with true pages. `extra_citations` records the count.
    # A not-found question has nothing to cite, so it is not scored on citation.
    if q["answerable"]:
        gold_cited = any((c["file"], c["page"]) in gold for c in citations)
        extra = sum(1 for c in citations if (c["file"], c["page"]) not in gold)
        quotes_ok = True
        for c in citations:
            if not pathlib.Path(c["file"]).exists():
                quotes_ok = False
                break
            # One page reader for both halves of the system: the PDF's text, with the indexed
            # OCR text for a page that has no text layer. A second reader here failed a quote
            # the pipeline had already verified (q003, step 19).
            page = norm_space(shared_page_text(pathlib.PurePosixPath(c["file"]).name, c["page"]))
            quote_n = norm_space(c.get("quote", ""))
            flipped = quote_case_variant(quote_n)
            if quote_n not in page and (flipped is None or flipped not in page):
                quotes_ok = False
                break
        out["citation_ok"] = bool(citations) and gold_cited and quotes_ok and extra <= MAX_EXTRA_CITATIONS
        out["extra_citations"] = extra
    else:
        out["citation_ok"] = None
        out["extra_citations"] = None

    if q["gold_numbers"]:
        out["numeric_ok"] = all(answer_has_number(answer, n["value"], n.get("unit", ""))
                                for n in q["gold_numbers"])
    else:
        out["numeric_ok"] = None

    if q["answerable"]:
        out["notfound_correct"] = not said_not_found and bool(answer.strip())
        out["notfound_case"] = "b"
    else:
        out["notfound_correct"] = said_not_found or not answer.strip()
        out["notfound_case"] = "a"

    if q["answerable"]:
        out["passed"] = bool(
            out["recall"][RECALL_KS[0]][1]
            and out["citation_ok"] is not False
            and (out["numeric_ok"] is not False)
            and out["notfound_correct"]
        )
    else:
        # nothing exists to retrieve: only the refusal is scored
        out["passed"] = out["notfound_correct"]
    return out


def pct(count: int, total: int) -> dict:
    return {"count": count, "of": total, "pct": round(100 * count / total, 1) if total else 0.0}


def _metrics(results: list[dict], questions: list[dict], split: str | None = None) -> dict:
    by_id = {q["id"]: q for q in questions}
    rows = [r for r in results if split is None or by_id[r["id"]]["split"] == split]
    answerable = [r for r in rows if by_id[r["id"]]["answerable"]]
    unanswerable = [r for r in rows if not by_id[r["id"]]["answerable"]]
    with_numbers = [r for r in rows if r["numeric_ok"] is not None]

    # recall, MRR and citation are scored on answerable questions only: a not-found
    # question has no page to retrieve and nothing to cite (eval/SCORER.md).
    retrieval = {f"recall@{k}": {"pass": pct(sum(1 for r in answerable if r["recall"][k][1]), len(answerable))}
                 for k in RECALL_KS}
    mrr = sum(r["mrr"] for r in answerable) / len(answerable) if answerable else 0.0

    # not-found (a) is gated on the dev set, so the overall figure is the dev one
    gate_a = [r for r in unanswerable if by_id[r["id"]]["split"] == "dev"] if split is None else unanswerable
    return {
        "n": len(rows),
        "retrieval": retrieval,
        "mrr": round(mrr, 3),
        "citation": pct(sum(1 for r in answerable if r["citation_ok"]), len(answerable)),
        "extra_citations": {
            "total": sum(r.get("extra_citations") or 0 for r in answerable),
            "max": max((r.get("extra_citations") or 0 for r in answerable), default=0),
            "answers": sum(1 for r in answerable if (r.get("extra_citations") or 0) > 0),
        },
        "numeric": pct(sum(1 for r in with_numbers if r["numeric_ok"]), len(with_numbers)),
        "notfound_a": pct(sum(1 for r in gate_a if r["notfound_correct"]), len(gate_a)),
        "notfound_a_scope": "dev" if split is None else split,
        "notfound_b": pct(sum(1 for r in answerable if r["notfound_correct"]), len(answerable)),
        "passed": pct(sum(1 for r in rows if r["passed"]), len(rows)),
        "points_per_question": round(100 / len(rows), 2) if rows else 0.0,
    }


def summarize(results: list[dict], questions: list[dict]) -> dict:
    out = _metrics(results, questions)
    out["by_split"] = {sp: _metrics(results, questions, sp) for sp in ("dev", "heldout")}
    # points are only meaningful per scored set (dev / held-out), never over both
    out["points_per_question"] = None
    out["points_per_question_by_split"] = {sp: m["points_per_question"] for sp, m in out["by_split"].items()}
    return out


def diff(baseline: list[dict], current: list[dict]) -> dict:
    b = {r["id"]: r for r in baseline}
    c = {r["id"]: r for r in current}
    return {
        "pass_to_fail": sorted(qid for qid in c if qid in b and b[qid]["passed"] and not c[qid]["passed"]),
        "fail_to_pass": sorted(qid for qid in c if qid in b and not b[qid]["passed"] and c[qid]["passed"]),
        "only_in_current": sorted(set(c) - set(b)),
        "only_in_baseline": sorted(set(b) - set(c)),
    }


def to_markdown(summary: dict, results: list[dict], d: dict | None, label: str) -> str:
    pts = summary.get("points_per_question_by_split") or {}
    per_set = ", ".join(f"{sp} {v} points" for sp, v in pts.items()) or "points not fixed"
    lines = [f"# Scores: {label}", "", f"{summary['n']} questions; one question is worth: {per_set}", ""]
    for key in ("recall@5", "recall@10", "recall@30"):
        v = summary["retrieval"][key]["pass"]
        lines.append(f"- {key}: {v['count']}/{v['of']} ({v['pct']}%) [answerable only]")
    lines.append(f"- MRR: {summary['mrr']}")
    for key in ("citation", "numeric", "notfound_a", "notfound_b", "passed"):
        v = summary[key]
        scope = " [dev]" if key == "notfound_a" else ""
        lines.append(f"- {key}{scope}: {v['count']}/{v['of']} ({v['pct']}%)")
    ex = summary.get("extra_citations")
    if ex:
        lines.append(f"- extra citations: {ex['total']} page(s) across {ex['answers']} answer(s), "
                     f"max {ex['max']} (cap {MAX_EXTRA_CITATIONS})")

    lines += ["", "## By split", "",
              "| split | n | recall@5 | MRR | citation | numeric | nf(a) | nf(b) | passed |",
              "|---|---|---|---|---|---|---|---|---|"]
    for sp, m in summary.get("by_split", {}).items():
        r5 = m["retrieval"]["recall@5"]["pass"]
        lines.append(f"| {sp} | {m['n']} | {r5['count']}/{r5['of']} | {m['mrr']} | "
                     f"{m['citation']['count']}/{m['citation']['of']} | "
                     f"{m['numeric']['count']}/{m['numeric']['of']} | "
                     f"{m['notfound_a']['count']}/{m['notfound_a']['of']} | "
                     f"{m['notfound_b']['count']}/{m['notfound_b']['of']} | "
                     f"{m['passed']['count']}/{m['n']} |")
    lines += ["", "| id | type | rank | cite | numeric | not-found | verdict |", "|---|---|---|---|---|---|---|"]
    for r in results:
        num = "n/a" if r["numeric_ok"] is None else ("ok" if r["numeric_ok"] else "FAIL")
        cite = "n/a" if r["citation_ok"] is None else ("ok" if r["citation_ok"] else "FAIL")
        lines.append(f"| {r['id']} | {r['type']} | {r['first_rank'] or '-'} | "
                     f"{cite} | {num} | "
                     f"{'ok' if r['notfound_correct'] else 'FAIL'} | {'PASS' if r['passed'] else 'FAIL'} |")
    if d is not None:
        lines += ["", "## Diff vs baseline", f"- pass -> fail: {', '.join(d['pass_to_fail']) or 'none'}",
                  f"- fail -> pass: {', '.join(d['fail_to_pass']) or 'none'}"]
    return "\n".join(lines) + "\n"


def load_jsonl(path: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--questions", default=DEFAULT_QUESTIONS)
    ap.add_argument("--corpus-root", default=DEFAULT_CORPUS_ROOT)
    ap.add_argument("--baseline")
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default=None)
    args = ap.parse_args()

    questions = load_jsonl(pathlib.Path(args.questions))
    run_path = pathlib.Path(args.run)
    if not run_path.exists():
        print(f"STOP: run file not found: {run_path}")
        return 2
    run = load_jsonl(run_path)

    problems = check_integrity(questions, run, pathlib.Path(args.corpus_root))
    if problems:
        print("STOP: corpus integrity check failed, no scores written:")
        for p in problems:
            print("  -", p)
        return 3

    by_id = {r["id"]: r for r in run}
    results = [score_question(q, by_id.get(q["id"])) for q in questions]
    summary = summarize(results, questions)

    baseline_results = None
    d = None
    if args.baseline:
        base = load_jsonl(pathlib.Path(args.baseline))
        base_by_id = {r["id"]: r for r in base}
        baseline_results = [score_question(q, base_by_id.get(q["id"])) for q in questions]
        d = diff(baseline_results, results)

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    label = args.label or run_path.stem
    (out_dir / "scores.json").write_text(json.dumps(
        {"label": label, "summary": summary, "results": results, "diff": d}, indent=2), encoding="utf-8")
    (out_dir / "scores.md").write_text(to_markdown(summary, results, d, label), encoding="utf-8")

    pts = summary["points_per_question_by_split"]
    print(f"{label}: {summary['n']} questions (dev {pts['dev']} pts each, held-out {pts['heldout']} pts each)")
    print(f"  recall@5  {summary['retrieval']['recall@5']['pass']['count']}/{summary['retrieval']['recall@5']['pass']['of']}")
    print(f"  MRR       {summary['mrr']}")
    print(f"  citation  {summary['citation']['count']}/{summary['citation']['of']}")
    print(f"  numeric   {summary['numeric']['count']}/{summary['numeric']['of']}")
    print(f"  nf(a) dev {summary['notfound_a']['count']}/{summary['notfound_a']['of']}")
    print(f"  nf(b)     {summary['notfound_b']['count']}/{summary['notfound_b']['of']}")
    print(f"  passed    {summary['passed']['count']}/{summary['n']}")
    for sp, m in summary["by_split"].items():
        print(f"  {sp:<8}  {m['passed']['count']}/{m['n']} passed")
    print(f"  wrote {out_dir/'scores.json'} and {out_dir/'scores.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
