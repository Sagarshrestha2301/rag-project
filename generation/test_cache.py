"""Prove the cache: a hit on a repeat, and a miss after anything that invalidates it.

Three guards, each tested as its own miss:

1. **The key** (D-017): question, index signature, model file, prompt version. A cache
   that only keyed on the question would serve yesterday's answer after a re-parse.
2. **The pages**: each entry hashes the text of every page it relied on, and a hit
   re-hashes them from the index. Same files, different parsed text — a re-OCR — is a
   miss.
3. **The index itself**: a hit is a miss when the index the process is holding no longer
   matches the corpus on disk (`corpus.is_current`). Without this, a long-lived process
   would keep re-checking page hashes against text the files no longer contain.

The fixtures are a temporary corpus (empty PDFs: the signature only stats them) and plain
index records, because that is what the guards read. Nothing here generates a real PDF.

Usage:
    .venv\\Scripts\\python.exe generation\\test_cache.py
"""

from __future__ import annotations

import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import corpus as corpus_lib                      # noqa: E402
from generation import cache                     # noqa: E402

FAILURES: list[str] = []
TOTAL = 0

VERSIONS = {"model_version": "qwen3.5:4b:abc123", "prompt_version": "s6-2"}

TISTUNG = ("Table 2: Flood damage in the East-Rapti basin. The 24-hour rainfall depth "
           "of 540 mm at Tistung was recorded in July 1970, and 139 households were "
           "surveyed in the lower catchment. Of these, 71 were growers.")


def check(name: str, fn) -> None:
    global TOTAL
    TOTAL += 1
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as exc:
        FAILURES.append(name)
        print(f"  FAIL  {name}: {exc}")


def temp_path() -> pathlib.Path:
    return pathlib.Path(tempfile.mkdtemp()) / "answer-cache.json"


def corpus_root(*names: str) -> pathlib.Path:
    """A corpus folder holding these (empty) PDFs, which is all the signature reads."""
    root = pathlib.Path(tempfile.mkdtemp())
    for name in names:
        (root / name).write_bytes(b"%PDF-1.4 test")
    return root


def index_for(root: pathlib.Path, *pages: tuple[str, int, str]) -> dict:
    """An index as `corpus.build()` would return it for this folder."""
    return {"pages": [{"doc": doc, "page": page, "text": text}
                      for doc, page, text in pages],
            "signature": corpus_lib.signature(root)}


def record(*sources: tuple[str, int]) -> dict:
    return {"answer": "540 mm",
            "passages": [{"n": n, "doc": doc, "page": page}
                         for n, (doc, page) in enumerate(sources, start=1)]}


# ---------------------------------------------------------------- the key (D-017)
def hit_on_repeat() -> None:
    root, path = corpus_root(), temp_path()
    index = index_for(root)
    cache.put("What was the rainfall at Tistung?", {"answer": "540 mm"}, path=path,
              index=index, **VERSIONS)
    got = cache.get("What was the rainfall at Tistung?", path=path, index=index,
                    root=root, **VERSIONS)
    assert got == {"answer": "540 mm"}, got


def hit_ignores_case_spacing_and_trailing_punctuation() -> None:
    root, path = corpus_root(), temp_path()
    index = index_for(root)
    cache.put("What was the rainfall at Tistung?", {"answer": "540 mm"}, path=path,
              index=index, **VERSIONS)
    for variant in ("what was the rainfall at tistung",
                    "  What was the rainfall   at Tistung ",
                    "What was the rainfall at Tistung"):
        assert cache.get(variant, path=path, index=index, root=root,
                         **VERSIONS) == {"answer": "540 mm"}, variant


def miss_after_index_change() -> None:
    first, second = corpus_root("a.pdf"), corpus_root("a.pdf", "b.pdf")
    path = temp_path()
    cache.put("q", {"answer": "540 mm"}, path=path, index=index_for(first), **VERSIONS)
    assert cache.get("q", path=path, index=index_for(second), root=second,
                     **VERSIONS) is None


def miss_after_model_change() -> None:
    root, path = corpus_root(), temp_path()
    index = index_for(root)
    cache.put("q", {"answer": "540 mm"}, path=path, index=index, **VERSIONS)
    changed = {**VERSIONS, "model_version": "qwen3.5:4b:def456"}
    assert cache.get("q", path=path, index=index, root=root, **changed) is None


def miss_after_prompt_change() -> None:
    root, path = corpus_root(), temp_path()
    index = index_for(root)
    cache.put("q", {"answer": "540 mm"}, path=path, index=index, **VERSIONS)
    changed = {**VERSIONS, "prompt_version": "s6-3"}
    assert cache.get("q", path=path, index=index, root=root, **changed) is None


def miss_on_a_different_question() -> None:
    root, path = corpus_root(), temp_path()
    index = index_for(root)
    cache.put("What was the rainfall at Tistung?", {"answer": "540 mm"}, path=path,
              index=index, **VERSIONS)
    assert cache.get("What was the rainfall at Ghantemadi?", path=path, index=index,
                     root=root, **VERSIONS) is None
    assert cache.get("What was the rainfall at Tistung in mm?", path=path, index=index,
                     root=root, **VERSIONS) is None


def a_follow_up_rewritten_into_another_question_is_a_miss() -> None:
    """Measured 2026-11-19: two different questions got the same answer, marked cached.

    A follow-up is rewritten before it is searched, and the condenser can return the
    previous question. Keying on the rewritten text alone made that follow-up replay the
    previous answer, so both questions must be in the key.
    """
    root, path = corpus_root("a.pdf"), temp_path()
    index = index_for(root, ("a.pdf", 1, TISTUNG))
    first = "What was the 24-hour rainfall at Tistung in July 1993?"
    second = "Bagmati River that had favored severe flooding is only about"
    cache.put(first, record(("a.pdf", 1)), path=path, index=index, **VERSIONS)

    # The condenser turned the follow-up back into the first question.
    assert cache.get(second, search_question=first, path=path, index=index,
                     root=root, **VERSIONS) is None, "the follow-up replays the first answer"
    # The first question, asked again, is still a hit.
    assert cache.get(first, search_question=first, path=path, index=index,
                     root=root, **VERSIONS) is not None
    # And the follow-up is stored under its own key, so it cannot displace that hit.
    cache.put(second, record(("a.pdf", 1)), search_question=first, path=path,
              index=index, **VERSIONS)
    assert cache.get(first, search_question=first, path=path, index=index,
                     root=root, **VERSIONS) is not None
    assert cache.get(second, search_question=first, path=path, index=index,
                     root=root, **VERSIONS) is not None


def survives_a_reload() -> None:
    """The cache is a file, so a new process must find what the last one wrote."""
    root, path = corpus_root(), temp_path()
    index = index_for(root)
    cache.put("q", {"answer": "540 mm"}, path=path, index=index, **VERSIONS)
    assert len(cache.load(path)) == 1
    assert cache.get("q", path=path, index=index, root=root,
                     **VERSIONS) == {"answer": "540 mm"}


def missing_file_is_an_empty_cache() -> None:
    assert cache.load(pathlib.Path(tempfile.mkdtemp()) / "nope.json") == {}


def corrupt_file_is_an_empty_cache() -> None:
    root, path = corpus_root(), temp_path()
    path.write_text("{not json", encoding="utf-8")
    assert cache.load(path) == {}
    assert cache.get("q", path=path, index=index_for(root), root=root,
                     **VERSIONS) is None


def index_version_follows_the_signature() -> None:
    one = {"signature": [{"doc": "a.pdf", "size": 10, "mtime": 1}]}
    two = {"signature": [{"doc": "a.pdf", "size": 10, "mtime": 2}]}
    assert cache.index_version(one) != cache.index_version(two)
    assert cache.index_version(one) == cache.index_version(dict(one))


def model_version_prefers_the_digest() -> None:
    assert cache.model_version("qwen3.5:4b") == "qwen3.5:4b"
    assert cache.model_version("qwen3.5:4b", "a" * 64) == "qwen3.5:4b:aaaaaaaaaaaa"


# ------------------------------------------------- the page fingerprints (re-verify)
def unchanged_pages_are_a_hit() -> None:
    root, path = corpus_root("a.pdf"), temp_path()
    index = index_for(root, ("a.pdf", 1, TISTUNG))
    cache.put("q", record(("a.pdf", 1)), path=path, index=index, **VERSIONS)
    assert cache.get("q", path=path, index=index, root=root, **VERSIONS) is not None


def an_altered_page_is_a_miss() -> None:
    """Same file name and size on purpose: the key cannot see this, the text hash can."""
    root, path = corpus_root("a.pdf"), temp_path()
    cache.put("q", record(("a.pdf", 1)), path=path,
              index=index_for(root, ("a.pdf", 1, TISTUNG)), **VERSIONS)
    altered = index_for(root, ("a.pdf", 1, TISTUNG.replace("540 mm", "482 mm")))
    assert cache.get("q", path=path, index=altered, root=root, **VERSIONS) is None


def a_page_missing_from_the_index_is_a_miss() -> None:
    root, path = corpus_root("a.pdf"), temp_path()
    cache.put("q", record(("a.pdf", 2)), path=path,
              index=index_for(root, ("a.pdf", 1, TISTUNG), ("a.pdf", 2, TISTUNG)),
              **VERSIONS)
    assert cache.get("q", path=path, index=index_for(root, ("a.pdf", 1, TISTUNG)),
                     root=root, **VERSIONS) is None


def an_unrelated_page_changing_is_not_a_miss() -> None:
    root, path = corpus_root("a.pdf", "b.pdf"), temp_path()
    before = index_for(root, ("a.pdf", 1, TISTUNG), ("b.pdf", 1, TISTUNG))
    after = index_for(root, ("a.pdf", 1, TISTUNG), ("b.pdf", 1, TISTUNG.replace("540", "482")))
    cache.put("q", record(("a.pdf", 1)), path=path, index=before, **VERSIONS)
    assert cache.get("q", path=path, index=after, root=root, **VERSIONS) is not None


def a_page_without_index_text_is_never_a_hit() -> None:
    """A page the index has no text for cannot be re-checked, so it is not served."""
    root, path = corpus_root("a.pdf"), temp_path()
    index = index_for(root, ("a.pdf", 1, ""))
    cache.put("q", record(("a.pdf", 1)), path=path, index=index, **VERSIONS)
    assert cache.get("q", path=path, index=index, root=root, **VERSIONS) is None


def an_entry_without_fingerprints_is_a_miss() -> None:
    """Entries written before this guard cannot be re-checked, so they are not served."""
    root, path = corpus_root(), temp_path()
    cache.save({cache.key("q", index_version="v1", **VERSIONS): {"answer": "540 mm"}}, path)
    assert cache.get("q", path=path, index={"signature": [], "pages": []},
                     root=root, **VERSIONS) is None


# ------------------------------------------------ the index against the disk (stale)
def a_stale_index_is_a_miss() -> None:
    """The process has been up since before a document arrived; the files say otherwise."""
    root, path = corpus_root("a.pdf"), temp_path()
    index = index_for(root, ("a.pdf", 1, TISTUNG))
    cache.put("q", record(("a.pdf", 1)), path=path, index=index, **VERSIONS)
    assert cache.get("q", path=path, index=index, root=root, **VERSIONS) is not None

    (root / "b.pdf").write_bytes(b"%PDF-1.4 new document")
    assert cache.get("q", path=path, index=index, root=root, **VERSIONS) is None, \
        "a hit was served from an index that no longer matches the corpus"


def a_removed_document_makes_the_index_stale() -> None:
    root, path = corpus_root("a.pdf", "b.pdf"), temp_path()
    index = index_for(root, ("a.pdf", 1, TISTUNG))
    cache.put("q", record(("a.pdf", 1)), path=path, index=index, **VERSIONS)
    (root / "b.pdf").unlink()
    assert cache.get("q", path=path, index=index, root=root, **VERSIONS) is None


def a_rebuilt_index_needs_its_own_entry() -> None:
    """A rebuild changes the key, so the question is answered once more and then cached.

    This is D-017 working as intended: a new document makes every old answer provisional,
    so it is re-computed rather than replayed, and the next identical question is fast.
    """
    root, path = corpus_root("a.pdf"), temp_path()
    cache.put("q", record(("a.pdf", 1)), path=path,
              index=index_for(root, ("a.pdf", 1, TISTUNG)), **VERSIONS)
    (root / "b.pdf").write_bytes(b"%PDF-1.4 new document")
    rebuilt = index_for(root, ("a.pdf", 1, TISTUNG), ("b.pdf", 1, TISTUNG))
    assert cache.get("q", path=path, index=rebuilt, root=root, **VERSIONS) is None
    cache.put("q", record(("a.pdf", 1)), path=path, index=rebuilt, **VERSIONS)
    assert cache.get("q", path=path, index=rebuilt, root=root, **VERSIONS) is not None


def main() -> int:
    cases = [
        ("a repeated question is a hit", hit_on_repeat),
        ("case, spacing and trailing punctuation do not matter",
         hit_ignores_case_spacing_and_trailing_punctuation),
        ("a re-parsed index is a miss", miss_after_index_change),
        ("a different model file is a miss", miss_after_model_change),
        ("an edited prompt is a miss", miss_after_prompt_change),
        ("a different question is a miss", miss_on_a_different_question),
        ("a follow-up rewritten into another question is a miss",
         a_follow_up_rewritten_into_another_question_is_a_miss),
        ("the cache survives a reload", survives_a_reload),
        ("a missing file is an empty cache", missing_file_is_an_empty_cache),
        ("a corrupt file is an empty cache", corrupt_file_is_an_empty_cache),
        ("the index version follows the corpus signature", index_version_follows_the_signature),
        ("the model version prefers the digest", model_version_prefers_the_digest),
        ("a hit re-checks unchanged pages", unchanged_pages_are_a_hit),
        ("a hit with an altered page is a miss", an_altered_page_is_a_miss),
        ("a hit with a page gone from the index is a miss",
         a_page_missing_from_the_index_is_a_miss),
        ("an unrelated page changing does not invalidate a hit",
         an_unrelated_page_changing_is_not_a_miss),
        ("a page with no index text is never a hit", a_page_without_index_text_is_never_a_hit),
        ("an entry without fingerprints is a miss", an_entry_without_fingerprints_is_a_miss),
        ("a hit is a miss when the index is stale", a_stale_index_is_a_miss),
        ("a removed document makes the index stale", a_removed_document_makes_the_index_stale),
        ("a rebuilt index needs its own entry, then hits",
         a_rebuilt_index_needs_its_own_entry),
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
