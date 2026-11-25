"""Prove the gate: the floor refuses before the model, the verdict decides after it.

The two halves are tested separately because they run at different times: `pre_ask` sees
passages and no answer, `resolve` sees a verdict and no passages. A case that mixed them
would be testing a sequence the pipeline never performs.

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


# --------------------------------------------------------------- before the model
def empty_retrieval_is_refused() -> None:
    checked = gate.pre_ask([])
    assert checked["refused"] is True and checked["decision"] == "not_found", checked
    assert "no page above zero" in checked["reason"], checked["reason"]


def below_floor_is_refused() -> None:
    checked = gate.pre_ask(pages(4.0, 2.0, 1.0))
    assert checked["refused"] is True, checked
    assert checked["top"] == 4.0, checked["top"]


def the_floor_is_the_boundary() -> None:
    assert gate.pre_ask(pages(gate.FLOOR - 0.01))["refused"] is True
    assert gate.pre_ask(pages(gate.FLOOR))["refused"] is False, "the floor itself is allowed"


def the_highest_score_decides() -> None:
    """Ranking puts the best page first, but the floor must not depend on that."""
    assert gate.pre_ask(pages(2.0, 90.0, 1.0))["refused"] is False


def a_custom_floor_is_honoured() -> None:
    assert gate.pre_ask(pages(40.0), floor=50.0)["refused"] is True
    assert gate.pre_ask(pages(40.0), floor=10.0)["refused"] is False


def a_missing_score_counts_as_zero() -> None:
    assert gate.top_score([{"doc": "a.pdf", "page": 1}]) == 0.0
    assert gate.pre_ask([{"doc": "a.pdf", "page": 1}])["refused"] is True


# ---------------------------------------------------------------- after the model
def a_refusal_is_not_found() -> None:
    decision = gate.resolve({"said_not_found": True, "ok": True, "problems": []})
    assert decision["decision"] == "not_found", decision
    assert "refused" in decision["reason"], decision["reason"]


def a_refusal_with_prose_is_also_not_found() -> None:
    """Step 15: the verifier accepts the wide form, and the gate must say why."""
    decision = gate.resolve({"said_not_found": True, "ok": True, "problems": [],
                             "refusal_form": "exact_line_with_prose"})
    assert decision["decision"] == "not_found", decision
    assert "exact" in decision["reason"], decision["reason"]


def a_strict_refusal_does_not_mention_the_wide_form() -> None:
    decision = gate.resolve({"said_not_found": True, "ok": True, "problems": [],
                             "refusal_form": "line_only"})
    assert "Step 15" not in decision["reason"], decision["reason"]


def a_verified_answer_is_an_answer() -> None:
    decision = gate.resolve({"said_not_found": False, "ok": True, "problems": []})
    assert decision["decision"] == "answer", decision


def a_failed_check_is_unverified_not_a_refusal() -> None:
    decision = gate.resolve({"said_not_found": False, "ok": False,
                             "problems": ["[1] the quotation is not on a.pdf page 1"]})
    assert decision["decision"] == "unverified", decision
    assert "not on" in decision["reason"], decision["reason"]


def main() -> int:
    groups = [
        ("before the model: the floor", [
            ("empty retrieval is refused", empty_retrieval_is_refused),
            ("a passage below the floor is refused", below_floor_is_refused),
            ("the floor is the boundary", the_floor_is_the_boundary),
            ("the highest score decides", the_highest_score_decides),
            ("a custom floor is honoured", a_custom_floor_is_honoured),
            ("a missing score counts as zero", a_missing_score_counts_as_zero),
        ]),
        ("after the model: the verdict", [
            ("a refusal is not-found", a_refusal_is_not_found),
            ("a refusal with prose is not-found and says so", a_refusal_with_prose_is_also_not_found),
            ("a strict refusal keeps the plain reason", a_strict_refusal_does_not_mention_the_wide_form),
            ("a verified answer is an answer", a_verified_answer_is_an_answer),
            ("a failed check is unverified, not a refusal",
             a_failed_check_is_unverified_not_a_refusal),
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
