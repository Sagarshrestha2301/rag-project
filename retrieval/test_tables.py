"""Prove the table pass: it adds the page a table chunk lives on, and changes nothing else.

Cases: the flag off is a no-op, a table hit adds its page, a page already in the list is
not duplicated, the list stays at `k`, a page with no indexed text is skipped, and a
missing chunk file leaves the hits alone.

Usage:
    .venv\\Scripts\\python.exe retrieval\\test_tables.py
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from retrieval import tables  # noqa: E402

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


def page(doc: str, number: int, text: str) -> dict:
    return {"doc": doc, "page": number, "label": doc.split("_")[0], "text": text,
            "source": "text"}


INDEX = {"pages": [
    page("1970_Das_Beliefs.pdf", 6,
         "Level of belief in Superstitions and Taboos in the Terai, the Midhills and "
         "Kerabari. 102 households do not believe. table of counts."),
    page("1970_Das_Beliefs.pdf", 9,
         "Superstitions and taboos that discourage bamboo planting, by growing status."),
    page("1970_Marahatta.pdf", 2, "The 24-hour rainfall depth of 540 mm at Tistung."),
]}

TABLE_TEXT = ("Table 2 Level of beliefs in superstitions and taboos against bamboo "
              "planting in the Terai, the Midhills and Kerabari | Level | Midhills "
              "Do not believe 102 49.04 |")


def chunk(file: str, page_start: int, text: str) -> dict:
    return {"chunk_id": f"{file}:p{page_start}", "file": file, "page_start": page_start,
            "page_end": page_start, "type": "table", "text": text}


def write_chunks(rows: list[dict]) -> pathlib.Path:
    handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                         encoding="utf-8")
    with handle as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return pathlib.Path(handle.name)


QUESTION = "In Table 2, how many Midhills households do not believe in the superstitions?"
HITS = [{"doc": "1970_Marahatta.pdf", "page": 2, "label": "Marahatta", "score": 12.0,
         "ocr": False, "context": "rainfall", "snippet": "rainfall"}]


def with_flag(value: str | None, name: str = tables.FLAG):
    """Set one flag for a case, restoring the environment afterwards."""
    class Flag:
        def __enter__(self):
            self.old = os.environ.get(name)
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
            return self

        def __exit__(self, *exc):
            if self.old is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = self.old
    return Flag()


def flag_off_is_a_no_op() -> None:
    path = write_chunks([chunk("1970_Das_Beliefs.pdf", 6, TABLE_TEXT)])
    with with_flag(None):
        assert not tables.enabled()
        assert tables.merge(INDEX, QUESTION, HITS, k=5, path=path) == HITS


def table_page_is_added() -> None:
    path = write_chunks([chunk("1970_Das_Beliefs.pdf", 6, TABLE_TEXT)])
    with with_flag("1"):
        merged = tables.merge(INDEX, QUESTION, HITS, k=5, path=path)
    assert len(merged) == 2, len(merged)
    added = merged[-1]
    assert (added["doc"], added["page"]) == ("1970_Das_Beliefs.pdf", 6), added
    assert added["via"] == "table" and added["score"] > 0, added
    assert "table of counts" in added["context"] or "Midhills" in added["context"], added


def an_existing_page_is_not_duplicated() -> None:
    path = write_chunks([chunk("1970_Marahatta.pdf", 2, "24-hour rainfall 540 mm Tistung")])
    with with_flag("1"):
        merged = tables.merge(INDEX, "24-hour rainfall at Tistung", HITS, k=5, path=path)
    assert merged == HITS, merged


def the_list_stays_at_k() -> None:
    path = write_chunks([chunk("1970_Das_Beliefs.pdf", 6, TABLE_TEXT),
                         chunk("1970_Das_Beliefs.pdf", 9, TABLE_TEXT.replace("Table 2", "Table 3"))])
    hits = HITS * 1 + [{"doc": "1970_Das_Beliefs.pdf", "page": 9, "label": "Das",
                        "score": 9.0, "ocr": False, "context": "c", "snippet": "s"},
                       {"doc": "x.pdf", "page": 1, "label": "X", "score": 8.0, "ocr": False,
                        "context": "c", "snippet": "s"}]
    with with_flag("1"):
        merged = tables.merge(INDEX, QUESTION, hits, k=3, path=path)
    assert len(merged) <= 3, len(merged)
    assert merged[0] is hits[0], merged[0]


def a_page_without_text_is_skipped() -> None:
    index = {"pages": [page("1970_Das_Beliefs.pdf", 6, "")]}
    path = write_chunks([chunk("1970_Das_Beliefs.pdf", 6, TABLE_TEXT)])
    with with_flag("1"):
        merged = tables.merge(index, QUESTION, HITS, k=5, path=path)
    assert merged == HITS, merged


def a_missing_chunk_file_changes_nothing() -> None:
    with with_flag("1"):
        merged = tables.merge(INDEX, QUESTION, HITS, k=5,
                              path=pathlib.Path("does-not-exist.jsonl"))
    assert merged == HITS, merged


ROWS = {("1970_Das_Beliefs.pdf", 6): TABLE_TEXT}
CONTENT_HITS = [{"doc": "1970_Das_Beliefs.pdf", "page": 6, "label": "Das",
                 "score": 50.0, "ocr": False, "context": "prose about taboos",
                 "snippet": "taboos"},
                {"doc": "1970_Marahatta.pdf", "page": 2, "label": "Marahatta",
                 "score": 9.0, "ocr": False, "context": "rainfall prose",
                 "snippet": "rainfall"}]


def content_flag_off_is_a_no_op() -> None:
    with with_flag(None, tables.CONTENT_FLAG):
        assert not tables.rows_enabled()
        assert tables.with_rows(CONTENT_HITS, rows=ROWS) == CONTENT_HITS


def a_page_gains_its_rows() -> None:
    with with_flag("1", tables.CONTENT_FLAG):
        got = tables.with_rows(CONTENT_HITS, rows=ROWS)
    assert "prose about taboos" in got[0]["context"], "the prose must stay"
    assert TABLE_TEXT in got[0]["context"], "the page's own rows must be added"
    assert "TABLE ROWS FROM THIS PAGE" in got[0]["context"]


def a_page_without_a_table_is_unchanged() -> None:
    with with_flag("1", tables.CONTENT_FLAG):
        got = tables.with_rows(CONTENT_HITS, rows=ROWS)
    assert got[1] == CONTENT_HITS[1], "a page with no table must not change"


def the_rows_are_capped() -> None:
    long_rows = {("1970_Das_Beliefs.pdf", 6): "row " * 500}
    with with_flag("1", tables.CONTENT_FLAG):
        got = tables.with_rows(CONTENT_HITS, rows=long_rows, limit=100)
    added = got[0]["context"].split("TABLE ROWS FROM THIS PAGE")[1]
    assert len(added) < 260, f"the rows were not capped: {len(added)} characters"


def the_hit_is_not_mutated() -> None:
    with with_flag("1", tables.CONTENT_FLAG):
        tables.with_rows(CONTENT_HITS, rows=ROWS)
    assert CONTENT_HITS[0]["context"] == "prose about taboos", "the caller's hit was changed"


def main() -> int:
    print("table retrieval")
    for name, fn in [
        ("flag off leaves the hits alone", flag_off_is_a_no_op),
        ("a matching table chunk adds its page", table_page_is_added),
        ("a page already in the list is not duplicated", an_existing_page_is_not_duplicated),
        ("the merged list stays at k", the_list_stays_at_k),
        ("a page with no indexed text is skipped", a_page_without_text_is_skipped),
        ("a missing chunk file changes nothing", a_missing_chunk_file_changes_nothing),
        ("the content flag off leaves the passages alone", content_flag_off_is_a_no_op),
        ("a page with a table gains its rows", a_page_gains_its_rows),
        ("a page without a table is unchanged", a_page_without_a_table_is_unchanged),
        ("the rows are capped", the_rows_are_capped),
        ("the hit is copied, not mutated", the_hit_is_not_mutated),
    ]:
        check(name, fn)
    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} of {TOTAL} case(s): {FAILURES}")
        return 1
    print(f"all {TOTAL} cases pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
