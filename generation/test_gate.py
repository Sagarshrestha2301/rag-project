"""Prove the not-found gate: floor before the model, refusal after it, nothing invented.

Usage:
    .venv\\Scripts\\python.exe generation\\test_gate.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from generation import gate                      # noqa: E402

FAILURES: list[str] = []
TOTAL = 0


def pages(*scores: float) -> list[dict]:
    return [{"doc": f"p{i}.pdf", "page": i, "score": s} for i, s in enumerate(scores, start=1)]


def check(name: str, fn) -> None:
    global TOTAL
    TOTAL += 1
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as exc:
        FAILURES.append(name)
        print(f"  FAIL  {name}: {exc}")


# ------------------------------------------------------------------ before asking
def empty_retrieval_is_refused() -> None:
    verdict = gate.decide([])
    assert verdict["decision"] == "not_found", verdict
    assert verdict["ask_model"] is False
    assert "no page above zero" in verdict["reason"], verdict["reason"]


def below_floor_is_refused_without_asking() -> None:
    verdict = gate.decide(pages(4.0, 2.0, 1.0))
    assert verdict["decision"] == "not_found" and verdict["ask_model"] is False, verdict
    assert verdict["top"] == 4.0


def just_below_floor_is_refused() -> None:
    assert gate.decide(pages(gate.FLOOR - 0.01))["decision"] == "not_found"


def just_above_floor_asks_the_model() -> None:
    verdict = gate.decide(pages(gate.FLOOR + 0.01))
    assert verdict["ask_model"] is True and verdict["decision"] == "answer", verdict


def top_score_wins_not_the_last_page() -> None:
    assert gate.decide(pages(2.0, 90.0, 1.0))["ask_model"] is True


def custom_floor_is_honoured() -> None:
    assert gate.decide(pages(40.0), floor=50.0)["decision"] == "not_found"
    assert gate.decide(pages(40.0), floor=10.0)["decision"] == "answer"


def missing_scores_count_as_zero() -> None:
    assert gate.top_score([{"doc": "a.pdf", "page": 1}]) == 0.0


# ------------------------------------------------------------------- after asking
def model_refusal_becomes_not_found() -> None:
    verdict = gate.decide(pages(40.0), {"said_not_found": True, "ok": True, "problems": []})
    assert verdict["decision"] == "not_found", verdict
    assert "refused" in verdict["reason"], verdict["reason"]


def verified_answer_is_an_answer() -> None:
    verdict = gate.decide(pages(40.0), {"said_not_found": False, "ok": True, "problems": []})
    assert verdict["decision"] == "answer", verdict


def failed_verification_is_not_a_refusal() -> None:
    verdict = gate.decide(pages(40.0), {"said_not_found": False, "ok": False,
                                        "problems": ["[1] the quotation is not on a.pdf page 1"]})
    assert verdict["decision"] == "unverified", verdict
    assert "not on" in verdict["reason"], verdict["reason"]


def a_below_floor_question_is_still_refused_even_if_the_model_answered() -> None:
    """The floor runs first: a strong answer cannot come from a passage that scored 4."""
    verdict = gate.decide(pages(4.0), {"said_not_found": False, "ok": True, "problems": []})
    assert verdict["decision"] == "not_found", verdict


def main() -> int:
    groups = [
        ("before the model: the floor", [
            ("empty retrieval is refused", empty_retrieval_is_refused),
            ("a passage below the floor is refused without asking", below_floor_is_refused_without_asking),
            ("just below the floor is refused", just_below_floor_is_refused),
            ("just above the floor asks the model", just_above_floor_asks_the_model),
            ("the highest score decides, not the last page", top_score_wins_not_the_last_page),
            ("a custom floor is honoured", custom_floor_is_honoured),
            ("a missing score counts as zero", missing_scores_count_as_zero),
        ]),
        ("after the model: its refusal", [
            ("a refusal becomes not-found", model_refusal_becomes_not_found),
            ("a verified answer is an answer", verified_answer_is_an_answer),
            ("a failed check is unverified, not a refusal", failed_verification_is_not_a_refusal),
            ("the floor still wins over a confident answer", a_below_floor_question_is_still_refused_even_if_the_model_answered),
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
