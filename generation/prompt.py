"""The prompt that makes an answer citable, and the format it must come back in.

Two things are forced here, in this order:

1. every factual sentence carries the number of the passage it came from, and
2. the answer ends with one citation line per number, holding the file name, the
   page, and a quotation copied from that page.

The quotation is what makes the answer checkable: `generation/verify.py` looks for
that exact text on that page, so a sentence the model made up has nothing to cite.

Usage:
    from generation import prompt
    text = prompt.build_system(hits)          # hits from corpus.search
    prompt.PROMPT_VERSION                     # changes when this file's wording does

Example of the shape a compliant answer has (this is what verify.py parses):

    540 mm fell in 24 hours at Tistung [1].
    Of 139 households surveyed, 71 were growers [2].

    [1] 1970_Marahatta_Relating_Hydrological_Extremes_W2121362616.pdf, p. 2: "the 24-hour rainfall depth of 540 mm at Tistung"
    [2] 1970_Das_Beliefs_..._W1999918290.pdf, p. 3: "of the 139 households, 71 were growers"
"""

from __future__ import annotations

import pathlib

# Bumped whenever SYSTEM_RULES or build_system changes, because the answer cache is
# keyed on it (D-017): a prompt edit must never serve yesterday's answers.
PROMPT_VERSION = "s6-2"

# Written out here, quoted by the prompt, and compared against in answer.py, so the
# refusal the model is told to produce is exactly the one the code looks for.
NOT_FOUND_TEXT = "Not found in the indexed documents."

# Order matters: the rules come after the passages, because a small model follows an
# instruction that follows the text more reliably than one that precedes it (the UI
# prototype learned this first — see ui/server.py).
SYSTEM_RULES = f"""You answer questions about the passages above and nothing else.

Cite like this:
- After every sentence that states a fact, put the number of the passage it came from \
in square brackets, exactly as printed beside that passage: [1], [2], and so on. One \
number per sentence is enough; use two only when the sentence needs both.
- Never write a number that is not printed beside a passage.

Then, after the answer and one blank line, write one citation line per number you used, \
in this exact shape:

[1] <file name exactly as printed beside the passage>, p. <page number>: "<quotation>"

The quotation must be copied character for character from that page, 8 to 25 words, \
with the original capitalisation and punctuation. Do not paraphrase, do not join two \
sentences with "...", and do not correct a typo in the original. It is checked against \
the page text in code and a quotation that is not found there is rejected.

Rules:
- Use only the passages above. Never use outside knowledge, never estimate, never \
calculate a number that is not printed.
- Answer in at most four sentences. Short beats complete.
- If the passages do not contain the answer, reply with exactly this line and nothing \
else: {NOT_FOUND_TEXT}"""


# Route-specific rules (task 4). Appended after SYSTEM_RULES so the citation contract
# never moves; these only change what counts as a complete answer.
EXTRA_RULES = {
    "normal": "",
    "table": (
        "\n\nThis question is about figures in a table. Copy every number exactly as it "
        "is printed, including its unit and any thousands separator, and quote the table "
        "row or header you took it from. If the table gives a range, give the range, not "
        "the midpoint you calculate."
    ),
    "summary": (
        "\n\nThis question asks for an overview. You may use up to six sentences and "
        "cite more than one passage, one [n] per claim, but every sentence still needs a "
        "verified quotation: summarise only what you can quote."
    ),
}


def file_name(hit: dict) -> str:
    """The passage's file name, without its folders.

    Citations are compared against `doc`, which the retrieval index stores as a bare
    name, while `file` may carry the corpus sub-folder (D-030 keeps the Drive layout).
    """
    return hit.get("doc") or pathlib.PurePosixPath(str(hit.get("file", ""))).name


def build_system(hits: list[dict], *, mode: str = "normal") -> str:
    """Number the passages, then append the rules.

    The number is printed next to the passage three times -- in the heading, at the
    end of the passage, and in the rules' example -- because the model otherwise
    miscounts which passage a sentence came from, which is how the UI prototype
    ended up citing [2] for text only passage 1 contained (D-044).
    """
    extra = EXTRA_RULES.get(mode, "")
    if not hits:
        return ("No passage was retrieved for this question.\n\n" + SYSTEM_RULES + extra)

    blocks = []
    for number, hit in enumerate(hits, start=1):
        body = hit.get("context") or hit.get("text") or ""
        blocks.append(
            f"PASSAGE [{number}] — {hit.get('label') or file_name(hit)}, "
            f"page {hit['page']}, file {file_name(hit)}\n"
            f"{body}\n"
            f"(End of passage [{number}]: anything taken from here is cited as "
            f"[{number}] and quoted from {file_name(hit)}, p. {hit['page']}.)"
        )
    return "\n\n".join(blocks) + "\n\n" + SYSTEM_RULES + extra


def retry_message(problems: list[str]) -> str:
    """What the model is told after its first answer failed verification.

    It names the failure and nothing else: the passages are not repeated, because a
    second copy of the context doubles the prompt and the model starts citing the
    second copy's numbering.
    """
    listed = "\n".join(f"- {problem}" for problem in problems)
    return (
        "Your answer failed citation check:\n"
        f"{listed}\n\n"
        "Answer the same question again, in the same format. Every quotation must be "
        "copied from the page you cite, unchanged, without \"...\" and without joining "
        "two sentences. If you cannot quote the page, answer " + NOT_FOUND_TEXT
    )
