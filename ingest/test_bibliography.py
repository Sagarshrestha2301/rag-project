"""Prove that a bibliographic field is only kept when page 1 prints it.

The model is not called here: every case feeds `validate` / `extract` a draft, the way a
run would, so the rules can be checked without Ollama or the real corpus. The last case
builds a two-document artifact in a temp folder and checks that a second run does nothing.

Usage:
    .venv\\Scripts\\python.exe ingest\\test_bibliography.py
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingest import bibliography as bib           # noqa: E402

PAGE = ("44 S. Marahatta & J. K. Bhusal August 2009 Relating Hydrological Extremes with "
        "Area - A Case on Extreme Floods in South Central Nepal. Suresh Marahatta and "
        "Jagat Kumar Bhusal. Journal of Hydrology and Meteorology, Vol. 6, No. 1. "
        "doi:10.3126/jhm.v6i1.10101")

FAILURES: list[str] = []


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as exc:
        FAILURES.append(name)
        print(f"  FAIL  {name}: {exc}")


def test_validate_keeps_printed_fields() -> None:
    record = bib.validate({"title": "Relating Hydrological Extremes with Area - A Case on "
                                    "Extreme Floods in South Central Nepal",
                           "authors": ["Suresh Marahatta", "Jagat Kumar Bhusal"],
                           "year": 2009, "venue": "Journal of Hydrology and Meteorology",
                           "doi": "10.3126/jhm.v6i1.10101"}, PAGE)
    assert record["year"] == 2009, record
    assert record["authors"] == ["Suresh Marahatta", "Jagat Kumar Bhusal"], record["authors"]
    assert record["venue"] == "Journal of Hydrology and Meteorology", record["venue"]
    assert record["doi"] == "10.3126/jhm.v6i1.10101", record["doi"]
    assert record["evidence"]["title"].startswith("Bhusal August 2009"), record["evidence"]


def test_validate_drops_invented_values() -> None:
    record = bib.validate({"title": "Rainfall in the Kathmandu Valley 1890-1990",
                           "authors": ["Suresh Marahatta", "Nobody Here"],
                           "year": 1993, "venue": "Nature", "doi": "10.1000/xyz"}, PAGE)
    assert record["title"] is None, record["title"]
    assert record["rejected"]["title"] == "not found in the header pages", record["rejected"]
    assert record["authors"] == ["Suresh Marahatta"], record["authors"]
    assert record["year"] is None and "not found" in record["rejected"]["year"], record
    assert record["venue"] is None, record["venue"]
    assert record["doi"] is None and \
        record["rejected"]["doi"] == "not found in the header pages", record


def test_validate_rejects_junk_and_bad_years() -> None:
    junk = bib.validate({"title": "Final Added Vol 15-2.pmd", "authors": ["user@MAHESH"],
                         "year": 2999, "venue": "", "doi": "not-a-doi"}, PAGE)
    assert junk["title"] is None and junk["authors"] == [], junk
    assert junk["year"] is None and junk["doi"] is None, junk
    assert bib.clean_year("(2009)") == 2009
    assert bib.clean_year(1500) is None


def test_authors_and_reference_format() -> None:
    assert bib.format_authors(["S. Marahatta", "J. K. Bhusal"]) == "Marahatta & Bhusal"
    assert bib.format_authors(["A One", "B Two", "C Three"]) == "One, Two, Three"
    assert bib.format_authors(["A One", "B Two", "C Three", "D Four"]) == "One et al."
    full = {"authors": ["Suresh Marahatta"], "year": 2009,
            "title": "Relating Hydrological Extremes with Area", "venue": "JHM"}
    assert bib.reference_line(full) == ("Marahatta (2009). Relating Hydrological Extremes "
                                        "with Area. JHM"), bib.reference_line(full)
    assert bib.reference_line({"title": "Only a Title"}) == "Only a Title"
    assert bib.reference_line({"year": 1993}) == "(1993)"
    assert bib.reference_line({}) == ""


def test_deterministic_fallback_fills_doi_and_year() -> None:
    record = bib.extract(PAGE, allow_model=False)
    assert record["year"] == 2009, record["year"]
    assert record["doi"] == "10.3126/jhm.v6i1.10101", record["doi"]
    assert record["title"] is None, "no model, so no title should be guessed"


def test_build_writes_and_resumes() -> None:
    with tempfile.TemporaryDirectory() as folder:
        index = pathlib.Path(folder)
        pages = {"pages": [{"doc": "a.pdf", "page": 1, "text": PAGE},
                           {"doc": "a.pdf", "page": 2, "text": "nothing here"},
                           {"doc": "b.pdf", "page": 1, "text": "Untitled scan, no header"}]}
        (index / "pages.json").write_text(json.dumps(pages), encoding="utf-8")
        db = sqlite3.connect(index / "manifest.sqlite")
        db.execute("CREATE TABLE documents (name TEXT, sha256 TEXT)")
        db.executemany("INSERT INTO documents VALUES (?, ?)",
                       [("a.pdf", "a" * 64), ("b.pdf", "b" * 64)])
        db.commit()
        db.close()

        first = bib.build(index, allow_model=False, log=lambda line: None)
        assert first["counts"]["documents"] == 2, first["counts"]
        assert first["counts"]["year"] == 1, first["counts"]
        line = bib.reference_line(first["documents"]["a.pdf"])
        assert line == "(2009). doi:10.3126/jhm.v6i1.10101", line

        second = bib.build(index, allow_model=False, log=lambda line: None)
        assert second["seconds"] < 2 and second["counts"]["documents"] == 2, second
        assert not (index / bib.LOCK_FILE).exists(), "the lock is released"


def test_a_second_build_is_refused_while_the_lock_is_held() -> None:
    """Two writers would drop each other's records, so the second one must not start."""
    with tempfile.TemporaryDirectory() as folder:
        index = pathlib.Path(folder)
        (index / bib.LOCK_FILE).write_text("1234\n", encoding="utf-8")
        result = bib.build(index, allow_model=False, log=lambda line: None)
        assert result.get("skipped") is True, result
        assert (index / bib.LOCK_FILE).exists(), "a held lock is left alone"


def main() -> int:
    tests = [("validate keeps printed fields", test_validate_keeps_printed_fields),
             ("validate drops invented values", test_validate_drops_invented_values),
             ("validate rejects junk and bad years", test_validate_rejects_junk_and_bad_years),
             ("author and reference formatting", test_authors_and_reference_format),
             ("deterministic fallback", test_deterministic_fallback_fills_doi_and_year),
             ("build writes and resumes", test_build_writes_and_resumes),
             ("a second build is refused", test_a_second_build_is_refused_while_the_lock_is_held)]
    for name, fn in tests:
        check(name, fn)
    print(f"\n{'all cases pass' if not FAILURES else 'FAILURES: ' + ', '.join(FAILURES)}"
          f" ({len(tests)} total)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
