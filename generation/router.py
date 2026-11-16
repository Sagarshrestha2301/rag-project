"""Decide what kind of question this is, and what that changes.

Rule-based on purpose (Step 6 task 4): a regex over the question text, never a model
call, so the route is free, deterministic and explainable — and so a routing mistake
shows up as a wrong `k` in a log rather than as an unpredictable answer.

Five routes, each changing one or two settings:

| route | retrieval | prompt | why |
|---|---|---|---|
| `greeting` | none | none | "hello" is not a corpus question; answering it from passages is how a chat starts quoting a rainfall paper at you |
| `followup` | 5 passages | normal, question condensed first | "and in 1990?" only means something with the previous turn (task 5) |
| `summary` | 8 passages | `summary` rules | an overview legitimately needs more than one page |
| `table` | 6 passages | `table` rules | figures need the rule that says copy the number, the unit and the row |
| `normal` | 5 passages | normal | everything else |

Off-topic questions are deliberately **not** a route: there is no reliable rule for "this
question is about something else", and the gate in `generation/gate.py` already refuses
whatever retrieval cannot support (top-1 below the floor, or the model's own refusal).

Usage:
    from generation import router
    route = router.route("and in 1990?", history=[{"role": "user", ...}])
    route["route"], route["k"], route["prompt_mode"], route["condense"]
    # ('followup', 5, 'normal', True)
"""

from __future__ import annotations

import re

GREETING = re.compile(
    r"^\s*(hi|hello|hey|hiya|yo|good\s+(morning|afternoon|evening)|thanks|thank\s+you|"
    r"bye|goodbye|cheers|ok(ay)?)\b",
    re.IGNORECASE,
)
SUMMARY = re.compile(
    r"\b(summari[sz]e|summary|overview|main\s+(findings?|points?|results?)|"
    r"key\s+findings?|what\s+(is|does|did)\s+(this|the)\s+(paper|document|report|study)"
    r"\s+(say|about|conclude)|across\s+(all\s+)?(the\s+)?(documents?|papers?|corpus))\b",
    re.IGNORECASE,
)
TABLE = re.compile(
    r"\b(tables?|tabled|rows?|columns?|tabulated|how\s+many|how\s+much|"
    r"percent(age)?|proportion|average|mean|median|total\s+number)\b|%",
    re.IGNORECASE,
)
# A pronoun or a bare continuation with no subject of its own: it needs the previous turn.
FOLLOWUP = re.compile(
    r"(^\s*(and|but|also|then|what\s+about|how\s+about)\b)|"
    r"\b(it|its|it's|that|those|these|they|them|their|this|he|she|his|her|there|same)\b",
    re.IGNORECASE,
)

SETTINGS = {
    "greeting": {"k": 0, "prompt_mode": "normal", "condense": False},
    "followup": {"k": 5, "prompt_mode": "normal", "condense": True},
    "summary": {"k": 8, "prompt_mode": "summary", "condense": False},
    "table": {"k": 6, "prompt_mode": "table", "condense": False},
    "normal": {"k": 5, "prompt_mode": "normal", "condense": False},
}
SHORT_QUESTION_WORDS = 12


def word_count(question: str) -> int:
    return len([w for w in re.split(r"\s+", (question or "").strip()) if w])


def has_user_turn(history: list[dict] | None) -> bool:
    return any((m.get("role") == "user" and (m.get("content") or "").strip())
               for m in history or [])


def route(question: str, history: list[dict] | None = None) -> dict:
    """The route for this question plus the settings it implies.

    `history` is the chat so far, oldest first, same shape as the UI's messages. It is
    only consulted for follow-ups: with no previous question, "and in 1990?" is a
    question with no subject, and condensing cannot invent one.
    """
    text = (question or "").strip()

    if not text:
        return {"route": "greeting", "reason": "empty question", **SETTINGS["greeting"]}

    if GREETING.match(text) and word_count(text) <= 4:
        return {"route": "greeting", "reason": "opens with a greeting or thanks",
                **SETTINGS["greeting"]}

    # Follow-up before summary/table: "what about the table?" is still a follow-up.
    if has_user_turn(history) and FOLLOWUP.search(text) and (
            word_count(text) <= SHORT_QUESTION_WORDS or text.lower().startswith(
                ("and", "but", "also", "then", "what about", "how about"))):
        return {"route": "followup", "reason": "refers back to the previous turn",
                **SETTINGS["followup"]}

    if SUMMARY.search(text):
        return {"route": "summary", "reason": "asks for an overview",
                **SETTINGS["summary"]}

    if TABLE.search(text):
        return {"route": "table", "reason": "asks for a figure from a table",
                **SETTINGS["table"]}

    return {"route": "normal", "reason": "no rule matched", **SETTINGS["normal"]}
