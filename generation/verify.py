"""Check that an answer's quotations actually exist on the pages it cites.

This is the half of D-010 that survives (D-058): a citation is not accepted because
it looks plausible, only because the quoted words are on that page. The comparison
is deliberately the plain one the eval scorer uses (`eval/score.py`) — collapsing
whitespace and folding typographic quotation marks — and nothing looser: no stemming,
no case folding, no accepting a quote split by "...". If the model will not copy the
page, the answer is retried and then reported as unverified.

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

import pymupdf

from generation.prompt import NOT_FOUND_TEXT

# TODO(step-06): the verifier checks quotations, not the numbers in the answer prose. A
# sentence can read "720 mm [1]" while quoting "540 mm" from page 2, and this module
# passes it because the quotation is genuine; only the numeric metric in EVAL.md sees
# that. Task 3 (the gate, D-058) is where a prose check belongs, before the answer is
# returned as grounded.

CORPUS = pathlib.Path("data/corpus")
INDEX_CACHE = pathlib.Path("index/ui-pages.json")
# Below this a page has no usable text layer, so its indexed OCR text is the only
# text there is to quote (the same threshold ui/retrieval.py uses).
MIN_PAGE_CHARS = 40

# One citation line: [2] name.pdf, p. 12: "quote"  (the quote may be unquoted)
# Every dash a model has been seen to type before the quotation is accepted here --
# colon, hyphen, en dash, em dash -- because the prompt's own headings use an em dash.
_CITATION = re.compile(
    r"^\s*\[(\d+)\]\s*(?P<file>[^\n,]+?)\s*,\s*p\.?\s*(?P<page>\d+)\s*[:\-–—]\s*(?P<quote>.+?)\s*$",
    re.MULTILINE,
)
_INLINE = re.compile(r"\[(\d+)\]")
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


def _corpus_files() -> dict[str, pathlib.Path]:
    return {path.name: path for path in CORPUS.rglob("*.pdf")}


_FILES: dict[str, pathlib.Path] | None = None
_PAGE_TEXT: dict[tuple[str, int], str] = {}


def page_text(doc: str, page: int) -> str:
    """The text of one corpus page, from the PDF, with the OCR text as fallback.

    The PDF is the authority: the quote has to be on the page the reader will open,
    not merely in a cached index. Scanned pages have no text layer, so for those the
    indexed OCR text (`index/ui-pages.json`) is used, which is what the retriever
    showed the model in the first place.
    """
    key = (doc, page)
    if key in _PAGE_TEXT:
        return _PAGE_TEXT[key]

    global _FILES
    if _FILES is None:
        _FILES = _corpus_files()

    text = ""
    path = _FILES.get(pathlib.PurePosixPath(doc).name)
    if path is not None:
        try:
            with pymupdf.open(path) as pdf:
                if 1 <= page <= pdf.page_count:
                    text = pdf[page - 1].get_text()
        except Exception as exc:  # noqa: BLE001 - a broken PDF must not crash a check
            print(f"[verify] cannot read {path.name}: {exc.__class__.__name__}: {exc}")

    if len(re.sub(r"\s+", "", text)) < MIN_PAGE_CHARS and INDEX_CACHE.exists():
        import json

        try:
            pages = json.loads(INDEX_CACHE.read_text(encoding="utf-8")).get("pages", [])
        except (json.JSONDecodeError, OSError):
            pages = []
        for entry in pages:
            if entry.get("doc") == pathlib.PurePosixPath(doc).name and entry.get("page") == page:
                text = entry.get("text") or text
                break

    _PAGE_TEXT[key] = text
    return text


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


def said_not_found(answer: str) -> bool:
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

    missing = sorted({c["n"] for c in citations if 1 <= c["n"] <= len(passages)} - seen)
    if citations and missing and not result["problems"]:
        result["problems"].append(f"no verified quotation for [{missing[0]}]")

    result["ok"] = not result["problems"] and result["verified_quotes"] > 0
    return result
