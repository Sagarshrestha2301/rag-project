"""Prove the condense step: only for follow-ups, and it never loses the question.

The model call is injected, so these cases need no Ollama and stay deterministic — what
is under test is the decision to rewrite and the safe fallback, not the model's wording.

Usage:
    .venv\\Scripts\\python.exe generation\\test_condense.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from generation import condense                   # noqa: E402

FAILURES: list[str] = []
TOTAL = 0

HISTORY = [{"role": "user", "content": "What was the 24-hour rainfall depth at Tistung?"},
           {"role": "assistant", "content": "540 mm [1]."}]


def check(name: str, fn) -> None:
    global TOTAL
    TOTAL += 1
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as exc:
        FAILURES.append(name)
        print(f"  FAIL  {name}: {exc}")


def answers(text: str):
    """An `ask` that always returns `text`, and records that it was called."""
    calls: list[list[dict]] = []

    def ask(messages):
        calls.append(messages)
        return text

    ask.calls = calls      # type: ignore[attr-defined]
    return ask


def rewrites_a_follow_up() -> None:
    ask = answers("What was the rainfall depth at Tistung in 1990?")
    text, used = condense.condense("and in 1990?", HISTORY, ask=ask)
    assert used is True, "the rewrite was not used"
    assert text == "What was the rainfall depth at Tistung in 1990?", text
    assert ask.calls, "the model was never asked"


def sends_the_history_to_the_model() -> None:
    ask = answers("rewritten question")
    condense.condense("and in 1990?", HISTORY, ask=ask)
    sent = ask.calls[0]
    assert sent[0]["role"] == "system", sent[0]
    body = sent[1]["content"]
    assert "Tistung" in body, "the previous question was not included"
    assert "and in 1990?" in body, "the last question was not included"


def no_history_means_no_rewrite() -> None:
    ask = answers("something else entirely")
    for history in (None, [], [{"role": "assistant", "content": "hi"}]):
        text, used = condense.condense("and in 1990?", history, ask=ask)
        assert (text, used) == ("and in 1990?", False), (history, text, used)
    assert not ask.calls, "the model was called with nothing to rewrite against"


def unchanged_rewrite_is_not_a_rewrite() -> None:
    text, used = condense.condense("and in 1990?", HISTORY, ask=answers("and in 1990?"))
    assert (text, used) == ("and in 1990?", False)


def empty_rewrite_falls_back() -> None:
    for bad in ("", "   ", "\n\n"):
        text, used = condense.condense("and in 1990?", HISTORY, ask=answers(bad))
        assert (text, used) == ("and in 1990?", False), bad


def rambling_rewrite_falls_back() -> None:
    rambling = "Below is the rewritten question you asked for: " + "word " * 40
    text, used = condense.condense("and in 1990?", HISTORY, ask=answers(rambling))
    assert (text, used) == ("and in 1990?", False), text


def a_failing_model_does_not_lose_the_question() -> None:
    def ask(messages):
        raise RuntimeError("Ollama unreachable")

    text, used = condense.condense("and in 1990?", HISTORY, ask=ask)
    assert (text, used) == ("and in 1990?", False), (text, used)


def first_line_only_and_quotes_stripped() -> None:
    ask = answers('"What was the rainfall at Tistung in 1990?"\nExplanation: ...')
    text, used = condense.condense("and in 1990?", HISTORY, ask=ask)
    assert used and text == "What was the rainfall at Tistung in 1990?", text


def no_ask_means_no_rewrite() -> None:
    assert condense.condense("and in 1990?", HISTORY, ask=None) == ("and in 1990?", False)


def main() -> int:
    cases = [
        ("a follow-up is rewritten", rewrites_a_follow_up),
        ("the history reaches the model", sends_the_history_to_the_model),
        ("no history means no rewrite", no_history_means_no_rewrite),
        ("an unchanged rewrite is not a rewrite", unchanged_rewrite_is_not_a_rewrite),
        ("an empty rewrite falls back", empty_rewrite_falls_back),
        ("a rambling rewrite falls back", rambling_rewrite_falls_back),
        ("a failing model does not lose the question", a_failing_model_does_not_lose_the_question),
        ("only the first line is kept, quotes stripped", first_line_only_and_quotes_stripped),
        ("no ask function means no rewrite", no_ask_means_no_rewrite),
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
