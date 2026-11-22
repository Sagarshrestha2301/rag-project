"""Move the mostly non-Latin documents out of `data/corpus` (reversible).

The pipeline is English-only, so a Devanagari document is indexed and can never be
retrieved from an English question. This takes such documents out of the corpus, keeping
the file itself under `data/quarantine/non-english/<same relative path>`, and records one
JSON line per file so the change can be undone by moving them back.

Nothing is deleted: `data/corpus` entries are hardlinks into `data/raw`, so moving one
leaves the owner's original untouched.

Example (dry run, then apply):
    python scripts/english-only-corpus.py --below 0.5
      would move 29 documents out of data/corpus (214 indexed, 185 left)
      data/corpus/2025_National_Tiger_Survey...pdf -> data/quarantine/non-english/...
      ...
    python scripts/english-only-corpus.py --below 0.5 --apply --prune-index
      moved 29 documents to data/quarantine/non-english (log: logs/english-only-removed.jsonl)
      pruned 29 manifest rows and 1,247 vector rows
"""

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import corpus  # noqa: E402
from ingest.pipeline import Manifest, sha256  # noqa: E402

CORPUS = ROOT / "data" / "corpus"
QUARANTINE = ROOT / "data" / "quarantine" / "non-english"
INDEX = ROOT / "index"
LOG = ROOT / "logs" / "english-only-removed.jsonl"


def non_english(index_path: pathlib.Path, below: float) -> list[str]:
    """The corpus file names under `below` Latin share, least Latin first."""
    index = json.loads(index_path.read_text(encoding="utf-8"))
    by_doc: dict[str, list[dict]] = {}
    for page in index["pages"]:
        by_doc.setdefault(page["doc"], []).append(page)
    shares = {}
    for doc, pages in by_doc.items():
        letters = ascii_letters = 0
        for page in pages:
            for char in page.get("text") or "":
                if char.isalpha():
                    letters += 1
                    ascii_letters += char.isascii()
        shares[doc] = ascii_letters / letters if letters else 0.0
    return sorted((doc for doc, share in shares.items() if share < below),
                  key=lambda doc: (shares[doc], doc))


def locate(name: str) -> pathlib.Path:
    """The corpus path of a document, which may sit in an `incoming-wave-*` folder."""
    matches = [path for path in CORPUS.rglob(name) if path.is_file()]
    if len(matches) != 1:
        raise SystemExit(f"{name}: expected one file in {CORPUS}, found {len(matches)}")
    return matches[0]


def move(path: pathlib.Path, record: dict) -> None:
    """Move one corpus file into quarantine under its corpus-relative path."""
    relative = path.relative_to(CORPUS)
    target = QUARANTINE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise SystemExit(f"quarantine already holds {relative}; refusing to overwrite")
    path.rename(target)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record) + "\n")


def prune(names: set[str]) -> dict:
    """Drop the quarantined documents from the manifest and the vector table.

    `index/pages.json` and `index/chunks.jsonl` follow the corpus, but the manifest keeps
    a row per file it has ever seen and LanceDB keeps the old vectors, so both are pruned
    here to keep the index describing the corpus it ships with.
    """
    manifest = Manifest(INDEX)
    before = manifest.counts()
    pruned_manifest = 0
    for row in manifest.rows():
        if row["name"] in names:
            manifest.db.execute("DELETE FROM documents WHERE name = ?", (row["name"],))
            pruned_manifest += 1
    manifest.db.commit()
    after = manifest.counts()
    manifest.close()

    pruned_vectors = 0
    db_dir = INDEX / "lancedb"
    if db_dir.exists():
        import lancedb

        db = lancedb.connect(str(db_dir))
        if "chunks" in db.list_tables():
            table = db.open_table("chunks")
            for name in sorted(names):
                for path in [name, f"incoming-wave-pilot/{name}"]:
                    table.delete(f"file = '{path.replace(chr(39), chr(39) * 2)}'")
            pruned_vectors = sum(1 for row in table.to_arrow().to_pylist()
                                 if pathlib.PurePosixPath(row["file"]).name in names)
    return {"manifest": pruned_manifest, "counts_before": before, "counts_after": after,
            "vectors_left_for_quarantined": pruned_vectors}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="english-only-corpus.py")
    parser.add_argument("--below", type=float, default=0.5,
                        help="Latin share under which a document leaves the corpus")
    parser.add_argument("--index", default=str(INDEX))
    parser.add_argument("--apply", action="store_true", help="actually move the files")
    parser.add_argument("--prune-index", action="store_true",
                        help="also delete the manifest and vector rows (run build after)")
    args = parser.parse_args(argv)

    index_path = pathlib.Path(args.index) / "pages.json"
    names = non_english(index_path, args.below)
    indexed = len(json.loads(index_path.read_text(encoding="utf-8"))["docs"])
    print(f"{'would move' if not args.apply else 'moving'} {len(names)} documents out of "
          f"data/corpus ({indexed} indexed, {indexed - len(names)} left)")
    if not args.apply:
        for name in names:
            print(f"  {locate(name).relative_to(ROOT).as_posix()}")
        return 0

    moved = 0
    for name in names:
        path = locate(name)
        record = {"name": name, "corpus": path.relative_to(ROOT).as_posix(),
                  "quarantine": (QUARANTINE / path.relative_to(CORPUS)).relative_to(ROOT)
                  .as_posix(), "sha256": sha256(path), "bytes": path.stat().st_size}
        move(path, record)
        moved += 1
    print(f"moved {moved} documents to data/quarantine/non-english (log: "
          f"{LOG.relative_to(ROOT).as_posix()})")
    if args.prune_index:
        result = prune(set(names))
        print(f"pruned {result['manifest']} manifest rows and "
              f"{result['vectors_left_for_quarantined']} vector rows")
        print(f"status before {result['counts_before']} after {result['counts_after']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
