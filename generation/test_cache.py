"""Prove the cache: a hit on a repeat, a miss after anything that invalidates it.

D-017 requires the key to include the index, the model files and the prompt version, so
each of those is tested as its own miss. A cache that only keys on the question would
serve yesterday's answer after a re-parse and nobody would notice.

The last group tests the second guard: an entry stores a fingerprint of every page it
relied on, and a hit re-checks them against the corpus. A page that was removed, or a
page whose text changed, must be a miss even when the key still matches.

Usage:
    .venv\\Scripts\\python.exe generation\\test_cache.py
"""

from __future__ import annotations

import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pymupdf                                    # noqa: E402

from generation import cache                      # noqa: E402

FAILURES: list[str] = []
TOTAL = 0

VERSIONS = {"index_version": "idx-a", "model_version": "qwen3.5:4b:abc123",
            "prompt_version": "s6-2"}

PAGE_TEXT = ("Table 2: Flood damage in the East-Rapti basin. The 24-hour rainfall depth "
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


def write_pdf(path: pathlib.Path, pages: list[str]) -> None:
    """A real PDF with a real text layer, so the page lookup is exercised for real."""
    path.unlink(missing_ok=True)
    doc = pymupdf.open()
    for text in pages:
        doc.new_page().insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def record(*pages: tuple[str, int]) -> dict:
    return {"answer": "540 mm",
            "passages": [{"n": n, "doc": doc, "page": page}
                         for n, (doc, page) in enumerate(pages, start=1)]}


# ---------------------------------------------------------------- the key (D-017)
def hit_on_repeat() -> None:
    path = temp_path()
    cache.put("What was the rainfall at Tistung?", {"answer": "540 mm"}, path=path, **VERSIONS)
    got = cache.get("What was the rainfall at Tistung?", path=path, **VERSIONS)
    assert got == {"answer": "540 mm"}, got


def hit_ignores_case_spacing_and_trailing_punctuation() -> None:
    path = temp_path()
    cache.put("What was the rainfall at Tistung?", {"answer": "540 mm"}, path=path, **VERSIONS)
    for variant in ("what was the rainfall at tistung",
                    "  What was the rainfall   at Tistung ",
                    "What was the rainfall at Tistung"):
        assert cache.get(variant, path=path, **VERSIONS) == {"answer": "540 mm"}, variant


def miss_after_index_change() -> None:
    path = temp_path()
    cache.put("q", {"answer": "540 mm"}, path=path, **VERSIONS)
    changed = {**VERSIONS, "index_version": "idx-b"}
    assert cache.get("q", path=path, **changed) is None


def miss_after_model_change() -> None:
    path = temp_path()
    cache.put("q", {"answer": "540 mm"}, path=path, **VERSIONS)
    changed = {**VERSIONS, "model_version": "qwen3.5:4b:def456"}
    assert cache.get("q", path=path, **changed) is None


def miss_after_prompt_change() -> None:
    path = temp_path()
    cache.put("q", {"answer": "540 mm"}, path=path, **VERSIONS)
    changed = {**VERSIONS, "prompt_version": "s6-3"}
    assert cache.get("q", path=path, **changed) is None


def miss_on_a_different_question() -> None:
    path = temp_path()
    cache.put("What was the rainfall at Tistung?", {"answer": "540 mm"}, path=path, **VERSIONS)
    assert cache.get("What was the rainfall at Ghantemadi?", path=path, **VERSIONS) is None
    assert cache.get("What was the rainfall at Tistung in mm?", path=path, **VERSIONS) is None


def survives_a_reload() -> None:
    """The cache is a file, so a new process must find what the last one wrote."""
    path = temp_path()
    cache.put("q", {"answer": "540 mm"}, path=path, **VERSIONS)
    entries = cache.load(path)
    assert len(entries) == 1, entries
    assert cache.get("q", path=path, **VERSIONS) == {"answer": "540 mm"}


def missing_file_is_an_empty_cache() -> None:
    assert cache.load(pathlib.Path(tempfile.mkdtemp()) / "nope.json") == {}


def corrupt_file_is_an_empty_cache() -> None:
    path = temp_path()
    path.write_text("{not json", encoding="utf-8")
    assert cache.load(path) == {}
    assert cache.get("q", path=path, **VERSIONS) is None


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
    root, path = pathlib.Path(tempfile.mkdtemp()), temp_path()
    write_pdf(root / "a.pdf", [PAGE_TEXT])
    cache.put("q", record(("a.pdf", 1)), path=path, corpus_root=root, **VERSIONS)
    assert cache.get("q", path=path, corpus_root=root, **VERSIONS) is not None


def a_removed_document_is_a_miss() -> None:
    root, path = pathlib.Path(tempfile.mkdtemp()), temp_path()
    write_pdf(root / "a.pdf", [PAGE_TEXT])
    cache.put("q", record(("a.pdf", 1)), path=path, corpus_root=root, **VERSIONS)
    (root / "a.pdf").unlink()
    assert cache.get("q", path=path, corpus_root=root, **VERSIONS) is None


def an_altered_page_is_a_miss() -> None:
    root, path = pathlib.Path(tempfile.mkdtemp()), temp_path()
    write_pdf(root / "a.pdf", [PAGE_TEXT])
    cache.put("q", record(("a.pdf", 1)), path=path, corpus_root=root, **VERSIONS)
    write_pdf(root / "a.pdf", [PAGE_TEXT.replace("540 mm", "482 mm")])
    assert cache.get("q", path=path, corpus_root=root, **VERSIONS) is None


def a_removed_page_is_a_miss() -> None:
    root, path = pathlib.Path(tempfile.mkdtemp()), temp_path()
    write_pdf(root / "a.pdf", ["Cover page. " * 8, PAGE_TEXT])
    cache.put("q", record(("a.pdf", 2)), path=path, corpus_root=root, **VERSIONS)
    write_pdf(root / "a.pdf", ["Cover page. " * 8])
    assert cache.get("q", path=path, corpus_root=root, **VERSIONS) is None


def a_change_to_an_unrelated_document_is_not_a_miss() -> None:
    root, path = pathlib.Path(tempfile.mkdtemp()), temp_path()
    write_pdf(root / "a.pdf", [PAGE_TEXT])
    write_pdf(root / "b.pdf", [PAGE_TEXT])
    cache.put("q", record(("a.pdf", 1)), path=path, corpus_root=root, **VERSIONS)
    write_pdf(root / "b.pdf", [PAGE_TEXT.replace("540 mm", "482 mm")])
    assert cache.get("q", path=path, corpus_root=root, **VERSIONS) is not None


def an_entry_without_fingerprints_is_a_miss() -> None:
    """Entries written before this guard cannot be re-checked, so they are not served."""
    path = temp_path()
    old_key = cache.key("q", **VERSIONS)
    cache.save({old_key: {"answer": "540 mm"}}, path)
    assert cache.get("q", path=path, **VERSIONS) is None


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
        ("a hit with a removed document is a miss", a_removed_document_is_a_miss),
        ("a hit with an altered page is a miss", an_altered_page_is_a_miss),
        ("a hit with a removed page is a miss", a_removed_page_is_a_miss),
        ("an unrelated document does not invalidate a hit",
         a_change_to_an_unrelated_document_is_not_a_miss),
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
