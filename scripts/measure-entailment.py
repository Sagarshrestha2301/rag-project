"""Prototype: does the quote a sentence cites actually support it? (D-067, measure only)

The verifier proves a quotation exists on the cited page and that a number in the citing
sentence appears in that quotation. It does not judge the sentence itself, so an inference
built on the quote ("the data indicates Tistung received more") counts as verified.

This script puts that gap on the record: for every factual sentence in a saved eval run
that carries a `[n]`, it asks the local model whether that sentence follows from the
quoted text for `[n]`. It writes `reports/entailment.md` and prints a summary. It is a
measurement, never a gate: the judge is a 4B model, so its verdict is a secondary signal
(D-010, D-058).

Usage:
    .venv\\Scripts\\python.exe scripts\\measure-entailment.py
    .venv\\Scripts\\python.exe scripts\\measure-entailment.py --run eval/runs/<dir> --limit 10
    .venv\\Scripts\\python.exe scripts\\measure-entailment.py --selftest

One judged sentence, as the report lists it:
    q017 [1] PARTIAL  "The data indicates that Tistung received a greater amount ..."
         reason: the quote gives both depths, but does not compare them
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time

import httpx

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_RUN = ROOT / "eval" / "runs" / "2026-11-19-step8-full"
QUESTIONS = ROOT / "eval" / "questions.jsonl"
PAGES = ROOT / "index" / "pages.json"
RESULTS = ROOT / "reports" / "entailment.jsonl"
DIGITS = re.compile(r"\d[\d.,]*\d|\d")
OUT = ROOT / "reports" / "entailment.md"
OLLAMA_URL = "http://127.0.0.1:11434"
MODEL = "qwen3.5:4b"

REFUSAL = re.compile(r"(do not|does not|did not) (state|contain|mention|provide)|"
                     r"not found in the indexed", re.I)
MARKER = re.compile(r"\[(\d{1,2})\]")
# `[1] file.pdf, p. 2: "quotation"`
CITATION = re.compile(r"^\[(\d{1,2})\]\s+(.+?),\s*p\.\s*(\d+)\s*:\s*\"(.+?)\"\s*$", re.M)
SENTENCE = re.compile(r"(?<=[.!?])\s+")

PROMPT = """You check one sentence against the passages it cites. The only evidence is\
 the quoted text below. Do not use outside knowledge and do not decide whether the quote\
 is true.

Answer with one word on the first line: SUPPORTED, PARTIAL or UNSUPPORTED.
- SUPPORTED: every claim in the sentence is stated or directly implied by the quote.
- PARTIAL: part of the sentence is in the quote and part goes beyond it.
- UNSUPPORTED: the sentence adds a claim the quote does not make, or contradicts it.
On the second line write the reason in at most 15 words."""


def parse_answer(answer: str) -> tuple[list[tuple[int, str]], dict[str, dict]]:
    """Split an answer into (sentence, marker) pairs and its citation records.

    The blank line before the first `[n] <file>, p. <n>: "<quote>"` starts the citation
    block; everything above it is prose. A sentence may carry more than one marker.
    """
    body, citations = answer, {}
    first_ref = re.search(r"\n\s*\n\s*\[\d{1,2}\]\s+\S.*?,\s*p\.\s*\d+\s*:", answer)
    if first_ref:
        body, tail = answer[:first_ref.start()], answer[first_ref.start():]
        for match in CITATION.finditer(tail.strip()):
            citations[match.group(1)] = {"file": match.group(2).strip(),
                                         "page": int(match.group(3)),
                                         "quote": " ".join(match.group(4).split())}

    sentences: list[tuple[int, str]] = []
    for line in body.splitlines():
        for sentence in SENTENCE.split(line.strip()):
            sentence = sentence.strip()
            numbers = MARKER.findall(sentence)
            if len(sentence.split()) < 4 or not numbers or REFUSAL.search(sentence):
                continue
            sentences.append((int(numbers[0]), sentence))
    return sentences, citations


def ask(question: str, sentence: str, quote: str, model: str = MODEL) -> tuple[str, str]:
    """One judge call: (verdict, reason). A transport error is reported, not swallowed."""
    body = {
        "model": model,
        "messages": [{"role": "system", "content": PROMPT},
                     {"role": "user", "content":
                      f"Question: {question}\n\nQuoted passage: \"{quote}\"\n\n"
                      f"Sentence: {sentence}"}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_ctx": 4096, "seed": 0, "num_predict": 60},
    }
    with httpx.Client(timeout=httpx.Timeout(connect=5, read=120, write=30, pool=5)) as client:
        response = client.post(f"{OLLAMA_URL}/api/chat", json=body)
    if response.status_code != 200:
        raise RuntimeError(f"Ollama {response.status_code}: {response.text[:200]}")
    text = ((response.json().get("message") or {}).get("content") or "").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    verdict = next((word for word in re.findall(r"SUPPORTED|PARTIAL|UNSUPPORTED",
                                                lines[0].upper() if lines else "")), "UNKNOWN")
    return verdict, (lines[1] if len(lines) > 1 else "")[:120]


def squeezed(text: str) -> str:
    """Digits without separators, so `12,000 m3 s-1` and `12 000` compare equal."""
    return re.sub(r"[\s,.]", "", text)


def page_texts(path: pathlib.Path = PAGES) -> dict[tuple[str, int], str]:
    """The index's own text for every page, so a number can be looked for on the page as
    well as in the one quotation the answer printed for it."""
    pages = json.loads(path.read_text(encoding="utf-8"))["pages"]
    return {(page["doc"], int(page["page"])): page.get("text") or "" for page in pages}


def rows(path: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def questions(path: pathlib.Path = QUESTIONS) -> dict[str, str]:
    """`run.jsonl` stores the id and the answer, not the question: the judge needs the
    question, and it comes from the eval set (read only - nothing here writes to it)."""
    return {row["id"]: row["question"] for row in rows(path)}


def write_report(results: list[dict], counts: dict, summary: str,
                 path: pathlib.Path = OUT) -> pathlib.Path:
    """`reports/entailment.md`, from the judged rows; nothing is estimated."""
    failures = [row for row in results if row["verdict"] != "SUPPORTED"]
    lines = [
        "# Sentence-level entailment check (prototype, D-067)",
        "",
        "Written by `scripts/measure-entailment.py`. This is a **secondary signal**, not a",
        "gate: the judge is `qwen3.5:4b` at temperature 0, and D-010/D-058 keep the",
        "page-checked quotation as the arbiter. A failure here means the sentence goes",
        "beyond the words it quotes; it does not mean the fact is wrong.",
        "",
        "## Summary",
        "",
        f"- Answers in the run: **{counts['answers']}**; sentences judged: **{counts['sentences']}**",
        f"- SUPPORTED: **{counts['SUPPORTED']}**",
        f"- PARTIAL: **{counts['PARTIAL']}**",
        f"- UNSUPPORTED: **{counts['UNSUPPORTED']}**",
        f"- No verdict (judge error or unparseable): **{counts['UNKNOWN']}**",
        f"- Sentences whose marker has no citation line: **{counts['uncited']}**",
        "- Every judged row is in `reports/entailment.jsonl` with the quote, the file and",
        "  page, and the numbers the sentence states that the quote does not.",
        "",
        summary,
        "",
        "## Sentences that are not fully supported",
        "",
    ]
    lines += ([f"- `{row['id']}` [{row['n']}] **{row['verdict']}** — \"{row['sentence']}\""
               f"\n  - reason: {row['reason'] or '(none given)'}"
               f"\n  - quote: \"{row['quote'][:220]}\"" for row in failures] or ["None."])
    lines += ["", "## Method", "",
              "- Source run: `eval/runs/2026-11-19-step8-full/run.jsonl` (55 questions).",
              "- A sentence joins the check when it has four or more words, carries `[n]`,",
              "  and is not a refusal.",
              "- The quote is the one the answer printed for that `[n]`, which the verifier",
              "  already matched against the cited page.",
              "- One judge call per sentence; temperature 0, seed 0; the verdict is the",
              "  first word of the reply.", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def selftest() -> int:
    answer = ("The 24-hour rainfall depth was 540 mm [1]. These were taken in the morning "
              "[1].\n\n[1] 1970_Marahatta_x.pdf, p. 2: \"The 24-hour rainfall depth of 540 "
              "mm at Tistung\"\n[2] 1960_Dhar_y.pdf, p. 4: \"TABLE 3 Highest rainfall\"")
    sentences, citations = parse_answer(answer)
    assert len(sentences) == 2, sentences
    assert citations["1"]["page"] == 2 and "540" in citations["1"]["quote"], citations
    assert citations["2"]["file"] == "1960_Dhar_y.pdf", citations
    refused = parse_answer("The provided passages do not state the total [1].")
    assert refused[0] == [], refused[0]
    print("selftest: pass")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="measure-entailment")
    parser.add_argument("--run", default=str(DEFAULT_RUN))
    parser.add_argument("--limit", type=int, default=None, help="judge at most N sentences")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()

    asked = questions()
    pages = page_texts()
    records = [row for row in rows(pathlib.Path(args.run) / "run.jsonl")
               if row.get("status") == "verified" and (row.get("answer") or "").strip()]
    results: list[dict] = []
    counts = {"answers": len(records), "sentences": 0, "SUPPORTED": 0, "PARTIAL": 0,
              "UNSUPPORTED": 0, "UNKNOWN": 0, "uncited": 0}
    began = time.perf_counter()

    for record in records:
        sentences, parsed = parse_answer(record["answer"])
        # The run stores the verified citations, so prefer them over re-parsing the text.
        citations = {str(c["n"]): c for c in record.get("citations") or []} or parsed
        for number, sentence in sentences:
            if args.limit and counts["sentences"] >= args.limit:
                break
            citation = citations.get(str(number))
            counts["sentences"] += 1
            if not citation:
                counts["uncited"] += 1
                continue
            try:
                verdict, reason = ask(record.get("question") or asked[record["id"]],
                                      sentence, citation["quote"], args.model)
            except (httpx.HTTPError, RuntimeError) as exc:
                verdict, reason = "UNKNOWN", f"{exc.__class__.__name__}: {exc}"[:120]
            counts[verdict] = counts.get(verdict, 0) + 1
            # A sentence can quote one passage and use a fact printed elsewhere on the
            # same page: that is a weak quotation, not an invention. Record which it is by
            # looking for the sentence's numbers in the quotation and then on the page.
            page = pages.get((pathlib.Path(citation["file"]).name, int(citation["page"])), "")
            # Drop the `[n]` markers first: their digits are references, not quantities.
            stated = MARKER.sub(" ", sentence)
            missing = [d for d in DIGITS.findall(stated)
                       if squeezed(d) not in squeezed(citation["quote"])]
            elsewhere = [d for d in missing if squeezed(d) in squeezed(page)]
            results.append({"id": record.get("id"), "n": number, "sentence": sentence,
                            "verdict": verdict, "reason": reason,
                            "quote": citation["quote"], "file": citation["file"],
                            "page": citation["page"], "numbers_outside_quote": missing,
                            "numbers_on_the_page": elsewhere})
            print(f"  {record.get('id')} [{number}] {verdict:11s} "
                  f"{sentence[:64]}", file=sys.stderr)

    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in results),
                       encoding="utf-8", newline="\n")

    judged = counts["sentences"] - counts["uncited"]
    failed = counts["PARTIAL"] + counts["UNSUPPORTED"]
    failures = [row for row in results if row["verdict"] != "SUPPORTED"]
    elsewhere = [row for row in failures if row["numbers_outside_quote"] and
                 len(row["numbers_on_the_page"]) == len(row["numbers_outside_quote"])]
    nowhere = [row for row in failures if row["numbers_outside_quote"] and
               not row["numbers_on_the_page"]]
    summary = (f"{failed} of {judged} judged sentences are not fully supported by the "
               f"quote they cite ({failed / judged * 100:.1f}%). Of those {failed}, "
               f"{len(elsewhere)} state a number that the quotation lacks but the cited "
               f"page prints (a weak quotation, not an invented fact) and {len(nowhere)} "
               f"state a number that appears neither in the quotation nor on the page.")
    path = write_report(results, counts, summary)
    print(json.dumps({**counts, "judged": judged, "seconds": round(time.perf_counter() - began, 1),
                      "report": str(path)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
