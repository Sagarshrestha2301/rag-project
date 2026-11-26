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
# The prompt text has not changed since s6-5; s6-6 records that an answer is now verified
# against the list shape as well (Step 17), and the cache key carries this version (D-017),
# so a cached s6-5 answer cannot be replayed as if it had been shaped.
# "s6-4" is deliberately skipped: it is the label of the rejected list rule whose run is
# stored in eval/runs/2026-11-25-step16-list-format (D-092), so reusing it would make two
# different prompts look like one.
PROMPT_VERSION = "s6-6"

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

A quotation supports the sentence that carries its number, and only that sentence. When \
two sentences state different facts or figures from the same page, give each its own \
number and its own quotation of the words that carry that fact; never reuse one quotation \
for both. If a sentence states a figure, its quotation must contain that figure as printed.

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


# Step 16: the list shape, appended only for a question the router flags as a list. The
# length contract is kept, not waived - the rejected s6-4 rule allowed eight items and no
# sentence limit, and every question it broke had gained a sentence with an extra citation
# to a real but non-gold page (D-092).
LIST_RULES = (
    "\n\n- When the answer is a set of parallel items -- years, names, crops, places -- "
    "answer with one list instead of sentences: at most six lines, each starting with "
    "\"- \" and ending with the [n] of the passage that item came from. The list is the "
    "answer; if the items need a unit or a range, at most one sentence may follow the "
    "list. Do not add a sentence or a citation to explain or contextualise the list, and "
    "cite only the passage the items came from."
)


def build_system(hits: list[dict], *, mode: str = "normal", list_style: bool = False) -> str:
    """Number the passages, then append the rules.

    The number is printed next to the passage three times -- in the heading, at the
    end of the passage, and in the rules' example -- because the model otherwise
    miscounts which passage a sentence came from, which is how the UI prototype
    ended up citing [2] for text only passage 1 contained (D-044).
    """
    extra = EXTRA_RULES.get(mode, "")
    if list_style:
        extra += LIST_RULES
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


def retry_message(problems: list[str], *, previous_kept: bool = True) -> str:
    """What the model is told after its first answer failed verification.

    It names the failure and nothing else: the passages are not repeated, because a
    second copy of the context doubles the prompt and the model starts citing the
    second copy's numbering.

    `previous_kept=False` is for a retry whose context is already nearly full
    (D-072): the caller drops the failed answer from the conversation, and this
    sentence tells the model why it cannot see what it wrote. Measured on q047, whose
    retry prompt was 4,063 of 4,096 tokens, so its second answer was cut at 33.

    Example: retry_message(["quote not on the page"], previous_kept=False) opens with
    "Your previous answer failed citation check. It is not repeated here...".
    """
    listed = "\n".join(f"- {problem}" for problem in problems)
    opening = "Your answer failed citation check:"
    if not previous_kept:
        opening = ("Your previous answer failed citation check. It is not repeated here "
                   "because the context is nearly full:")
    return (
        f"{opening}\n"
        f"{listed}\n\n"
        "Answer the same question again, in the same format. Every quotation must be "
        "copied from the page you cite, unchanged, without \"...\" and without joining "
        "two sentences. If you cannot quote the page, answer " + NOT_FOUND_TEXT
    )
