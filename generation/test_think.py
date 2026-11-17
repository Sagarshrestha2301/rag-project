"""Prove the think filter: the tag never reaches a user, prose that says "thinking" survives.

qwen3.5 emits a literal empty pair of think tags at the start of an answer even with
`think: false`. The filter has to remove it while streaming, including when the tag is cut
between two chunks, and it must not touch the ordinary word "thinking" in an answer.

Usage:
    .venv\\Scripts\\python.exe generation\\test_think.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from generation import think                      # noqa: E402

FAILURES: list[str] = []
TOTAL = 0

OPEN, CLOSE = "<think", "</think>"


def check(name: str, fn) -> None:
    global TOTAL
    TOTAL += 1
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as exc:
        FAILURES.append(name)
        print(f"  FAIL  {name}: {exc}")


def streamed(*chunks: str) -> str:
    """Feed the chunks the way the server does, then flush."""
    thinker = think.ThinkFilter()
    return "".join(thinker.feed(chunk) for chunk in chunks) + thinker.flush()


# ------------------------------------------------------------- what the model sends
def the_empty_pair_is_stripped() -> None:
    assert streamed(f"{OPEN}\n\n{CLOSE}The floods were 12,000 and 6,800 m3/s.") == \
        "The floods were 12,000 and 6,800 m3/s."


def a_block_with_reasoning_is_stripped() -> None:
    assert streamed(f"{OPEN}\nweigh the two rivers\n{CLOSE}Bagmati is larger.") == "Bagmati is larger."


def the_tag_is_the_literal_token() -> None:
    """Regression: OPEN was once \" thinking\", so nothing matched and the tag was shown."""
    assert think.ThinkFilter.OPEN == OPEN, [ord(c) for c in think.ThinkFilter.OPEN]
    assert think.ThinkFilter.CLOSE == CLOSE, [ord(c) for c in think.ThinkFilter.CLOSE]


def text_before_the_tag_survives() -> None:
    assert streamed(f"Answer. {OPEN}{CLOSE} More.") == "Answer.  More."


def a_complete_answer_strips_to_the_same_text() -> None:
    assert think.strip(f"{OPEN}\n\n\n{CLOSE}Hello") == "Hello"


# --------------------------------------------------------------- the awkward cases
def a_split_tag_is_held_back() -> None:
    assert streamed("<thi") == "", "a partial opening tag must not be shown"
    assert streamed("<thi", "nk>\n\nA") == "\n\nA"
    assert streamed("A <", "th", "ink>hidden</thi", "nk>B") == "A B"


def an_unterminated_open_tag_discards_the_rest() -> None:
    thinker = think.ThinkFilter()
    assert thinker.feed(f"Kept. {OPEN}never closed") == "Kept. "
    assert thinker.flush() == "", "text inside an unclosed tag is not shown"


def plain_text_is_untouched() -> None:
    text = "The model is thinking about 12,000 m3/s, not 6,800."
    assert streamed(text) == text
    assert streamed("Bag", "mati ", "and East-Rapti") == "Bagmati and East-Rapti"


def main() -> int:
    groups = [
        ("what the model sends", [
            ("the empty pair is stripped", the_empty_pair_is_stripped),
            ("a block with reasoning is stripped", a_block_with_reasoning_is_stripped),
            ("the tag is the literal token", the_tag_is_the_literal_token),
            ("text before the tag survives", text_before_the_tag_survives),
            ("a complete answer strips to the same text", a_complete_answer_strips_to_the_same_text),
        ]),
        ("the awkward cases", [
            ("a tag split across chunks is held back", a_split_tag_is_held_back),
            ("an unterminated open tag discards the rest", an_unterminated_open_tag_discards_the_rest),
            ("plain text is untouched", plain_text_is_untouched),
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
