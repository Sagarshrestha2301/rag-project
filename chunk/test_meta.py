"""Prove metadata comes from the path and doc contexts are cached, not re-asked.

Every case uses a real corpus name: the folder decides the document type, the
organisation folder is the only publisher the path states, and a name that
starts with `0_` or `nd_` has no year rather than a guessed one.

Usage:
    .venv\\Scripts\\python.exe chunk\\test_meta.py
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from chunk import doc_context, meta                  # noqa: E402
from ingest.base import corpus_files                 # noqa: E402

FAILURES: list[str] = []


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as exc:
        FAILURES.append(name)
        print(f"  FAIL  {name}: {exc}")


# --- year, publisher, doc type -------------------------------------------

def bare_name_has_year_but_no_publisher():
    got = meta.to_meta("1970_Das_Beliefs_superstitions_and_taboos_W1999918290.pdf")
    assert got.year == 1970, got
    assert got.publisher == "" and got.doc_type == "", got
    assert got.file.startswith("1970_Das_"), got


def papers_folder_is_a_journal_article_not_a_publisher():
    got = meta.to_meta("papers/01_Floods_GLOFs/2001_Li_Water_Induced_Disasters_W3204701976.pdf")
    assert got.year == 2001 and got.doc_type == "journal-article", got
    assert got.publisher == "", "a topic folder must not become a publisher"


def reports_folder_names_the_publisher():
    got = meta.to_meta("data/corpus/reports/USGS/1991_Preliminary_report_18253.pdf")
    assert (got.year, got.publisher, got.doc_type) == (1991, "USGS", "report"), got


def undated_report_has_no_year():
    got = meta.to_meta("reports/DHM/nd_1001402765Payment_procedure_dhm1.pdf")
    assert got.year is None and got.publisher == "DHM", got


def zero_prefixed_name_has_no_year():
    got = meta.to_meta("0_NARAYAN_Investigation_of_Soil_Liquefaction_R7208248247.pdf")
    assert got.year is None and got.doc_type == "", got


def year_must_be_at_the_start():
    got = meta.to_meta("reports/DoFSC/2023_annual_plan_2080_2090_0ec3a3f7d9.pdf")
    assert got.year == 2023, f"a later 2080 must not win: {got}"


def windows_separators_give_the_same_answer():
    assert meta.to_meta("papers\\07_Forest_Fire\\2015_Khanal_Wildfire_W1698680011.pdf") == \
        meta.to_meta("papers/07_Forest_Fire/2015_Khanal_Wildfire_W1698680011.pdf")


def unknown_folder_has_no_doc_type():
    got = meta.to_meta("misc/Other/x.pdf")
    assert got.doc_type == "" and got.publisher == "", got


# --- the real corpus -----------------------------------------------------

def every_corpus_document_gets_honest_metadata():
    paths = corpus_files()
    assert len(paths) >= 90, f"expected the grown corpus, found {len(paths)} PDFs"
    for path in paths:
        got = meta.to_meta(path)
        assert got.file == path.name, (got.file, path.name)
        assert got.year is None or 1900 <= got.year <= 2100, (path.name, got.year)
        if "reports" in path.parts:
            assert got.publisher and got.doc_type == "report", (path.name, got)


# --- document context cache ---------------------------------------------

def contexts_are_written_once_and_reused():
    parsed = pathlib.Path(tempfile.mkdtemp()) / "pages.jsonl"
    parsed.write_text(
        json.dumps({"doc": "a.pdf", "pdf_page": 1, "text": "Opening text about floods."}) + "\n",
        encoding="utf-8")
    calls: list[str] = []
    cache = parsed.parent / "contexts.json"

    def first_ask(opening: str, model: str, port: int) -> str:
        calls.append(opening)
        return "Line one about floods.\nLine two about Nepal."

    got = doc_context.build("test-model", ask=first_ask, parsed=parsed, cache=cache)
    assert calls == ["Opening text about floods.\n"], calls
    assert got["a.pdf"]["context"] == "Line one about floods. Line two about Nepal."
    assert got["a.pdf"]["model"] == "test-model" and got["a.pdf"]["prompt"]

    def never_ask(opening: str, model: str, port: int) -> str:
        raise AssertionError("cache miss: the model was asked twice")

    again = doc_context.build("test-model", ask=never_ask, parsed=parsed, cache=cache)
    assert again["a.pdf"]["context"] == got["a.pdf"]["context"]


def a_different_model_regenerates():
    parsed = pathlib.Path(tempfile.mkdtemp()) / "pages.jsonl"
    parsed.write_text(
        json.dumps({"doc": "a.pdf", "pdf_page": 1, "text": "Flood text."}) + "\n",
        encoding="utf-8")
    cache = parsed.parent / "contexts.json"
    doc_context.build("model-a", ask=lambda o, m, p: "A", parsed=parsed, cache=cache)
    got = doc_context.build("model-b", ask=lambda o, m, p: "B", parsed=parsed, cache=cache)
    assert got["a.pdf"]["context"] == "B" and got["a.pdf"]["model"] == "model-b", got


def page_evidence_gives_a_year():
    assert meta.year_from_text("BANKO JANAKARI Vol. 8, No. 1, 2019 page 3") == 2019
    assert meta.year_from_text("(c) 2005 ICIMOD, Kathmandu") == 2005
    assert meta.year_from_text("M. N. Ahasan December 2010 1 Variability and trends") == 2010


def page_evidence_refuses_a_citation():
    # The same words sit in the references on page 1 of two real papers.
    text = "Variability and trends " + "filler " * 80 + \
        "Journal of Hydrology and Meteorology, Vol. 7, No. 1, 2010"
    assert meta.year_from_text(text) is None, "took a citation year as the publication year"
    assert meta.publisher_from_text(text) == "", "took a cited journal as the publisher"


def page_evidence_gives_a_publisher():
    assert meta.publisher_from_text(
        "Nepal Journal of Science and Technology Vol. 12, 2011, 45-52") == \
        "Nepal Journal of Science and Technology"
    assert meta.publisher_from_text(
        "Journal of Hydrology and Meteorology, Vol. 6, No. 1 SOHAM-Nepal") == \
        "Journal of Hydrology and Meteorology"


def a_masthead_without_an_outlet_word_stays_empty():
    # Real page-1 head of 1970_Das: title and author, no journal name anywhere.
    assert meta.publisher_from_text(
        "Beliefs, superstitions and taboos associated with bamboos in Nepal A.N. Das") == ""


def main() -> int:
    print("metadata from the path")
    for name, fn in [
        ("a bare name has a year but no publisher", bare_name_has_year_but_no_publisher),
        ("papers/ is a journal article, not a publisher",
         papers_folder_is_a_journal_article_not_a_publisher),
        ("reports/ names the publisher", reports_folder_names_the_publisher),
        ("an undated report has no year", undated_report_has_no_year),
        ("0_ has no year", zero_prefixed_name_has_no_year),
        ("the year must be at the start", year_must_be_at_the_start),
        ("windows and posix separators agree", windows_separators_give_the_same_answer),
        ("an unknown folder has no doc type", unknown_folder_has_no_doc_type),
    ]:
        check(name, fn)

    print("metadata from the page (only when the path is silent)")
    for name, fn in [("a volume, copyright or masthead date gives the year",
                      page_evidence_gives_a_year),
                     ("a citation on page 1 gives nothing", page_evidence_refuses_a_citation),
                     ("a printed journal name is used", page_evidence_gives_a_publisher),
                     ("a masthead with no outlet word stays empty",
                      a_masthead_without_an_outlet_word_stays_empty)]:
        check(name, fn)

    print("the real corpus")
    check("every document gets honest metadata", every_corpus_document_gets_honest_metadata)

    print("document context cache")
    check("contexts are written once and reused", contexts_are_written_once_and_reused)
    check("a different model regenerates", a_different_model_regenerates)

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} case(s): {FAILURES}")
        return 1
    print("all cases pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
