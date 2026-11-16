"""The "not found" gate: one retrieval floor, and the model's own refusal.

D-058 measured why there is no score threshold here. On the re-based dev set the
answerable and not-found BM25 ranges overlap on every statistic -- top-1 18.43-80.52
against 18.01-29.97, margin 0.10-26.93 against 0.01-6.25, ratio 1.01-2.20 against
1.00-1.39 -- so a threshold that catches all six not-found questions also rejects 12 of
39 answerable ones. The decision belongs to the model, which reads the passages and can
tell whether they answer the question; the score is only used to skip the model when
retrieval produced nothing worth reading.

The two steps happen at different times, so they are two functions:

- `pre_ask(passages)` -- before the model: refuse, or say the model decides. Below
  `FLOOR` the model is never asked. At `FLOOR = 15` that cost nothing on the dev set
  (0 of 6 not-found caught, 0 of 39 answerable lost), which is the point: it catches an
  empty or off-topic query, not a near-topic question the corpus cannot answer.
- `resolve(verdict)` -- after the model, from `generation.verify`'s verdict alone: a
  refusal in the prompt's exact words is "not found", a verified answer is an answer, and
  a failed check is `unverified`. A model that drifted is never reported as a corpus that
  was silent.

Usage:
    from generation import gate
    checked = gate.pre_ask(passages)
    if checked["refused"]:
        ...                                  # the answer is the refusal; no model call
    else:
        ...                                  # ask, then verify
        decision = gate.resolve(verdict)

Example:
    >>> gate.pre_ask([{"doc": "a.pdf", "page": 1, "score": 4.2}])["refused"]
    True
    >>> gate.pre_ask([{"doc": "a.pdf", "page": 1, "score": 40.0}])["refused"]
    False
    >>> gate.resolve({"said_not_found": True, "ok": True})["decision"]
    'not_found'
    >>> gate.resolve({"said_not_found": False, "ok": False, "problems": ["x"]})["decision"]
    'unverified'
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


def pre_ask(passages: list[dict], floor: float = FLOOR) -> dict:
    """Refuse on the floor, or hand the decision to the model.

    `refused` is the only thing the caller must branch on; `decision` is filled in so a
    refusal record reads like an answered one.
    """
    top = top_score(passages)
    result = {"floor": floor, "top": round(top, 2), "refused": True,
              "decision": "not_found", "reason": ""}

    if not passages:
        result["reason"] = "retrieval returned no page above zero"
    elif top < floor:
        result["reason"] = f"best passage scored {top:.1f}, below the floor of {floor:.0f}"
    else:
        result.update(refused=False, decision="answer",
                      reason=f"best passage scored {top:.1f}, so the model decides")
    return result


def resolve(verdict: dict) -> dict:
    """What the model's answer means, from its verification verdict alone."""
    if verdict.get("said_not_found"):
        return {"decision": "not_found",
                "reason": "the model refused: the passages do not answer the question"}

    if verdict.get("ok"):
        return {"decision": "answer",
                "reason": "every quotation was found on the page it cites"}

    problems = "; ".join(verdict.get("problems") or [])[:300]
    return {"decision": "unverified",
            "reason": f"the answer's quotations could not be verified: {problems}"}
