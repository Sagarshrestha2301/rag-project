"""One bibliographic record per document, extracted once and checked against page 1.

A citation that names a file (`1970_Marahatta_..._W2121362616.pdf`) is a storage key, and
for at least one document the year in the name is wrong: that paper says "August 2009" on
page 1. This module turns page 1 into `{title, authors, year, venue, doi}` once per
document, and keeps a field only if its text is found on the page.

Two rules decide everything here:

- The model proposes, this module disposes. A 4B model reads page 1 and returns JSON; every
  string is then located in the page text (NFKC, lower-cased, punctuation collapsed) and a
  field that is not found there is dropped, with the reason recorded. A blank field is
  honest, a guessed one is not (rule 4).
- Embedded PDF metadata is not trusted. The corpus carries titles like
  "Final Added Vol 15-2.pmd" and authors like "user@MAHESH", so metadata is only used when
  its value also occurs on page 1.

Usage:
    python -m ingest.bibliography build            # fill what is missing, resume-safe
    python -m ingest.bibliography build --limit 3
    python -m ingest.bibliography show             # counts and a few records

One record, as `index/bibliography.json` stores it:
    {"1970_Marahatta_....pdf": {"sha256": "2f1c…", "title": "Relating Hydrological
     Extremes with Area - A Case on Extreme Floods", "authors": ["S. Marahatta",
     "J. K. Bhusal"], "year": 2009, "venue": "Journal of Hydrology and Meteorology",
     "doi": null, "evidence": {"title": "Relating Hydrological Extremes with Area …"},
     "rejected": {"doi": "not found on page 1"}}}

The UI's source list reads `reference_line()` from here, so the rail and this module cannot
disagree about what a document is called.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import time
import unicodedata

import httpx

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX_FILE = "bibliography.json"
LOCK_FILE = "bibliography.lock"              # one build at a time, see build()
PROMPT_VERSION = "bib-3"                       # bump when PROMPT or field rules change
HEADER_PAGES = 4                               # page 1 is blank on some ICIMOD reports
MODEL = os.environ.get("BIB_MODEL", "qwen3.5:4b")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
PAGE_CHARS = 4500                              # page 1, trimmed: enough for a header block
NUM_CTX = 8192
SEED = 0
TEMPERATURE = 0.0
YEAR_RANGE = (1800, 2030)
DOI = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+")
NOT_A_TITLE = re.compile(r"^(untitled|unknown|document|microsoft word|.*\.pmd|.*\.docx?)$", re.I)

PROMPT = """Read the first page of a document and copy its bibliographic header.

Return JSON only, with these keys:
- "title": the document's title, exactly as printed (one string, null if there is none)
- "authors": list of author names exactly as printed (empty list if none)
- "year": the year of publication as a 4-digit number (null if not printed)
- "venue": the journal, book or publisher name (null if not printed)
- "doi": the DOI (null if not printed)

Copy characters from the page. Never guess, never complete a truncated name, never use
your own knowledge about the document. If a value is not printed on the page, use null
or an empty list."""


# --------------------------------------------------------------- text helpers

def normalize(text: str) -> str:
    """Lower-case, NFKC, punctuation collapsed, so a line break cannot hide a match."""
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _snippet(page: str, value: str, width: int = 90) -> str:
    """The page text around `value`, for the record's evidence field."""
    flat = " ".join((page or "").split())
    index = normalize(flat).find(normalize(value))
    if index < 0:
        return ""
    # normalized offsets are not flat offsets, so search the flat text case-insensitively
    match = re.search(re.escape(" ".join(value.split())), flat, re.I)
    start = match.start() if match else 0
    return flat[max(0, start - 20):start + width].strip()


def _found(page: str, value: str, minimum: int = 4) -> bool:
    """True when `value` (normalized) occurs in the page text (normalized)."""
    needle = normalize(value)
    return len(needle) >= minimum and needle in normalize(page)


def clean(value) -> str | None:
    """One trimmed line, or None for empty/placeholder values."""
    if not isinstance(value, str):
        return None
    # A PDF's own text layer often carries a broken dash (U+FFFD); a title reading
    # "Area \ufffd A Case" is not something a reader should see.
    text = " ".join(value.replace("\ufffd", "-").split()).strip(" .;,")
    if not text or NOT_A_TITLE.match(text) or len(text) > 300:
        return None
    return text


def clean_authors(value) -> list[str]:
    """Author names from a list or a single string, de-duplicated in printed order."""
    if isinstance(value, str):
        value = re.split(r";| and |&|\u2022|\n", value)
    names: list[str] = []
    for item in value or []:
        name = clean(item)
        if name and len(name) <= 80 and not any(ch.isdigit() for ch in name):
            if name.lower() not in {seen.lower() for seen in names}:
                names.append(name)
    return names[:12]


def clean_year(value) -> int | None:
    """A plausible 4-digit year, or None."""
    if isinstance(value, bool):
        return None
    match = re.search(r"\b(\d{4})\b", str(value or ""))
    if not match:
        return None
    year = int(match.group(1))
    return year if YEAR_RANGE[0] <= year <= YEAR_RANGE[1] else None


def format_authors(names: list[str]) -> str:
    """`['S. Marahatta', 'J. K. Bhusal']` -> `'Marahatta & Bhusal'`.

    Surnames only, because a reader scanning the rail does not need initials; more than
    three authors become the first surname plus "et al.".
    """
    surnames = []
    for name in names:
        parts = [part for part in re.split(r"[\s,]+", name) if part]
        if parts:
            surnames.append(parts[-1])
    if not surnames:
        return ""
    if len(surnames) > 3:
        return f"{surnames[0]} et al."
    return " & ".join(surnames[:2]) if len(surnames) <= 2 else ", ".join(surnames)


def reference_line(entry: dict | None) -> str:
    """A human-readable reference, falling back only as far as the evidence goes.

    With a title and an author/year this reads like a citation; with less, it says less
    rather than inventing the missing part.
    """
    entry = entry or {}
    authors = format_authors(entry.get("authors") or [])
    year = entry.get("year")
    title = entry.get("title")
    venue = entry.get("venue")
    doi = entry.get("doi")

    head = " ".join(part for part in (authors, f"({year})" if year else "") if part)
    body = ". ".join(part for part in (head, title or "") if part)
    if venue and normalize(venue) not in normalize(body):
        body = f"{body}. {venue}" if body else venue
    if doi:
        body = f"{body}. doi:{doi}" if body else f"doi:{doi}"
    return body or ""


# ---------------------------------------------------------------- extraction

def deterministic(page: str) -> dict:
    """Fields that can be read off the page without a model: the DOI and a year."""
    numbers = re.findall(r"\b(1[89]\d\d|20\d\d)\b", page or "")
    year = int(numbers[0]) if numbers else None
    match = DOI.search(page or "")
    return {"year": year, "doi": match.group(0).rstrip(".,;)") if match else None}


def validate(draft: dict, page: str) -> dict:
    """Keep only what page 1 actually prints; record why the rest was dropped."""
    record: dict = {"title": None, "authors": [], "year": None, "venue": None, "doi": None,
                    "evidence": {}, "rejected": {}}

    title = clean(draft.get("title"))
    if not title:
        record["rejected"]["title"] = "not printed"
    elif len(title) < 8 or not _found(page, title):
        record["rejected"]["title"] = "not found in the header pages"
    else:
        record["title"] = title
        record["evidence"]["title"] = _snippet(page, title)

    authors = [name for name in clean_authors(draft.get("authors")) if _found(page, name)]
    dropped = [name for name in clean_authors(draft.get("authors")) if not _found(page, name)]
    if dropped:
        record["rejected"]["authors"] = (
            f"not found in the header pages: {', '.join(dropped[:4])}")
    if authors:
        record["authors"] = authors
        record["evidence"]["authors"] = _snippet(page, authors[0])

    year = clean_year(draft.get("year"))
    if year is None:
        record["rejected"]["year"] = "not printed"
    elif str(year) not in (page or ""):
        record["rejected"]["year"] = "not found in the header pages"
    else:
        record["year"] = year
        record["evidence"]["year"] = _snippet(page, str(year))

    venue = clean(draft.get("venue"))
    if not venue:
        record["rejected"]["venue"] = "not printed"
    elif not _found(page, venue):
        record["rejected"]["venue"] = "not found in the header pages"
    else:
        record["venue"] = venue
        record["evidence"]["venue"] = _snippet(page, venue)

    doi = (clean(draft.get("doi")) or "").rstrip(".,;")
    if not doi:
        record["rejected"]["doi"] = "not printed"
    elif not DOI.fullmatch(doi):
        record["rejected"]["doi"] = "not a DOI"
    elif doi not in (page or ""):
        record["rejected"]["doi"] = "not found in the header pages"
    else:
        record["doi"] = doi
    return record


def ask_model(page: str, model: str = MODEL, url: str = OLLAMA_URL) -> dict:
    """One JSON answer from the local model; raises on a transport or parse failure."""
    body = {
        "model": model,
        "messages": [{"role": "system", "content": PROMPT},
                     {"role": "user", "content": page[:PAGE_CHARS]}],
        "stream": False,
        "think": False,
        "format": "json",
        # num_predict caps a 4B model's habit of writing a paragraph around five keys.
        "options": {"temperature": TEMPERATURE, "num_ctx": NUM_CTX, "seed": SEED,
                    "num_predict": 220},
    }
    with httpx.Client(timeout=httpx.Timeout(connect=5, read=180, write=30, pool=5)) as client:
        response = client.post(f"{url}/api/chat", json=body)
    if response.status_code != 200:
        raise RuntimeError(f"Ollama {response.status_code}: {response.text[:200]}")
    content = (response.json().get("message") or {}).get("content") or ""
    try:
        draft = json.loads(content)
    except ValueError as exc:
        raise RuntimeError(f"model did not return JSON: {content[:160]}") from exc
    return draft if isinstance(draft, dict) else {}


def extract(page: str, model: str = MODEL, allow_model: bool = True) -> dict:
    """Page 1 -> a validated record, model first and deterministic values as a fallback."""
    draft: dict = {}
    error = None
    if allow_model:
        try:
            draft = ask_model(page, model)
        except (httpx.HTTPError, RuntimeError) as exc:
            error = f"{exc.__class__.__name__}: {exc}"[:200]
    fallback = deterministic(page)
    for key, value in fallback.items():
        if not draft.get(key):
            draft[key] = value
    record = validate(draft, page)
    if error:
        record["error"] = error
    return record


# --------------------------------------------------------------------- build

def _pages_by_doc(index_dir: pathlib.Path) -> dict[str, list[dict]]:
    """Document name -> its first pages, from the index the pipeline already assembled."""
    source = json.loads((index_dir / "pages.json").read_text(encoding="utf-8"))
    pages: dict[str, list[dict]] = {}
    for page in source.get("pages", []):
        doc = page.get("doc")
        if not doc:
            continue
        if page.get("page", 0) <= HEADER_PAGES:
            pages.setdefault(doc, []).append(page)
    return pages


def header_page(pages: list[dict]) -> tuple[int, str]:
    """The first page with real text, and the header block the model reads.

    Some reports open with a blank page or a one-line cover, and an ICIMOD report puts a
    series blurb on page 2 with the title on page 3. The model therefore reads the first
    three pages together; `page` records where the text starts, for the evidence trail.
    """
    ordered = sorted(pages, key=lambda entry: entry.get("page", 0))
    start = int(ordered[0].get("page", 1)) if ordered else 1
    for page in ordered:
        if len(normalize(page.get("text") or "")) >= 120:
            start = int(page.get("page", 1))
            break
    block = "\n".join(page.get("text") or "" for page in ordered[:3])
    return start, block[:PAGE_CHARS * 2]


def _sha_of(index_dir: pathlib.Path) -> dict[str, str]:
    """Document name -> content hash, so a changed file is extracted again."""
    import sqlite3
    db = sqlite3.connect(index_dir / "manifest.sqlite")
    try:
        return {name: sha for name, sha in db.execute("SELECT name, sha256 FROM documents")}
    finally:
        db.close()


def _prompt_hash() -> str:
    return hashlib.sha256((PROMPT + PROMPT_VERSION).encode("utf-8")).hexdigest()[:12]


def load(index_dir: pathlib.Path = ROOT / "index") -> dict:
    """The artifact as written, or an empty shell; callers never see a missing-file error."""
    path = pathlib.Path(index_dir) / INDEX_FILE
    if not path.exists():
        return {"version": PROMPT_VERSION, "model": MODEL, "prompt": _prompt_hash(),
                "documents": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _acquire(lock: pathlib.Path) -> bool:
    """Create the lock file; False when a build already holds it. Release with unlink."""
    try:
        handle = lock.open("x", encoding="utf-8", newline="\n")
    except FileExistsError:
        return False
    with handle:
        handle.write(f"{os.getpid()}\n")
    return True


def build(index_dir: pathlib.Path = ROOT / "index", model: str = MODEL,
          limit: int | None = None, allow_model: bool = True, force: bool = False,
          log=print) -> dict:
    """Fill `index/bibliography.json` for every document, resuming where it stopped.

    The file is written after every document, so a long run on a slow model can be
    killed and restarted without paying for the same page twice. A second build on the
    same index is refused by `bibliography.lock`: two writers would each rewrite the
    file from their own start snapshot and drop the other's records. A run that was
    killed leaves the lock behind: delete `index/bibliography.lock`, or pass
    `force=True`, only after checking that no build is running.
    """
    index_dir = pathlib.Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    lock = index_dir / LOCK_FILE
    if force:
        lock.unlink(missing_ok=True)
    if not _acquire(lock):
        log(f"  another build holds {LOCK_FILE}; not starting (delete it if none is "
            "running)")
        return {"counts": counts(load(index_dir)), "seconds": 0.0, "skipped": True}
    try:
        return _build(index_dir, model=model, limit=limit, allow_model=allow_model, log=log)
    finally:
        lock.unlink(missing_ok=True)


def _build(index_dir: pathlib.Path, model: str = MODEL, limit: int | None = None,
           allow_model: bool = True, log=print) -> dict:
    """`build` without the lock: fill the artifact, one model call per new document."""
    artifact = load(index_dir)
    artifact.update({"version": PROMPT_VERSION, "model": model, "prompt": _prompt_hash()})
    if not allow_model:
        artifact["model"] = "none"
    documents: dict = artifact.setdefault("documents", {})
    pages = _pages_by_doc(index_dir)
    shas = _sha_of(index_dir)
    todo = [(name, header_page(entries)) for name, entries in pages.items()
            if documents.get(name, {}).get("sha256") != shas.get(name)
            or documents.get(name, {}).get("version") != PROMPT_VERSION]
    if limit:
        todo = todo[:limit]

    began = time.perf_counter()
    for position, (name, (number, text)) in enumerate(todo, start=1):
        record = extract(text, model=model, allow_model=allow_model)
        record["sha256"] = shas.get(name)
        record["version"] = PROMPT_VERSION
        record["page"] = number
        documents[name] = record
        _write(index_dir / INDEX_FILE, artifact)
        filled = [key for key in ("title", "authors", "year", "venue", "doi")
                  if record.get(key)]
        log(f"  [{position}/{len(todo)}] {name[:46]:48s} {','.join(filled) or 'nothing'}"
            f" {time.perf_counter() - began:>6.1f}s")

    artifact["counts"] = counts(artifact)
    artifact["built"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _write(index_dir / INDEX_FILE, artifact)
    artifact["seconds"] = round(time.perf_counter() - began, 1)
    return artifact


def _write(path: pathlib.Path, artifact: dict) -> None:
    """UTF-8 with LF, like every other index artifact (ingest.pipeline._write)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(artifact, handle, ensure_ascii=False, indent=1)


def counts(artifact: dict | None = None) -> dict:
    """How many documents have each field, and how many were read at all."""
    documents = (artifact or {}).get("documents") or {}
    out = {"documents": len(documents)}
    for key in ("title", "authors", "year", "venue", "doi"):
        out[key] = sum(1 for record in documents.values() if record.get(key))
    out["reference"] = sum(1 for record in documents.values() if reference_line(record))
    out["errors"] = sum(1 for record in documents.values() if record.get("error"))
    return out


# ----------------------------------------------------------------------- cli

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="ingest.bibliography")
    sub = parser.add_subparsers(dest="command", required=True)
    build_cmd = sub.add_parser("build", help="extract what is missing")
    build_cmd.add_argument("--index", default=str(ROOT / "index"))
    build_cmd.add_argument("--model", default=MODEL)
    build_cmd.add_argument("--limit", type=int, default=None)
    build_cmd.add_argument("--no-model", action="store_true",
                           help="deterministic fields only (DOI, year); no model call")
    build_cmd.add_argument("--force", action="store_true",
                           help="take over a lock left by a killed run (check first)")
    show_cmd = sub.add_parser("show", help="counts and the first records")
    show_cmd.add_argument("--index", default=str(ROOT / "index"))
    show_cmd.add_argument("--limit", type=int, default=5)
    args = parser.parse_args(argv)

    if args.command == "show":
        artifact = load(pathlib.Path(args.index))
        print(json.dumps(counts(artifact), indent=1))
        for name, record in list(artifact.get("documents", {}).items())[:args.limit]:
            print(f"{name[:44]:46s} {reference_line(record) or '(no reference)'}")
        return 0

    artifact = build(pathlib.Path(args.index), model=args.model, limit=args.limit,
                     allow_model=not args.no_model, force=args.force,
                     log=lambda line: print(line, file=sys.stderr))
    print(json.dumps({"counts": artifact["counts"], "seconds": artifact["seconds"],
                      "skipped": artifact.get("skipped", False)}, indent=1))
    return 2 if artifact.get("skipped") else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
