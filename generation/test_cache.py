"""Prove the cache: a hit on a repeat, and a miss after anything that invalidates it.

D-017 requires the key to include the index, the model files and the prompt version, so
each of those is tested as its own miss: a cache that only keyed on the question would
serve yesterday's answer after a re-parse and nobody would notice.

The last group tests the second guard, which the key cannot express: an entry stores a
hash of every page it relied on and a hit re-hashes them from the index. Same files,
different parsed text — a re-OCR, a changed extractor — is a miss, and so is a page that
left the index. Pages are plain index records here, because that is what the guard reads.

Usage:
    .venv\\Scripts\\python.exe generation\\test_cache.py
"""

from __future__ import annotations

import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from generation import cache                      # noqa: E402

FAILURES: list[str] = []
TOTAL = 0

VERSIONS = {"index_version": "idx-a", "model_version": "qwen3.5:4b:abc123",
            "prompt_version": "s6-2"}

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


def pages(*items: tuple[str, int, str]) -> list[dict]:
    """An index page list: (doc, page, text)."""
    return [{"doc": doc, "page": page, "text": text} for doc, page, text in items]


def record(*sources: tuple[str, int]) -> dict:
    return {"answer": "540 mm",
            "passages": [{"n": n, "doc": doc, "page": page}
                         for n, (doc, page) in enumerate(sources, start=1)]}


# ---------------------------------------------------------------- the key (D-017)
def hit_on_repeat() -> None:
    path = temp_path()
    cache.put("What was the rainfall at Tistung?", {"answer": "540 mm"}, path=path,
              pages=[], **VERSIONS)
    got = cache.get("What was the rainfall at Tistung?", path=path, pages=[], **VERSIONS)
    assert got == {"answer": "540 mm"}, got


def hit_ignores_case_spacing_and_trailing_punctuation() -> None:
    path = temp_path()
    cache.put("What was the rainfall at Tistung?", {"answer": "540 mm"}, path=path,
              pages=[], **VERSIONS)
    for variant in ("what was the rainfall at tistung",
                    "  What was the rainfall   at Tistung ",
                    "What was the rainfall at Tistung"):
        assert cache.get(variant, path=path, pages=[],
                         **VERSIONS) == {"answer": "540 mm"}, variant


def miss_after_index_change() -> None:
    path = temp_path()
    cache.put("q", {"answer": "540 mm"}, path=path, pages=[], **VERSIONS)
    changed = {**VERSIONS, "index_version": "idx-b"}
    assert cache.get("q", path=path, pages=[], **changed) is None


def miss_after_model_change() -> None:
    path = temp_path()
    cache.put("q", {"answer": "540 mm"}, path=path, pages=[], **VERSIONS)
    changed = {**VERSIONS, "model_version": "qwen3.5:4b:def456"}
    assert cache.get("q", path=path, pages=[], **changed) is None


def miss_after_prompt_change() -> None:
    path = temp_path()
    cache.put("q", {"answer": "540 mm"}, path=path, pages=[], **VERSIONS)
    changed = {**VERSIONS, "prompt_version": "s6-3"}
    assert cache.get("q", path=path, pages=[], **changed) is None


def miss_on_a_different_question() -> None:
    path = temp_path()
    cache.put("What was the rainfall at Tistung?", {"answer": "540 mm"}, path=path,
              pages=[], **VERSIONS)
    assert cache.get("What was the rainfall at Ghantemadi?", path=path, pages=[],
                     **VERSIONS) is None
    assert cache.get("What was the rainfall at Tistung in mm?", path=path, pages=[],
                     **VERSIONS) is None


def survives_a_reload() -> None:
    """The cache is a file, so a new process must find what the last one wrote."""
    path = temp_path()
    cache.put("q", {"answer": "540 mm"}, path=path, pages=[], **VERSIONS)
    assert len(cache.load(path)) == 1
    assert cache.get("q", path=path, pages=[], **VERSIONS) == {"answer": "540 mm"}


def missing_file_is_an_empty_cache() -> None:
    assert cache.load(pathlib.Path(tempfile.mkdtemp()) / "nope.json") == {}


def corrupt_file_is_an_empty_cache() -> None:
    path = temp_path()
    path.write_text("{not json", encoding="utf-8")
    assert cache.load(path) == {}
    assert cache.get("q", path=path, pages=[], **VERSIONS) is None


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
    path = temp_path()
    index_pages = pages(("a.pdf", 1, TISTUNG))
    cache.put("q", record(("a.pdf", 1)), path=path, pages=index_pages, **VERSIONS)
    assert cache.get("q", path=path, pages=index_pages, **VERSIONS) is not None


def an_altered_page_is_a_miss() -> None:
    """Same file name and size on purpose: the key cannot see this, the text hash can."""
    path = temp_path()
    cache.put("q", record(("a.pdf", 1)), path=path,
              pages=pages(("a.pdf", 1, TISTUNG)), **VERSIONS)
    altered = pages(("a.pdf", 1, TISTUNG.replace("540 mm", "482 mm")))
    assert cache.get("q", path=path, pages=altered, **VERSIONS) is None


def a_page_missing_from_the_index_is_a_miss() -> None:
    path = temp_path()
    cache.put("q", record(("a.pdf", 2)), path=path,
              pages=pages(("a.pdf", 1, TISTUNG), ("a.pdf", 2, TISTUNG)), **VERSIONS)
    assert cache.get("q", path=path, pages=pages(("a.pdf", 1, TISTUNG)),
                     **VERSIONS) is None


def an_unrelated_page_changing_is_not_a_miss() -> None:
    path = temp_path()
    before = pages(("a.pdf", 1, TISTUNG), ("b.pdf", 1, TISTUNG))
    after = pages(("a.pdf", 1, TISTUNG), ("b.pdf", 1, TISTUNG.replace("540", "482")))
    cache.put("q", record(("a.pdf", 1)), path=path, pages=before, **VERSIONS)
    assert cache.get("q", path=path, pages=after, **VERSIONS) is not None


def a_page_without_index_text_is_never_a_hit() -> None:
    """A page the index has no text for cannot be re-checked, so it is not served."""
    path = temp_path()
    empty = pages(("a.pdf", 1, ""))
    cache.put("q", record(("a.pdf", 1)), path=path, pages=empty, **VERSIONS)
    assert cache.get("q", path=path, pages=empty, **VERSIONS) is None


def an_entry_without_fingerprints_is_a_miss() -> None:
    """Entries written before this guard cannot be re-checked, so they are not served."""
    path = temp_path()
    cache.save({cache.key("q", **VERSIONS): {"answer": "540 mm"}}, path)
    assert cache.get("q", path=path, pages=[], **VERSIONS) is None


def main() -> int:
    cases = [
        ("a repeated question is a hit", hit_on_repeat),
        ("case, spacing and trailing punctuation do not matter",
         hit_ignores_case_spacing_and_trailing_punctuation),
        ("a re-parsed index is a miss", miss_after_index_change),
        ("a different model file is a miss", miss_after_model_change),
        ("an edited prompt is a miss", miss_after_prompt_change),
        ("a different question is a miss", miss_on_a_different_question),
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
