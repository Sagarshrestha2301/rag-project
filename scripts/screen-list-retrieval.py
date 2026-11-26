"""Stage 1 of Step 16: what the list change touches, measured without calling a model.

The step's guarantee is that a question the list trigger does not match receives
byte-identical input, so it cannot answer differently. This screen proves it by hashing
what the model would be given - the rendered prompt and every retrieved passage - for all
55 questions, and comparing against a baseline captured before the change.

Usage:
    # once, on the code as it was before the change:
    .venv\\Scripts\\python.exe scripts\\screen-list-retrieval.py --write-baseline
    # after the change (exit 1 if a canary moved or the change is wider than designed):
    .venv\\Scripts\\python.exe scripts\\screen-list-retrieval.py

The baseline is `reports/list-retrieval-baseline-hashes.json`. It holds hashes only, so it
is small and can be committed as the evidence the guarantee rests on.

Example (compare run, after the change):
    $ python scripts/screen-list-retrieval.py
    trigger fires on: q036, q050
    changed: q036, q050   (2 of 55)
    canaries unchanged: q002, q004, q006, q013
    q036 passage 1367 -> 1623 chars, contains 'Sunkosi': True, '1964': True
    PASS
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import corpus                                              # noqa: E402
from generation import prompt, router                      # noqa: E402

QUESTIONS = ROOT / "eval" / "questions.jsonl"
BASELINE = ROOT / "reports" / "list-retrieval-baseline-hashes.json"
REPORT = ROOT / "reports" / "list-retrieval-screen-2026-11-25.md"
CANARIES = ("q002", "q004", "q006", "q013")
LIST_QUESTIONS = ("q036", "q050")
# The trigger as designed in steps/16-list-retrieval.md. Imported from the router when it
# has one, so this screen measures the shipped rule rather than a copy of it.
FALLBACK = re.compile(
    r"\b(list|enumerate)\b|\bname the\b"
    r"|\bwhich\s+[a-z]+s\s+(can|could|are|were|do|did|have|include)\b",
    re.IGNORECASE,
)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def trigger() -> re.Pattern:
    return getattr(router, "LIST", FALLBACK)


def search(index: dict, question: str, k: int, is_list: bool) -> list[dict]:
    """Search with the new `cover` keyword when it exists, today's call otherwise.

    The baseline is captured on the pre-change code, so this file has to run both before
    and after the change; anything else would make the comparison depend on a copy of the
    old code rather than on the old code itself.
    """
    try:
        return corpus.search(index, question, k=k, cover=is_list)
    except TypeError:
        return corpus.search(index, question, k=k)


def render(hits: list[dict], mode: str, is_list: bool) -> str:
    try:
        return prompt.build_system(hits, mode=mode, list_style=is_list)
    except TypeError:
        return prompt.build_system(hits, mode=mode)


def snapshot(index: dict, questions: list[dict]) -> dict:
    """What the model would be given for each question: prompt hash, passage hashes."""
    out = {}
    for record in questions:
        routed = router.route(record["question"], record.get("history") or [])
        if routed["k"] == 0:
            continue
        is_list = bool(routed.get("list")) or bool(trigger().search(record["question"]))
        hits = search(index, record["question"], routed["k"], is_list)
        text = render(hits, routed["prompt_mode"], is_list)
        out[record["id"]] = {
            "prompt": sha(text),
            "contexts": [sha(h["context"]) for h in hits],
            "pages": [f"{h['doc']}#{h['page']}" for h in hits],
            "chars": [len(h["context"]) for h in hits],
        }
    return out


def contains(index: dict, question_id: str, questions: list[dict], needles: tuple[str, ...]) -> dict:
    record = next(q for q in questions if q["id"] == question_id)
    routed = router.route(record["question"], record.get("history") or [])
    is_list = bool(routed.get("list")) or bool(trigger().search(record["question"]))
    hits = search(index, record["question"], routed["k"], is_list)
    body = " ".join(h["context"] for h in hits)
    top = hits[0] if hits else {"page": None, "context": ""}
    return {"chars": [len(h["context"]) for h in hits],
            "top_page": top.get("page"),
            "top_chars": len(top["context"]),
            "found": {needle: needle.lower() in body.lower() for needle in needles}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-baseline", action="store_true",
                        help="record hashes for the code as it is now (run before the change)")
    args = parser.parse_args()

    questions = [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines()
                 if line.strip()]
    index = corpus.build()
    fired = [q["id"] for q in questions if trigger().search(q["question"])]
    now = snapshot(index, questions)

    if args.write_baseline:
        BASELINE.write_text(json.dumps(now, indent=1, sort_keys=True), encoding="utf-8")
        print(f"wrote {BASELINE.relative_to(ROOT)}: {len(now)} questions hashed")
        print("trigger fires on:", ", ".join(fired) or "(nothing)")
        return 0

    if not BASELINE.exists():
        print(f"FAIL  no baseline at {BASELINE.relative_to(ROOT)}; run --write-baseline "
              "on the pre-change code first")
        return 1
    before = json.loads(BASELINE.read_text(encoding="utf-8"))

    changed = [qid for qid in now if before.get(qid) != now[qid]]
    missing = [qid for qid in before if qid not in now]
    canary_moved = [qid for qid in CANARIES if qid in changed]
    wider = [qid for qid in changed if qid not in LIST_QUESTIONS]

    q036 = contains(index, "q036", questions, ("Sunkosi", "1964", "1984"))
    q050 = contains(index, "q050", questions, ("ginger", "11-15"))

    old_chars = (before.get("q036", {}).get("chars") or [None])[0]
    lines = [
        "# Stage 1 screen: Step 16 list retrieval",
        "",
        "Written by `scripts/screen-list-retrieval.py`; no model was called.",
        f"Baseline: `{BASELINE.relative_to(ROOT).as_posix()}` (captured before the change).",
        "",
        "## Trigger",
        "",
        f"Fires on **{len(fired)} of {len(questions)}** questions: "
        + (", ".join(f"`{q}`" for q in fired) or "(none)"),
        "",
        f"- designed for: {', '.join(f'`{q}`' for q in LIST_QUESTIONS)}",
        f"- canaries that must not fire: {', '.join(f'`{q}`' for q in CANARIES)}",
        "",
        "## What the model would be given",
        "",
        f"- questions compared: **{len(now)}**",
        f"- changed prompt or passages: **{len(changed)}** — "
        + (", ".join(f"`{q}`" for q in changed) or "(none)"),
        f"- changed but **not** a list question (must be empty): "
        + (", ".join(f"`{q}`" for q in wider) or "none"),
        f"- canaries changed (must be empty): " + (", ".join(f"`{q}`" for q in canary_moved) or "none"),
        f"- questions in the baseline but not now (must be empty): "
        + (", ".join(f"`{q}`" for q in missing) or "none"),
        "",
        "## The two list questions",
        "",
        "| question | top page | top passage chars | needed words present |",
        "|---|---|---|---|",
        f"| q036 | {q036['top_page']} | {q036['top_chars']} (was {old_chars}) | "
        + ", ".join(f"`{w}` {'yes' if ok else 'NO'}" for w, ok in q036["found"].items()) + " |",
        f"| q050 | {q050['top_page']} | {q050['top_chars']} | "
        + ", ".join(f"`{w}` {'yes' if ok else 'NO'}" for w, ok in q050["found"].items()) + " |",
        "",
    ]
    ok = (not canary_moved and not missing and not wider
          and sorted(changed) == sorted(LIST_QUESTIONS)
          and all(q036["found"].values()))
    lines += ["## Result", "",
              "**PASS** — exactly the two list questions change, the four canaries are "
              "byte-identical, and q036's passage carries its sentence."
              if ok else
              "**FAIL** — the change is wider than designed, a canary moved, or q036's "
              "sentence is still missing. Do not run the model."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("trigger fires on:", ", ".join(fired) or "(nothing)")
    print("changed:", ", ".join(changed) or "(none)")
    print("canaries unchanged:", ", ".join(q for q in CANARIES if q not in changed) or "(none)")
    print(f"q036 passage {old_chars} -> {q036['top_chars']} chars, needs: {q036['found']}")
    print(f"q050 passage {q050['top_chars']} chars, needs: {q050['found']}")
    print("PASS" if ok else "FAIL")
    print(f"report: {REPORT.relative_to(ROOT)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
