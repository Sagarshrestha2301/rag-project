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


def the_ui_serves_the_same_root() -> None:
    """The PDF route guards `CORPUS in path.parents`, so a second root would break links."""
    import ui.server                                   # noqa: F401 - builds the app

    assert ui.server.CORPUS == corpus.CORPUS, (ui.server.CORPUS, corpus.CORPUS)


def main() -> int:
    cases = [
        ("the root is the project folder", the_root_is_the_project_folder),
        ("every default path is absolute", every_default_path_is_absolute),
        ("the answer cache sits beside the index", the_answer_cache_sits_by_the_index),
        ("the index cache default follows the project", the_index_cache_default_follows_the_project),
        ("the same documents from any folder", the_same_documents_from_anywhere),
        ("a document still resolves from elsewhere", a_document_still_resolves_from_elsewhere),
        ("the UI serves the same root", the_ui_serves_the_same_root),
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
