"""Check that an answer's quotations exist on the pages it cites, and so do its numbers.

This is the half of D-010 that survives (D-058): a citation is not accepted because
it looks plausible, only because the quoted words are on that page. The comparison
is deliberately the plain one the eval scorer uses (`eval/score.py`) — collapsing
whitespace and folding typographic quotation marks — and nothing looser: no stemming,
no case folding, no accepting a quote split by "...". If the model will not copy the
page, the answer is retried and then reported as unverified.

A second check covers the numbers in the prose. Every number a sentence states must
appear on a page that same sentence cites, so "which is 54 mm [1]" fails when page 1
says 540 mm and the quotation happens to be genuine. Measured on the 55 saved answers
of 2026-11-16 before it was added: 114 numbers checked, 1 flagged (q039, a real
misstatement), so it costs 1 of 55 answers and bought a caught error. It ignores digits
glued to letters (`P0`, `m3`), `[n]` markers, and sentences with no marker, where the
separate "no [n] marker" rule already speaks.

Accepting a refusal written in the model's own words was measured and **not kept**
(D-060, 2026-11-20). The rule was: a first sentence that negates what the passages
contain, about the question asked, counts as a refusal and is normalised to
`NOT_FOUND_TEXT`. It fixed all three prose refusals (not-found (a) 3/6 -> 6/6) but also
swallowed two answerable questions whose model answer opens with the same shape
(q027, q028: "the provided passages do not contain Table 2 ..."), so not-found (b) fell
37/39 -> 35/39 on dev and `eval/gate.py` rejected the change. Only the exact line counts;
the cases in `test_verify.py` pin the measured behaviour.

Usage:
    from generation import prompt, verify
    hits = retrieval.search(index, question, k=5)
    result = verify.verify_answer(model_text, hits)
    result["ok"]           # False -> retry once (answer.py does this)
    result["problems"]     # one sentence per reason, handed back to the model

Example:
    >>> hits = [{"doc": "a.pdf", "page": 2, "context": "The depth was 540 mm."}]
    >>> verify.verify_answer('It rained 540 mm [1].\\n\\n[1] a.pdf, p. 2: "The depth was 540 mm"', hits)["ok"]
    True
    >>> verify.verify_answer('It rained 999 mm [1].\\n\\n[1] a.pdf, p. 2: "The depth was 540 mm"', hits)["ok"]
    False
"""

from __future__ import annotations

import pathlib
import re

from corpus import page_text
from generation.prompt import NOT_FOUND_TEXT

# One citation line: [2] name.pdf, p. 12: "quote"  (the quote may be unquoted)
# Every dash a model has been seen to type before the quotation is accepted here --
# colon, hyphen, en dash, em dash -- because the prompt's own headings use an em dash.
_CITATION = re.compile(
    r"^\s*\[(\d+)\]\s*(?P<file>[^\n,]+?)\s*,\s*p\.?\s*(?P<page>\d+)\s*[:\-–—]\s*(?P<quote>.+?)\s*$",
    re.MULTILINE,
)
_INLINE = re.compile(r"\[(\d+)\]")
# A number a sentence states: not glued to a letter or a decimal point of a variable
# (P0, m3, h-1), thousands separators allowed. "24-hour" is 24; "0.033" is one number.
_NUMBER = re.compile(r"(?<![A-Za-z0-9_.])\d[\d,]*(?:\.\d+)?(?![A-Za-z0-9])")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
# "p. 3" and "et al." are not sentence ends; a full stop inside them is parked on a
# look-alike character while the text is split.
_ABBREVIATION = re.compile(r"\b(p|pp|e\.g|i\.e|al|No|vs|Fig|approx|cf)\.", re.IGNORECASE)
_PARKED_STOP = "\u2024"
_WRAPPING = "\"'“”‘’"
_FOLD = {"“": '"', "”": '"', "‘": "'", "’": "'", "\u00a0": " "}


def norm(text: str) -> str:
    """Whitespace-collapsed, typographic quotes folded to ASCII.

    Case is left alone on purpose: the eval scorer is case-sensitive, so accepting a
    re-capitalised quotation here would make the runtime gate kinder than the eval
    that judges it.
    """
    folded = "".join(_FOLD.get(ch, ch) for ch in (text or ""))
    return re.sub(r"\s+", " ", folded).strip()


def strip_wrapping(quote: str) -> str:
    q = quote.strip()
    while len(q) >= 2 and q[0] in _WRAPPING and q[-1] in _WRAPPING:
        q = q[1:-1].strip()
    return q


def parse_citations(answer: str) -> list[dict]:
    """Every citation line in the answer, in order, with its quote de-quoted."""
    found = []
    for match in _CITATION.finditer(answer or ""):
        found.append({
            "n": int(match.group(1)),
            "file": match.group("file").strip(),
            "page": int(match.group("page")),
            "quote": strip_wrapping(match.group("quote")),
            "raw": match.group(0).strip(),
        })
    return found


def inline_numbers(answer: str) -> list[int]:
    """Passage numbers mentioned in the answer body, citations excluded."""
    body = _CITATION.sub("", answer or "")
    return [int(n) for n in _INLINE.findall(body)]


def sentences(text: str) -> list[str]:
    """Split prose into sentences without breaking on 'p.' or 'et al.'."""
    protected = _ABBREVIATION.sub(lambda m: m.group(0)[:-1] + _PARKED_STOP, text or "")
    return [part.replace(_PARKED_STOP, ".") for part in _SENTENCE.split(protected) if part.strip()]


def stated_numbers(text: str) -> list[str]:
    """The numbers a piece of text states, thousands separators removed."""
    return [raw.replace(",", "") for raw in _NUMBER.findall(text or "")]


def prose_number_problems(answer: str, citations: list[dict], read_page) -> list[str]:
    """Every number a sentence states must be on a page that sentence cites.

    The page read is the one the citation line names, not the passage's page, so a
    citation that already points at the wrong page is judged on what it actually claims.
    """
    body = _CITATION.sub("", answer or "")
    by_number = {c["n"]: (c["file"], c["page"]) for c in citations}
    numbers_on: dict[tuple[str, int], set[str]] = {}
    problems: list[str] = []

    def page_numbers(name: str, page: int) -> set[str]:
        key = (name, page)
        if key not in numbers_on:
            numbers_on[key] = set(stated_numbers(read_page(name, page)))
        return numbers_on[key]

    for sentence in sentences(body):
        markers = sorted({int(n) for n in _INLINE.findall(sentence)})
        numbers = stated_numbers(_INLINE.sub(" ", sentence))
        targets = [by_number[n] for n in markers if n in by_number]
        if not numbers or not targets:
            continue
        for number in dict.fromkeys(numbers):
            if any(number in page_numbers(pathlib.PurePosixPath(str(file).replace("\\", "/")).name, int(page))
                   for file, page in targets):
                continue
            file, page = targets[0]
            name = pathlib.PurePosixPath(str(file).replace("\\", "/")).name
            problems.append(f"[{markers[0]}] the sentence states {number}, but that number is "
                            f"not on {name} page {page}")
    return problems


def said_not_found(answer: str) -> bool:
    """Did the model refuse with the prompt's exact line (first non-empty line)?

    Prose refusals are deliberately **not** accepted: measured on 2026-11-20, accepting
    them cost two answerable dev questions (D-060, see the module docstring).
    """
    first = (answer or "").strip().splitlines()[0].strip() if (answer or "").strip() else ""
    return first.rstrip(".").lower() == NOT_FOUND_TEXT.rstrip(".").lower()


def verify_answer(answer: str, passages: list[dict], *, check_page=None) -> dict:
    """Decide whether every quotation in `answer` is on the page it names.

    `passages` is what the model was shown: each needs `doc` (or `file`) and `page`.
    `check_page` overrides how page text is read, which is how the tests run without
    a corpus on disk.
    """
    read_page = check_page or page_text
    result: dict = {"said_not_found": said_not_found(answer), "citations": [],
                    "problems": [], "ok": False, "verified_quotes": 0}

    if result["said_not_found"]:
        extra = [line for line in (answer or "").strip().splitlines()[1:] if line.strip()]
        if extra:
            result["problems"].append(
                "the refusal line must be the whole answer, but more text follows it")
        result["ok"] = not result["problems"]
        return result

    if not (answer or "").strip():
        result["problems"].append("the answer is empty")
        return result

    citations = parse_citations(answer)
    result["citations"] = citations
    if not citations:
        result["problems"].append(
            "no citation line found; every answer needs at least one line like "
            '[1] name.pdf, p. 12: "quoted words"')

    numbers = inline_numbers(answer) or [c["n"] for c in citations]
    if not numbers:
        result["problems"].append(
            "no [n] marker after the sentences, so no sentence can be traced to a page")

    for number in sorted(set(numbers)):
        if not 1 <= number <= len(passages):
            result["problems"].append(
                f"[{number}] does not exist: {len(passages)} passage(s) were supplied")

    seen = set()
    for citation in citations:
        n, cite_file, cite_page, quote = (citation["n"], citation["file"],
                                          citation["page"], citation["quote"])
        if not 1 <= n <= len(passages):
            continue
        passage = passages[n - 1]
        want_file = pathlib.PurePosixPath(str(passage.get("doc") or passage.get("file", ""))).name
        if pathlib.PurePosixPath(cite_file.replace("\\", "/")).name != want_file:
            result["problems"].append(
                f"[{n}] cites {pathlib.PurePosixPath(cite_file).name} but passage [{n}] "
                f"is {want_file}")
            continue
        if int(passage["page"]) != cite_page:
            result["problems"].append(
                f"[{n}] cites page {cite_page} but passage [{n}] is page {passage['page']}")
            continue
        if not quote.strip():
            result["problems"].append(f"[{n}] has no quotation, only a page reference")
            continue
        if "..." in quote or "…" in quote:
            result["problems"].append(
                f'[{n}] joins text with "..."; quote one continuous run of words instead')
            continue
        page = read_page(want_file, cite_page)
        if norm(quote) in norm(page):
            result["verified_quotes"] += 1
            seen.add(n)
            continue
        result["problems"].append(
            f'[{n}] the quotation is not on {want_file} page {cite_page}: "{quote[:70]}"')

    if citations:
        result["problems"].extend(prose_number_problems(answer, citations, read_page))

    missing = sorted({c["n"] for c in citations if 1 <= c["n"] <= len(passages)} - seen)
    if citations and missing and not result["problems"]:
        result["problems"].append(f"no verified quotation for [{missing[0]}]")

    result["ok"] = not result["problems"] and result["verified_quotes"] > 0
    return result
