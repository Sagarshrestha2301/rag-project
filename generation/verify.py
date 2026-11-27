"""Check that an answer's quotations exist on the pages it cites, and so do its numbers.

This is the half of D-010 that survives (D-058): a citation is not accepted because
it looks plausible, only because the quoted words are on that page. The comparison
is deliberately the plain one the eval scorer uses (`eval/score.py`) — collapsing
whitespace and folding typographic quotation marks — and nothing looser: no stemming, no
case folding beyond a single first-letter flip (step 20, q052), no accepting a quote split
by "...". If the model will not copy the
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
37/39 -> 35/39 on dev and `eval/gate.py` rejected the change.

Step 15 adds the narrower half that D-068 left unmeasured: the prompt's **exact** line is
accepted wherever it appears, but only when the answer cites nothing at all. The prose is
never read, so this is not D-060. Measured on the 2026-11-24 run, 11 of 55 answers carry
the exact line; the no-marker guard keeps the two prose refusals that should pass (q021,
q055) and still misfiles one answerable question that never cited anything (q027), which
is the one-question cost this rule was accepted with. `said_not_found()` stays strict; the
wider form is reported by `refused_with_line()`, so a refusal can never be invented from a
paraphrase.

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

from corpus import page_text, quote_case_variant
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

    Case is left alone here on purpose: the one case difference both halves accept is the
    first character's, and both apply it through `corpus.quote_case_variant` (step 20),
    so the runtime gate and the eval cannot drift apart the way the page readers did.
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


def refused_with_line(answer: str) -> dict:
    """Did the model write the exact refusal line without citing anything?

    Two accepted forms, both of which are the prompt's own words and nothing invented:

    - `line_only`: the first non-empty line is the exact line (the old contract);
    - `exact_line_with_prose`: the exact line appears as a whole line somewhere and the
      answer carries **no `[n]` marker at all**, so it never tried to cite a page. This
      is q021/q055, and it is why the rule cannot swallow a real answer attempt (q026,
      q028 cite a page even while disclaiming one).

    The prose is not read and no paraphrase is accepted: D-060's rule was measured and
    rejected (D-068) because it guessed at meaning.

    Usage:
        >>> refused_with_line("The passages do not state it.  Not found in the indexed documents.")["accepted"]
        True
        >>> refused_with_line('No Table 2 here. [3] Das 1970, p. 4: "x"')["accepted"]
        False
    """
    text = (answer or "").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()] if text else []
    target = NOT_FOUND_TEXT.rstrip(".").lower()
    has_line = any(line.rstrip(".").lower() == target for line in lines)
    markers = len(_INLINE.findall(text))

    if not text:
        return {"accepted": False, "form": None, "markers": 0,
                "reason": "the answer is empty"}
    if not has_line:
        return {"accepted": False, "form": None, "markers": markers,
                "reason": "the exact refusal line is not in the answer"}
    if markers:
        return {"accepted": False, "form": None, "markers": markers,
                "reason": f"the answer cites {markers} page(s), so it is an answer attempt"}
    if len(lines) == 1:
        return {"accepted": True, "form": "line_only", "markers": 0,
                "reason": "the refusal line is the whole answer"}
    return {"accepted": True, "form": "exact_line_with_prose", "markers": 0,
            "reason": "the model wrote the refusal line and cited no page"}


# Step 17: a list question's answer must be a list. The prompt asked twice and the model
# wrote prose both times (D-092, D-093), so the shape is checked here and the retry carries
# the complaint back. The citation block is evidence, not answer prose, so it is excluded
# by the first line that opens with a citation marker.
_CITE_LINE = re.compile(r"^\[\d+\]")


def _answer_body(answer: str) -> list[str]:
    """The answer without its citation block, one stripped non-empty line per entry."""
    lines = [line.strip() for line in (answer or "").splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if _CITE_LINE.match(line):
            return lines[:index]
    return lines


def list_shape_problems(answer: str) -> list[str]:
    """What is wrong with the shape of an answer to a list question.

    The contract is the prompt's own (`prompt.LIST_RULES`): one `- ` line per item, at
    least two of them, nothing before the list, and at most one closing sentence for a
    unit or a range. Only the shape is read; the facts are the citation and numeric
    rules' job.

    Usage:
        >>> list_shape_problems('- 1964 [1]\n- 1981 [1]\n\n[1] x.pdf, p. 1: "Floods of 1964 ..."')
        []
        >>> list_shape_problems("The paper lists 1964 and 1981 [1].")
        ['the answer is a list question, so it must be written as "- " lines (at least two), not as prose']
    """
    body = _answer_body(answer)
    if not body:
        return []
    items = [line for line in body if line.startswith("- ")]
    before, after = [], []
    first = next((i for i, line in enumerate(body) if line.startswith("- ")), None)
    if first is not None:
        before, after = body[:first], body[first + 1:]
    after = [line for line in after if not line.startswith("- ")]

    problems: list[str] = []
    if len(items) < 2:
        problems.append('the answer is a list question, so it must be written as "- " lines '
                        "(at least two), not as prose")
    if items and before:
        problems.append('put no sentence before the list: every item line starts with "- "')
    if len(after) > 1:
        problems.append("at most one sentence may follow the list (a unit or a range); "
                        f"{len(after)} do")
    return problems


def verify_answer(answer: str, passages: list[dict], *, check_page=None,
                  list_style: bool = False) -> dict:
    """Decide whether every quotation in `answer` is on the page it names.

    `passages` is what the model was shown: each needs `doc` (or `file`) and `page`.
    `check_page` overrides how page text is read, which is how the tests run without
    a corpus on disk.
    """
    read_page = check_page or page_text
    refusal = refused_with_line(answer)
    result: dict = {"said_not_found": said_not_found(answer) or refusal["accepted"],
                    "refusal_form": refusal["form"], "citations": [],
                    "problems": [], "ok": False, "verified_quotes": 0}

    if result["said_not_found"]:
        # A strict refusal that keeps talking is still a problem; the wide form is the
        # one that deliberately allows prose around the line (Step 15).
        if refusal["form"] != "exact_line_with_prose":
            extra = [line for line in (answer or "").strip().splitlines()[1:] if line.strip()]
            if extra:
                result["problems"].append(
                    "the refusal line must be the whole answer, but more text follows it")
        result["ok"] = not result["problems"]
        return result

    if not (answer or "").strip():
        result["problems"].append("the answer is empty")
        return result

    # Step 17: only a list question, and only when it is answering rather than refusing.
    if list_style:
        result["problems"].extend(list_shape_problems(answer))

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
        # Step 20: the quotation as typed, or the same text with only its first letter's
        # case flipped (q052 quotes "bamboo clumps …" where the page prints "Bamboo
        # clumps …"). A case change anywhere else still fails.
        page_n, quote_n = norm(page), norm(quote)
        flipped = quote_case_variant(quote_n)
        if quote_n in page_n or (flipped is not None and flipped in page_n):
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
