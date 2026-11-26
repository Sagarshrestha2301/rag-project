"""Prove the corpus root is absolute: the working directory cannot change it.

`corpus.CORPUS` and `corpus.INDEX_CACHE` are derived from this project folder, not from
wherever the process was started, so a question asked from another folder searches the
same documents and reuses the same index. `generation.cache` and `ui/server.py` take the
root from `corpus` instead of re-deriving `data/corpus` themselves.

Usage:
    .venv\\Scripts\\python.exe test_corpus.py
    cd %TEMP% && C:\\path\\to\\venv\\Scripts\\python.exe C:\\path\\to\\test_corpus.py
"""

from __future__ import annotations

import inspect
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import corpus                                     # noqa: E402
from generation import cache                      # noqa: E402

FAILURES: list[str] = []
TOTAL = 0


def check(name: str, fn) -> None:
    global TOTAL
    TOTAL += 1
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as exc:
        FAILURES.append(name)
        print(f"  FAIL  {name}: {exc}")


class Elsewhere:
    """Run the block as if the process had been started in an empty folder."""

    def __enter__(self) -> pathlib.Path:
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.was = pathlib.Path.cwd()
        os.chdir(self.root)
        return self.root

    def __exit__(self, *exc) -> None:
        os.chdir(self.was)


# ------------------------------------------------------------------------ the root
def the_root_is_the_project_folder() -> None:
    assert corpus.ROOT == pathlib.Path(corpus.__file__).resolve().parent, corpus.ROOT
    assert corpus.CORPUS == corpus.ROOT / "data" / "corpus", corpus.CORPUS
    assert corpus.INDEX_CACHE == corpus.ROOT / "index" / "pages.json", corpus.INDEX_CACHE


def every_default_path_is_absolute() -> None:
    for name, path in (("ROOT", corpus.ROOT), ("CORPUS", corpus.CORPUS),
                       ("INDEX_CACHE", corpus.INDEX_CACHE), ("CACHE_PATH", cache.CACHE_PATH)):
        assert path.is_absolute(), f"{name} is still relative: {path}"


def the_answer_cache_sits_by_the_index() -> None:
    assert cache.CACHE_PATH == corpus.ROOT / "index" / "answer-cache.json", cache.CACHE_PATH


def the_index_cache_default_follows_the_project() -> None:
    default = inspect.signature(corpus.build).parameters["cache"].default
    assert default == corpus.INDEX_CACHE, default


# --------------------------------------------------------------- from another folder
def the_same_documents_from_anywhere() -> None:
    here = [path.relative_to(corpus.ROOT) for path in corpus.files()]
    with Elsewhere():
        there = [path.relative_to(corpus.ROOT) for path in corpus.files()]
        assert corpus.CORPUS.is_absolute(), corpus.CORPUS
    assert here == there, f"{len(here)} documents here, {len(there)} elsewhere"


def a_document_still_resolves_from_elsewhere() -> None:
    """`path_for` is what every PDF link and every page read goes through."""
    documents = corpus.files()
    if not documents:
        assert corpus.files() == [], "no corpus, which is consistent in both places"
        return
    name = documents[0].name
    with Elsewhere():
        found = corpus.path_for(name)
        assert found.is_file(), found
        assert found.name == name, found


def the_ui_serves_the_same_documents() -> None:
    """A citation chip's file name resolves through the same root the pages were read from.

    `ui.pipeline.pdf_path` is the PDF route's only resolver (Step 7), so this checks the
    real function instead of a module constant that no longer exists.
    """
    from ui import pipeline

    documents = corpus.files()
    if not documents:
        assert pipeline.pdf_path("anything.pdf") is None, "no corpus, but a PDF resolved"
        return
    name = documents[0].name
    assert pipeline.pdf_path(name) == corpus.path_for(name).resolve(), name
    # A name that is not a plain corpus file name is refused, not joined onto the root.
    assert pipeline.pdf_path("../outside.pdf") is None
    assert pipeline.pdf_path("..\\outside.pdf") is None
    assert pipeline.pdf_path("not-in-the-corpus.pdf") is None


# ---------------------------------------------------------------- passage placement
# A page where the answering sentence sits after the window the old rule picked: the
# question's common words are in the head, its one rare word is not (the q036 shape).
# The head repeats three common query words, so it wins the term count; the rare word sits
# far below in a line that repeats none of them. That is the q036 shape in miniature.
LONG_PAGE = (
    "which years floods " * 40
    + "Plain filler prose that carries no query term at all. " * 40
    + "The Sunkosi River records 1964, 1981 and 1984."
)
IDF = {"sunkosi": 7.5, "floods": 4.0, "years": 2.5, "which": 1.2}


def a_cover_rule_moves_the_window_onto_the_rare_term() -> None:
    terms = ["which", "years", "floods", "sunkosi"]
    plain = corpus.context_for(LONG_PAGE, terms)
    assert "Sunkosi" not in plain, "fixture must reproduce the blind spot"
    covered = corpus.context_for(LONG_PAGE, terms,
                                 cover=corpus.cover_terms(LONG_PAGE, terms, IDF))
    assert "Sunkosi" in covered, "the coverage rule must reach the answering sentence"
    # The invariant is that the window moves rather than grows (D-073's token budget):
    # head plus one window plus the ellipsis, never two windows.
    assert len(covered) <= corpus.HEAD_CHARS + corpus.WINDOW_CHARS + 3, len(covered)
    assert len(plain) <= corpus.HEAD_CHARS + corpus.WINDOW_CHARS, len(plain)


def cover_terms_are_rarest_first_and_only_what_the_page_prints() -> None:
    terms = ["which", "years", "floods", "sunkosi", "absentword"]
    got = corpus.cover_terms(LONG_PAGE, terms, IDF)
    assert got == ["sunkosi", "floods"], got
    assert "absentword" not in got
    assert corpus.cover_terms(LONG_PAGE, terms, IDF, top=1) == ["sunkosi"]


def the_default_placement_is_unchanged() -> None:
    """Step 16 must not move a passage for any caller that does not ask for it."""
    terms = ["which", "years", "floods", "sunkosi"]
    assert corpus.context_for(LONG_PAGE, terms, cover=()) == \
        corpus.context_for(LONG_PAGE, terms)
    start, window = corpus.best_window(LONG_PAGE, terms)
    assert window == LONG_PAGE[start:start + corpus.WINDOW_CHARS]


def training_a_window_on_a_term_already_covered_is_a_no_op() -> None:
    terms = ["which", "years"]
    before = corpus.context_for(LONG_PAGE, terms)
    after = corpus.context_for(LONG_PAGE, terms, cover=("years",))
    assert before == after, "a covered term must not move the window"


def main() -> int:
    cases = [
        ("the root is the project folder", the_root_is_the_project_folder),
        ("every default path is absolute", every_default_path_is_absolute),
        ("the answer cache sits beside the index", the_answer_cache_sits_by_the_index),
        ("the index cache default follows the project", the_index_cache_default_follows_the_project),
        ("the same documents from any folder", the_same_documents_from_anywhere),
        ("a document still resolves from elsewhere", a_document_still_resolves_from_elsewhere),
        ("the UI serves the same documents", the_ui_serves_the_same_documents),
        ("a cover rule moves the window onto the rare term",
         a_cover_rule_moves_the_window_onto_the_rare_term),
        ("cover terms are rarest first and only on the page",
         cover_terms_are_rarest_first_and_only_what_the_page_prints),
        ("the default placement is unchanged", the_default_placement_is_unchanged),
        ("a covered term does not move the window",
         training_a_window_on_a_term_already_covered_is_a_no_op),
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
