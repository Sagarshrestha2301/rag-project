"""Prove the prompt numbers every passage, names its file and page, and keeps the rules.

Usage:
    .venv\\Scripts\\python.exe generation\\test_prompt.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from generation import prompt                     # noqa: E402

FAILURES: list[str] = []
TOTAL = 0

HITS = [
    {"doc": "1970_Test_Paper_W1.pdf", "page": 2, "label": "Test 1970",
     "context": "The 24-hour rainfall depth of 540 mm at Tistung."},
    {"file": "reports/1971_Other_Paper_W2.pdf", "page": 7, "label": "Other 1971",
     "context": "Nothing about rainfall appears here."},
]


def check(name: str, fn) -> None:
    global TOTAL
    TOTAL += 1
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as exc:
        FAILURES.append(name)
        print(f"  FAIL  {name}: {exc}")


def five_passages_are_numbered() -> None:
    hits = [dict(HITS[0], page=i) for i in range(1, 6)]
    text = prompt.build_system(hits)
    for number in range(1, 6):
        assert f"PASSAGE [{number}]" in text, f"passage [{number}] missing"
        assert f"(End of passage [{number}]" in text, f"end marker [{number}] missing"
    assert "PASSAGE [6]" not in text


def file_and_page_are_named() -> None:
    text = prompt.build_system(HITS)
    assert "page 2, file 1970_Test_Paper_W1.pdf" in text, text[:200]


def folders_are_stripped_from_the_citation_name() -> None:
    text = prompt.build_system(HITS)
    assert "file 1971_Other_Paper_W2.pdf" in text
    assert "reports/1971_Other_Paper_W2.pdf" not in text, "a folder leaked into the name"


def passage_body_is_included() -> None:
    text = prompt.build_system(HITS)
    assert "The 24-hour rainfall depth of 540 mm at Tistung." in text


def rules_force_the_format() -> None:
    text = prompt.build_system(HITS)
    assert prompt.NOT_FOUND_TEXT in text, "the refusal line is not quoted in the rules"
    assert 'p. <page number>: "<quotation>"' in text, "the citation shape is not shown"
    assert "copied character for character" in text


def empty_retrieval_says_so() -> None:
    text = prompt.build_system([])
    assert "No passage was retrieved" in text
    assert prompt.NOT_FOUND_TEXT in text


def version_is_set() -> None:
    assert prompt.PROMPT_VERSION, "the prompt needs a version: the answer cache is keyed on it"


def retry_message_can_say_the_answer_is_gone() -> None:
    kept = prompt.retry_message(["quote not on the page"])
    assert "Your answer failed citation check:" in kept
    assert "not repeated here" not in kept
    dropped = prompt.retry_message(["quote not on the page"], previous_kept=False)
    assert "not repeated here" in dropped, "a retry that drops the answer must say so"
    assert "- quote not on the page" in dropped, "the problems must survive"
    assert prompt.NOT_FOUND_TEXT in dropped


def main() -> int:
    cases = [
        ("five passages are numbered 1-5", five_passages_are_numbered),
        ("each passage names its file and page", file_and_page_are_named),
        ("folders are stripped from the citation name", folders_are_stripped_from_the_citation_name),
        ("the passage body is included", passage_body_is_included),
        ("the rules force the citation shape and the refusal", rules_force_the_format),
        ("empty retrieval is stated, not left blank", empty_retrieval_says_so),
        ("the prompt carries a version", version_is_set),
        ("a retry can say the failed answer is not repeated",
         retry_message_can_say_the_answer_is_gone),
    ]
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
