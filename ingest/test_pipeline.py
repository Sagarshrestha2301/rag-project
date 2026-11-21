"""Prove the Step 8 ingestion pipeline resumes, skips duplicates and can be restored.

Every case runs on a throwaway corpus of small synthetic PDFs under the system temp
folder, so the real `data/corpus`, `index/` and manifest are never touched. The one
case that touches a real code path end to end is the first: the pipeline's assembly
must produce the same `pages.json` a full `corpus.build` produces for the same files,
because that file is what every later step searches.

Usage:
    .venv\\Scripts\\python.exe ingest\\test_pipeline.py
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import corpus                                # noqa: E402
import pymupdf                               # noqa: E402
from ingest import pipeline                  # noqa: E402

FAILURES: list[str] = []


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as exc:
        FAILURES.append(name)
        print(f"  FAIL  {name}: {exc}")


def make_pdf(path: pathlib.Path, pages: list[str], title: str = "") -> pathlib.Path:
    """A small real PDF, one paragraph per page, long enough to skip OCR."""
    path.parent.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open()
    for text in pages:
        page = document.new_page()
        page.insert_text((72, 100), text, fontsize=11)
    document.set_metadata({"title": title or path.stem})
    document.save(path)
    document.close()
    return path


def workspace() -> tuple[pathlib.Path, pathlib.Path]:
    """(corpus root, index dir) in a fresh temp folder."""
    root = pathlib.Path(tempfile.mkdtemp(prefix="step8-test-"))
    return root / "corpus", root / "index"


def run(corpus_root: pathlib.Path, index_dir: pathlib.Path,
        stages: str = "scan,parse,assemble,chunk", limit: int | None = None) -> dict:
    return pipeline.build(corpus_root, index_dir,
                          tuple(part for part in stages.split(",") if part), limit)


PAGES_A = [
    "The 24 hour rainfall depth at Tistung was 540 millimetres on 20 July 1993, "
    "recorded by the gauging station in the morning hours of that day.",
    "Peak discharge in the Bagmati River reached 12000 cubic metres per second, "
    "estimated by the slope area method with a roughness coefficient of 0.06.",
]
PAGES_B = [
    "Bamboo flowering cycles in the Terai were recorded for fifty species, and the "
    "household survey covered two hundred and eight households across five villages.",
    "Beliefs and taboos about bamboo were reported by 199 households, which is a "
    "share of the surveyed population that the authors discuss at some length.",
]


def pages_for(tag: str) -> list[str]:
    """Two distinct pages, so unrelated documents do not look like duplicates."""
    return [
        f"Document {tag} reports a rainfall depth of {len(tag) + 300} millimetres at "
        f"station {tag}, measured during the monsoon season in the study year.",
        f"The discussion in document {tag} compares household counts of {len(tag) * 37} "
        f"against the regional survey, and explains the difference at some length.",
    ]


# --- the artifact every later step reads ------------------------------------

def pages_json_matches_a_full_build():
    root, index = workspace()
    make_pdf(root / "1970_A_test.pdf", PAGES_A)
    make_pdf(root / "1970_B_test.pdf", PAGES_B)
    run(root, index)

    assembled = json.loads((index / "pages.json").read_text(encoding="utf-8"))
    rebuilt = corpus.build(force=True, root=root, cache=index / "pages-check.json")
    assert assembled == rebuilt, "the pipeline's pages.json differs from corpus.build"
    assert len(assembled["pages"]) == 4, len(assembled["pages"])


def chunk_export_is_written_and_citable():
    root, index = workspace()
    make_pdf(root / "1970_A_test.pdf", PAGES_A)
    make_pdf(root / "1970_B_test.pdf", PAGES_B)
    result = run(root, index)
    assert result["stages"]["chunk"]["chunks"] >= 2, result["stages"]["chunk"]
    chunks = [json.loads(line) for line in
              (index / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if line]
    assert {chunk["file"] for chunk in chunks} == {"1970_A_test.pdf", "1970_B_test.pdf"}
    assert all(chunk["text"].strip() for chunk in chunks)


# --- resume -----------------------------------------------------------------

def second_run_parses_nothing():
    root, index = workspace()
    make_pdf(root / "1970_A_test.pdf", PAGES_A)
    make_pdf(root / "1970_B_test.pdf", PAGES_B)
    first = run(root, index)
    second = run(root, index)
    assert first["stages"]["parse"]["parsed"] == 2, first["stages"]["parse"]
    assert second["stages"]["parse"]["parsed"] == 0, second["stages"]["parse"]
    assert second["counts"]["embedded"] == 0


def a_killed_run_resumes_where_it_stopped():
    root, index = workspace()
    for letter in "ABC":
        make_pdf(root / f"1970_{letter}_test.pdf", pages_for(letter))
    # Only scan+parse, so the unfinished run looks like a kill before chunking.
    run(root, index, stages="scan,parse", limit=2)
    interim = pipeline.status(index)
    assert interim["counts"]["parsed"] == 2, interim["counts"]
    assert interim["counts"]["pending"] == 1, interim["counts"]

    resumed = run(root, index)
    assert resumed["stages"]["parse"]["parsed"] == 1, resumed["stages"]["parse"]
    counts = pipeline.status(index)["counts"]
    assert counts["pending"] == 0, counts
    assert counts["parsed"] + counts["chunked"] + counts["embedded"] == 3, counts


def a_changed_file_is_parsed_again():
    root, index = workspace()
    path = make_pdf(root / "1970_A_test.pdf", PAGES_A)
    run(root, index)
    old_hash = json.loads((index / "pages.json").read_text(encoding="utf-8"))["pages"][0]["text"]

    make_pdf(path, PAGES_B)                        # same name, new bytes
    again = run(root, index)
    assert again["stages"]["parse"]["parsed"] == 1, again["stages"]["parse"]
    row = pipeline.Manifest(index).row("1970_A_test.pdf")
    new_hash = again["stages"]["scan"]["counts"]["pending"]
    assert row["status"] in ("parsed", "chunked"), row["status"]
    assert new_hash in (0, 1), new_hash
    text = json.loads((index / "pages.json").read_text(encoding="utf-8"))["pages"][0]["text"]
    assert text != old_hash, "the replaced document kept its old text"


# --- duplicates -------------------------------------------------------------

def same_bytes_under_another_name_is_a_duplicate():
    root, index = workspace()
    make_pdf(root / "1970_A_test.pdf", PAGES_A)
    run(root, index)
    # A copy arrives after the original is indexed: the original must stay the one
    # questions cite, and the copy is flagged rather than silently dropped.
    shutil.copy2(root / "1970_A_test.pdf", root / "1970_A_copy.pdf")
    result = run(root, index)
    status = pipeline.status(index)
    assert result["stages"]["parse"]["parsed"] == 0, result["stages"]["parse"]
    assert status["counts"]["duplicate"] == 1, status["counts"]
    duplicate = status["duplicates"][0]
    assert duplicate["name"] == "1970_A_copy.pdf", duplicate
    assert duplicate["of"] == "1970_A_test.pdf", duplicate
    docs = json.loads((index / "pages.json").read_text(encoding="utf-8"))["docs"]
    assert [doc["doc"] for doc in docs] == ["1970_A_test.pdf"], docs


def same_text_in_new_bytes_is_a_near_duplicate():
    root, index = workspace()
    make_pdf(root / "1970_A_test.pdf", PAGES_A, title="first printing")
    # Same words, different bytes: a re-download or a re-saved copy, not a new paper.
    make_pdf(root / "1970_A_resaved.pdf", PAGES_A, title="second printing")
    run(root, index)
    status = pipeline.status(index)
    assert status["counts"]["duplicate"] == 1, status["counts"]
    pair = {status["duplicates"][0]["name"], status["duplicates"][0]["of"]}
    assert pair == {"1970_A_test.pdf", "1970_A_resaved.pdf"}, status["duplicates"]
    docs = json.loads((index / "pages.json").read_text(encoding="utf-8"))["docs"]
    assert len(docs) == 1, docs


# --- incremental add --------------------------------------------------------

def adding_documents_processes_only_the_new_ones():
    root, index = workspace()
    make_pdf(root / "1970_A_test.pdf", PAGES_A)
    make_pdf(root / "1970_B_test.pdf", PAGES_B)
    run(root, index)

    for letter in "CDE":
        make_pdf(root / f"1970_{letter}_test.pdf", pages_for(letter))
    added = run(root, index)
    assert added["stages"]["parse"]["parsed"] == 3, added["stages"]["parse"]
    assert added["stages"]["scan"]["counts"]["pending"] in (3, 4), added["stages"]["scan"]
    docs = json.loads((index / "pages.json").read_text(encoding="utf-8"))["docs"]
    assert len(docs) == 5, [doc["doc"] for doc in docs]


# --- manifest ---------------------------------------------------------------

def the_manifest_is_complete():
    root, index = workspace()
    make_pdf(root / "1970_A_test.pdf", PAGES_A)
    (root / "broken.pdf").write_bytes(b"%PDF-1.4 truncated")
    run(root, index)

    summary = pipeline.status(index)
    assert summary["documents"] == 2, summary["documents"]
    assert summary["without_sha256"] == [], summary["without_sha256"]
    assert summary["failures"], "a truncated PDF must be recorded as failed"
    assert summary["failures"][0]["error"], summary["failures"]

    rows = pipeline.Manifest(index).rows()
    for row in rows:
        assert pipeline._is_sha256(row["sha256"]), row["name"]
        assert row["status"] in pipeline.STATUSES, (row["name"], row["status"])
        assert row["embedding_model"] == pipeline.EMBEDDING_MODEL, row["name"]


def unreadable_pages_are_stored_per_file():
    root, index = workspace()
    make_pdf(root / "1970_A_test.pdf", PAGES_A + [""])   # page 3 has no text at all
    run(root, index)
    summary = pipeline.status(index)
    assert summary["unreadable"].get("1970_A_test.pdf") == [3], summary["unreadable"]


# --- backup -----------------------------------------------------------------

def backup_and_restore_round_trip():
    root, index = workspace()
    make_pdf(root / "1970_A_test.pdf", PAGES_A)
    make_pdf(root / "1970_B_test.pdf", PAGES_B)
    run(root, index)
    before = pipeline.status(index)

    saved = pipeline.backup(index, root / "backup")
    for expected in ("manifest.sqlite", "pages.json", "chunks.jsonl"):
        assert (root / "backup" / expected).exists(), expected

    shutil.rmtree(index)
    restored = pipeline.restore(root / "backup", index)
    assert restored["counts"] == before["counts"], (restored["counts"], before["counts"])
    assert json.loads((index / "pages.json").read_text(encoding="utf-8"))["docs"], \
        "pages.json did not come back"
    # Everything the backup holds must land in the restored index, dense vectors included.
    for path in (root / "backup").rglob("*"):
        if path.is_file():
            assert (index / path.relative_to(root / "backup")).is_file(), path


def bibliography_stage_survives_a_missing_model() -> None:
    """D-066: the stage is best-effort - a dead model must not fail an ingestion run."""
    root, index = workspace()
    make_pdf(root / "a.pdf", PAGES_A)
    original = pipeline.bibliography.ask_model

    def down(*args, **kwargs):
        raise RuntimeError("no model")

    pipeline.bibliography.ask_model = down
    try:
        report = run(root, index, "scan,parse,assemble,bibliography")
    finally:
        pipeline.bibliography.ask_model = original
    assert report["stages"]["bibliography"]["documents"] == 1, report["stages"]
    artifact = json.loads((index / "bibliography.json").read_text(encoding="utf-8"))
    record = artifact["documents"]["a.pdf"]
    assert record["title"] is None and "no model" in record["error"], record


# --- batch ingestion ---------------------------------------------------------

def batch_workspace() -> tuple[pathlib.Path, pathlib.Path, pathlib.Path, pathlib.Path]:
    """(corpus root, index dir, staged raw root, wave log) in a fresh temp folder."""
    corpus_root, index_dir = workspace()
    raw = corpus_root.parent / "raw"
    raw.mkdir(parents=True)
    return corpus_root, index_dir, raw, corpus_root.parent / "logs" / "wave.jsonl"


def add_batch(corpus_root: pathlib.Path, index_dir: pathlib.Path, raw: pathlib.Path,
              log: pathlib.Path, source: pathlib.Path | None = None,
              wave: str = "00") -> dict:
    return pipeline.add_batch(source or raw / "incoming", wave, corpus_root=corpus_root,
                              index_dir=index_dir,
                              stages=("scan", "parse", "assemble", "chunk"),
                              raw_root=raw, log_path=log)


def a_batch_links_and_indexes_every_file():
    corpus_root, index_dir, raw, log = batch_workspace()
    make_pdf(raw / "incoming" / "alpha.pdf", pages_for("alpha"))
    make_pdf(raw / "incoming" / "nested" / "beta.pdf", pages_for("beta"))
    result = add_batch(corpus_root, index_dir, raw, log)
    assert result["added"] == 2 and not result["refused"], result
    assert (corpus_root / "incoming" / "alpha.pdf").is_file()
    assert (corpus_root / "incoming" / "nested" / "beta.pdf").is_file(), \
        "the batch lost its folder relative to data/raw"
    assert result["build"]["counts"]["chunked"] == 2, result["build"]["counts"]
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2, "one log row per file"
    manifest = pipeline.Manifest(index_dir)
    try:
        assert json.loads(manifest.get_meta("wave-00"))["documents"] == 2
    finally:
        manifest.close()


def a_repeated_name_inside_the_batch_refuses_everything():
    corpus_root, index_dir, raw, log = batch_workspace()
    make_pdf(raw / "incoming" / "a" / "same.pdf", pages_for("alpha"))
    make_pdf(raw / "incoming" / "b" / "same.pdf", pages_for("beta"))
    result = add_batch(corpus_root, index_dir, raw, log)
    assert result["added"] == 0 and result["refused"], result
    assert not (corpus_root / "incoming").exists(), "a refused batch placed files"


def a_name_the_corpus_already_has_is_refused():
    corpus_root, index_dir, raw, log = batch_workspace()
    existing = make_pdf(corpus_root / "existing.pdf", pages_for("keep"))
    before = existing.read_bytes()
    make_pdf(raw / "incoming" / "existing.pdf", pages_for("other"))
    result = add_batch(corpus_root, index_dir, raw, log)
    assert result["added"] == 0 and any("different file" in line for line in result["refused"]), \
        result
    assert existing.read_bytes() == before, "a refused batch overwrote a corpus file"


def the_same_bytes_under_another_name_is_skipped():
    """Owner request 2026-11-21: a duplicate is reported, not a reason to lose the batch."""
    corpus_root, index_dir, raw, log = batch_workspace()
    make_pdf(raw / "incoming" / "alpha.pdf", pages_for("alpha"))
    assert add_batch(corpus_root, index_dir, raw, log)["added"] == 1
    shutil.copyfile(corpus_root / "incoming" / "alpha.pdf", raw / "incoming" / "copy.pdf")
    make_pdf(raw / "incoming" / "beta.pdf", pages_for("beta"))
    result = add_batch(corpus_root, index_dir, raw, log)
    assert result["added"] == 1, result
    assert [item["name"] for item in result["skipped"]] == ["copy.pdf"], result
    assert "same bytes" in result["skipped"][0]["reason"], result
    assert not result["refused"], result
    assert (corpus_root / "incoming" / "beta.pdf").is_file(), "the new file was not placed"
    assert not (corpus_root / "incoming" / "copy.pdf").exists(), "the duplicate was placed"


def rerunning_a_landed_batch_changes_nothing():
    corpus_root, index_dir, raw, log = batch_workspace()
    make_pdf(raw / "incoming" / "alpha.pdf", pages_for("alpha"))
    make_pdf(raw / "incoming" / "beta.pdf", pages_for("beta"))
    add_batch(corpus_root, index_dir, raw, log)
    again = add_batch(corpus_root, index_dir, raw, log)
    assert again["added"] == 0 and again["unchanged"] == 2 and not again["refused"], again
    assert (corpus_root / "incoming" / "alpha.pdf").is_file()


def a_batch_outside_raw_or_with_word_files_is_refused():
    corpus_root, index_dir, raw, log = batch_workspace()
    elsewhere = corpus_root.parent / "staging"
    make_pdf(elsewhere / "alpha.pdf", pages_for("alpha"))
    outside = add_batch(corpus_root, index_dir, raw, log, source=elsewhere)
    assert outside["added"] == 0 and any("data/raw" in line for line in outside["refused"]), \
        outside

    make_pdf(raw / "incoming" / "alpha.pdf", pages_for("alpha"))
    (raw / "incoming" / "report.docx").write_text("not a pdf", encoding="utf-8")
    word = add_batch(corpus_root, index_dir, raw, log)
    assert word["added"] == 0 and any("docx.pdf" in line for line in word["refused"]), word
    assert not (corpus_root / "incoming" / "alpha.pdf").exists(), "the valid file was placed"


def a_batch_is_copied_when_the_hardlink_fails():
    corpus_root, index_dir, raw, log = batch_workspace()
    source = make_pdf(raw / "incoming" / "alpha.pdf", pages_for("alpha"))
    original = os.link

    def refuse(*args, **kwargs):
        raise OSError("links disabled in this test")

    os.link = refuse
    try:
        result = add_batch(corpus_root, index_dir, raw, log)
    finally:
        os.link = original
    assert result["modes"]["copied"] == 1, result
    target = corpus_root / "incoming" / "alpha.pdf"
    assert target.is_file() and target.read_bytes() == source.read_bytes()


CASES = [
    ("a batch links and indexes every file", a_batch_links_and_indexes_every_file),
    ("a repeated name inside the batch refuses everything",
     a_repeated_name_inside_the_batch_refuses_everything),
    ("a name the corpus already has is refused", a_name_the_corpus_already_has_is_refused),
    ("the same bytes under another name is skipped", the_same_bytes_under_another_name_is_skipped),
    ("rerunning a landed batch changes nothing", rerunning_a_landed_batch_changes_nothing),
    ("a batch outside raw or with Word files is refused",
     a_batch_outside_raw_or_with_word_files_is_refused),
    ("a batch is copied when the hardlink fails", a_batch_is_copied_when_the_hardlink_fails),
    ("pages.json matches a full corpus.build", pages_json_matches_a_full_build),
    ("the bibliography stage survives a dead model", bibliography_stage_survives_a_missing_model),
    ("chunk export is written and citable", chunk_export_is_written_and_citable),
    ("a second run parses nothing", second_run_parses_nothing),
    ("a killed run resumes where it stopped", a_killed_run_resumes_where_it_stopped),
    ("a changed file is parsed again", a_changed_file_is_parsed_again),
    ("same bytes under another name is a duplicate", same_bytes_under_another_name_is_a_duplicate),
    ("same text in new bytes is a near duplicate", same_text_in_new_bytes_is_a_near_duplicate),
    ("adding documents processes only the new ones", adding_documents_processes_only_the_new_ones),
    ("the manifest is complete", the_manifest_is_complete),
    ("unreadable pages are stored per file", unreadable_pages_are_stored_per_file),
    ("backup and restore round trip", backup_and_restore_round_trip),
]


def main() -> int:
    print(f"{len(CASES)} cases")
    for name, fn in CASES:
        check(name, fn)
    passed = len(CASES) - len(FAILURES)
    print(f"\n{passed}/{len(CASES)} pass" + ("" if not FAILURES else f"; failed: {FAILURES}"))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
