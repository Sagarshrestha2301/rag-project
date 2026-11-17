"""Measure, on the saved 55-question run, what a per-sentence number check would flag.

Read-only. For each answer: drop the citation list, split the prose into sentences, take
the numbers a sentence states (inline [n] markers and digits glued to letters such as P0
or m3 excluded), and compare each number with every page the sentence's markers name.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from corpus import page_text

RUN = pathlib.Path("eval/runs/2026-11-16-step6-full/run.jsonl")
INLINE = re.compile(r"\[(\d+)\]")
# A citation list line, in either shape the model produces:
#   [1] name.pdf, p. 3: "quote"        /  [1] Das 1970, page 6, file name.pdf, p. 6: "quote"
CITATION_BLOCK = re.compile(r"\n\s*\[\d+\][^\n]*p\.?\s*\d+\s*[:.\-–—].*$", re.DOTALL)
# A number a sentence states: not glued to a letter (P0, m3, Q100) or a file-name digit.
NUMBER = re.compile(r"(?<![A-Za-z0-9_.])\d[\d,]*(?:\.\d+)?(?![A-Za-z0-9])")
SENTENCE = re.compile(r"(?<=[.!?])\s+")


def page_numbers(text: str) -> set[str]:
    return {raw.replace(",", "") for raw in NUMBER.findall(text or "")}


def prose(answer: str) -> str:
    text = answer or ""
    cut = CITATION_BLOCK.search(text)
    return (text[:cut.start()] if cut else text).strip()


def main() -> int:
    rows = [json.loads(line) for line in RUN.read_text(encoding="utf-8").splitlines() if line.strip()]
    cites = {row["id"]: {c["n"]: (c["file"], c["page"]) for c in row.get("citations") or []}
             for row in rows}

    answers = checked = 0
    misses, blind = [], []
    for row in rows:
        body = prose(row.get("answer") or "")
        if not body:
            continue
        answers += 1
        for sentence in SENTENCE.split(body):
            sentence = sentence.strip()
            if not sentence:
                continue
            numbers = [raw.replace(",", "") for raw in NUMBER.findall(INLINE.sub(" ", sentence))]
            markers = sorted({int(n) for n in INLINE.findall(sentence)})
            if not numbers or not markers:
                continue
            pages = [cites[row["id"]][m] for m in markers if m in cites[row["id"]]]
            if not pages:
                blind.append({"id": row["id"], "numbers": numbers, "sentence": sentence})
                continue
            for number in numbers:
                checked += 1
                if any(number in page_numbers(page_text(file, page)) for file, page in pages):
                    continue
                misses.append({"id": row["id"], "number": number, "markers": markers,
                               "pages": pages, "sentence": sentence})

    affected = {m["id"] for m in misses}
    print(f"answers with prose: {answers} of {len(rows)}")
    print(f"numbers checked (sentence has a [n] and a number): {checked}")
    print(f"numbers missing from every page the sentence cites: {len(misses)}")
    print(f"answers that would become unverified: {len(affected)} of {answers}")
    print(f"sentences whose markers resolved to no citation: {len(blind)}")
    print()
    for miss in misses:
        where = ", ".join(f"{pathlib.PurePosixPath(f).name[:26]} p{p}" for f, p in miss["pages"])
        print(f"{miss['id']}  {miss['number']:>9}  [{','.join(map(str, miss['markers']))}] {where}")
        print(f"      {miss['sentence'][:160]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
