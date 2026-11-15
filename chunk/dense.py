"""Build the LanceDB chunk index and measure what a page costs on disk (Step 4 task 6).

This is the storage half of Step 4: it embeds `index/chunks.jsonl` with the pinned
`models/bge-small-en-v1.5` on **CPU** (rule 10 keeps the GPU for the LLM) and writes
one LanceDB table, `index/lancedb/chunks`, with the chunk text and its vector side by
side. Step 5 can then open the table instead of re-encoding every chunk.

It also measures the thing the definition of done asks for: bytes per page on this
corpus, and what that scales to at 100k pages. The measurement is written to
`reports/index-size.md` and printed, because a number that only lives in a chat
message is a number nobody can check later.

The embedder choice is D-054, decided by the owner on 2026-11-15 as
`bge-small-en-v1.5`. This script uses that folder by default, and `--model`
swaps the folder if the owner later picks e5 instead. Rebuilding with a
different folder writes a different table name suffix.

Usage:
    .venv\\Scripts\\python.exe -m chunk.dense
    .venv\\Scripts\\python.exe -m chunk.dense --model multilingual-e5-small
Output:
    index/lancedb/chunks/            (gitignored)
    reports/index-size.md            (committed)
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CHUNKS = ROOT / "index" / "chunks.jsonl"
MODELS = ROOT / "models"
DB = ROOT / "index" / "lancedb"
REPORT = ROOT / "reports" / "index-size.md"
TABLE = "chunks"
# e5 is trained with a "query: " instruction prefix; bge needs none.
PREFIX = {"multilingual-e5-small": "query: ", "bge-small-en-v1.5": ""}


def load_chunks(path: pathlib.Path = CHUNKS) -> list[dict]:
    """Every chunk record from `index/chunks.jsonl`, in index order."""
    if not path.exists():
        raise SystemExit(f"missing {path}: run `python -m chunk.cli build` first")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def folder_bytes(path: pathlib.Path) -> tuple[int, int]:
    """(total bytes, file count) under a directory."""
    files = [f for f in path.rglob("*") if f.is_file()]
    return sum(f.stat().st_size for f in files), len(files)


def build(model_folder: str, batch_size: int = 32) -> dict:
    """Embed every chunk, write the LanceDB table, and return what it measured."""
    from sentence_transformers import SentenceTransformer
    import lancedb

    model_path = MODELS / model_folder
    if not model_path.exists():
        raise SystemExit(f"missing model folder: {model_path} (download it first)")

    chunks = load_chunks()
    began = time.perf_counter()
    model = SentenceTransformer(str(model_path), device="cpu")
    vectors = model.encode([chunk["text"] for chunk in chunks], batch_size=batch_size,
                           convert_to_numpy=True, normalize_embeddings=True,
                           show_progress_bar=False)
    encode_seconds = time.perf_counter() - began

    records = []
    for chunk, vector in zip(chunks, vectors):
        records.append({
            "chunk_id": chunk["chunk_id"],
            "file": chunk["file"],
            "page_start": int(chunk["page_start"]),
            "page_end": int(chunk["page_end"]),
            "type": chunk.get("type", "text"),
            "section_path": chunk.get("section_path", ""),
            "year": chunk.get("year"),
            "publisher": chunk.get("publisher", ""),
            "text": chunk["text"],
            "vector": [float(value) for value in vector],
        })

    # A prefix keeps the query side comparable: e5 expects "query: ..." for questions
    # and bare text for passages, so the prefix is recorded with the table.
    #
    # The directory is removed first on purpose. LanceDB keeps a table's previous
    # versions as extra data files, so rebuilding with mode="overwrite" measured
    # 15.99 MB for the same 3,226 chunks that took 7.99 MB on a clean build - the
    # byte figure this script exists to report would have been double the truth.
    import shutil

    if DB.exists():
        shutil.rmtree(DB)
    DB.mkdir(parents=True, exist_ok=True)
    table_name = TABLE if model_folder == "bge-small-en-v1.5" else f"{TABLE}-{model_folder}"
    db = lancedb.connect(str(DB))
    db.create_table(table_name, data=records, mode="overwrite")
    write_seconds = time.perf_counter() - began - encode_seconds

    pages = len({(chunk["file"], page)
                 for chunk in chunks
                 for page in range(chunk["page_start"], chunk["page_end"] + 1)})
    size_bytes, file_count = folder_bytes(DB)
    summary = {
        "model": model_folder,
        "table": table_name,
        "chunks": len(chunks),
        "pages": pages,
        "dim": int(vectors.shape[1]),
        "encode_seconds": round(encode_seconds, 1),
        "write_seconds": round(write_seconds, 1),
        "index_bytes": size_bytes,
        "index_files": file_count,
        "bytes_per_chunk": round(size_bytes / max(1, len(chunks))),
        "bytes_per_page": round(size_bytes / max(1, pages)),
        "prefix": PREFIX.get(model_folder, ""),
    }
    summary["bytes_for_100k_pages"] = summary["bytes_per_page"] * 100_000
    return summary


def write_report(summaries: list[dict]) -> pathlib.Path:
    """Write `reports/index-size.md` from measured summaries, never from estimates."""
    lines = [
        "# Dense index size (Step 4 task 6)",
        "",
        "Measured, not estimated: the table below is the byte size of `index/lancedb` on",
        "disk after embedding every chunk of the 97-document corpus, read back with",
        "`python -m chunk.dense` (which prints the same numbers it writes here).",
        "",
        "| Embedder | Chunks | Pages | Dim | Index size | Bytes/chunk | Bytes/page | 100k pages | Encode |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in summaries:
        row = dict(row)
        row["chunks_per_page"] = round(row["chunks"] / max(1, row["pages"]), 2)
        lines.append(
            f"| `{row['model']}` | {row['chunks']} | {row['pages']} | {row['dim']} | "
            f"{row['index_bytes'] / 1e6:.2f} MB | {row['bytes_per_chunk']} B | "
            f"{row['bytes_per_page']} B | {row['bytes_for_100k_pages'] / 1e9:.2f} GB | "
            f"{row['encode_seconds']} s |")
    lines += [
        "",
        "## How to read it",
        "",
        "`Pages` counts the pages a chunk actually covers; the corpus has 851 pages and the",
        "rest are unreadable or empty, so they cost nothing in the index. The ratio is",
        "computed from the row above: the same text chunked differently moves bytes/chunk",
        "but barely moves bytes/page, which is why bytes/page is the unit used here.",
        "",
        "The extrapolation multiplies **bytes/page** by 100,000 and assumes the same",
        "average page and the same chunking. It does not model LanceDB compaction or",
        "version overhead growing with table count, which only makes a real 100k-page",
        "table larger, never smaller.",
        "",
        "What is *not* included: any BM25/lexical index (Step 5 builds that), the",
        "`index/chunks.jsonl` file itself, and the embedding model weights (134 MB for",
        "bge, 493 MB for e5), which are shipped once and not per page.",
        "",
        "Usage: `.venv\\Scripts\\python.exe -m chunk.dense`",
        "",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    return REPORT


def main(argv: list[str]) -> int:
    """Build the table, keep the raw measurement in `artifacts/step4/`, print the numbers."""
    parser = argparse.ArgumentParser(prog="chunk.dense")
    parser.add_argument("--model", default="bge-small-en-v1.5",
                        help="folder under models/ (D-054 proposes bge-small-en-v1.5)")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args(argv)

    summary = build(args.model, args.batch_size)
    # Keep the measurement itself, so the report can be rebuilt without re-encoding
    # 3,226 chunks (about 5 minutes) and so a later reader can see the raw numbers.
    evidence = ROOT / "artifacts" / "step4" / "dense-index.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(summary, indent=1), encoding="utf-8")
    path = write_report([summary])
    print(f"table   {summary['table']}: {summary['chunks']} chunks, {summary['dim']} dims")
    print(f"index   {summary['index_bytes'] / 1e6:.2f} MB in {summary['index_files']} files "
          f"({summary['bytes_per_chunk']} B/chunk, {summary['bytes_per_page']} B/page)")
    print(f"100k    {summary['bytes_for_100k_pages'] / 1e9:.2f} GB at this bytes/page")
    print(f"wrote   {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
