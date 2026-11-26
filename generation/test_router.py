"""Prove the router's rules: five routes, the settings each one changes, and its refusals.

Usage:
    .venv\\Scripts\\python.exe generation\\test_router.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from generation import router                     # noqa: E402

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


def expect(name: str, question: str, want: str, history=None) -> None:
    got = router.route(question, history)["route"]
    assert got == want, f"{question!r} routed to {got}, wanted {want}"


# ------------------------------------------------------------------------- routes
def greetings() -> None:
    for text in ("hi", "Hello!", "hey there", "Good morning", "thanks", "ok"):
        expect(text, text, "greeting")


def a_greeting_with_a_question_is_not_a_greeting() -> None:
    """'hello, what was the rainfall at Tistung?' is a corpus question wearing a hello.

    It is a table question because it asks "how much"; what matters here is only that a
    long question is never answered with the greeting reply.
    """
    question = "hello, what was the rainfall at Tistung in 1970 and how much?"
    assert router.route(question)["route"] != "greeting", router.route(question)


def summaries() -> None:
    for text in ("Summarise this paper", "give me an overview of the report",
                 "what are the main findings", "summarize across all documents"):
        expect(text, text, "summary")


def tables() -> None:
    for text in ("how many households were surveyed", "what percentage of growers",
                 "the table of flood damage", "average rainfall in July"):
        expect(text, text, "table")


def followup_needs_history() -> None:
    expect("and in 1990?", "and in 1990?", "followup", HISTORY)
    expect("what about the other district?", "what about the other district?",
           "followup", HISTORY)
    expect("how many were affected there?", "how many were affected there?", "followup",
           HISTORY)


def followup_without_history_is_not_a_followup() -> None:
    """With no previous turn a pronoun has no referent; condensing cannot invent one."""
    expect("and in 1990?", "and in 1990?", "normal", None)
    expect("what about it?", "what about it?", "normal", [])


def a_complete_question_with_history_is_not_a_followup() -> None:
    """History alone never turns a self-contained question into a follow-up.

    This one mentions "the same table of results", so it routes to `table`; the invariant
    under test is that it is not condensed, because it already names its own subject.
    """
    long_question = ("What was the 24-hour rainfall depth recorded at Tistung during the "
                     "storm described in the Marahatta paper, and how does it compare with "
                     "the value at Ghantemadi in the same table of results?")
    routed = router.route(long_question, HISTORY)
    assert routed["route"] != "followup", routed
    assert routed["condense"] is False, routed


def table_question_with_history_is_still_a_table_question_if_complete() -> None:
    text = "How many households were surveyed in the lower catchment of the East-Rapti basin?"
    expect(text, text, "table", HISTORY)


# ----------------------------------------------------------------------- settings
def settings_per_route() -> None:
    assert router.route("hi")["k"] == 0, "a greeting must not retrieve"
    assert router.route("summarise this paper")["k"] == 6
    assert router.route("summarise this paper")["prompt_mode"] == "summary"
    assert router.route("how many households")["k"] == 6
    assert router.route("how many households")["prompt_mode"] == "table"
    assert router.route("what was the rainfall at Tistung")["k"] == 5
    assert router.route("what was the rainfall at Tistung")["prompt_mode"] == "normal"


def every_route_stays_inside_the_context_budget() -> None:
    """Task 1 pins 4-6 passages in context; a route may not raise that on its own."""
    for name, settings in router.SETTINGS.items():
        if name == "greeting":
            assert settings["k"] == 0, "a greeting must not retrieve"
        else:
            assert 4 <= settings["k"] <= 6, f"{name} asks for k={settings['k']}"


def the_cli_does_not_override_the_route() -> None:
    """`--k` unset must mean "the route's k", or summary and table never get theirs."""
    from generation import answer

    assert answer._parser().parse_args(["a question"]).k is None
    assert answer._parser().parse_args(["a question", "--k", "4"]).k == 4


def a_question_about_this_paper_is_not_a_followup() -> None:
    """"this paper" names its own subject, so it is complete even after a previous turn.

    Routing it as a follow-up would condense it against the last turn and search for a
    question the user did not ask.
    """
    routed = router.route("What does this paper say about the rainfall in Tistung?",
                          HISTORY)
    assert routed["route"] != "followup", routed
    assert routed["condense"] is False, routed


def a_continuation_still_wins_over_a_named_subject() -> None:
    """...but a question that opens by referring back is a follow-up regardless."""
    routed = router.route("and what about the same table?", HISTORY)
    assert routed["route"] == "followup", routed


# -------------------------------------------------------------------- list modifier
LIST_QUESTIONS = (
    "In which years does the paper list floods in the Sunkosi River?",
    "Which crops can be grown up to 11-15 m from a bamboo row, according to the study cited?",
    "List the organizations that were interviewed in the cook stove programme study.",
    "Name the districts covered by the wetland survey.",
)
# The four questions the rejected s6-4 rule broke, plus q038, which both dropped variants
# of the trigger would have caught. None may be flagged: that is what keeps their prompts
# and passages byte-identical (steps/16-list-retrieval.md, Stage 1).
NOT_LIST_QUESTIONS = (
    "What was the peak flood in the Bagmati River during the July 1993 event?",
    "How large is the area of the Bagmati River basin whose physiography favoured severe flooding?",
    "What range of specific flows do streams with drainage areas between 100 and 3000 km2 show?",
    "How does the paper derive a relationship between rainfall depth and catchment area?",
    "Which river has the lowest coefficient value among those listed by DHM/DPTC (1994)?",
)


def list_questions_are_flagged() -> None:
    for text in LIST_QUESTIONS:
        assert router.route(text)["list"] is True, text


def list_flag_is_scoped_and_cannot_leak() -> None:
    """A question the trigger misses must not be treated as a list, or the guarantee fails."""
    for text in NOT_LIST_QUESTIONS:
        assert router.route(text)["list"] is False, text


def the_list_flag_changes_no_retrieval_setting() -> None:
    """List is a modifier: the same question routes, retrieves and prompts as before."""
    table = router.route(LIST_QUESTIONS[1])
    assert (table["route"], table["k"], table["prompt_mode"]) == ("table", 6, "table"), table
    normal = router.route(LIST_QUESTIONS[0])
    assert (normal["route"], normal["k"], normal["prompt_mode"]) == ("normal", 5, "normal")
    assert "list" not in router.SETTINGS["normal"], "list must not become a route setting"


def only_followups_condense() -> None:
    assert router.route("and in 1990?", HISTORY)["condense"] is True
    assert router.route("what was the rainfall at Tistung")["condense"] is False
    assert router.route("summarise this paper")["condense"] is False


def empty_question_is_a_greeting() -> None:
    """Nothing to retrieve, nothing to ask: the UI sends this when the box is blank."""
    assert router.route("   ")["route"] == "greeting"


def every_route_has_a_reason() -> None:
    for text in ("hi", "summarise this", "how many rows", "plain question here", ""):
        assert router.route(text)["reason"], f"no reason for {text!r}"


def main() -> int:
    groups = [
        ("greetings", [
            ("hi, hello, thanks, ok", greetings),
            ("a greeting wrapped around a real question is not a greeting",
             a_greeting_with_a_question_is_not_a_greeting),
            ("an empty question is a greeting", empty_question_is_a_greeting),
        ]),
        ("summary and table", [
            ("summarise, overview, main findings", summaries),
            ("how many, percentage, table, average", tables),
        ]),
        ("follow-ups need a previous turn", [
            ("and/what about/how many ... there", followup_needs_history),
            ("the same words with no history stay normal", followup_without_history_is_not_a_followup),
            ("a complete question with history is not a follow-up",
             a_complete_question_with_history_is_not_a_followup),
            ("a complete table question stays a table question",
             table_question_with_history_is_still_a_table_question_if_complete),
            ("'this paper' is a subject, not a back-reference",
             a_question_about_this_paper_is_not_a_followup),
            ("an opening continuation still wins", a_continuation_still_wins_over_a_named_subject),
        ]),
        ("settings", [
            ("each route sets its own k and prompt mode", settings_per_route),
            ("no route exceeds the 4-6 context budget", every_route_stays_inside_the_context_budget),
            ("the CLI leaves the route's k alone", the_cli_does_not_override_the_route),
            ("only a follow-up condenses", only_followups_condense),
            ("every route explains itself", every_route_has_a_reason),
        ]),
        ("list modifier", [
            ("list questions are flagged", list_questions_are_flagged),
            ("the list flag is scoped and cannot leak", list_flag_is_scoped_and_cannot_leak),
            ("the list flag changes no retrieval setting",
             the_list_flag_changes_no_retrieval_setting),
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
