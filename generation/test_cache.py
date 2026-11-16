"""Prove the cache: hit on a repeat, miss after any change that could invalidate it.

D-017 requires the key to include the index, the model files and the prompt version, so
each of those is tested as its own miss — a cache that only keys on the question would
serve yesterday's answer after a re-parse and nobody would notice.

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
