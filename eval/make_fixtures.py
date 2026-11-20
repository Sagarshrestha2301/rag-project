"""Build hand-made fake run files used to test the scorer (Step 1 task 7).

The scorer must be proven against outputs whose scores are known in advance,
before any real retrieval exists.

Fixtures written to eval/fixtures/:
    perfect.jsonl  every question answered from the gold page with the gold quote
    empty.jsonl    nothing retrieved, "not found" everywhere
    partial.jsonl  first half perfect, second half wrong page / wrong number
    outside.jsonl  cites data/raw/ instead of data/corpus/ (must be rejected)

Usage:
    .venv\\Scripts\\python.exe eval\\make_fixtures.py
"""

from __future__ import annotations

import json
import pathlib

import pymupdf

QUESTIONS = pathlib.Path("eval/questions.jsonl")
FIXTURES = pathlib.Path("eval/fixtures")


def load_questions() -> list[dict]:
    return [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines() if line.strip()]


def other_page(path: str, page: int) -> int:
    with pymupdf.open(path) as doc:
        pages = doc.page_count
    return page + 1 if page < pages else 1


def perfect_row(q: dict) -> dict:
    # The answerable check comes first: an unanswerable question has no gold source in
    # the grown set, and reading [0] before this check is what broke the rebuild.
    if not q["answerable"] or not q["gold_sources"]:
        return {"id": q["id"], "retrieved": [], "answer": "", "citations": [],
                "said_not_found": True, "timings": {"retrieve_s": 0.1}}
    src = q["gold_sources"][0]
    return {
        "id": q["id"],
        "retrieved": [{"file": src["file"], "page": src["page"], "score": 0.95},
                      {"file": src["file"], "page": other_page(src["file"], src["page"]), "score": 0.40}],
        "answer": q["gold_answer"],
        "citations": [{"file": src["file"], "page": src["page"], "quote": q["gold_quote"]}],
        "said_not_found": False,
        "timings": {"retrieve_s": 0.1, "rerank_s": 0.05, "generate_s": 0.8},
    }


def empty_row(q: dict) -> dict:
    return {"id": q["id"], "retrieved": [], "answer": "", "citations": [],
            "said_not_found": True, "timings": {"retrieve_s": 0.1}}


def broken_row(q: dict) -> dict:
    """Wrong page, wrong quote, wrong answer, but still an answer.

    An unanswerable question has no gold source to get wrong, so it stays a refusal: the
    fixture's point is the *second half of the set* failing, not a crash on a row with no
    gold page to mangle.
    """
    if not q["answerable"] or not q["gold_sources"]:
        return empty_row(q)
    src = q["gold_sources"][0]
    wrong = other_page(src["file"], src["page"])
    return {
        "id": q["id"],
        "retrieved": [{"file": src["file"], "page": wrong, "score": 0.30}],
        "answer": "I could not determine this from the documents.",
        "citations": [{"file": src["file"], "page": wrong, "quote": "this text is not on the page"}],
        "said_not_found": False,
        "timings": {"retrieve_s": 0.1},
    }


def outside_row(q: dict) -> dict:
    if not q["answerable"] or not q["gold_sources"]:
        return empty_row(q)
    src = q["gold_sources"][0]
    outside = src["file"].replace("data/corpus/", "data/raw/")
    return {
        "id": q["id"],
        "retrieved": [{"file": outside, "page": src["page"], "score": 0.9}],
        "answer": q["gold_answer"],
        "citations": [{"file": outside, "page": src["page"], "quote": q["gold_quote"]}],
        "said_not_found": False,
        "timings": {"retrieve_s": 0.1},
    }


def write(name: str, rows: list[dict]) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    path = FIXTURES / name
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {path} ({len(rows)} rows)")


def main() -> int:
    questions = load_questions()
    half = len(questions) // 2

    write("perfect.jsonl", [perfect_row(q) for q in questions])
    write("empty.jsonl", [empty_row(q) for q in questions])
    write("partial.jsonl", [perfect_row(q) if i < half else broken_row(q)
                            for i, q in enumerate(questions)])
    write("outside.jsonl", [outside_row(q) for q in questions])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
