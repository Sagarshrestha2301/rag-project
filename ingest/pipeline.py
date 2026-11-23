"""Resumable, incremental ingestion with a SQLite manifest (Step 8).

This is the orchestrator the project lacked: it walks `data/corpus`, remembers what it
already did in `index/manifest.sqlite`, and only parses, chunks or embeds what is new or
changed. Killing it mid-run costs at most the document in flight.

Stages, in order (`build` runs them all):

    scan         hash every corpus PDF, record size/pages, flag duplicates
    parse        one child per document, `--jobs N` at once -> shards under index/parsed/shards/
    assemble     write index/pages.json (search) and index/parsed/pages.jsonl (chunking)
    bibliography one validated title/authors/year/venue/DOI record per document (D-066);
                 **not run by default** - one model call per document, ~8 s (Step 14)
    chunk        one chunk record per unit into index/chunks.jsonl
    embed        append each new document's chunks to the LanceDB table

Resume is per document, not per stage: the manifest row's `status` is written only after
that document's work is on disk, so a killed run leaves unfinished documents `pending`
and finished ones untouched. `shards/` is keyed by SHA-256, so an edited file with a new
hash is parsed again and the old shard is simply unused.

Duplicate rule: a second file with the same SHA-256, or a file whose pages are at least
80% the same text as an earlier file, is marked `duplicate` with `duplicate_of` set and
skipped from the index. Nothing is ever deleted or renamed - the report lists it.

Usage:
    .venv\\Scripts\\python.exe -m ingest.pipeline build         # everything still pending
    .venv\\Scripts\\python.exe -m ingest.pipeline add-batch --from data/raw/incoming-wave-00 --wave 00
    .venv\\Scripts\\python.exe -m ingest.pipeline build --limit 5
    .venv\\Scripts\\python.exe -m ingest.pipeline status
    .venv\\Scripts\\python.exe -m ingest.pipeline backup --out backups/2026-11-19
    .venv\\Scripts\\python.exe -m ingest.pipeline restore --from backups/2026-11-19

Manifest row, as `status` prints it:
    data/corpus/1970_Marahatta_....pdf | sha256 2f1c… | 5 pages | parsed | []

Output: stdout is one JSON summary, so a script can read it (`scripts/add-document.ps1`
does); per-document progress goes to stderr.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import corpus                                     # noqa: E402
from chunk import cli as chunk_cli                # noqa: E402
from ingest import bibliography                   # noqa: E402
from ingest import drive                          # noqa: E402
from ingest import manifest as structure          # noqa: E402
from ingest import text                           # noqa: E402

DEFAULT_CORPUS = ROOT / "data" / "corpus"
DEFAULT_INDEX = ROOT / "index"
DEFAULT_RAW = ROOT / "data" / "raw"
DEFAULT_WAVE_LOG = ROOT / "logs" / "wave-additions.jsonl"
CRASH_PREFIX = "crash: exit code"   # parse_stage's record for a dead child (D-075)
TIMEOUT_PREFIX = "timeout: no result after"   # parse_stage's record for a hung child
PARSE_TIMEOUT = 900.0   # seconds per parse child at jobs=1; slowest serial pilot document 310 s
PARSE_ENTRY = [sys.executable, "-m", "ingest.pipeline", "parse-one"]
DB_NAME = "manifest.sqlite"
SHARDS = "parsed/shards"

# Bump a version when the thing it names changes; a row with an older version is redone.
PARSER_VERSION = "step8-v1"          # corpus.parse_document + ingest.manifest.parse_document
CHUNKER_VERSION = "step4-v1"         # chunk.base.Chunk.chunker_version
EMBEDDING_MODEL = "bge-small-en-v1.5"   # D-054, models/bge-small-en-v1.5
NEAR_DUPLICATE_RATIO = 0.8           # shared pages / smaller document's pages
STATUSES = ("pending", "parsed", "chunked", "embedded", "duplicate", "failed")
WORK_STATUSES = ("pending", "parsed", "chunked")   # not finished, not skipped

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    path             TEXT PRIMARY KEY,   -- corpus-relative posix path
    name             TEXT NOT NULL UNIQUE,
    sha256           TEXT NOT NULL,
    bytes            INTEGER NOT NULL,
    pages            INTEGER,
    parser_version   TEXT,
    chunker_version  TEXT,
    embedding_model  TEXT,
    status           TEXT NOT NULL,
    error            TEXT,
    duplicate_of     TEXT,
    unreadable_pages TEXT,               -- JSON list of page numbers
    page_hashes      TEXT,               -- JSON list, for near-duplicate detection
    seconds          REAL,
    updated_at       TEXT
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def sha256(path: pathlib.Path) -> str:
    """The file's content hash, in blocks so a large PDF does not fill memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class Manifest:
    """The SQLite manifest: one row per corpus file, plus free-form meta rows."""

    def __init__(self, index_dir: pathlib.Path):
        self.index_dir = index_dir
        index_dir.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(index_dir / DB_NAME)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('schema', '1')")
        self.db.commit()

    # --- reading ---------------------------------------------------------
    def rows(self, status: str | None = None) -> list[sqlite3.Row]:
        if status:
            return self.db.execute(
                "SELECT * FROM documents WHERE status = ? ORDER BY path", (status,)).fetchall()
        return self.db.execute("SELECT * FROM documents ORDER BY path").fetchall()

    def row(self, name: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM documents WHERE name = ?", (name,)).fetchone()

    def counts(self) -> dict[str, int]:
        found = {status: 0 for status in STATUSES}
        for row in self.db.execute("SELECT status, COUNT(*) AS n FROM documents GROUP BY status"):
            found[row["status"]] = row["n"]
        return found

    # --- writing ---------------------------------------------------------
    def upsert(self, record: dict) -> None:
        """Insert or update one file row; unchanged hashes keep their status."""
        existing = self.db.execute("SELECT * FROM documents WHERE path = ?",
                                   (record["path"],)).fetchone()
        values = {"error": None, "duplicate_of": None, "unreadable_pages": "[]",
                  "page_hashes": None, "pages": None, "seconds": None,
                  "parser_version": PARSER_VERSION, "chunker_version": None,
                  "embedding_model": EMBEDDING_MODEL, "status": "pending"}
        values.update(record)
        if existing and existing["sha256"] == values["sha256"]:
            # Same bytes as last time: keep what was already done for this file.
            return
        values["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.db.execute(
            "INSERT OR REPLACE INTO documents (path, name, sha256, bytes, pages, parser_version,"
            " chunker_version, embedding_model, status, error, duplicate_of, unreadable_pages,"
            " page_hashes, seconds, updated_at)"
            " VALUES (:path, :name, :sha256, :bytes, :pages, :parser_version, :chunker_version,"
            " :embedding_model, :status, :error, :duplicate_of, :unreadable_pages,"
            " :page_hashes, :seconds, :updated_at)", values)
        self.db.commit()

    def set_status(self, name: str, status: str, **fields) -> None:
        allowed = {"error", "duplicate_of", "pages", "unreadable_pages", "page_hashes",
                   "seconds", "chunker_version", "embedding_model", "parser_version"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"unknown manifest fields: {sorted(unknown)}")
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values())
        self.db.execute(
            f"UPDATE documents SET status = ?, updated_at = ?, {assignments} WHERE name = ?"
            if assignments else
            "UPDATE documents SET status = ?, updated_at = ? WHERE name = ?",
            [status, time.strftime("%Y-%m-%dT%H:%M:%S"), *values, name])
        self.db.commit()

    def set_meta(self, key: str, value: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, value))
        self.db.commit()

    def get_meta(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def close(self) -> None:
        self.db.close()


# --------------------------------------------------------------------- scan

def scan(root: pathlib.Path, manifest: Manifest) -> dict:
    """Hash every corpus PDF and register it; same-content files are duplicates.

    A new file is `pending`. A file whose hash changed goes back to `pending` and its
    old shards stop matching. A file already recorded with the same hash keeps its
    status, which is what makes a second run cheap.
    """
    files = corpus.files(root)
    known = {row["name"] for row in manifest.rows()}
    groups: dict[str, list[str]] = {}
    for path in files:
        record = {
            "path": path.relative_to(root).as_posix(),
            "name": path.name,
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        manifest.upsert(record)
        groups.setdefault(record["sha256"], []).append(path.name)

    for names in groups.values():
        if len(names) < 2:
            continue
        # A file the manifest already knew wins, so dropping a copy beside an
        # indexed document never demotes the document that questions cite.
        canonical = next((name for name in names if name in known), names[0])
        for name in names:
            if name != canonical:
                manifest.set_status(name, "duplicate", duplicate_of=canonical)

    exact = [row["name"] for row in manifest.rows("duplicate")]
    return {"files": len(files), "duplicates": exact,
            "counts": manifest.counts()}


# -------------------------------------------------------------------- parse

def _shard(index_dir: pathlib.Path, sha: str, kind: str) -> pathlib.Path:
    path = index_dir / SHARDS / f"{sha}.{kind}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write(path: pathlib.Path, text: str) -> None:
    """Write UTF-8 with LF endings, so an artifact is byte-identical on any machine.

    `Path.write_text` translates `\n` to CRLF on Windows; the committed eval artifacts
    and `pages.jsonl` are LF, so a rebuild that used `write_text` would change hashes
    without changing a single character of content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _page_hashes(pages: list[dict]) -> list[str]:
    """One hash per page of normalized text, for near-duplicate detection."""
    out = []
    for page in pages:
        words = " ".join(str(page.get("text") or "").lower().split())
        out.append(hashlib.sha256(words.encode("utf-8")).hexdigest() if words else "")
    return out


def _near_duplicate(name: str, hashes: list[str], manifest: Manifest) -> str | None:
    """The earlier document this one repeats, if at least 80% of pages match."""
    mine = {value for value in hashes if value}
    if not mine:
        return None
    for row in manifest.rows():
        if row["name"] == name or row["status"] not in ("parsed", "chunked", "embedded"):
            continue
        theirs = {value for value in json.loads(row["page_hashes"] or "[]") if value}
        if not theirs:
            continue
        shared = len(mine & theirs)
        if shared / min(len(mine), len(theirs)) >= NEAR_DUPLICATE_RATIO:
            return row["name"]
    return None


def parse_document(path: pathlib.Path, index_dir: pathlib.Path, sha: str,
                   rel: str) -> dict:
    """Parse one document into its three shards; returns only what the parent needs.

    This function is run by a child process (see `parse_stage`), so it must stay
    importable at module level and its arguments stay paths and strings, because the
    caller passes them on a command line. A native crash inside PyMuPDF cannot be caught
    in Python, which is exactly why the caller isolates it here (D-075).

    Example:
        >>> parse_document(pathlib.Path("data/corpus/a.pdf"), index / "parsed", sha, "a.pdf")
        {'page_count': 5, 'unreadable': [3], 'page_hashes': ['9f2c…', …]}
    """
    search = corpus.parse_document(path)
    pages, summary = structure.parse_document(path)
    summary["furniture_lines"] = text.strip_furniture(pages)
    _write(_shard(index_dir, sha, "search.json"),
           json.dumps({**search, "sha256": sha, "path": rel}))
    _write(_shard(index_dir, sha, "structure.jsonl"),
           "".join(json.dumps(page.as_dict(), ensure_ascii=False) + "\n"
                   for page in pages))
    _write(_shard(index_dir, sha, "summary.json"),
           json.dumps(summary, ensure_ascii=False))
    return {"page_count": search["page_count"], "unreadable": search["unreadable"],
            "page_hashes": _page_hashes(search["pages"])}


def _run_isolated(path: pathlib.Path, index_dir: pathlib.Path, sha: str, rel: str,
                  entry: list[str] | None = None,
                  timeout: float = PARSE_TIMEOUT) -> tuple[str, object]:
    """Parse one document in a fresh interpreter: ('ok', result), ('error', text), ('crash', code), ('timeout', seconds).

    A separate `python -m` process rather than `multiprocessing`: a native access
    violation cannot be caught, and spawn was measured here to stall PyMuPDF's table
    detector on a 198-page scanned report (`find_tables` -> `table.py:make_chars`, 1400 s
    CPU, no return) where a plain new interpreter parsed the same file in 308 s.

    `timeout` bounds the wait, because a child that never returns (PyMuPDF's table code
    has been seen to) would otherwise stall the whole wave. The child is killed and the
    document recorded as failed; its partial shards are never assembled, because the row
    never becomes `parsed`. `entry` is the command prefix, so a test can point the
    isolation at a fake parser.
    """
    entry = entry or PARSE_ENTRY
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8")
    result_file = pathlib.Path(handle.name)
    handle.close()
    try:
        try:
            completed = subprocess.run(
                [*entry, "--path", str(path), "--index", str(index_dir),
                 "--sha", sha, "--rel", rel, "--result", str(result_file)],
                cwd=ROOT, check=False, timeout=timeout,
                # The child prints parser banners; they belong with the progress lines,
                # so `build`'s stdout stays the one JSON summary a script can read.
                stdout=sys.stderr)
        except subprocess.TimeoutExpired:
            return "timeout", timeout
        except OSError as exc:
            return "error", f"{exc.__class__.__name__}: {exc}"
        try:
            report = json.loads(result_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "crash", completed.returncode
        if completed.returncode != 0 or "error" in report:
            return "error", report.get("error", f"exit code {completed.returncode}")
        return "ok", report
    finally:
        result_file.unlink(missing_ok=True)


def _parse_child(row: dict, root: pathlib.Path, index_dir: pathlib.Path,
                 entry: list[str] | None, timeout: float) -> tuple[str, object, float]:
    """One document's child parse, returning `(state, payload, that child's seconds)`.

    Both the serial and the parallel path call this, so there is one place that decides
    what a parse child is (Step 13).
    """
    began = time.perf_counter()
    state, payload = _run_isolated(root / row["path"], index_dir, row["sha256"],
                                   row["path"], entry, timeout)
    return state, payload, time.perf_counter() - began


def _parse_outcomes(todo: list[dict], root: pathlib.Path, index_dir: pathlib.Path,
                    entry: list[str] | None, timeout: float, jobs: int):
    """Yield `(row, state, payload, seconds)` in **plan order**, `jobs` children at a time.

    Plan order, not completion order: the parent records each row exactly where a serial
    run would record it, so near-duplicate detection and the counters cannot depend on
    which document happened to finish first. A thread pool is enough because the work is
    a blocking `subprocess.run`; `multiprocessing` spawn was measured to stall PyMuPDF
    (D-076), and the isolation unit is the `python -m` child, not a worker.
    """
    if jobs == 1:
        for row in todo:
            yield (row, *_parse_child(row, root, index_dir, entry, timeout))
        return
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        running = [(row, pool.submit(_parse_child, row, root, index_dir, entry, timeout))
                   for row in todo]
        for row, future in running:
            try:
                outcome = future.result()
            except Exception as exc:            # noqa: BLE001 - one file must not stop the run
                outcome = ("error", f"{exc.__class__.__name__}: {exc}", 0.0)
            yield (row, *outcome)


def parse_timeout_for(jobs: int, timeout: float | None = None) -> float:
    """Seconds one parse child gets. `None` means the default, which scales with `jobs`.

    Parallel children contend: on 2026-11-23 the same 198-page annual report took 310.4 s
    serial and **1,749.6 s at `--jobs 8`**, and three OCR-heavy reports needed
    953 / 1,255 / 1,068 s, so a flat 900 s watchdog killed work that would have finished.
    An explicit `timeout` always wins, so a caller that wants a short cap still gets it.

    Example:
        >>> parse_timeout_for(1), parse_timeout_for(8), parse_timeout_for(8, 3600)
        (900.0, 7200.0, 3600.0)
    """
    if timeout is not None:
        return float(timeout)
    return PARSE_TIMEOUT * max(1, jobs)


def parse_stage(root: pathlib.Path, index_dir: pathlib.Path, manifest: Manifest,
                limit: int | None = None, entry: list[str] | None = None,
                timeout: float | None = None, jobs: int = 1) -> dict:
    """Parse every pending or changed document in its own child process (D-075).

    Each parse is a fresh interpreter (see `_run_isolated`), so a document that kills the
    parser with a native access violation costs that one document (`crash: exit code N`)
    instead of the whole batch; `assemble` skips the failed row, and still reports a row
    marked `parsed` whose shards are missing. `entry` exists so tests can point the child
    at a parser that exits or raises on purpose.

    `jobs` runs that many children at once (Step 13). Measured on 2026-11-22 over 20 real
    corpus documents: **202.2 s one at a time (87.9 pages/min)** and **132.2 s at 8
    (134.3 pages/min, 1.53x)**, with identical page counts. Past 8 there is no further
    gain: each child's table detector and OCR already use the cores and they contend.
    The default 1 is the serial behaviour every earlier log and `STATUS.md` number was
    produced with. `timeout` defaults to `parse_timeout_for(jobs)`, so the watchdog grows
    with the contention instead of killing documents that are actually progressing.

    Example:
        >>> parse_stage(root, index, manifest, jobs=8)
        {'parsed': 1960, 'failed': 3, 'seconds': 127800.4}
    """
    todo = [row for row in manifest.rows() if row["status"] in ("pending", "failed")
            and not row["duplicate_of"]
            # A native crash or a hang is reproducible; retrying it every restart only
            # burns time (or stalls it again). A changed file gets a new SHA-256, which
            # `upsert` turns back into `pending`.
            and not (row["error"] or "").startswith((CRASH_PREFIX, TIMEOUT_PREFIX))]
    if limit:
        todo = todo[:limit]
    if jobs < 1:
        raise SystemExit(f"jobs must be at least 1, not {jobs}; 8 is the measured knee")
    jobs = min(jobs, max(1, len(todo)))
    timeout = parse_timeout_for(jobs, timeout)
    started = time.perf_counter()
    parsed = failed = 0

    outcomes = _parse_outcomes(todo, root, index_dir, entry, timeout, jobs)
    for position, (row, state, payload, elapsed) in enumerate(outcomes, start=1):
        if state != "ok":
            failed += 1
            if state == "crash":
                error = f"{CRASH_PREFIX} {payload}"
            elif state == "timeout":
                error = f"{TIMEOUT_PREFIX} {payload:.0f} s; killed it"
            else:
                error = str(payload)
            manifest.set_status(row["name"], "failed", error=error)
            print(f"  ! {row['name'][:56]}: {error}", file=sys.stderr)
            continue
        try:
            result = dict(payload)
            hashes = result["page_hashes"]
            duplicate_of = _near_duplicate(row["name"], hashes, manifest)
            manifest.set_status(
                row["name"], "duplicate" if duplicate_of else "parsed",
                duplicate_of=duplicate_of, pages=result["page_count"],
                unreadable_pages=json.dumps(result["unreadable"]),
                page_hashes=json.dumps(hashes),
                seconds=round(elapsed, 1))
            if duplicate_of:
                print(f"  duplicate: {row['name']} repeats {duplicate_of}; kept, not indexed",
                      file=sys.stderr)
            else:
                parsed += 1
        except Exception as exc:                    # noqa: BLE001 - one file must not stop the run
            failed += 1
            manifest.set_status(row["name"], "failed",
                                error=f"{exc.__class__.__name__}: {exc}")
            print(f"  ! {row['name'][:56]}: {exc.__class__.__name__}: {exc}",
                  file=sys.stderr)
            continue

        done = time.perf_counter() - started
        # `position` counts *completed* documents, so `done / position` is already the
        # amortised wall time per document at this concurrency; dividing by `jobs` again
        # would promise a speedup the machine does not deliver (1.41x measured, not 8x).
        eta = (done / position) * (len(todo) - position)
        print(f"  [{position}/{len(todo)}] {row['name'][:52]:54s} "
              f"{result['page_count']:>3}p {elapsed:>6.1f}s "
              f"eta {eta:>5.0f}s", file=sys.stderr)

    manifest.set_meta("last_parse", time.strftime("%Y-%m-%dT%H:%M:%S"))
    return {"parsed": parsed, "failed": failed, "seconds": round(time.perf_counter() - started, 1)}


# ----------------------------------------------------------------- assemble

def assemble(root: pathlib.Path, index_dir: pathlib.Path, manifest: Manifest) -> dict:
    """Write the two artifacts the rest of the system reads, from the shards.

    `index/pages.json` is what `corpus.search` reads (page-level BM25) and
    `index/parsed/pages.jsonl` is what the chunker reads. Both are assembled in
    `corpus.files()` order, so the result does not depend on the order documents were
    added.
    """
    pages: list[dict] = []
    unreadable: dict[str, list[int]] = {}
    docs: list[dict] = []
    ocr_pages = 0
    structure_lines: list[str] = []
    summaries: list[dict] = []
    missing: list[str] = []

    for path in corpus.files(root):
        row = manifest.row(path.name)
        if row is None or row["status"] not in ("parsed", "chunked", "embedded"):
            continue
        shard = _shard(index_dir, row["sha256"], "search.json")
        structure_shard = _shard(index_dir, row["sha256"], "structure.jsonl")
        if not shard.exists() or not structure_shard.exists():
            missing.append(row["name"])
            continue
        parsed = json.loads(shard.read_text(encoding="utf-8"))
        pages.extend(parsed["pages"])
        docs.append({"doc": parsed["name"], "label": parsed["label"],
                     "pages": parsed["page_count"]})
        if parsed["unreadable"]:
            unreadable[parsed["name"]] = parsed["unreadable"]
        ocr_pages += parsed["ocr_pages"]
        structure_lines.append(structure_shard.read_text(encoding="utf-8"))
        summaries.append(json.loads(
            _shard(index_dir, row["sha256"], "summary.json").read_text(encoding="utf-8")))

    index = {"pages": pages, "unreadable": unreadable, "docs": docs,
             "signature": corpus.signature(root), "ocr_pages": ocr_pages}
    _write(index_dir / "pages.json", json.dumps(index))

    parsed_dir = index_dir / "parsed"
    _write(parsed_dir / "pages.jsonl", "".join(structure_lines))
    _write(parsed_dir / "manifest.json", json.dumps({
        "corpus": str(root),
        "docs": summaries,
        "totals": {
            "documents": len(summaries),
            "pages": len(pages),
            "tables": sum(summary.get("tables", 0) for summary in summaries),
            "ocr_pages": ocr_pages,
            "unreadable_pages": sum(len(v) for v in unreadable.values()),
        },
    }, indent=2))
    return {"documents": len(docs), "pages": len(pages), "ocr_pages": ocr_pages,
            "missing_shards": missing}


# -------------------------------------------------------------------- chunk

def chunk_stage(root: pathlib.Path, index_dir: pathlib.Path, manifest: Manifest) -> dict:
    """Rebuild `index/chunks.jsonl` from the assembled pages; mark what needs embedding.

    Chunking the whole corpus is deterministic and takes about half a second, so it is
    done in one pass; what is per-document is the *status*, and only documents chunked
    by this run (or by an older chunker) are then embedded.
    """
    parsed = index_dir / "parsed" / "pages.jsonl"
    chunks = chunk_cli.build_chunks(parsed, root=root)
    problems = chunk_cli.check(chunks)
    if problems:
        raise SystemExit("chunk check failed:\n  " + "\n  ".join(problems[:20]))
    with (index_dir / "chunks.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk.as_dict(), ensure_ascii=False) + "\n")

    needing = 0
    for row in manifest.rows():
        if row["status"] in ("parsed", "chunked") and row["chunker_version"] != CHUNKER_VERSION:
            manifest.set_status(row["name"], "chunked")
            needing += 1
    manifest.set_meta("chunks", str(len(chunks)))
    return {"chunks": len(chunks), "needs_embedding": needing}


# -------------------------------------------------------------------- embed

def _chunks_by_doc(path: pathlib.Path) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            grouped.setdefault(record["file"], []).append(record)
    return grouped


def embed_stage(index_dir: pathlib.Path, manifest: Manifest,
                model_folder: str = EMBEDDING_MODEL, batch_size: int = 32,
                limit: int | None = None) -> dict:
    """Append each document's new chunks to the LanceDB table, replacing its old rows.

    Documents are the unit of work, so adding five files embeds five files. On CPU on
    purpose: Step 4 did not benchmark GPU embedding as faster and rule 10 keeps VRAM for
    the LLM (TODO(step-08): benchmark GPU embedding during a bulk build before using it).
    """
    todo = [row for row in manifest.rows("chunked")]
    if limit:
        todo = todo[:limit]
    if not todo:
        return {"embedded": 0, "chunks": 0}

    import lancedb
    from sentence_transformers import SentenceTransformer

    model_path = ROOT / "models" / model_folder
    if not model_path.exists():
        raise SystemExit(f"missing model folder: {model_path} (download it first)")
    chunks_by_doc = _chunks_by_doc(index_dir / "chunks.jsonl")
    db_dir = index_dir / "lancedb"
    db_dir.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(db_dir))
    table = db.open_table("chunks") if "chunks" in db.list_tables() else None
    model = SentenceTransformer(str(model_path), device="cpu")
    began = time.perf_counter()
    written = 0

    for position, row in enumerate(todo, start=1):
        records = chunks_by_doc.get(row["name"]) or []
        if records:
            vectors = model.encode([record["text"] for record in records],
                                   batch_size=batch_size, convert_to_numpy=True,
                                   normalize_embeddings=True, show_progress_bar=False)
            rows = [{"chunk_id": record["chunk_id"], "file": record["file"],
                     "page_start": int(record["page_start"]), "page_end": int(record["page_end"]),
                     "type": record.get("type", "text"), "section_path": record.get("section_path", ""),
                     "year": record.get("year"), "publisher": record.get("publisher", ""),
                     "text": record["text"], "vector": [float(value) for value in vector]}
                    for record, vector in zip(records, vectors)]
            if table is None:
                table = db.create_table("chunks", data=rows)
            else:
                # Re-embedding a changed document must not leave its old rows behind.
                table.delete(f"file = '{record_file(rows)}'")
                table.add(rows)
            written += len(rows)
        manifest.set_status(row["name"], "embedded", chunker_version=CHUNKER_VERSION,
                            embedding_model=model_folder)
        eta = (time.perf_counter() - began) / position * (len(todo) - position)
        print(f"  [{position}/{len(todo)}] {row['name'][:52]:54s} "
              f"{len(records):>3} chunks eta {eta:>5.0f}s", file=sys.stderr)

    return {"embedded": len(todo), "chunks": written,
            "seconds": round(time.perf_counter() - began, 1)}


def record_file(rows: list[dict]) -> str:
    """The `file` value shared by one document's rows, for the delete predicate."""
    return rows[0]["file"].replace("'", "''")


# ------------------------------------------------------------------- build

def build(root: pathlib.Path = DEFAULT_CORPUS, index_dir: pathlib.Path = DEFAULT_INDEX,
          stages: tuple[str, ...] = ("scan", "parse", "assemble", "chunk", "embed"),
          limit: int | None = None, parse_timeout: float | None = None,
          parse_jobs: int = 1) -> dict:
    """Run the requested stages in order and return what each one measured.

    `parse_jobs` goes to `parse_stage`: 1 is one document at a time and 8 is the measured
    knee (1.53x, Step 13).

    The bibliography is **not** in the default stages: it is one model call per document
    (~8.2 s measured, ~45 h for 20,000 documents) for metadata only the evidence rail
    shows, so a wave skips it unless asked (`--stages ...,bibliography,...`). Its own
    command fills it on demand: `python -m ingest.bibliography build` (Step 14).
    """
    started = time.perf_counter()
    manifest = Manifest(index_dir)
    report: dict = {"root": str(root), "index": str(index_dir), "stages": {}}
    try:
        if "scan" in stages:
            report["stages"]["scan"] = scan(root, manifest)
        if "parse" in stages:
            report["stages"]["parse"] = parse_stage(root, index_dir, manifest, limit,
                                                    timeout=parse_timeout,
                                                    jobs=parse_jobs)
        if "assemble" in stages:
            report["stages"]["assemble"] = assemble(root, index_dir, manifest)
        if "bibliography" in stages:
            # Slow (one local model call per new document) and never fatal: a missing model
            # leaves the DOI and year and blanks the rest, and the UI falls back to a label.
            artifact = bibliography.build(index_dir, log=lambda line: print(line, file=sys.stderr))
            report["stages"]["bibliography"] = {
                **artifact.get("counts", {}), "seconds": artifact.get("seconds")}
        if "chunk" in stages:
            report["stages"]["chunk"] = chunk_stage(root, index_dir, manifest)
        if "embed" in stages:
            report["stages"]["embed"] = embed_stage(index_dir, manifest, limit=limit)
        report["counts"] = manifest.counts()
        failures = [{"name": row["name"], "error": row["error"]}
                    for row in manifest.rows("failed")]
        report["failures"] = failures
        report["seconds"] = round(time.perf_counter() - started, 1)
    finally:
        manifest.close()
    return report


# ----------------------------------------------------------- status/report

def status(index_dir: pathlib.Path = DEFAULT_INDEX) -> dict:
    """Counts per status, the failures with reasons, and documents with unreadable pages."""
    manifest = Manifest(index_dir)
    try:
        rows = manifest.rows()
        return {
            "documents": len(rows),
            "counts": manifest.counts(),
            "failures": [{"name": row["name"], "error": row["error"]}
                         for row in rows if row["status"] == "failed"],
            "duplicates": [{"name": row["name"], "of": row["duplicate_of"]}
                           for row in rows if row["status"] == "duplicate"],
            "unreadable": {row["name"]: json.loads(row["unreadable_pages"] or "[]")
                           for row in rows if json.loads(row["unreadable_pages"] or "[]")},
            "without_sha256": [row["name"] for row in rows
                               if not _is_sha256(row["sha256"] or "")],
            # Only the parse stage stores a per-document duration, so this is that
            # number summed, not a wall-clock total for a whole build.
            "parse_seconds": round(sum(row["seconds"] or 0 for row in rows), 1),
        }
    finally:
        manifest.close()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _size(path: pathlib.Path) -> int:
    """Bytes on disk for a file or a folder; 0 when it does not exist."""
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
    return 0


def write_report(index_dir: pathlib.Path = DEFAULT_INDEX,
                 path: pathlib.Path | None = None) -> pathlib.Path:
    """`reports/full-ingestion.md` from the manifest, never from estimates."""
    summary = status(index_dir)
    out = path or (ROOT / "reports" / "full-ingestion.md")
    lines = [
        "# Full ingestion (Step 8)",
        "",
        "Written by `python -m ingest.pipeline status`; every number is read from",
        "`index/manifest.sqlite`, not estimated.",
        "",
        f"- Documents in the manifest: **{summary['documents']}**",
        f"- Status counts: `{json.dumps(summary['counts'])}`",
        f"- Failures: **{len(summary['failures'])}**",
        f"- Duplicates flagged and skipped: **{len(summary['duplicates'])}**",
        f"- Documents without a valid SHA-256: **{len(summary['without_sha256'])}**",
        f"- Sum of the measured per-document parse times: **{summary['parse_seconds']:.0f} s**",
        "",
        "## Index size (bytes on disk)",
        "",
        "| Artifact | Bytes |",
        "|---|---|",
    ]
    for label, path in (("`index/pages.json`", index_dir / "pages.json"),
                        ("`index/chunks.jsonl`", index_dir / "chunks.jsonl"),
                        ("`index/parsed/` (pages.jsonl + shards)", index_dir / "parsed"),
                        ("`index/lancedb/`", index_dir / "lancedb"),
                        ("`index/manifest.sqlite`", index_dir / DB_NAME)):
        lines.append(f"| {label} | {_size(path):,} |")
    total = _size(index_dir)
    lines += [f"| **total `index/`** | **{total:,}** |", "",
              "## Failures with reasons",
        "",
    ]
    lines += ([f"- `{item['name']}`: {item['error']}" for item in summary["failures"]]
              or ["None."])
    lines += ["", "## Duplicates (kept, not indexed)", ""]
    lines += ([f"- `{item['name']}` repeats `{item['of']}`" for item in summary["duplicates"]]
              or ["None."])
    lines += ["", "## Unreadable pages per document", ""]
    lines += ([f"- `{name}`: pages {pages}" for name, pages in summary["unreadable"].items()]
              or ["None."])
    lines += ["", "## Scale", "",
              "The corpus this pipeline currently runs on is the 97-document / 851-page set,",
              "so the numbers above are that scale. The 100k-page target is a scope question",
              "for the owner (see `STATUS.md`); nothing here is projected to it.", ""]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ------------------------------------------------------------------- backup

BACKUP_FILES = ("pages.json", "chunks.jsonl", "parsed/pages.jsonl", "parsed/manifest.json",
                bibliography.INDEX_FILE)
BACKUP_DIRS = (SHARDS, "lancedb")      # dense vectors included: a restore is usable at once


def backup(index_dir: pathlib.Path = DEFAULT_INDEX, out: pathlib.Path | None = None) -> dict:
    """Copy the manifest and every index artifact into one folder, DB via sqlite backup.

    The dense vectors are included, so a restore answers questions immediately instead
    of waiting for a re-embed.
    """
    target = out or (ROOT / "backups" / time.strftime("%Y-%m-%d-%H%M%S"))
    target.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(index_dir / DB_NAME)
    destination = sqlite3.connect(target / DB_NAME)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    copied = [DB_NAME]
    for relative in BACKUP_FILES:
        origin = index_dir / relative
        if origin.exists():
            (target / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origin, target / relative)
            copied.append(relative)
    for relative in BACKUP_DIRS:
        origin = index_dir / relative
        if origin.exists():
            shutil.copytree(origin, target / relative, dirs_exist_ok=True)
            copied.append(relative)
    return {"backup": str(target), "files": copied}


def restore(backup_dir: pathlib.Path, index_dir: pathlib.Path = DEFAULT_INDEX) -> dict:
    """Put a backup back and check the manifest still counts the same documents."""
    if not (backup_dir / DB_NAME).exists():
        raise SystemExit(f"{backup_dir} holds no {DB_NAME}")
    index_dir.mkdir(parents=True, exist_ok=True)
    for relative in (DB_NAME, *BACKUP_FILES):
        origin = backup_dir / relative
        if origin.exists():
            (index_dir / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origin, index_dir / relative)
    for relative in BACKUP_DIRS:
        origin = backup_dir / relative
        if origin.exists():
            shutil.copytree(origin, index_dir / relative, dirs_exist_ok=True)
    return status(index_dir)


def _is_within(path: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def add_batch(source_dir: pathlib.Path, wave: str, *,
              corpus_root: pathlib.Path = DEFAULT_CORPUS,
              index_dir: pathlib.Path = DEFAULT_INDEX,
              stages: tuple[str, ...] = ("scan", "parse", "assemble", "chunk", "embed"),
              limit: int | None = None, build_after: bool = True,
              raw_root: pathlib.Path = DEFAULT_RAW,
              log_path: pathlib.Path = DEFAULT_WAVE_LOG,
              parse_timeout: float | None = None,
              parse_jobs: int = 1) -> dict:
    """Bring one staged folder of PDFs into the corpus, all or nothing (Step 10).

    Every refusal is decided before a single file is linked, so a batch with one bad
    name leaves the corpus exactly as it was. Files keep their folder relative to
    `raw_root` (D-030) and are hardlinked, copied only if the link fails. Rerunning a
    batch that already landed reports the files as `unchanged` instead of refusing.

    Example:
        .venv\\Scripts\\python.exe -m ingest.pipeline add-batch \\
            --from data/raw/incoming-wave-00 --wave 00
        {'wave': '00', 'added': 2, 'unchanged': 0, 'skipped': [], 'refused': [],
         'bytes': 48123, 'modes': {'hardlink': 2}, 'build': {...}}

    A duplicate name prints every offending file and returns `added: 0`. A file whose
    bytes are already indexed is **skipped** with its reason and the rest of the batch
    still lands, so re-fetching a folder that overlaps the corpus is harmless.
    """
    source = pathlib.Path(source_dir).resolve()
    raw = pathlib.Path(raw_root).resolve()
    corpus_dir = pathlib.Path(corpus_root).resolve()
    refused: list[str] = []
    added: list[dict] = []
    unchanged: list[str] = []
    skipped: list[dict] = []
    modes: dict[str, int] = {"hardlink": 0, "copied": 0}
    report: dict | None = None

    if not source.is_dir():
        refused.append(f"{source} is not a folder")
    else:
        if not _is_within(source, raw):
            refused.append(f"{source} is not inside {raw}; a staged batch keeps its folder "
                           "relative to data/raw")
        if _is_within(source, corpus_dir):
            refused.append(f"{source} is already inside the corpus ({corpus_dir})")

    files = sorted(path for path in source.rglob("*") if path.is_file()) if not refused else []
    if not refused and not files:
        refused.append(f"{source} holds no files")

    manifest = Manifest(index_dir)
    try:
        if not refused:
            indexed = {row["sha256"]: row["name"] for row in manifest.rows()}
            existing = ({path.name: path for path in corpus.files(corpus_dir)}
                        if corpus_dir.is_dir() else {})
            names: dict[str, pathlib.Path] = {}
            hashes: dict[str, pathlib.Path] = {}
            accepted: list[pathlib.Path] = []
            for path in files:
                if path.suffix.lower() != ".pdf":
                    refused.append(f"{path.name}: not a .pdf - convert Word files with the "
                                   "pinned LibreOffice to <name>.docx.pdf first")
                    continue
                digest = sha256(path)
                if path.name in names:
                    refused.append(f"{path.name}: appears twice in the batch "
                                   f"({names[path.name]} and {path})")
                    continue
                names[path.name] = path
                if path.name in existing:
                    if sha256(existing[path.name]) == digest:
                        unchanged.append(path.name)
                    else:
                        refused.append(f"{path.name}: the corpus already has a different "
                                       f"file with that name ({existing[path.name]})")
                    continue
                if digest in hashes:
                    # A duplicate is skipped, not fatal: the batch still lands and the
                    # report says which file it repeats (owner request, 2026-11-21).
                    skipped.append({"name": path.name,
                                    "reason": f"same bytes as {hashes[digest].name} in this batch"})
                    continue
                hashes[digest] = path
                if digest in indexed:
                    skipped.append({"name": path.name,
                                    "reason": f"same bytes as the indexed document "
                                              f"{indexed[digest]}"})
                    continue
                accepted.append(path)

        if not refused:
            for path in accepted:
                target, mode = drive.mirror(path, corpus_dir, raw)
                if mode == "already there":
                    unchanged.append(path.name)
                    continue
                modes["hardlink" if mode == "hardlink" else "copied"] += 1
                relative = target.relative_to(corpus_dir).as_posix()
                drive.record({"name": path.name, "path": relative, "wave": str(wave),
                              "sha256": sha256(path), "bytes": path.stat().st_size,
                              "source": str(path)}, corpus_dir, mode, manifest=log_path)
                added.append({"name": path.name, "path": relative,
                              "bytes": path.stat().st_size, "mode": mode})

            key = f"wave-{wave}"
            previous = json.loads(manifest.get_meta(key) or "{}")
            manifest.set_meta(key, json.dumps({
                "documents": previous.get("documents", 0) + len(added),
                "bytes": previous.get("bytes", 0) + sum(item["bytes"] for item in added),
                "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }))

            if build_after:
                report = build(corpus_dir, index_dir, stages, limit,
                               parse_timeout=parse_timeout, parse_jobs=parse_jobs)
    finally:
        manifest.close()

    return {"wave": str(wave), "added": len(added), "unchanged": len(unchanged),
            "skipped": skipped, "refused": refused,
            "bytes": sum(item["bytes"] for item in added),
            "modes": modes, "files": added, "build": report}


# ---------------------------------------------------------------------- cli

def _parser() -> argparse.ArgumentParser:
    """The command line, split out so a test can read its defaults (Step 14)."""
    parser = argparse.ArgumentParser(prog="ingest.pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    build_cmd = sub.add_parser("build", help="run the stages that have work to do")
    build_cmd.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    build_cmd.add_argument("--index", default=str(DEFAULT_INDEX))
    build_cmd.add_argument("--stages", default="scan,parse,assemble,chunk,embed",
                           help="comma-separated subset: scan,parse,assemble,bibliography,"
                                "chunk,embed; bibliography is opt-in (one model call per"
                                " document)")
    build_cmd.add_argument("--limit", type=int, default=None,
                           help="work on at most N documents this run (dry run, resume test)")
    build_cmd.add_argument("--parse-timeout", type=float, default=None,
                           help="seconds before a document's parse child is killed;"
                                " default 900 x --jobs (7200 at 8), because parallel"
                                " children make each document ~6x slower")
    build_cmd.add_argument("--jobs", type=int, default=1,
                           help="documents to parse at once; 1 keeps today's serial run,"
                                " 8 is the measured knee (1.53x, Step 13)")

    status_cmd = sub.add_parser("status", help="print counts, failures and duplicates")
    status_cmd.add_argument("--index", default=str(DEFAULT_INDEX))
    status_cmd.add_argument("--report", action="store_true",
                            help="also write reports/full-ingestion.md")

    backup_cmd = sub.add_parser("backup", help="copy the manifest and index artifacts")
    backup_cmd.add_argument("--index", default=str(DEFAULT_INDEX))
    backup_cmd.add_argument("--out", default=None)

    restore_cmd = sub.add_parser("restore", help="restore a backup and print its counts")
    restore_cmd.add_argument("--from", dest="source", required=True)
    restore_cmd.add_argument("--index", default=str(DEFAULT_INDEX))

    batch_cmd = sub.add_parser("add-batch",
                               help="link a staged folder of PDFs into the corpus, all or nothing")
    batch_cmd.add_argument("--from", dest="source", required=True,
                           help="staged folder, inside data/raw")
    batch_cmd.add_argument("--wave", required=True, help="wave label, e.g. 00")
    batch_cmd.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    batch_cmd.add_argument("--index", default=str(DEFAULT_INDEX))
    batch_cmd.add_argument("--stages", default="scan,parse,assemble,chunk,embed",
                           help="bibliography is opt-in: one model call per document")
    batch_cmd.add_argument("--limit", type=int, default=None)
    batch_cmd.add_argument("--parse-timeout", type=float, default=None,
                           help="seconds before a document's parse child is killed;"
                                " default 900 x --jobs (7200 at 8), because parallel"
                                " children make each document ~6x slower")
    batch_cmd.add_argument("--jobs", type=int, default=1,
                           help="documents to parse at once; 1 keeps today's serial run,"
                                " 8 is the measured knee (1.53x, Step 13)")
    batch_cmd.add_argument("--no-build", action="store_true",
                           help="place the files and stop before parsing anything")
    batch_cmd.add_argument("--log", default=str(DEFAULT_WAVE_LOG))

    # Not for people: the child half of parse isolation (D-075), spawned by parse_stage.
    one_cmd = sub.add_parser("parse-one", help=argparse.SUPPRESS)
    one_cmd.add_argument("--path", required=True)
    one_cmd.add_argument("--index", required=True)
    one_cmd.add_argument("--sha", required=True)
    one_cmd.add_argument("--rel", required=True)
    one_cmd.add_argument("--result", required=True)

    return parser


def main(argv: list[str]) -> int:
    args = _parser().parse_args(argv)

    if args.command == "parse-one":
        try:
            report = parse_document(pathlib.Path(args.path), pathlib.Path(args.index),
                                    args.sha, args.rel)
        except Exception as exc:              # noqa: BLE001 - the parent records the text
            _write(pathlib.Path(args.result),
                   json.dumps({"error": f"{exc.__class__.__name__}: {exc}"}))
            return 2
        _write(pathlib.Path(args.result), json.dumps(report))
        return 0

    if args.command == "build":
        report = build(pathlib.Path(args.corpus), pathlib.Path(args.index),
                       tuple(part.strip() for part in args.stages.split(",") if part.strip()),
                       args.limit, parse_timeout=args.parse_timeout,
                       parse_jobs=args.jobs)
        print(json.dumps(report, indent=1))
        return 1 if report["failures"] else 0
    if args.command == "status":
        summary = status(pathlib.Path(args.index))
        print(json.dumps(summary, indent=1))
        if args.report:
            print(f"wrote {write_report(pathlib.Path(args.index))}")
        return 0 if not summary["failures"] else 1
    if args.command == "backup":
        result = backup(pathlib.Path(args.index),
                        pathlib.Path(args.out) if args.out else None)
        print(json.dumps(result, indent=1))
        return 0
    if args.command == "add-batch":
        summary = add_batch(pathlib.Path(args.source), args.wave,
                            corpus_root=pathlib.Path(args.corpus),
                            index_dir=pathlib.Path(args.index),
                            stages=tuple(part.strip() for part in args.stages.split(",")
                                         if part.strip()),
                            limit=args.limit, build_after=not args.no_build,
                            log_path=pathlib.Path(args.log),
                            parse_timeout=args.parse_timeout,
                            parse_jobs=args.jobs)
        print(json.dumps(summary, indent=1))
        if summary["refused"]:
            return 1
        return 1 if summary["build"] and summary["build"]["failures"] else 0
    result = restore(pathlib.Path(args.source), pathlib.Path(args.index))
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
