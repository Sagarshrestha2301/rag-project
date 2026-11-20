"""Prove the quote verifier: it passes a real quotation and refuses everything else.

The last group runs against a real corpus PDF, because a checker that only passes its
own fixtures has not met the thing it will actually read.

Usage:
    .venv\\Scripts\\python.exe generation\\test_verify.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pymupdf                                  # noqa: E402

from corpus import CORPUS as CORPUS_ROOT          # noqa: E402
from generation import prompt, verify           # noqa: E402

FAILURES: list[str] = []
TOTAL = 0

PAGE = ("Table 2: Flood damage in the East-Rapti basin. The 24-hour rainfall depth of "
        "540 mm at Tistung was recorded in July 1970, and 139 households were surveyed "
        "in the lower catchment. Of these, 71 were growers.")
OTHER = "Annual report of the department, 1988. Nothing about rainfall appears here."
THIRD = "Flood damage reached 12,000 rupees in 1993 across the district."
THIRD_PASSAGE = [{"doc": "1972_Third_Paper_W3.pdf", "page": 4, "label": "Third 1972"}]
QUOTE = "The 24-hour rainfall depth of 540 mm at Tistung was recorded in July 1970"

PASSAGES = [
    {"doc": "1970_Test_Paper_W1.pdf", "page": 2, "label": "Test 1970"},
    {"doc": "1971_Other_Paper_W2.pdf", "page": 7, "label": "Other 1971"},
]


def fake_page(doc: str, page: int) -> str:
    """Stand-in for a corpus: two pages, both known here."""
    if doc == "1970_Test_Paper_W1.pdf" and page == 2:
        return PAGE
    if doc == "1971_Other_Paper_W2.pdf" and page == 7:
        return OTHER
    if doc == "1972_Third_Paper_W3.pdf" and page == 4:
        return THIRD
    return ""


def answer_with(quote: str = QUOTE, *, n: int = 1, page: int = 2,
                doc: str = "1970_Test_Paper_W1.pdf", quoted: bool = True) -> str:
    text = f'"{quote}"' if quoted else quote
    return f"540 mm fell in 24 hours at Tistung [{n}].\n\n[{n}] {doc}, p. {page}: {text}"


def run(answer: str, passages: list[dict] | None = None) -> dict:
    return verify.verify_answer(answer, passages or PASSAGES, check_page=fake_page)


def expect_ok(name: str, answer: str, passages: list[dict] | None = None) -> None:
    result = run(answer, passages)
    if not result["ok"]:
        raise AssertionError(f"expected a pass, got {result['problems']}")


def expect_fail(name: str, answer: str, needle: str = "",
                passages: list[dict] | None = None) -> None:
    result = run(answer, passages)
    if result["ok"]:
        raise AssertionError("expected a refusal, got a pass")
    if needle and not any(needle in problem for problem in result["problems"]):
        raise AssertionError(f"no problem mentions {needle!r}: {result['problems']}")


def check(name: str, fn) -> None:
    global TOTAL
    TOTAL += 1
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as exc:
        FAILURES.append(name)
        print(f"  FAIL  {name}: {exc}")


# --------------------------------------------------------------------- the cases
def good_quote_passes() -> None:
    expect_ok("good", answer_with())


def unquoted_quote_passes() -> None:
    expect_ok("good", answer_with(quoted=False))


def dashed_citations_parse() -> None:
    """Every dash a model types before the quotation must still parse."""
    for dash in (":", "-", "–", "—"):
        expect_ok(dash, f'540 mm [1].\n\n[1] 1970_Test_Paper_W1.pdf, p. 2 {dash} "{QUOTE}"')


def invented_quote_fails() -> None:
    expect_fail("bad", answer_with("the rainfall depth of 999 mm at Tistung in July 1970"),
                "not on")


def real_quote_from_another_page_fails() -> None:
    """The words are genuinely in the corpus, just not on the page that was cited."""
    expect_fail("bad", answer_with("Nothing about rainfall appears here"), "not on")


def quote_from_other_passage_fails() -> None:
    expect_fail("bad", answer_with(n=2, page=7, doc="1971_Other_Paper_W2.pdf"), "not on")


def case_change_fails() -> None:
    expect_fail("bad", answer_with(QUOTE.lower()), "not on")


def joined_quote_fails() -> None:
    expect_fail("bad", answer_with("The 24-hour rainfall depth of 540 mm ... 139 households"),
                "...")


def wrong_file_fails() -> None:
    expect_fail("bad", answer_with(doc="1971_Other_Paper_W2.pdf"), "cites")


def wrong_page_number_fails() -> None:
    expect_fail("bad", answer_with(page=3), "page")


def missing_number_fails() -> None:
    expect_fail("bad", answer_with(n=7), "does not exist")


def no_citation_line_fails() -> None:
    expect_fail("bad", "540 mm fell at Tistung in 1970.", "no citation line")


def empty_answer_fails() -> None:
    expect_fail("bad", "   ", "empty")


def refusal_passes() -> None:
    result = run(prompt.NOT_FOUND_TEXT)
    assert result["ok"] and result["said_not_found"], result


def refusal_with_extra_text_fails() -> None:
    result = run(prompt.NOT_FOUND_TEXT + "\nThe documents do not cover this.")
    assert not result["ok"] and result["said_not_found"], result


def prose_refusal_is_not_a_refusal() -> None:
    """q020's shape. Measured 2026-11-20: accepting it fixed 3 and lost 2 (D-060)."""
    answer = ("The provided passages do not state the total population living in the "
              "Bagmati catchment. They mention that data collection started in the "
              'sixties [1].\n\n[1] 1970_Test_Paper_W1.pdf, p. 2: "Hydrological data"')
    result = run(answer)
    assert not result["said_not_found"], result


def refusal_on_the_second_line_is_not_a_refusal() -> None:
    """q021's shape: only the first non-empty line is the contract."""
    answer = ("The provided passages do not state the total economic loss caused by the "
              "July 1993 floods.\n" + prompt.NOT_FOUND_TEXT)
    result = run(answer)
    assert not result["said_not_found"], result


def an_answer_then_the_exact_line_is_not_a_refusal() -> None:
    """q028's shape: the first sentence asserts a fact, so the trailing line proves nothing."""
    answer = ("The provided text states that there were no households in the Terai [1].\n"
              + prompt.NOT_FOUND_TEXT)
    result = run(answer)
    assert not result["said_not_found"], result


def number_not_on_cited_page_fails() -> None:
    """A genuine quotation does not excuse a number the page never states."""
    expect_fail("bad", 'The depth is 54 mm [1].\n\n[1] 1970_Test_Paper_W1.pdf, p. 2: "' + QUOTE + '"',
                "states 54")


def number_on_cited_page_passes() -> None:
    expect_ok("good", 'It rained 540 mm in 24 hours [1].\n\n[1] 1970_Test_Paper_W1.pdf, p. 2: "' + QUOTE + '"')


def thousands_separators_are_the_same_number() -> None:
    """'12000' in the prose is the page's '12,000'."""
    expect_ok("good", 'Damage reached 12000 rupees in 1993 [1].\n\n[1] 1972_Third_Paper_W3.pdf, p. 4: '
              '"Flood damage reached 12,000 rupees in 1993"', THIRD_PASSAGE)


def digits_glued_to_letters_are_not_numbers() -> None:
    """P0, m3 and h-1 are names, not quantities to look up on a page."""
    expect_ok("good", 'P0 is defined there [1].\n\n[1] 1970_Test_Paper_W1.pdf, p. 2: "' + QUOTE + '"')


def markers_are_not_numbers() -> None:
    """[1] is a pointer; only the digits outside the brackets are looked for."""
    expect_ok("good", 'The depth was 540 mm [1].\n\n[1] 1970_Test_Paper_W1.pdf, p. 2: "' + QUOTE + '"')


def number_without_a_marker_is_another_rules_business() -> None:
    """A sentence with no [n] has nothing to check the number against; the marker rule speaks."""
    expect_ok("good", '540 mm fell in 24 hours. The report records it [1].\n\n[1] '
              '1970_Test_Paper_W1.pdf, p. 2: "' + QUOTE + '"')


def first_readable_page() -> tuple[str, int, str]:
    """Name, page and text of the first corpus page with at least 400 characters."""
    for path in sorted(CORPUS_ROOT.rglob("*.pdf")):
        with pymupdf.open(path) as pdf:
            for number, page in enumerate(pdf, start=1):
                text = verify.norm(page.get_text())
                if len(text) >= 400:
                    return path.name, number, text
    raise AssertionError("no readable corpus page found")


def real_quote_verifies() -> None:
    name, page, text = first_readable_page()
    quote = " ".join(text.split()[40:52])
    passages = [{"doc": name, "page": page}]
    result = verify.verify_answer(f'It says so [1].\n\n[1] {name}, p. {page}: "{quote}"',
                                  passages)
    assert result["ok"], result["problems"]


def real_quote_fails_on_other_page() -> None:
    name, page, text = first_readable_page()
    quote = " ".join(text.split()[40:52])
    passages = [{"doc": name, "page": page}]
    result = verify.verify_answer(f'It says so [1].\n\n[1] {name}, p. {page + 1}: "{quote}"',
                                  passages)
    assert not result["ok"], "a quote was accepted on a page it is not on"


def main() -> int:
    groups = [
        ("a real quotation passes", [
            ("exact quote on the cited page", good_quote_passes),
            ("quote accepted without quotation marks", unquoted_quote_passes),
            ("every dash before the quote still parses", dashed_citations_parse),
        ]),
        ("an invented quotation is refused", [
            ("fake quote that is not on the page", invented_quote_fails),
            ("real quote that belongs to another page", real_quote_from_another_page_fails),
            ("quote from a different passage than the one cited", quote_from_other_passage_fails),
        ]),
        ("citation bookkeeping is checked", [
            ("changed capitalisation is refused", case_change_fails),
            ("quote joined with ... is refused", joined_quote_fails),
            ("file that does not match the passage number", wrong_file_fails),
            ("wrong page number", wrong_page_number_fails),
            ("citation number that was never supplied", missing_number_fails),
            ("answer with no citation line", no_citation_line_fails),
            ("empty answer", empty_answer_fails),
        ]),
        ("numbers stated in the prose", [
            ("a number the cited page does not state is refused", number_not_on_cited_page_fails),
            ("a number the page states passes", number_on_cited_page_passes),
            ("thousands separators are the same number", thousands_separators_are_the_same_number),
            ("digits glued to letters are not numbers", digits_glued_to_letters_are_not_numbers),
            ("citation markers are not numbers", markers_are_not_numbers),
            ("a number in a sentence with no marker is left to the marker rule",
             number_without_a_marker_is_another_rules_business),
        ]),
        ("the refusal is its own case", [
            ("exact refusal is accepted", refusal_passes),
            ("refusal followed by extra text is refused", refusal_with_extra_text_fails),
            ("a prose disclaimer is not a refusal (measured, D-060)",
             prose_refusal_is_not_a_refusal),
            ("a refusal on the second line is not a refusal",
             refusal_on_the_second_line_is_not_a_refusal),
            ("an answer then the exact line is not a refusal",
             an_answer_then_the_exact_line_is_not_a_refusal),
        ]),
        ("real corpus page", [
            ("a quotation copied from a real PDF verifies", real_quote_verifies),
            ("the same quotation fails on a page it is not on", real_quote_fails_on_other_page),
        ]),
    ]
    for heading, cases in groups:
        print(heading)
        for name, fn in cases:
            check(name, fn)

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} of {TOTAL} case(s): {FAILURES}")
        return 1
    print(f"all {TOTAL} cases pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
