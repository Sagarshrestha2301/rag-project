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

OPEN, CLOSE = (chr(60) + 'think' + chr(62), chr(60) + '/think' + chr(62))


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
    assert streamed("A <", "th", "ink>hidden</thi", "nk>B") == "A B"


def a_split_tag_still_strips_its_block() -> None:
    """Split across chunks, open and close: the block goes, the text after it stays."""
    body = chr(10) + chr(10) + "A"
    assert streamed("<thi", "nk>", body, "</thi", "nk>", "B") == "B"
    assert streamed(OPEN + "hidden" + CLOSE[:4], CLOSE[4:] + "seen") == "seen"


def an_unterminated_open_tag_discards_the_rest() -> None:
    thinker = think.ThinkFilter()
    assert thinker.feed(f"Kept. {OPEN}never closed") == "Kept. "
    assert thinker.flush() == "", "text inside an unclosed tag is not shown"


def plain_text_is_untouched() -> None:
    text = "The model is thinking about 12,000 m3/s, not 6,800."
    assert streamed(text) == text
    assert streamed("Bag", "mati ", "and East-Rapti") == "Bagmati and East-Rapti"


def prose_and_tags_keep_every_word() -> None:
    """The ordinary word, a lone '<', and the text after a tag all survive."""
    prose = "The model is thinking about 540 mm, and thinking is not a tag."
    assert streamed(prose) == prose, "the ordinary word must be shown in full"
    assert streamed("think", "ing") == "thinking", "the word split across chunks must survive"
    assert streamed("if a <") == "if a <", "a lone '<' is text, not a tag prefix"
    assert streamed(OPEN, CLOSE, "540 mm") == "540 mm", "text after a tag pair is kept"
    assert streamed(OPEN, "r", CLOSE[:4], CLOSE[4:] + "540 mm") == "540 mm"
    assert streamed(CLOSE, "540 mm") == "540 mm", "a stray closing tag is a tag, not prose"
    assert streamed(CLOSE[:4], CLOSE[4:] + "540 mm") == "540 mm"
    assert streamed(OPEN, "r", CLOSE, "thinking continues") == "thinking continues"


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
            ("a split tag still strips its block", a_split_tag_still_strips_its_block),
            ("an unterminated open tag discards the rest", an_unterminated_open_tag_discards_the_rest),
            ("plain text is untouched", plain_text_is_untouched),
            ("the prose around a tag is never swallowed", prose_and_tags_keep_every_word),
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
