"""Prove the retry keeps or drops the failed answer on measured counts only (D-072).

The retry used to append the failed answer unconditionally. q047 showed the cost: its
retry prompt reached 4,063 of the 4,096-token context, so the second answer was cut at
33 tokens. The guard reads what Ollama reported for the first call and drops the answer
only when prompt plus answer already reached `answer.RETRY_HEADROOM` of `num_ctx`.

Usage:
    .venv\\Scripts\\python.exe generation\\test_answer.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from generation import answer, prompt, verify        # noqa: E402

FAILURES: list[str] = []
TOTAL = 0

MESSAGES = [{"role": "system", "content": "passages"},
            {"role": "user", "content": "the question"}]
FAILED = 'The rainfall was 69.85% [1], p. 2: "Believe in taboos".'
PROBLEMS = ["quote not on the page"]


def check(name: str, fn) -> None:
    global TOTAL
    TOTAL += 1
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as exc:
        FAILURES.append(name)
        print(f"  FAIL  {name}: {exc}")


def over_budget_drops_the_answer() -> None:
    """The measured q047 shape: 4,063 of 4,096 tokens."""
    timing = {"prompt_tokens": 4030, "answer_tokens": 33}
    messages, dropped = answer._retry_messages(MESSAGES, FAILED, PROBLEMS, timing)
    assert dropped is True, "a retry at 4,063 of 4,096 tokens must drop the failed answer"
    assert len(messages) == len(MESSAGES) + 1, "only the retry message is added"
    assert not any(m["role"] == "assistant" for m in messages), "the failed answer leaked"
    assert "not repeated here" in messages[-1]["content"]
    assert "- quote not on the page" in messages[-1]["content"]


def under_budget_keeps_the_answer() -> None:
    timing = {"prompt_tokens": 1200, "answer_tokens": 300}
    messages, dropped = answer._retry_messages(MESSAGES, FAILED, PROBLEMS, timing)
    assert dropped is False, "a short prompt must keep the answer"
    assert messages[-2] == {"role": "assistant", "content": FAILED}
    assert "Your answer failed citation check:" in messages[-1]["content"]


def the_threshold_is_the_measured_limit() -> None:
    limit = answer.RETRY_HEADROOM * answer.NUM_CTX
    just_under = {"prompt_tokens": int(limit) - 10, "answer_tokens": 0}
    just_over = {"prompt_tokens": int(limit) + 10, "answer_tokens": 0}
    assert answer._retry_messages(MESSAGES, FAILED, PROBLEMS, just_under)[1] is False
    assert answer._retry_messages(MESSAGES, FAILED, PROBLEMS, just_over)[1] is True


def missing_counts_keep_the_answer() -> None:
    """A backend that reports nothing must not silently lose the model's own words."""
    messages, dropped = answer._retry_messages(MESSAGES, FAILED, PROBLEMS, {})
    assert dropped is False
    assert messages[-2]["role"] == "assistant"


VERIFIED = ('- 540 mm [1]\n- 139 households [1]\n\n[1] 1970_Test_Paper_W1.pdf, p. 2: '
            '"The 24-hour rainfall depth of 540 mm at Tistung was recorded in July 1970"')
PROSE = ('540 mm fell in 24 hours at Tistung [1].\n\n[1] 1970_Test_Paper_W1.pdf, p. 2: '
         '"The 24-hour rainfall depth of 540 mm at Tistung was recorded in July 1970"')
PASSAGES = [{"doc": "1970_Test_Paper_W1.pdf", "page": 2, "label": "Test 1970"}]


def a_list_route_verifies_the_shape() -> None:
    """Step 17: the route's `list` flag reaches the verifier, and only there."""
    page = ("The 24-hour rainfall depth of 540 mm at Tistung was recorded in July 1970, "
            "and 139 households were surveyed.")
    original = verify.page_text
    verify.page_text = lambda doc, number: page
    try:
        assert answer._verdict(VERIFIED, PASSAGES, {"list": True})["ok"]
        prose = answer._verdict(PROSE, PASSAGES, {"list": True})
        assert not prose["ok"], "prose must fail on a list question, so the retry fires"
        assert any('"- " lines' in p for p in prose["problems"]), prose["problems"]
        assert answer._verdict(PROSE, PASSAGES, {})["ok"], \
            "a non-list route must verify exactly as before"
        assert answer._verdict(PROSE, PASSAGES, {"list": False})["ok"]
    finally:
        verify.page_text = original


def the_retry_text_still_carries_the_refusal() -> None:
    messages, _ = answer._retry_messages(MESSAGES, FAILED, PROBLEMS,
                                         {"prompt_tokens": 4030, "answer_tokens": 33})
    assert prompt.NOT_FOUND_TEXT in messages[-1]["content"]


def main() -> int:
    cases = [
        ("a near-full context drops the failed answer", over_budget_drops_the_answer),
        ("a short context keeps it", under_budget_keeps_the_answer),
        ("the threshold is RETRY_HEADROOM x num_ctx", the_threshold_is_the_measured_limit),
        ("missing counts keep the answer", missing_counts_keep_the_answer),
        ("a list route verifies the shape (Step 17)", a_list_route_verifies_the_shape),
        ("the retry still offers the refusal", the_retry_text_still_carries_the_refusal),
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
