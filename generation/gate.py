"""The "not found" gate: one retrieval floor, and the model's own refusal.

D-058 measured why there is no score threshold here. On the re-based dev set the
answerable and not-found BM25 ranges overlap on every statistic -- top-1 18.43-80.52
against 18.01-29.97, margin 0.10-26.93 against 0.01-6.25, ratio 1.01-2.20 against
1.00-1.39 -- so a threshold that catches all six not-found questions also rejects 12 of
39 answerable ones. The decision therefore belongs to the model, which reads the
passages and can tell whether they answer the question; the score is only used to skip
the model when retrieval produced nothing worth reading.

Two outcomes, in this order:

1. **floor** -- if the best passage scores below `FLOOR`, the model is never asked. This
   catches an empty or off-topic query (a greeting, a one-word noise term), not a
   near-topic question the corpus cannot answer. At `FLOOR = 15` it cost nothing on the
   dev set: 0 of 6 not-found questions and 0 of 39 answerable ones. Raising it is a
   regression unless a measurement says otherwise.
2. **refusal** -- otherwise the model decides, and its refusal is accepted only in the
   exact words the prompt demands (`prompt.NOT_FOUND_TEXT`).

Usage:
    from generation import gate
    verdict = gate.decide(passages)                    # before asking the model
    if verdict["ask_model"]: ...
    verdict = gate.decide(passages, verify_result)     # after

Example:
    >>> gate.decide([{"doc": "a.pdf", "page": 1, "score": 4.2}])["decision"]
    'not_found'
    >>> gate.decide([{"doc": "a.pdf", "page": 1, "score": 40.0}])["ask_model"]
    True
"""

from __future__ import annotations

# Measured 2026-11-16 on eval/runs/2026-11-16-rebased-2026-11-16 (45 dev questions,
# 39 answerable, 6 not found): at 15 nothing answerable is lost and nothing not-found
# is caught, which is the point -- it guards empty retrieval, it does not judge content.
# `eval/calibrate_gate.py` prints that table from the saved run.
FLOOR = 15.0


def top_score(passages: list[dict]) -> float:
    """Highest BM25 score among the retrieved pages, 0.0 when nothing was retrieved."""
    return max((float(p.get("score") or 0.0) for p in passages), default=0.0)


def decide(passages: list[dict], verdict: dict | None = None,
           floor: float = FLOOR) -> dict:
    """Decide `not_found`, `answer` or `unverified`.

    With no `verdict`, the answer is either "ask the model" or a refusal made on the
    floor alone. With a verdict from `generation.verify`, the model has spoken and this
    resolves what its answer means.
    """
    top = top_score(passages)
    result = {"floor": floor, "top": round(top, 2), "ask_model": False,
              "decision": "not_found", "reason": ""}

    if not passages:
        result["reason"] = "retrieval returned no page above zero"
        return result

    if top < floor:
        result["reason"] = f"best passage scored {top:.1f}, below the floor of {floor:.0f}"
        return result

    if verdict is None:
        result.update(ask_model=True, decision="answer",
                      reason=f"best passage scored {top:.1f}, so the model decides")
        return result

    if verdict.get("said_not_found"):
        result.update(decision="not_found",
                      reason="the model refused: the passages do not answer the question")
        return result

    if verdict.get("ok"):
        result.update(decision="answer",
                      reason="every quotation was found on the page it cites")
        return result

    # A failed answer is not a refusal. Reporting it as "not found" would hide a model
    # that tried and drifted, so it stays unverified and says why.
    result.update(decision="unverified",
                  reason="the answer's quotations could not be verified: "
                         + "; ".join(verdict.get("problems") or [])[:300])
    return result
