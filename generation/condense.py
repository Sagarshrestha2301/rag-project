"""Turn "and in 1990?" into a question that can be retrieved on its own.

Step 6 task 5: only when there is chat history. A follow-up like "what about the
other district?" retrieves nothing useful on its own — the terms that make it
searchable ("rainfall", "Tistung") are in the previous turn — but rewriting every
question would change the meaning of questions that are already complete, so this runs
only for the `followup` route with a previous user turn present.

The rewrite is a model call at temperature 0 with a tight prompt, and it is allowed to
fail: if the model returns nothing useful, or echoes the question unchanged, the
original is used and `condensed` is False. Retrieval then behaves exactly as it would
have without this module, which is the safe failure.

Usage:
    from generation import condense
    text, used = condense.condense("and in 1990?", history, ask=my_ask_function)

Example:
    >>> condense.condense("and in 1990?", [], ask=lambda m: "unused")
    ('and in 1990?', False)
"""

from __future__ import annotations

MAX_HISTORY_TURNS = 4          # enough to resolve a pronoun, short enough to stay cheap
MAX_WORDS = 40                 # a rewrite longer than this is the model explaining itself

SYSTEM = (
    "Rewrite the user's last question as a standalone question, in at most 20 words, "
    "using the earlier conversation to resolve what it refers to.\n"
    "Rules:\n"
    "- Keep every name, place, year and number from the last question.\n"
    "- Do not answer the question and do not add facts the user did not say.\n"
    "- If the last question is already standalone, return it unchanged.\n"
    "Return only the rewritten question."
)


def _history_lines(history: list[dict]) -> list[str]:
    turns = [m for m in history if (m.get("content") or "").strip()]
    return [f"{m.get('role', 'user').capitalize()}: {m['content'].strip()}"
            for m in turns[-MAX_HISTORY_TURNS:]]


def condense(question: str, history: list[dict] | None, ask=None) -> tuple[str, bool]:
    """Return (question to retrieve with, whether it was rewritten).

    `ask` is the model call, injected so the tests need no Ollama: it takes a list of
    chat messages and returns the text. `generation.answer._ask` fits it.
    """
    if not history or not any((m.get("role") == "user") for m in history):
        return question, False
    if ask is None:
        return question, False

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "\n".join(_history_lines(history)
                                              + [f"Last question: {question.strip()}"])},
    ]
    try:
        rewritten = (ask(messages) or "").strip()
    except Exception as exc:  # noqa: BLE001 - a failed rewrite must not lose the question
        print(f"[condense] rewrite failed, using the original: {exc.__class__.__name__}: {exc}")
        return question, False

    # The model can answer with nothing but whitespace or a blank first line; splitlines()
    # on "" returns [], so take the first non-empty line, if there is one at all.
    lines = [line for line in rewritten.splitlines() if line.strip()]
    rewritten = lines[0].strip().strip('"').strip() if lines else ""
    if not rewritten or len(rewritten.split()) > MAX_WORDS:
        return question, False
    if rewritten.rstrip("?.!").lower() == question.strip().rstrip("?.!").lower():
        return question, False
    return rewritten, True
